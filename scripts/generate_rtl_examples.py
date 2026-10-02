"""Build the RTL examples and publish them to the configured Activity workspace."""

from __future__ import annotations

import argparse
import tempfile
from dataclasses import dataclass
from pathlib import Path

from spec2gds.agent_spec.activities import (
    ActivitySnapshot,
    LocalActivityWorkspace,
    SpecExtensionRegistry,
    invoke_activity,
)
from spec2gds.agent_spec.activities.rtl import register_extensions
from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.models import EntityRef
from spec2gds.agent_spec.spec_format.naming import generated_path
from spec2gds.agent_spec.spec_format.sections import (
    SECTION_NAMESPACE,
    SECTION_ROOT,
    upsert_systemverilog_section,
)
from spec2gds.service_registry import load_service_registry

ROOT = Path(__file__).resolve().parents[1]
BASE_SPEC = ROOT / "samples/minimal/single_component.spec"

ONE_CYCLE_BODY = """always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        data_out <= '0;
    end else if (valid_in) begin
        data_out <= data_in;
    end
end
"""

TWO_CYCLE_BODY = """logic [31:0] data_pipe;
logic valid_pipe;

always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        data_pipe <= '0;
        valid_pipe <= 1'b0;
        data_out <= '0;
    end else begin
        valid_pipe <= valid_in;
        if (valid_in) begin
            data_pipe <= data_in;
        end
        if (valid_pipe) begin
            data_out <= data_pipe;
        end
    end
end
"""


@dataclass(frozen=True)
class Example:
    """One reproducible source package and its body semantics."""

    name: str
    spec_path: Path
    body: str
    document_id: str | None = None


EXAMPLES = (
    Example(
        name="one_cycle",
        spec_path=ROOT / "samples/minimal/single_component_with_rtl.spec",
        body=ONE_CYCLE_BODY,
    ),
    Example(
        name="two_cycle",
        spec_path=ROOT / "samples/minimal/single_component_with_2cycle_rtl.spec",
        body=TWO_CYCLE_BODY,
        document_id="spec_single_component_two_cycle",
    ),
)


def _local_ref(reference: EntityRef, document_id: str) -> EntityRef:
    return reference.model_copy(update={"document_id": document_id})


def build_package(example: Example) -> SpecPackage:
    """Refresh example bodies while preserving existing identities and topology."""
    existing = example.spec_path.exists()
    package = SpecPackage.load(str(example.spec_path if existing else BASE_SPEC))
    if not existing:
        package.files = {
            path: data
            for path, data in package.files.items()
            if not path.startswith("activity/") and not path.startswith(f"{SECTION_ROOT}/")
        }
        package.manifest = package.manifest.model_copy(
            update={
                "annotation_schemas": [
                    item
                    for item in package.manifest.annotation_schemas
                    if item.namespace != SECTION_NAMESPACE
                ]
            }
        )
    if example.document_id is not None and not existing:
        document_id = example.document_id
        package.manifest = package.manifest.model_copy(
            update={
                "document_id": document_id,
                "entry_designs": [
                    _local_ref(item, document_id)
                    for item in package.manifest.entry_designs
                ],
                "component_compositions": [
                    item.model_copy(
                        update={
                            "component": _local_ref(item.component, document_id),
                            "internal_design": _local_ref(item.internal_design, document_id),
                        }
                    )
                    for item in package.manifest.component_compositions
                ],
            }
        )
        package.narrative = package.narrative.model_copy(update={"document_id": document_id})

    if example.spec_path.exists():
        package.narrative = package.narrative.model_copy(update={"title": SpecPackage.load(str(example.spec_path)).narrative.title})
    revision = SpecRevision.from_package(package)
    component = revision.components[0]
    upsert_systemverilog_section(package, component.ref, example.body)
    package.require_valid()
    return package


def generate_project(package: SpecPackage, workspace_root: Path) -> Path:
    """Run the real Activity snapshot/workspace path and return its project root."""
    revision = SpecRevision.from_package(package)
    target = revision.entry_designs()[0]
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    result = invoke_activity(
        registry,
        "rtl.generate",
        ActivitySnapshot.create(revision, target.ref),
        LocalActivityWorkspace(workspace_root),
    )
    return workspace_root / result.report["output_path"]


def read_tree(root: Path) -> dict[str, bytes]:
    """Read one generated project tree for byte-for-byte comparison."""
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def expected_tree(package: SpecPackage) -> dict[str, bytes]:
    """Generate an isolated expected tree without touching configured output."""
    with tempfile.TemporaryDirectory(prefix="spec2gds-rtl-example-") as temporary:
        return read_tree(generate_project(package, Path(temporary)))


def configured_project(package: SpecPackage, workspace_root: Path) -> Path:
    """Resolve the generator-owned location for one example package."""
    revision = SpecRevision.from_package(package)
    target = revision.entry_designs()[0]
    return workspace_root / generated_path(revision, target.ref, "rtl")


def update_examples() -> None:
    """Rewrite both source packages and publish to the configured workspace."""
    workspace_root = load_service_registry().activities.workspace_root
    for example in EXAMPLES:
        package = build_package(example)
        revision = SpecRevision.from_package(package)
        target = revision.entry_designs()[0].ref
        legacy = f"rtl/{revision.document_id}/{target.entity_id}"
        current = generated_path(revision, target, "rtl")
        if (workspace_root / legacy).exists() and not (workspace_root / current).exists():
            LocalActivityWorkspace(workspace_root).move_owned_directory(
                legacy, current, generator_id="rtl.generate",
                document_id=revision.document_id, design_id=target.entity_id,
            )
        package.save(str(example.spec_path))
        output = generate_project(package, workspace_root)
        print(f"updated {example.name}: {example.spec_path.relative_to(ROOT)}")
        print(f"generated: {output}")


def check_examples() -> int:
    """Return nonzero when a source package or configured output is stale."""
    workspace_root = load_service_registry().activities.workspace_root
    stale: list[str] = []
    for example in EXAMPLES:
        package = build_package(example)
        if not example.spec_path.is_file() or example.spec_path.read_bytes() != package.to_bytes():
            stale.append(str(example.spec_path.relative_to(ROOT)))
        output = configured_project(package, workspace_root)
        if read_tree(output) != expected_tree(package):
            stale.append(str(output))
    if stale:
        print("stale RTL examples:")
        for path in stale:
            print(f"  {path}")
        print("run: uv run python scripts/generate_rtl_examples.py --update")
        return 1
    print(f"RTL examples are current under {workspace_root}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify packages and configured output")
    mode.add_argument(
        "--update",
        action="store_true",
        help="rewrite packages and publish to the configured Activity workspace",
    )
    arguments = parser.parse_args()
    if arguments.update:
        update_examples()
        return 0
    return check_examples()


if __name__ == "__main__":
    raise SystemExit(main())

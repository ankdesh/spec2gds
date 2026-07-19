"""Acceptance checks for the real hardware-document V1 benchmark corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmarks.agent_spec.hw_docs.build_benchmark import CASES, build_benchmarks
from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.models import NarrativeBlock


_REPOSITORY = Path(__file__).resolve().parents[3]
_BENCHMARK_ROOT = _REPOSITORY / "benchmarks" / "agent_spec" / "hw_docs"
_GENERATED = _BENCHMARK_ROOT / "generated"


def _blocks(blocks: list[NarrativeBlock]):
    """Yield every typed narrative block in document order."""
    for block in blocks:
        yield block
        yield from _blocks(block.children)


def _sha256(data: bytes) -> str:
    """Match the raw digest format used by the external benchmark manifest."""
    return hashlib.sha256(data).hexdigest()


def test_checked_in_hardware_benchmarks_are_complete_valid_and_auditable() -> None:
    """Require all paired sources, formal structure, and narrative projections."""
    manifest = json.loads((_GENERATED / "benchmark_manifest.json").read_text(encoding="utf-8"))
    assert manifest["format"] == "spec2gds-hardware-document-benchmark-v1"
    assert manifest["package_count"] == len(CASES) == 6
    assert [entry["benchmark_id"] for entry in manifest["packages"]] == [case.stem for case in CASES]

    for entry in manifest["packages"]:
        package_path = _GENERATED / entry["output"]
        package_bytes = package_path.read_bytes()
        package = SpecPackage.load(str(package_path))
        revision = SpecRevision.from_package(package)
        blocks = list(_blocks(package.narrative.blocks))
        block_types = {block.type for block in blocks}

        assert _sha256(package_bytes) == entry["package_sha256"]
        assert package.source_hash() == entry["source_revision_hash"]
        assert not revision.diagnostics
        assert len(revision.components) == 1
        assert len(revision.bus_definitions) == entry["formal_counts"]["bus_interfaces"]
        assert len(revision.abstraction_definitions) == entry["formal_counts"]["bus_interfaces"]
        assert len(revision.components[0].ports) == entry["formal_counts"]["ports"]
        assert len(revision.components[0].interfaces) == entry["formal_counts"]["bus_interfaces"]
        assert len(revision.annotations) == 3
        assert {"section", "paragraph", "entity_link"}.issubset(block_types)
        assert "" not in package.narrative.blocks[0].text
        if entry["narrative_counts"].get("table"):
            assert "table" in block_types
        if entry["narrative_counts"].get("list"):
            assert "list" in block_types

        annotation_data = {annotation.path: annotation.data for annotation in revision.annotations}
        for source_kind in ("html", "pdf", "ipxact_2014"):
            source = entry["source"][source_kind]
            source_bytes = (_BENCHMARK_ROOT / source["path"]).read_bytes()
            suffix = {"html": ".html", "pdf": ".pdf", "ipxact_2014": ".source.xml"}[source_kind]
            annotation_path = f"annotations/benchmark_source/{entry['benchmark_id']}{suffix}"
            assert annotation_data[annotation_path] == source_bytes
            assert len(source_bytes) == source["bytes"]
            assert _sha256(source_bytes) == source["sha256"]


def test_hardware_benchmark_rebuild_is_byte_for_byte_deterministic(tmp_path: Path) -> None:
    """Protect generated packages and their index from nondeterministic drift."""
    build_benchmarks(tmp_path)
    expected_names = {f"{case.stem}.spec" for case in CASES} | {"benchmark_manifest.json"}
    assert {path.name for path in tmp_path.iterdir()} == expected_names
    for name in expected_names:
        assert (tmp_path / name).read_bytes() == (_GENERATED / name).read_bytes()

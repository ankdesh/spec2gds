"""Deterministic SystemC AT skeleton generation tests."""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
from pathlib import Path

import pytest
from jinja2 import UndefinedError

from spec2gds.agent_spec.activities import (
    ActivitySnapshot,
    LocalActivityWorkspace,
    SpecAccess,
    SpecExtensionRegistry,
    activity_availability,
    invoke_activity,
)
from spec2gds.agent_spec.activities.systemc_at import register_extensions
from spec2gds.agent_spec.activities.systemc_at.codegen import (
    _render_template,
    generate_project,
)
from spec2gds.agent_spec.spec_format.ir import (
    ConnectionIR,
    InstanceIR,
    InterfaceEndpointIR,
    InterfaceIR,
    SpecRevision,
)
from spec2gds.agent_spec.spec_format.models import sha256_digest
from spec2gds.agent_spec.spec_format.testing import build_test_package


def revision() -> SpecRevision:
    return SpecRevision.from_package(build_test_package())


def registry() -> SpecExtensionRegistry:
    result = SpecExtensionRegistry()
    register_extensions(result)
    return result


def tree(path: Path) -> dict[str, bytes]:
    return {
        item.relative_to(path).as_posix(): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def test_activity_registers_for_design_scope_and_requires_workspace(tmp_path: Path) -> None:
    source = revision()
    extensions = registry()
    definition = extensions.activity("systemc.generate_at_skeleton").definition
    design_snapshot = ActivitySnapshot.create(source, source.entry_designs()[0].ref)

    assert definition.requires_workspace_output
    assert definition.scopes.entity_kinds == ("design",)
    assert activity_availability(
        extensions, "systemc.generate_at_skeleton", design_snapshot
    ).available
    assert not activity_availability(
        extensions, "systemc.generate_at_skeleton", ActivitySnapshot.create(source)
    ).available
    with pytest.raises(ValueError, match="requires a workspace"):
        invoke_activity(extensions, "systemc.generate_at_skeleton", design_snapshot)

    result = invoke_activity(
        extensions,
        "systemc.generate_at_skeleton",
        design_snapshot,
        LocalActivityWorkspace(tmp_path),
    )
    assert result.report["design"]["entity_id"] == "design_top_a"


def test_activity_generates_reachable_hierarchy_bindings_and_report(tmp_path: Path) -> None:
    source = revision()
    snapshot = ActivitySnapshot.create(source, source.entry_designs()[0].ref)
    result = invoke_activity(
        registry(),
        "systemc.generate_at_skeleton",
        snapshot,
        LocalActivityWorkspace(tmp_path),
    )
    output = tmp_path / result.report["output_path"]
    files = tree(output)

    assert result.report["component_definition_count"] == 3
    assert result.report["component_instance_count"] == 3
    assert result.report["design_module_count"] == 2
    assert result.report["connection_count"] == 1
    assert result.artifacts[0].role == "systemc.generation_report"
    assert json.loads(result.artifacts[0].data) == result.report
    assert "leaf0.link.bind(sink0.link);" in files[
        "include/designs/design_design_top_a_subsystem0.h"
    ].decode()
    assert "simple_initiator_socket" in files[
        "include/components/component_design_top_a_subsystem0_leaf0.h"
    ].decode()
    assert "simple_target_socket" in files[
        "include/components/component_design_top_a_subsystem0_sink0.h"
    ].decode()
    assert b"CMAKE_PREFIX_PATH" not in files["CMakeLists.txt"]
    assert b"find_package(SystemCLanguage REQUIRED)" in files["CMakeLists.txt"]
    manifest = json.loads(files["generation-manifest.json"])
    assert manifest["source_revision_hash"] == source.source_revision_hash
    assert "generated" not in result.report["output_path"].split("/")


def test_unconnected_interfaces_are_omitted(tmp_path: Path) -> None:
    source = revision()
    snapshot = ActivitySnapshot.create(source, source.entry_designs()[1].ref)
    result = invoke_activity(
        registry(),
        "systemc.generate_at_skeleton",
        snapshot,
        LocalActivityWorkspace(tmp_path),
    )
    output = tmp_path / result.report["output_path"]
    component_header = next((output / "include/components").glob("*.h")).read_text()

    assert result.report["connection_count"] == 0
    assert "simple_initiator_socket" not in component_header
    assert "simple_target_socket" not in component_header


def test_packaged_templates_reject_incomplete_render_contexts() -> None:
    with pytest.raises(UndefinedError, match="finish_message"):
        _render_template(
            "main.cpp.j2",
            include="designs/top.h",
            top_class="Top",
            start_message='"start"',
        )


def test_repeated_generation_is_byte_identical_and_removes_stale_files(tmp_path: Path) -> None:
    source = revision()
    snapshot = ActivitySnapshot.create(source, source.entry_designs()[0].ref)
    workspace = LocalActivityWorkspace(tmp_path)
    first = invoke_activity(
        registry(), "systemc.generate_at_skeleton", snapshot, workspace
    )
    output = tmp_path / first.report["output_path"]
    first_tree = tree(output)
    (output / "stale.cpp").write_text("stale")

    second = invoke_activity(
        registry(), "systemc.generate_at_skeleton", snapshot, workspace
    )

    assert second == first
    assert tree(output) == first_tree
    assert not (output / "stale.cpp").exists()


def test_new_source_revision_replaces_the_same_managed_folder(tmp_path: Path) -> None:
    first_source = revision()
    workspace = LocalActivityWorkspace(tmp_path)
    first = invoke_activity(
        registry(),
        "systemc.generate_at_skeleton",
        ActivitySnapshot.create(first_source, first_source.entry_designs()[0].ref),
        workspace,
    )

    package = build_test_package()
    package.narrative = package.narrative.model_copy(update={"title": "Updated title"})
    second_source = SpecRevision.from_package(package)
    second = invoke_activity(
        registry(),
        "systemc.generate_at_skeleton",
        ActivitySnapshot.create(second_source, second_source.entry_designs()[0].ref),
        workspace,
    )

    assert second.report["output_path"] == "systemc-at/updated-title/top-a"
    assert (tmp_path / first.report["output_path"]).is_dir()
    assert second.report["source_revision_hash"] != first.report["source_revision_hash"]
    assert second.report["tree_sha256"] != first.report["tree_sha256"]
    manifest = json.loads(
        (tmp_path / second.report["output_path"] / "generation-manifest.json").read_bytes()
    )
    assert manifest["source_revision_hash"] == second_source.source_revision_hash


def test_availability_aggregates_unsupported_topology_without_output(tmp_path: Path) -> None:
    package = build_test_package()
    entry = next(
        item for item in package.manifest.documents if item.entity_id == "design_subsystem_internal"
    )
    xml = package.files[entry.path].decode()
    xml = xml.replace(
        "  </ipxact:componentInstances>",
        '''    <ipxact:componentInstance>
      <ipxact:instanceName>sink1</ipxact:instanceName>
      <ipxact:componentRef vendor="spec2gds.example" library="demo" name="sink" version="1.0"/>
    </ipxact:componentInstance>
  </ipxact:componentInstances>''',
    )
    xml = xml.replace(
        "    </ipxact:interconnection>",
        '''      <ipxact:activeInterface componentInstanceRef="sink1" busRef="link"/>
    </ipxact:interconnection>''',
    )
    xml = xml.replace(
        "  </ipxact:interconnections>",
        '''  </ipxact:interconnections>
  <ipxact:adHocConnections>
    <ipxact:adHocConnection>
      <ipxact:name>wire0</ipxact:name>
      <ipxact:portReferences>
        <ipxact:internalPortReference componentInstanceRef="leaf0" portRef="irq"/>
        <ipxact:internalPortReference componentInstanceRef="sink0" portRef="payload_in"/>
      </ipxact:portReferences>
    </ipxact:adHocConnection>
  </ipxact:adHocConnections>''',
    )
    package.files[entry.path] = xml.encode()
    package.manifest = package.manifest.model_copy(
        update={
            "documents": [
                item.model_copy(update={"sha256": sha256_digest(package.files[entry.path])})
                if item.entity_id == entry.entity_id
                else item
                for item in package.manifest.documents
            ]
        }
    )
    source = SpecRevision.from_package(package)
    snapshot = ActivitySnapshot.create(source, source.entry_designs()[0].ref)
    extensions = registry()

    availability = activity_availability(
        extensions, "systemc.generate_at_skeleton", snapshot
    )
    assert not availability.available
    assert any("3 endpoints" in item for item in availability.diagnostics)
    assert any("ad-hoc" in item for item in availability.diagnostics)
    with pytest.raises(ValueError, match="unavailable"):
        invoke_activity(
            extensions,
            "systemc.generate_at_skeleton",
            snapshot,
            LocalActivityWorkspace(tmp_path),
        )
    assert not list(tmp_path.rglob("generation-manifest.json"))


def test_codegen_renders_supported_hierarchy_socket_binding() -> None:
    source = revision()
    leaf = next(item for item in source.components if item.ref.entity_id == "component_leaf")
    sink = next(item for item in source.components if item.ref.entity_id == "component_sink")
    composite = next(
        item for item in source.components if item.ref.entity_id == "component_subsystem"
    )
    internal = next(
        item for item in source.designs if item.ref.entity_id == "design_subsystem_internal"
    )
    top = next(item for item in source.designs if item.ref.entity_id == "design_top_a")
    exported = InterfaceIR(
        name="upstream",
        bus_vlnv=leaf.interfaces[0].bus_vlnv,
        abstraction_vlnv=leaf.interfaces[0].abstraction_vlnv,
        role="initiator",
    )
    imported = InterfaceIR(
        name="downstream",
        bus_vlnv=sink.interfaces[0].bus_vlnv,
        abstraction_vlnv=sink.interfaces[0].abstraction_vlnv,
        role="target",
    )
    composite = dataclasses.replace(composite, interfaces=(exported, imported))
    internal = dataclasses.replace(
        internal,
        connections=(
            ConnectionIR(
                name="export",
                kind="interface",
                interface_endpoints=(InterfaceEndpointIR("leaf0", "link"),),
                hierarchy_interfaces=("upstream",),
            ),
            ConnectionIR(
                name="import",
                kind="interface",
                interface_endpoints=(InterfaceEndpointIR("sink0", "link"),),
                hierarchy_interfaces=("downstream",),
            ),
        ),
    )
    top = dataclasses.replace(
        top,
        instances=(
            top.instances[0],
            InstanceIR(name="sink_top", component_vlnv=sink.vlnv),
            InstanceIR(name="leaf_top", component_vlnv=leaf.vlnv),
        ),
        connections=(
            ConnectionIR(
                name="top_link",
                kind="interface",
                interface_endpoints=(
                    InterfaceEndpointIR("subsystem0", "upstream"),
                    InterfaceEndpointIR("sink_top", "link"),
                ),
            ),
            ConnectionIR(
                name="top_return",
                kind="interface",
                interface_endpoints=(
                    InterfaceEndpointIR("leaf_top", "link"),
                    InterfaceEndpointIR("subsystem0", "downstream"),
                ),
            ),
        ),
    )
    source = dataclasses.replace(
        source,
        components=tuple(
            composite if item.ref == composite.ref else item for item in source.components
        ),
        designs=tuple(
            internal if item.ref == internal.ref else top if item.ref == top.ref else item
            for item in source.designs
        ),
    )

    project = generate_project(SpecAccess(source, top.ref), top.ref)
    composite_header = project.files[
        "include/designs/design_design_top_a_subsystem0.h"
    ].decode()
    top_header = project.files["include/designs/top_design_top_a.h"].decode()
    assert "leaf0.link.bind(upstream);" in composite_header
    assert "downstream.bind(sink0.link);" in composite_header
    assert "subsystem0.upstream.bind(sink_top.link);" in top_header
    assert "leaf_top.link.bind(subsystem0.downstream);" in top_header


@pytest.mark.skipif(not os.environ.get("SYSTEMC_PREFIX"), reason="SYSTEMC_PREFIX is not set")
def test_generated_project_optionally_compiles_and_runs(tmp_path: Path) -> None:
    source = revision()
    snapshot = ActivitySnapshot.create(source, source.entry_designs()[0].ref)
    result = invoke_activity(
        registry(),
        "systemc.generate_at_skeleton",
        snapshot,
        LocalActivityWorkspace(tmp_path),
    )
    output = tmp_path / result.report["output_path"]
    build = tmp_path / "cmake-build"
    subprocess.run(
        [
            "cmake",
            "-S",
            str(output),
            "-B",
            str(build),
            f"-DCMAKE_PREFIX_PATH={os.environ['SYSTEMC_PREFIX']}",
        ],
        check=True,
    )
    subprocess.run(["cmake", "--build", str(build)], check=True)
    binary = build / "top_a_systemc_at"
    completed = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
    assert "[CYCLE: 0]" in completed.stdout
    assert "[CYCLE: 10]" in completed.stdout

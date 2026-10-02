"""Acceptance tests for deterministic RTL project generation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from jinja2 import UndefinedError

from spec2gds.agent_spec.activities import (
    ActivitySnapshot,
    LocalActivityWorkspace,
    SpecExtensionRegistry,
    activity_availability,
    invoke_activity,
)
from spec2gds.agent_spec.activities.rtl import register_extensions
from spec2gds.agent_spec.activities.rtl.codegen import _render_template
from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.models import ComponentComposition, EntityRef
from spec2gds.agent_spec.spec_format.sections import upsert_systemverilog_section
from spec2gds.agent_spec.spec_format.testing import _xml, build_test_package


def _wire_port(
    name: str,
    direction: str,
    *,
    left: str | None = None,
    right: str | None = None,
) -> str:
    vectors = ""
    if left is not None and right is not None:
        vectors = f"""
      <ipxact:vectors><ipxact:vector><ipxact:left>{left}</ipxact:left><ipxact:right>{right}</ipxact:right></ipxact:vector></ipxact:vectors>"""
    return f"""
    <ipxact:port><ipxact:name>{name}</ipxact:name><ipxact:wire>
      <ipxact:direction>{direction}</ipxact:direction>{vectors}
    </ipxact:wire></ipxact:port>"""


def _rtl_package(
    *,
    symbolic: bool = False,
    nonwire: bool = False,
    mismatch: bool = False,
    multiple_driver: bool = False,
    reused_endpoint: bool = False,
    top_boundary: bool = False,
    multiple_boundary: bool = False,
) -> SpecPackage:
    package = SpecPackage.create("rtl_test")
    left = "WIDTH-1" if symbolic else "7"
    sink_left = "3" if mismatch else left
    producer_extra = """
    <ipxact:port><ipxact:name>service</ipxact:name><ipxact:transactional>
      <ipxact:initiative>requires</ipxact:initiative>
    </ipxact:transactional></ipxact:port>""" if nonwire else ""
    producer = package.add_document(
        "component",
        _xml(
            "component",
            "component_producer",
            "module",
            f"""
  <ipxact:model><ipxact:ports>
{_wire_port("data-out", "out", left=left, right="0")}
{_wire_port("wire", "in")}
{_wire_port("pad", "inout")}
{producer_extra}
  </ipxact:ports></ipxact:model>""",
        ),
    )
    unit = package.add_document(
        "component",
        _xml(
            "component",
            "component_unit",
            "unit",
            f"""
  <ipxact:model><ipxact:ports>
{_wire_port("din", "in", left=left, right="0")}
{_wire_port("dout", "out", left=left, right="0")}
{_wire_port("pad", "inout")}
{_wire_port("idle", "in")}
  </ipxact:ports></ipxact:model>""",
        ),
    )
    sink = package.add_document(
        "component",
        _xml(
            "component",
            "component_sink_rtl",
            "sink",
            f"""
  <ipxact:model><ipxact:ports>
{_wire_port("data", "in", left=sink_left, right="0")}
{_wire_port("status", "out")}
{_wire_port("probe", "inout")}
  </ipxact:ports></ipxact:model>""",
        ),
    )
    cluster = package.add_document(
        "component",
        _xml(
            "component",
            "component_cluster",
            "cluster",
            f"""
  <ipxact:model><ipxact:ports>
{_wire_port("ingress", "in", left=left, right="0")}
{_wire_port("egress", "out", left=left, right="0")}
{_wire_port("pad", "inout")}
  </ipxact:ports></ipxact:model>""",
        ),
    )

    if multiple_boundary:
        internal_connections = """
    <ipxact:adHocConnection><ipxact:name>ambiguous_boundary</ipxact:name><ipxact:portReferences>
      <ipxact:internalPortReference componentInstanceRef="u0" portRef="din"/>
      <ipxact:externalPortReference portRef="ingress"/>
      <ipxact:externalPortReference portRef="egress"/>
    </ipxact:portReferences></ipxact:adHocConnection>
    <ipxact:adHocConnection><ipxact:name>pad_boundary</ipxact:name><ipxact:portReferences>
      <ipxact:internalPortReference componentInstanceRef="u0" portRef="pad"/>
      <ipxact:externalPortReference portRef="pad"/>
    </ipxact:portReferences></ipxact:adHocConnection>"""
    else:
        internal_connections = """
    <ipxact:adHocConnection><ipxact:name>ingress_boundary</ipxact:name><ipxact:portReferences>
      <ipxact:internalPortReference componentInstanceRef="u0" portRef="din"/>
      <ipxact:externalPortReference portRef="ingress"/>
    </ipxact:portReferences></ipxact:adHocConnection>
    <ipxact:adHocConnection><ipxact:name>egress_boundary</ipxact:name><ipxact:portReferences>
      <ipxact:internalPortReference componentInstanceRef="u0" portRef="dout"/>
      <ipxact:externalPortReference portRef="egress"/>
    </ipxact:portReferences></ipxact:adHocConnection>
    <ipxact:adHocConnection><ipxact:name>pad_boundary</ipxact:name><ipxact:portReferences>
      <ipxact:internalPortReference componentInstanceRef="u0" portRef="pad"/>
      <ipxact:externalPortReference portRef="pad"/>
    </ipxact:portReferences></ipxact:adHocConnection>"""
    internal = package.add_document(
        "design",
        _xml(
            "design",
            "design_cluster_internal",
            "cluster_internal",
            f"""
  <ipxact:componentInstances>
    <ipxact:componentInstance><ipxact:instanceName>u0</ipxact:instanceName><ipxact:componentRef vendor="spec2gds.example" library="demo" name="unit" version="1.0"/></ipxact:componentInstance>
  </ipxact:componentInstances>
  <ipxact:adHocConnections>{internal_connections}
  </ipxact:adHocConnections>""",
        ),
    )

    extra_instances = ""
    extra_endpoints = ""
    if multiple_driver:
        extra_instances += """
    <ipxact:componentInstance><ipxact:instanceName>p1</ipxact:instanceName><ipxact:componentRef vendor="spec2gds.example" library="demo" name="module" version="1.0"/></ipxact:componentInstance>"""
        extra_endpoints += """
      <ipxact:internalPortReference componentInstanceRef="p1" portRef="data-out"/>"""
    if reused_endpoint:
        extra_instances += """
    <ipxact:componentInstance><ipxact:instanceName>s2</ipxact:instanceName><ipxact:componentRef vendor="spec2gds.example" library="demo" name="sink" version="1.0"/></ipxact:componentInstance>"""
    reused_connection = ""
    if reused_endpoint:
        reused_connection = """
    <ipxact:adHocConnection><ipxact:name>reused</ipxact:name><ipxact:portReferences>
      <ipxact:internalPortReference componentInstanceRef="p0" portRef="data-out"/>
      <ipxact:internalPortReference componentInstanceRef="s2" portRef="data"/>
    </ipxact:portReferences></ipxact:adHocConnection>"""
    root_boundary = ""
    if top_boundary:
        root_boundary = """
    <ipxact:adHocConnection><ipxact:name>root_boundary</ipxact:name><ipxact:portReferences>
      <ipxact:internalPortReference componentInstanceRef="p0" portRef="wire"/>
      <ipxact:externalPortReference portRef="root_in"/>
    </ipxact:portReferences></ipxact:adHocConnection>"""
    top = package.add_document(
        "design",
        _xml(
            "design",
            "design_rtl_top",
            "top",
            f"""
  <ipxact:componentInstances>
    <ipxact:componentInstance><ipxact:instanceName>p0</ipxact:instanceName><ipxact:componentRef vendor="spec2gds.example" library="demo" name="module" version="1.0"/></ipxact:componentInstance>
    <ipxact:componentInstance><ipxact:instanceName>c0</ipxact:instanceName><ipxact:componentRef vendor="spec2gds.example" library="demo" name="cluster" version="1.0"/></ipxact:componentInstance>
    <ipxact:componentInstance><ipxact:instanceName>s0</ipxact:instanceName><ipxact:componentRef vendor="spec2gds.example" library="demo" name="sink" version="1.0"/></ipxact:componentInstance>
    <ipxact:componentInstance><ipxact:instanceName>s1</ipxact:instanceName><ipxact:componentRef vendor="spec2gds.example" library="demo" name="sink" version="1.0"/></ipxact:componentInstance>{extra_instances}
  </ipxact:componentInstances>
  <ipxact:adHocConnections>
    <ipxact:adHocConnection><ipxact:name>p0</ipxact:name><ipxact:portReferences>
      <ipxact:internalPortReference componentInstanceRef="p0" portRef="data-out"/>
      <ipxact:internalPortReference componentInstanceRef="c0" portRef="ingress"/>{extra_endpoints}
    </ipxact:portReferences></ipxact:adHocConnection>
    <ipxact:adHocConnection><ipxact:name>fanout</ipxact:name><ipxact:portReferences>
      <ipxact:internalPortReference componentInstanceRef="c0" portRef="egress"/>
      <ipxact:internalPortReference componentInstanceRef="s0" portRef="data"/>
      <ipxact:internalPortReference componentInstanceRef="s1" portRef="data"/>
    </ipxact:portReferences></ipxact:adHocConnection>
    <ipxact:adHocConnection><ipxact:name>pads</ipxact:name><ipxact:portReferences>
      <ipxact:internalPortReference componentInstanceRef="p0" portRef="pad"/>
      <ipxact:internalPortReference componentInstanceRef="c0" portRef="pad"/>
    </ipxact:portReferences></ipxact:adHocConnection>{reused_connection}{root_boundary}
  </ipxact:adHocConnections>""",
        ),
    )
    package.manifest = package.manifest.model_copy(
        update={
            "entry_designs": [
                EntityRef(
                    document_id=package.manifest.document_id,
                    entity_id=top.entity_id,
                    entity_kind="design",
                )
            ],
            "component_compositions": [
                ComponentComposition(
                    component=EntityRef(
                        document_id=package.manifest.document_id,
                        entity_id=cluster.entity_id,
                        entity_kind="component",
                    ),
                    internal_design=EntityRef(
                        document_id=package.manifest.document_id,
                        entity_id=internal.entity_id,
                        entity_kind="design",
                    ),
                )
            ],
        }
    )
    del producer, unit, sink
    package.require_valid()
    return package


def _registry() -> SpecExtensionRegistry:
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    return registry


def _tree(path: Path) -> dict[str, bytes]:
    return {
        item.relative_to(path).as_posix(): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def test_activity_generates_hierarchy_report_warnings_and_name_map(tmp_path: Path) -> None:
    source = SpecRevision.from_package(_rtl_package())
    snapshot = ActivitySnapshot.create(source, source.entry_designs()[0].ref)
    registry = _registry()
    definition = registry.activity("rtl.generate").definition
    availability = activity_availability(registry, "rtl.generate", snapshot)

    assert definition.version == "1.2.0"
    assert definition.scopes.entity_kinds == ("component", "design")
    assert definition.requires_workspace_output
    assert availability.available
    assert len(availability.diagnostics) == 6
    assert all(item.startswith("Warning: ") for item in availability.diagnostics)
    with pytest.raises(ValueError, match="requires a workspace"):
        invoke_activity(registry, "rtl.generate", snapshot)

    result = invoke_activity(
        registry,
        "rtl.generate",
        snapshot,
        LocalActivityWorkspace(tmp_path),
    )
    output = tmp_path / result.report["output_path"]
    assert result.report["top_module"] == "top_top"
    assert result.report["wrapper_generated"]
    assert result.report["module_count"] == 5
    assert result.report["component_module_count"] == 4
    assert result.report["instance_count"] == 5
    assert result.report["net_count"] == 6
    assert result.report["unconnected_port_count"] == 6
    assert result.report["warnings"] == list(availability.diagnostics)
    assert result.artifacts[0].role == "rtl.generation_report"
    assert json.loads(result.artifacts[0].data) == result.report

    mappings = result.report["name_mappings"]
    assert any(
        item["kind"] == "module"
        and item["source_name"] == "module"
        and item["rtl_name"] == "module_rtl"
        for item in mappings
    )
    assert any(
        item["kind"] == "port"
        and item["source_name"] == "data-out"
        and item["rtl_name"] == "data_out"
        for item in mappings
    )
    connection_mapping = next(
        item
        for item in mappings
        if item["kind"] == "connection" and item["source_name"] == "p0"
    )
    assert connection_mapping["rtl_name"].startswith("p0_")

    producer = (output / "rtl/components/module_rtl.sv").read_text()
    cluster = (output / "rtl/components/cluster.sv").read_text()
    top = (output / "rtl/designs/top_top.sv").read_text()
    assert "output wire [7:0] data_out" in producer
    assert "input wire wire_rtl" in producer
    assert "assign data_out = '0;" in producer
    assert "assign pad = 'z;" in producer
    assert "wire _unused_ok;" in producer
    assert ".din(ingress)" in cluster
    assert ".dout(egress)" in cluster
    assert ".idle('0)" in cluster
    assert top.count("sink ") == 2
    assert ".wire_rtl('0)" in top
    assert top.count(".status()") == 2
    assert top.count(".probe()") == 2
    assert "wire [7:0] fanout;" in top
    assert "`default_nettype wire" in top
    assert "components/sink.sv" in (output / "rtl/files.f").read_text()
    assert "--top-module $(TOP_MODULE) -F rtl/files.f" in (
        output / "Makefile"
    ).read_text()


def test_internal_design_uses_owning_component_as_top(tmp_path: Path) -> None:
    source = SpecRevision.from_package(_rtl_package())
    internal = next(
        item for item in source.designs if item.ref.entity_id == "design_cluster_internal"
    )
    result = invoke_activity(
        _registry(),
        "rtl.generate",
        ActivitySnapshot.create(source, internal.ref),
        LocalActivityWorkspace(tmp_path),
    )
    output = tmp_path / result.report["output_path"]

    assert result.report["top_module"] == "cluster"
    assert not result.report["wrapper_generated"]
    assert result.report["module_count"] == 2
    assert result.report["instance_count"] == 1
    assert not (output / "rtl/designs").exists()
    assert (output / "rtl/components/cluster.sv").is_file()


def test_sv_bodies_survive_activity_snapshot_and_render_with_v2_provenance(
    tmp_path: Path,
) -> None:
    package = _rtl_package()
    initial = SpecRevision.from_package(package)
    unit = initial.by_vlnv("component", "spec2gds.example:demo:unit:1.0")
    cluster = initial.by_vlnv("component", "spec2gds.example:demo:cluster:1.0")
    internal = next(item for item in initial.designs if item.ref.entity_id == "design_cluster_internal")
    upsert_systemverilog_section(package, unit.ref, "assign dout = din;\nassign pad = 'z;\n")
    component_body = upsert_systemverilog_section(package, cluster.ref, "logic component_marker;\n")
    design_body = upsert_systemverilog_section(package, internal.ref, "logic design_marker;\n")

    source = SpecRevision.from_package(package)
    target = source.entry_designs()[0]
    snapshot = ActivitySnapshot.from_bytes(ActivitySnapshot.create(source, target.ref).to_bytes())
    result = invoke_activity(
        _registry(),
        "rtl.generate",
        snapshot,
        LocalActivityWorkspace(tmp_path),
    )
    output = tmp_path / result.report["output_path"]
    unit_source = (output / "rtl/components/unit.sv").read_text()
    cluster_source = (output / "rtl/components/cluster.sv").read_text()
    manifest = json.loads((output / "generation-manifest.json").read_text())

    assert "output logic [7:0] dout" in unit_source
    assert "inout wire pad" in unit_source
    assert "assign dout = '0;" not in unit_source
    assert "_unused_ok" not in unit_source
    assert "assign dout = din;" in unit_source
    assert cluster_source.index("unit u0") < cluster_source.index("logic component_marker")
    assert cluster_source.index("logic component_marker") < cluster_source.index("logic design_marker")
    assert f'`line 1 "{component_body.source_path}" 0' in cluster_source
    assert f'`line 1 "{design_body.source_path}" 0' in cluster_source
    assert manifest["schema_version"] == "spec2gds.rtl-generation.v3"
    assert {item["section_id"] for item in manifest["source_sections"]} >= {
        component_body.section_id,
        design_body.section_id,
    }
    assert {item["section_id"] for item in result.report["source_sections"]} >= {
        component_body.section_id,
        design_body.section_id,
    }


@pytest.mark.parametrize(
    ("package", "target_id", "messages"),
    [
        (build_test_package, "design_top_a", ("bus interface",)),
        (lambda: _rtl_package(nonwire=True), "design_rtl_top", ("transactional",)),
        (lambda: _rtl_package(symbolic=True), "design_rtl_top", ("symbolic range",)),
        (lambda: _rtl_package(mismatch=True), "design_rtl_top", ("incompatible ranges",)),
        (lambda: _rtl_package(multiple_driver=True), "design_rtl_top", ("multiple ordinary drivers",)),
        (lambda: _rtl_package(reused_endpoint=True), "design_rtl_top", ("reuses endpoint",)),
        (lambda: _rtl_package(top_boundary=True), "design_rtl_top", ("unowned design",)),
        (lambda: _rtl_package(multiple_boundary=True), "design_rtl_top", ("multiple external",)),
    ],
)
def test_preflight_aggregates_fatal_topology_without_output(
    tmp_path: Path,
    package,
    target_id: str,
    messages: tuple[str, ...],
) -> None:
    source = SpecRevision.from_package(package())
    target = next(item for item in source.designs if item.ref.entity_id == target_id)
    snapshot = ActivitySnapshot.create(source, target.ref)
    registry = _registry()
    availability = activity_availability(registry, "rtl.generate", snapshot)

    assert not availability.available
    assert all(any(message in item for item in availability.diagnostics) for message in messages)
    assert all(item.startswith(("Error: ", "Warning: ")) for item in availability.diagnostics)
    with pytest.raises(ValueError, match="unavailable"):
        invoke_activity(
            registry,
            "rtl.generate",
            snapshot,
            LocalActivityWorkspace(tmp_path),
        )
    assert not list(tmp_path.rglob("generation-manifest.json"))


def test_generation_is_byte_identical_and_removes_stale_files(tmp_path: Path) -> None:
    source = SpecRevision.from_package(_rtl_package())
    snapshot = ActivitySnapshot.create(source, source.entry_designs()[0].ref)
    workspace = LocalActivityWorkspace(tmp_path)
    first = invoke_activity(_registry(), "rtl.generate", snapshot, workspace)
    output = tmp_path / first.report["output_path"]
    first_tree = _tree(output)
    (output / "stale.sv").write_text("stale")

    second = invoke_activity(_registry(), "rtl.generate", snapshot, workspace)
    assert _tree(output) == first_tree
    assert second.report["tree_sha256"] == first.report["tree_sha256"]
    manifest = json.loads((output / "generation-manifest.json").read_text())
    assert manifest["generator_id"] == "rtl.generate"
    assert manifest["top_module"] == "top_top"
    assert manifest["warnings"] == second.report["warnings"]
    assert "generation-manifest.json" not in {item["path"] for item in manifest["files"]}


def test_new_source_revision_replaces_the_same_managed_folder(tmp_path: Path) -> None:
    first_source = SpecRevision.from_package(_rtl_package())
    workspace = LocalActivityWorkspace(tmp_path)
    first = invoke_activity(
        _registry(),
        "rtl.generate",
        ActivitySnapshot.create(first_source, first_source.entry_designs()[0].ref),
        workspace,
    )

    updated_package = _rtl_package()
    updated_package.narrative = updated_package.narrative.model_copy(
        update={"title": "Updated RTL source"}
    )
    second_source = SpecRevision.from_package(updated_package)
    second = invoke_activity(
        _registry(),
        "rtl.generate",
        ActivitySnapshot.create(second_source, second_source.entry_designs()[0].ref),
        workspace,
    )

    assert second.report["output_path"] == first.report["output_path"]
    assert second.report["source_revision_hash"] != first.report["source_revision_hash"]
    assert second.report["tree_sha256"] != first.report["tree_sha256"]
    manifest = json.loads(
        (
            tmp_path
            / second.report["output_path"]
            / "generation-manifest.json"
        ).read_text()
    )
    assert manifest["source_revision_hash"] == second_source.source_revision_hash


def test_activity_refuses_to_replace_an_unmanaged_destination(tmp_path: Path) -> None:
    source = SpecRevision.from_package(_rtl_package())
    target = source.entry_designs()[0]
    unmanaged = tmp_path / "rtl" / source.document_id / target.ref.entity_id
    unmanaged.mkdir(parents=True)
    (unmanaged / "manual.sv").write_text("module manual; endmodule\n")

    with pytest.raises(ValueError, match="unmanaged generated directory"):
        invoke_activity(
            _registry(),
            "rtl.generate",
            ActivitySnapshot.create(source, target.ref),
            LocalActivityWorkspace(tmp_path),
        )
    assert (unmanaged / "manual.sv").is_file()


def test_packaged_templates_reject_incomplete_contexts() -> None:
    with pytest.raises(UndefinedError):
        _render_template("module.sv.j2", module_name="incomplete")


def test_generated_project_lints_with_required_verilator(tmp_path: Path) -> None:
    version = subprocess.run(
        ["verilator", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert version.startswith("Verilator 5.")
    source = SpecRevision.from_package(_rtl_package())
    result = invoke_activity(
        _registry(),
        "rtl.generate",
        ActivitySnapshot.create(source, source.entry_designs()[0].ref),
        LocalActivityWorkspace(tmp_path),
    )
    subprocess.run(
        ["make", "lint"],
        cwd=tmp_path / result.report["output_path"],
        check=True,
    )

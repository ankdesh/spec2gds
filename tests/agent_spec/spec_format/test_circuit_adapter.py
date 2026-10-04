"""Direct-port IP-XACT to Circuit Designer adapter tests."""

import copy
import json

import pytest

from spec2gds.agent_spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.agent_spec.spec_format.circuit_adapter import (
    CircuitAdapterError,
    compile_circuit_sync_operations,
    project_component_to_circuit,
    project_design_to_circuit,
    source_session_document_id,
)
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.testing import _xml
from spec2gds.agent_spec.spec_format.transactions import SpecEditTransaction


def _direct_revision(*, connect_structured: bool = False, symbolic_slice: bool = False, bounds: tuple[str, str] = ("DATA_WIDTH-1", "0")) -> SpecRevision:
    package = SpecPackage.create("adapter_demo")
    package.add_document(
        "component",
        _xml(
            "component",
            "component_source",
            "source",
            f"""
  <ipxact:model><ipxact:ports>
    <ipxact:port><ipxact:name>data</ipxact:name><ipxact:wire>
      <ipxact:direction>inout</ipxact:direction>
      <ipxact:vectors><ipxact:vector><ipxact:left>{bounds[0]}</ipxact:left><ipxact:right>{bounds[1]}</ipxact:right></ipxact:vector></ipxact:vectors>
    </ipxact:wire></ipxact:port>
    <ipxact:port><ipxact:name>service</ipxact:name><ipxact:transactional>
      <ipxact:initiative>requires</ipxact:initiative>
    </ipxact:transactional></ipxact:port>
    <ipxact:port><ipxact:name>bundle</ipxact:name><ipxact:structured packed="true">
      <ipxact:struct direction="out"/>
      <ipxact:structPortTypeDefs><ipxact:structPortTypeDef><ipxact:typeName>bundle_struct_t</ipxact:typeName></ipxact:structPortTypeDef></ipxact:structPortTypeDefs>
    </ipxact:structured></ipxact:port>
  </ipxact:ports></ipxact:model>""",
        ),
    )
    package.add_document(
        "component",
        _xml(
            "component",
            "component_sink",
            "sink",
            f"""
  <ipxact:model><ipxact:ports>
    <ipxact:port><ipxact:name>data</ipxact:name><ipxact:wire>
      <ipxact:direction>in</ipxact:direction>
      <ipxact:vectors><ipxact:vector><ipxact:left>{bounds[0]}</ipxact:left><ipxact:right>{bounds[1]}</ipxact:right></ipxact:vector></ipxact:vectors>
    </ipxact:wire></ipxact:port>
    <ipxact:port><ipxact:name>bundle</ipxact:name><ipxact:structured packed="true">
      <ipxact:struct direction="in"/>
      <ipxact:structPortTypeDefs><ipxact:structPortTypeDef><ipxact:typeName>bundle_struct_t</ipxact:typeName></ipxact:structPortTypeDef></ipxact:structPortTypeDefs>
    </ipxact:structured></ipxact:port>
  </ipxact:ports></ipxact:model>""",
        ),
    )
    package.add_document(
        "design",
        _xml(
            "design",
            "design_direct",
            "direct",
            f"""
  <ipxact:componentInstances>
    <ipxact:componentInstance><ipxact:instanceName>source0</ipxact:instanceName><ipxact:componentRef vendor="spec2gds.example" library="demo" name="source" version="1.0"/></ipxact:componentInstance>
    <ipxact:componentInstance><ipxact:instanceName>sink0</ipxact:instanceName><ipxact:componentRef vendor="spec2gds.example" library="demo" name="sink" version="1.0"/></ipxact:componentInstance>
  </ipxact:componentInstances>
  <ipxact:adHocConnections><ipxact:adHocConnection>
    <ipxact:name>data_link</ipxact:name>
    <ipxact:portReferences>
      <ipxact:internalPortReference componentInstanceRef="source0" portRef="data">
        {'''<ipxact:partSelect><ipxact:range><ipxact:left>DATA_WIDTH-1</ipxact:left><ipxact:right>0</ipxact:right></ipxact:range></ipxact:partSelect>''' if symbolic_slice else ''}
      </ipxact:internalPortReference>
      <ipxact:internalPortReference componentInstanceRef="sink0" portRef="data"/>
    </ipxact:portReferences>
  </ipxact:adHocConnection>
  {'''<ipxact:adHocConnection>
    <ipxact:name>bundle_link</ipxact:name>
    <ipxact:portReferences>
      <ipxact:internalPortReference componentInstanceRef="source0" portRef="bundle"/>
      <ipxact:internalPortReference componentInstanceRef="sink0" portRef="bundle"/>
    </ipxact:portReferences>
  </ipxact:adHocConnection>''' if connect_structured else ''}
  </ipxact:adHocConnections>""",
        ),
    )
    return SpecRevision.from_package(package)


def test_projects_direct_ports_inout_and_opaque_vector_text() -> None:
    revision = _direct_revision()
    projection = project_design_to_circuit(revision, "design_direct")
    document = projection.document

    assert document["protocol_version"] == "circuit-designer.v1"
    assert document["design"]["id"] == "design_direct"
    assert [instance["label"] for instance in document["design"]["instances"]] == ["source0", "sink0"]
    assert len(document["design"]["nets"]) == 1
    assert document["design"]["nets"][0]["label"] == "data_link"
    terminals = [terminal for component in document["components"] for terminal in component["terminals"]]
    assert [terminal["direction"] for terminal in terminals] == ["inout", "input"]
    assert {terminal["width"] for terminal in terminals} == {"[DATA_WIDTH-1:0]"}
    assert projection.source_entity_kind == "design"
    assert projection.omitted_bus_items == ()
    assert set(projection.omitted_ports) == {"source.service", "source.bundle", "sink.bundle"}


@pytest.mark.parametrize("bounds, width", [(("3", "0"), 4), (("0", "3"), 4), (("7", "4"), 4), (("3", "3"), 1)])
def test_projects_concrete_vector_ranges_as_numeric_widths(bounds, width) -> None:
    revision = _direct_revision(bounds=bounds)
    document = project_design_to_circuit(revision, "design_direct").document
    terminals = [terminal for component in document["components"] for terminal in component["terminals"]]
    assert [terminal["width"] for terminal in terminals] == [width, width]
    assert all(type(terminal["width"]) is int for terminal in terminals)


def test_reports_bus_interconnections_as_intentionally_omitted() -> None:
    from spec2gds.agent_spec.spec_format.testing import build_test_package

    revision = SpecRevision.from_package(build_test_package())
    projection = project_design_to_circuit(revision, "design_subsystem_internal")

    assert projection.omitted_bus_items == ("link0",)
    assert projection.omitted_ports == ()
    assert projection.document["design"]["nets"] == []


def test_projects_a_leaf_component_as_one_preview_instance() -> None:
    revision = _direct_revision()
    projection = project_component_to_circuit(revision, "component_source")

    assert projection.source_entity_kind == "component"
    assert projection.source_entity_id == "component_source"
    assert projection.document["document_id"].endswith("_v2")
    assert projection.document["design"]["boundary_terminals"] == []
    assert projection.document["design"]["instances"] == [{
        "id": "component_source_preview",
        "label": "source",
        "component_id": "component_source",
        "parameter_values": {},
    }]
    assert projection.document["components"][0]["label"] == "source"
    assert projection.document["components"][0]["terminals"] == [{
        "id": "data",
        "label": "data",
        "direction": "inout",
        "width": "[DATA_WIDTH-1:0]",
        "category": "port",
    }]
    assert projection.omitted_ports == ("service", "bundle")


def test_rejects_a_design_connection_that_uses_a_non_wire_port() -> None:
    revision = _direct_revision(connect_structured=True)

    with pytest.raises(CircuitAdapterError, match="bundle is structured"):
        project_design_to_circuit(revision, "design_direct")


def test_preserves_symbolic_part_select_in_ir_but_marks_circuit_projection_unavailable() -> None:
    revision = _direct_revision(symbolic_slice=True)
    endpoint = revision.designs[0].connections[0].port_endpoints[0]

    assert endpoint.slice is None
    assert endpoint.symbolic_slice == "DATA_WIDTH-1:0"
    with pytest.raises(CircuitAdapterError, match="symbolic part-select DATA_WIDTH-1:0"):
        project_design_to_circuit(revision, "design_direct")


def test_round_trips_source_semantic_layout_and_numeric_slices() -> None:
    revision = _direct_revision()
    session_id = source_session_document_id(revision, "design_direct")
    projection = project_design_to_circuit(
        revision, "design_direct", session_document_id=session_id, include_catalog=True
    )
    candidate = copy.deepcopy(projection.document)
    candidate["layout"]["instance_geometry"]["source0"] = {
        "x": 40, "y": 60, "width": 180, "height": 100, "pinned": True,
    }
    candidate["design"]["nets"][0]["endpoints"][0]["slice"] = {"lsb": 1, "width": 2}
    operations = compile_circuit_sync_operations(revision, projection, candidate)
    result = SpecEditTransaction(revision.source_revision_hash, operations).apply(revision)

    assert result.succeeded, result.diagnostics
    assert result.revision is not None
    connection = next(item for item in result.revision.designs[0].connections if item.name == "data_link")
    assert connection.port_endpoints[0].slice is not None
    assert (connection.port_endpoints[0].slice.lsb, connection.port_endpoints[0].slice.width) == (1, 2)
    refreshed = project_design_to_circuit(
        result.revision, "design_direct", session_document_id=session_id, include_catalog=True
    )
    assert refreshed.document["layout"]["instance_geometry"]["source0"]["x"] == 40
    assert refreshed.document["document_id"] == session_id

    package = result.revision.to_package()
    layout_path = "annotations/circuit-layout/design_direct.json"
    malformed = json.loads(package.files[layout_path])
    malformed["instance_geometry"]["unknown_instance"] = {
        "x": 0, "y": 0, "width": -1, "height": 100,
    }
    package.files[layout_path] = json.dumps(malformed).encode()
    with pytest.raises(SpecValidationError, match="Invalid circuit layouts"):
        package.require_valid()


def test_round_trips_timing_markers_and_semantic_clock_assignments() -> None:
    revision = _direct_revision()
    session_id = source_session_document_id(revision, "design_direct")
    projection = project_design_to_circuit(
        revision, "design_direct", session_document_id=session_id, include_catalog=True
    )
    candidate = copy.deepcopy(projection.document)
    candidate["timing"] = {
        "schema_version": 1,
        "clock_domains": [
            {"id": "default", "label": "clk", "signal": {"kind": "net", "id": "data_link"}},
            {"id": "io", "label": "io_clk", "color": "#7c5ce7"},
        ],
        "cycle_edges": [
            {"id": "edge_1", "x": 320, "label": "C1", "next_stage_label": "Execute", "locked": True},
        ],
        "subject_domain_overrides": {"instance:sink0": "io"},
        "leading_stage_label": "Decode",
    }
    result = SpecEditTransaction(
        revision.source_revision_hash,
        compile_circuit_sync_operations(revision, projection, candidate),
    ).apply(revision)

    assert result.succeeded, result.diagnostics
    assert result.revision is not None
    package = result.revision.to_package()
    timing_path = "annotations/circuit-timing/design_direct.json"
    stored = json.loads(package.files[timing_path])
    assert stored["subject_domain_overrides"] == {"instance:sink0": "io"}
    assert stored["clock_domains"][0]["signal"] == {"kind": "net", "id": "data_link"}
    refreshed = project_design_to_circuit(
        result.revision, "design_direct", session_document_id=session_id, include_catalog=True
    )
    assert refreshed.document["timing"] == candidate["timing"]

    stored["subject_domain_overrides"]["instance:missing"] = "io"
    package.files[timing_path] = json.dumps(stored).encode()
    with pytest.raises(SpecValidationError, match="Invalid circuit timing"):
        package.require_valid()


def test_round_trip_creates_a_real_local_component_and_instance() -> None:
    revision = _direct_revision()
    projection = project_design_to_circuit(
        revision,
        "design_direct",
        session_document_id=source_session_document_id(revision, "design_direct"),
        include_catalog=True,
    )
    candidate = copy.deepcopy(projection.document)
    candidate["components"].append({
        "id": "alu",
        "label": "Arithmetic unit",
        "origin": "local",
        "editable": True,
        "terminals": [
            {"id": "input", "label": "input", "direction": "input", "width": 1, "category": "port"},
            {"id": "output", "label": "output", "direction": "output", "width": 1, "category": "port"},
        ],
        "parameters": [],
        "appearance": {"renderer_key": "generic", "properties": {}},
    })
    candidate["design"]["instances"].append({
        "id": "alu0", "label": "alu0", "component_id": "alu", "parameter_values": {},
    })
    result = SpecEditTransaction(
        revision.source_revision_hash,
        compile_circuit_sync_operations(revision, projection, candidate),
    ).apply(revision)

    assert result.succeeded, result.diagnostics
    assert result.revision is not None
    component = result.revision.by_vlnv("component", "spec2gds.local:work:arithmetic_unit:1.0")
    assert component.display_name == "Arithmetic unit"
    refreshed = project_design_to_circuit(result.revision, "design_direct", include_catalog=True)
    assert next(item for item in refreshed.document["components"] if item["id"] == component.ref.entity_id)["label"] == "Arithmetic unit"
    assert refreshed.document["design"]["nets"] == projection.document["design"]["nets"]
    assert any(item.name == "alu0" for item in result.revision.designs[0].instances)

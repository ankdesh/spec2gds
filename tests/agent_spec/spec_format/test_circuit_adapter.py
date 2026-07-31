"""Direct-port IP-XACT to Circuit Designer adapter tests."""

from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.circuit_adapter import (
    project_component_to_circuit,
    project_design_to_circuit,
)
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.samples import _xml


def _direct_revision() -> SpecRevision:
    package = SpecPackage.create("adapter_demo")
    package.add_document(
        "component",
        _xml(
            "component",
            "component_source",
            "source",
            """
  <ipxact:model><ipxact:ports>
    <ipxact:port><ipxact:name>data</ipxact:name><ipxact:wire>
      <ipxact:direction>inout</ipxact:direction>
      <ipxact:vectors><ipxact:vector><ipxact:left>DATA_WIDTH-1</ipxact:left><ipxact:right>0</ipxact:right></ipxact:vector></ipxact:vectors>
    </ipxact:wire></ipxact:port>
  </ipxact:ports></ipxact:model>""",
        ),
    )
    package.add_document(
        "component",
        _xml(
            "component",
            "component_sink",
            "sink",
            """
  <ipxact:model><ipxact:ports>
    <ipxact:port><ipxact:name>data</ipxact:name><ipxact:wire>
      <ipxact:direction>in</ipxact:direction>
      <ipxact:vectors><ipxact:vector><ipxact:left>DATA_WIDTH-1</ipxact:left><ipxact:right>0</ipxact:right></ipxact:vector></ipxact:vectors>
    </ipxact:wire></ipxact:port>
  </ipxact:ports></ipxact:model>""",
        ),
    )
    package.add_document(
        "design",
        _xml(
            "design",
            "design_direct",
            "direct",
            """
  <ipxact:componentInstances>
    <ipxact:componentInstance><ipxact:instanceName>source0</ipxact:instanceName><ipxact:componentRef vendor="spec2gds.example" library="demo" name="source" version="1.0"/></ipxact:componentInstance>
    <ipxact:componentInstance><ipxact:instanceName>sink0</ipxact:instanceName><ipxact:componentRef vendor="spec2gds.example" library="demo" name="sink" version="1.0"/></ipxact:componentInstance>
  </ipxact:componentInstances>
  <ipxact:adHocConnections><ipxact:adHocConnection>
    <ipxact:name>data_link</ipxact:name>
    <ipxact:portReferences>
      <ipxact:internalPortReference componentInstanceRef="source0" portRef="data"/>
      <ipxact:internalPortReference componentInstanceRef="sink0" portRef="data"/>
    </ipxact:portReferences>
  </ipxact:adHocConnection></ipxact:adHocConnections>""",
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


def test_reports_bus_interconnections_as_intentionally_omitted() -> None:
    from spec2gds.agent_spec.spec_format.samples import build_v1_sample

    revision = SpecRevision.from_package(build_v1_sample())
    projection = project_design_to_circuit(revision, "design_subsystem_internal")

    assert projection.omitted_bus_items == ("link0",)
    assert projection.document["design"]["nets"] == []


def test_projects_a_leaf_component_as_a_direct_port_boundary() -> None:
    revision = _direct_revision()
    projection = project_component_to_circuit(revision, "component_source")

    assert projection.source_entity_kind == "component"
    assert projection.source_entity_id == "component_source"
    assert projection.document["design"]["instances"] == []
    assert projection.document["design"]["boundary_terminals"] == [{
        "id": "data",
        "label": "data",
        "direction": "inout",
        "width": "[DATA_WIDTH-1:0]",
        "category": "port",
    }]

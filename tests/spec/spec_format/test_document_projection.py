"""Read-only unified document and A2UI v0.9 projection checks."""

import copy
import dataclasses

import pytest

from spec2gds.spec.spec_format import document as document_module
from spec2gds.spec.spec_format.circuit_adapter import CircuitAdapterError
from spec2gds.spec.spec_format.document import (
    A2UI_CATALOG_ID,
    build_a2ui_batch,
    build_document_projection,
)
from spec2gds.spec.spec_format.ir import (
    ConnectionIR,
    EndpointSliceIR,
    ExternalPortEndpointIR,
    PortEndpointIR,
    SpecRevision,
)
from spec2gds.spec.spec_format.testing import build_test_package


def _projection():
    return build_document_projection(SpecRevision.from_package(build_test_package()))


def test_connection_tables_show_independent_numeric_and_symbolic_selections() -> None:
    import lxml.etree as etree

    revision = SpecRevision.from_package(build_test_package())
    design = dataclasses.replace(revision.designs[0], connections=(
        ConnectionIR(name="lane", kind="ad_hoc", port_endpoints=(PortEndpointIR("u_lane", "din", EndpointSliceIR(0, 8)),), external_ports=(ExternalPortEndpointIR("data", EndpointSliceIR(16, 8)),)),
        ConnectionIR(name="enable", kind="ad_hoc", port_endpoints=(PortEndpointIR("u_lane", "enable", EndpointSliceIR(0, 1)),), external_ports=(ExternalPortEndpointIR("enable", EndpointSliceIR(2, 1)),)),
        ConnectionIR(name="symbolic", kind="ad_hoc", port_endpoints=(PortEndpointIR("u_lane", "din", symbolic_slice="N-1:0"),), external_ports=(ExternalPortEndpointIR("data", symbolic_slice="M+N-1:M"),)),
    ))
    tables = document_module._design_tables(design, etree.fromstring(b"<design/>"), {}, revision)
    rows = next(table for table in tables if table.kind == "ad_hoc_connections").rows
    assert rows[0].cells["endpoints"].value == "u_lane.din[7:0]"
    assert rows[0].cells["external"].value == "data[23:16]"
    assert rows[0].cells["width"].value == "8 bits"
    assert rows[1].cells["endpoints"].value == "u_lane.enable[0]"
    assert rows[1].cells["external"].value == "enable[2]"
    assert rows[1].cells["width"].value == "1 bit"
    assert rows[2].cells["endpoints"].value == "u_lane.din[N-1:0]"
    assert rows[2].cells["external"].value == "data[M+N-1:M]"
    assert rows[2].cells["width"].value == "Not resolved"


def test_document_projection_has_stable_human_hierarchy_and_profile_tables() -> None:
    projection = _projection()

    assert projection.schema_version == "spec2gds.document.v2"
    assert projection.sections[0].title == "Overview"
    assert projection.sections[0].facts == []
    level_one_titles = [section.title for section in projection.sections if section.level == 1]
    assert level_one_titles[:3] == ["Overview", "Top-level Designs", "Components"]
    assert "Protocols" not in level_one_titles
    assert projection.summary == "3 components · 3 designs"
    assert [entry.section_id for entry in projection.toc] == [
        section.section_id for section in projection.sections
    ]

    component_sections = [
        section for section in projection.sections
        if section.entity_ref and section.entity_ref.entity_kind == "component"
    ]
    assert len(component_sections) == 3
    table_kinds = {
        table.kind
        for section in projection.sections
        for table in section.tables
    }
    assert {
        "component_ports",
        "design_instances",
        "ad_hoc_connections",
    }.issubset(table_kinds)
    assert {
        "bus_interfaces",
        "port_maps",
        "interface_connections",
        "channels",
        "bus_properties",
        "abstraction_ports",
    }.isdisjoint(table_kinds)
    assert {
        section.entity_ref.entity_kind
        for section in projection.sections
        if section.entity_ref
    }.isdisjoint({"bus_definition", "abstraction_definition"})
    port_tables_by_section = [
        [table for table in section.tables if table.kind == "component_ports"]
        for section in component_sections
    ]
    assert all(len(tables) == 1 for tables in port_tables_by_section)
    assert all(tables[0].title == "Ports" for tables in port_tables_by_section)
    expected_counts = sorted(
        len(component.ports)
        for component in SpecRevision.from_package(build_test_package()).components
    )
    assert sorted(len(tables[0].rows) for tables in port_tables_by_section) == expected_counts


def test_editor_projection_does_not_remove_bus_protocol_data_from_source_revision() -> None:
    revision = SpecRevision.from_package(build_test_package())

    assert revision.bus_definitions
    assert revision.abstraction_definitions
    assert any(component.interfaces for component in revision.components)
    assert any(
        connection.kind == "interface"
        for design in revision.designs
        for connection in design.connections
    )


def test_document_cells_retain_schema_identity_and_presence() -> None:
    projection = _projection()
    cells = [
        cell
        for section in projection.sections
        for table in section.tables
        for row in table.rows
        for cell in row.cells.values()
    ]

    assert cells
    assert all(cell.schema_path.startswith("/") for cell in cells)
    assert any(cell.presence == "absent" and cell.value is None for cell in cells)
    assert any(cell.kind == "reference" for cell in cells)


def test_a2ui_batch_is_adjacency_list_for_the_custom_catalog() -> None:
    projection = _projection()
    batch = build_a2ui_batch(projection)

    assert batch.protocol_version == "v0.9"
    assert batch.catalog_id == A2UI_CATALOG_ID
    assert [next(key for key in message if key != "version") for message in batch.messages] == [
        "createSurface",
        "updateComponents",
        "updateDataModel",
    ]
    create = batch.messages[0]["createSurface"]
    update = batch.messages[1]["updateComponents"]
    assert create == {"surfaceId": batch.surface_id, "catalogId": A2UI_CATALOG_ID}
    assert update["surfaceId"] == batch.surface_id
    components = update["components"]
    assert components[-1]["id"] == "root"
    assert components[-1]["component"] == "SpecDocument"
    assert all("component" in component for component in components)
    assert not any(
        isinstance(component.get("children"), list)
        and any(isinstance(child, dict) for child in component["children"])
        for component in components
    )


def test_every_design_has_a_revision_derived_topology_before_its_tables() -> None:
    revision = SpecRevision.from_package(build_test_package())
    narrative_before = revision.narrative.model_dump(mode="json")
    assets_before = revision.manifest.assets
    projection = build_document_projection(revision)
    design_sections = [
        section for section in projection.sections
        if section.entity_ref and section.entity_ref.entity_kind == "design"
    ]

    assert len(design_sections) == len(revision.designs)
    topology_by_title = {
        section.title: [
            block for block in section.narrative
            if block["type"] == "live_view" and block["renderer_id"] == "design.topology"
        ]
        for section in design_sections
    }
    assert all(topology_by_title.values())
    assert topology_by_title["subsystem internal"][0]["block_id"] == "topology_live_view"
    assert topology_by_title["subsystem internal"][0]["options"]["status"] == "ready"
    assert topology_by_title["subsystem internal"][0]["options"]["omitted_bus_items"] == ["link0"]
    assert topology_by_title["top a"][0]["block_id"].startswith("derived_topology_")
    assert topology_by_title["top a"][0]["options"]["circuit_document"]["document_id"].endswith("_v2")
    assert revision.narrative.model_dump(mode="json") == narrative_before
    assert revision.manifest.assets == assets_before

    batch = build_a2ui_batch(projection)
    components = batch.messages[1]["updateComponents"]["components"]
    component_by_id = {component["id"]: component for component in components}
    for section in design_sections:
        section_component = component_by_id[f"section-{section.section_id}"]
        child_components = [component_by_id[child_id]["component"] for child_id in section_component["children"]]
        assert child_components[0] == "LiveView"
        assert "SpecTable" in child_components


def test_topology_projection_isolates_unsafe_and_empty_designs(monkeypatch: pytest.MonkeyPatch) -> None:
    revision = SpecRevision.from_package(build_test_package())
    original = document_module.project_source_to_circuit

    def controlled_projection(revision_value, entity_kind, entity_id):
        if entity_id == "design_top_b":
            raise CircuitAdapterError("connected structured endpoint cannot be represented")
        projected = original(revision_value, entity_kind, entity_id)
        if entity_id != "design_top_a":
            return projected
        document = copy.deepcopy(projected.document)
        document["design"]["instances"] = []
        document["design"]["nets"] = []
        document["design"]["boundary_terminals"] = []
        return dataclasses.replace(projected, document=document)

    monkeypatch.setattr(document_module, "project_source_to_circuit", controlled_projection)
    projection = build_document_projection(revision)
    states = {
        section.entity_ref.entity_id: next(
            block["options"] for block in section.narrative
            if block["type"] == "live_view" and block["renderer_id"] == "design.topology"
        )
        for section in projection.sections
        if section.entity_ref and section.entity_ref.entity_kind == "design"
    }

    assert states["design_top_a"]["status"] == "empty"
    assert "circuit_document" not in states["design_top_a"]
    assert states["design_top_b"] == {
        "document_name": "Specification",
        "schema_version": 1,
        "status": "unavailable",
        "omitted_bus_items": [],
        "omitted_ports": [],
        "message": "connected structured endpoint cannot be represented",
    }

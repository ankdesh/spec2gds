"""Read-only unified document and A2UI v0.9 projection checks."""

from spec2gds.agent_spec.spec_format.document import (
    A2UI_CATALOG_ID,
    build_a2ui_batch,
    build_document_projection,
)
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.testing import build_test_package


def _projection():
    return build_document_projection(SpecRevision.from_package(build_test_package()))


def test_document_projection_has_stable_human_hierarchy_and_profile_tables() -> None:
    projection = _projection()

    assert projection.schema_version == "spec2gds.document.v1"
    assert projection.sections[0].title == "Overview"
    assert projection.sections[0].facts == []
    level_one_titles = [section.title for section in projection.sections if section.level == 1]
    assert level_one_titles[:3] == ["Overview", "Designs", "Components"]
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

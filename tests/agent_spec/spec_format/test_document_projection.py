"""Read-only unified document and A2UI v0.9 projection checks."""

from spec2gds.agent_spec.spec_format.document import (
    A2UI_CATALOG_ID,
    build_a2ui_batch,
    build_document_projection,
)
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.samples import build_v1_sample


def _projection():
    return build_document_projection(SpecRevision.from_package(build_v1_sample()))


def test_document_projection_has_stable_human_hierarchy_and_profile_tables() -> None:
    projection = _projection()

    assert projection.schema_version == "spec2gds.document.v1"
    assert projection.sections[0].title == "Overview"
    level_one_titles = [section.title for section in projection.sections if section.level == 1]
    assert level_one_titles[:4] == ["Overview", "Designs", "Components", "Protocols"]
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
        "bus_interfaces",
        "port_maps",
        "design_instances",
        "interface_connections",
        "ad_hoc_connections",
        "bus_properties",
        "abstraction_ports",
    }.issubset(table_kinds)


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
    assert any(cell.presence == "defaulted" for cell in cells)
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

"""Renderer-neutral unified document projection and A2UI v0.9 messages.

The source of truth remains :class:`SpecRevision`.  This module only derives a
human-oriented, deterministic presentation contract from the validated IP-XACT
and narrative sources.  Browser renderers never receive XML nodes.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import typing

import lxml.etree as etree
import pydantic

from spec2gds.agent_spec.spec_format import ipxact
from spec2gds.agent_spec.spec_format.circuit_adapter import (
    CircuitAdapterError,
    project_source_to_circuit,
)
from spec2gds.agent_spec.spec_format.ir import (
    AbstractionDefinitionIR,
    BusDefinitionIR,
    ComponentIR,
    DesignIR,
    SpecRevision,
)
from spec2gds.agent_spec.spec_format.models import EntityRef, NarrativeBlock
from spec2gds.agent_spec.spec_format.naming import (
    document_name,
    entity_name,
    qualified_reference_name,
    reference_name,
)
from spec2gds.agent_spec.spec_format.sections import SECTION_TYPES
from spec2gds.agent_spec.spec_format.source_edits import format_wire_range
from spec2gds.agent_spec.spec_format.sv_validation import validate_revision_sections

A2UI_PROTOCOL_VERSION = "v0.9"
A2UI_CATALOG_ID = "urn:spec2gds:a2ui:document:v2"
DOCUMENT_SCHEMA_VERSION = "spec2gds.document.v2"

# Bus/protocol modeling remains part of SpecRevision and the projection builders
# below, but it is outside the current editor workflow. Keep the visibility rule
# at the final presentation boundary so source parsing and future UI support stay
# intact while the editor remains focused on components, ports, and direct wiring.
_EDITOR_HIDDEN_ENTITY_KINDS = frozenset({"bus_definition", "abstraction_definition"})
_EDITOR_HIDDEN_TABLE_KINDS = frozenset({
    "bus_interfaces",
    "channels",
    "interface_connections",
    "port_maps",
})

CellKind = typing.Literal["text", "multiline", "boolean", "integer", "expression", "enum", "reference"]
CellPresence = typing.Literal["explicit", "defaulted", "absent"]


class DocumentCell(pydantic.BaseModel):
    """One normalized display value with its exact source-schema identity."""

    model_config = pydantic.ConfigDict(extra="forbid")

    kind: CellKind = "text"
    value: str | int | bool | None = None
    presence: CellPresence = "explicit"
    schema_path: str
    reference_anchor: str = ""
    display_text: str = ""


class DocumentColumn(pydantic.BaseModel):
    """A stable, human-readable column in one fixed table kind."""

    model_config = pydantic.ConfigDict(extra="forbid")

    key: str
    label: str
    schema_path: str


class DocumentRow(pydantic.BaseModel):
    """A deterministic table row keyed independently of its visible values."""

    model_config = pydantic.ConfigDict(extra="forbid")

    row_id: str
    cells: dict[str, DocumentCell]


class DocumentTable(pydantic.BaseModel):
    """One fixed-column table derived from a profiled IP-XACT record family."""

    model_config = pydantic.ConfigDict(extra="forbid")

    table_id: str
    kind: str
    title: str
    columns: list[DocumentColumn]
    rows: list[DocumentRow]


class DocumentFact(pydantic.BaseModel):
    """A compact metadata value rendered above entity tables."""

    model_config = pydantic.ConfigDict(extra="forbid")

    label: str
    value: str
    schema_path: str = ""
    reference_anchor: str = ""
    display_text: str = ""


class SectionDiagnostic(pydantic.BaseModel):
    """One source-located validation result for an entity section."""

    model_config = pydantic.ConfigDict(extra="forbid")

    code: str
    message: str
    line: int | None = None
    column: int | None = None
    blocking: bool = False


class EntityContentSection(pydantic.BaseModel):
    """Typed content projected through the central section registry."""

    model_config = pydantic.ConfigDict(extra="forbid")

    section_id: str
    section_type: str
    type_version: int
    title: str
    owner: EntityRef
    payload: dict[str, typing.Any]
    editable: bool
    deletable: bool
    validation_status: typing.Literal["verified", "warnings", "unverified", "errors"] = "unverified"
    diagnostics: list[SectionDiagnostic] = pydantic.Field(default_factory=list)


class AvailableSectionType(pydantic.BaseModel):
    """A singleton section type that may be added to this entity."""

    model_config = pydantic.ConfigDict(extra="forbid")

    section_type: str
    type_version: int
    title: str


class DocumentSection(pydantic.BaseModel):
    """One ordered heading in the generated document."""

    model_config = pydantic.ConfigDict(extra="forbid")

    section_id: str
    title: str
    level: int
    qualified_name: str = ""
    eyebrow: str = ""
    entity_ref: EntityRef | None = None
    facts: list[DocumentFact] = pydantic.Field(default_factory=list)
    tables: list[DocumentTable] = pydantic.Field(default_factory=list)
    narrative: list[dict[str, typing.Any]] = pydantic.Field(default_factory=list)
    content_sections: list[EntityContentSection] = pydantic.Field(default_factory=list)
    available_section_types: list[AvailableSectionType] = pydantic.Field(default_factory=list)


class TocEntry(pydantic.BaseModel):
    """One stable table-of-contents link."""

    model_config = pydantic.ConfigDict(extra="forbid")

    section_id: str
    title: str
    level: int


class DocumentProjection(pydantic.BaseModel):
    """Complete renderer-neutral projection of one validated source revision."""

    model_config = pydantic.ConfigDict(extra="forbid")

    schema_version: str = DOCUMENT_SCHEMA_VERSION
    document_id: str
    source_revision_hash: str
    title: str
    summary: str
    toc: list[TocEntry]
    sections: list[DocumentSection]


class A2UIDocumentBatch(pydantic.BaseModel):
    """App wrapper around an ordered, directly consumable A2UI message batch."""

    model_config = pydantic.ConfigDict(extra="forbid")

    protocol_version: typing.Literal["v0.9"] = A2UI_PROTOCOL_VERSION
    catalog_id: str = A2UI_CATALOG_ID
    surface_id: str
    source_revision_hash: str
    messages: list[dict[str, typing.Any]]


def _children(node: etree._Element, name: str) -> list[etree._Element]:
    return typing.cast(list[etree._Element], node.xpath(f"./*[local-name()='{name}']"))


def _descendants(node: etree._Element, path: str) -> list[etree._Element]:
    expression = "./" + "/".join(f"*[local-name()='{part}']" for part in path.split("/"))
    return typing.cast(list[etree._Element], node.xpath(expression))


def _child(node: etree._Element, name: str) -> etree._Element | None:
    values = _children(node, name)
    return values[0] if values else None


def _text(node: etree._Element | None, name: str | None = None) -> str:
    if node is None:
        return ""
    target = _child(node, name) if name else node
    return (target.text or "").strip() if target is not None else ""


def _vlnv(node: etree._Element | None) -> str:
    if node is None:
        return ""
    values = [node.get(field, "") for field in ("vendor", "library", "name", "version")]
    return ":".join(values) if all(values) else ""


def _boolean(value: str | None) -> bool | None:
    """Normalize IP-XACT XML Schema boolean lexical values for the renderer."""
    normalized = (value or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    return None


def _root_vlnv_parts(root: etree._Element) -> tuple[str, str, str, str]:
    return tuple(_text(root, field) for field in ("vendor", "library", "name", "version"))  # type: ignore[return-value]


def _anchor(kind: str, entity_id: str) -> str:
    return f"{kind}-{entity_id}".replace("_", "-")


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return normalized or "item"


def _cell(
    value: str | int | bool | None,
    schema_path: str,
    *,
    kind: CellKind = "text",
    default: str | int | bool | None = None,
    reference_anchor: str = "",
) -> DocumentCell:
    if value is None or value == "":
        if default is not None:
            return DocumentCell(kind=kind, value=default, presence="defaulted", schema_path=schema_path, reference_anchor=reference_anchor)
        return DocumentCell(kind=kind, value=None, presence="absent", schema_path=schema_path, reference_anchor=reference_anchor)
    return DocumentCell(kind=kind, value=value, presence="explicit", schema_path=schema_path, reference_anchor=reference_anchor)


def _columns(*items: tuple[str, str, str]) -> list[DocumentColumn]:
    return [DocumentColumn(key=key, label=label, schema_path=path) for key, label, path in items]


def _row_key(row: dict[str, DocumentCell], kind: str) -> str:
    """Derive a stable row identity from semantic key cells, never list position."""
    preferred = ("name", "interface", "logical", "physical")
    values = [
        str(row[key].value)
        for key in preferred
        if key in row and row[key].value not in (None, "")
    ]
    if values:
        return _slug("-".join(values))
    if kind == "bus_properties":
        return "properties"
    canonical = json.dumps(
        {key: cell.value for key, cell in sorted(row.items())},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"content-{hashlib.sha256(canonical).hexdigest()[:12]}"


def _table(table_id: str, kind: str, title: str, columns: list[DocumentColumn], rows: list[dict[str, DocumentCell]]) -> DocumentTable:
    return DocumentTable(
        table_id=table_id,
        kind=kind,
        title=title,
        columns=columns,
        rows=[
            DocumentRow(row_id=f"{table_id}-row-{_row_key(row, kind)}", cells=row)
            for row in rows
        ],
    )


def _document_roots(revision: SpecRevision) -> dict[str, etree._Element]:
    package = revision.to_package()
    return {
        entry.entity_id: ipxact.parse_xml(package.files[entry.path])
        for entry in package.manifest.documents
    }


def _identity_facts(root: etree._Element, vlnv: str) -> list[DocumentFact]:
    vendor, library, name, version = _root_vlnv_parts(root)
    return [
        DocumentFact(label="VLNV", value=vlnv, schema_path="/vendor | /library | /name | /version"),
        DocumentFact(label="Vendor", value=vendor, schema_path="/vendor"),
        DocumentFact(label="Library", value=library, schema_path="/library"),
        DocumentFact(label="Name", value=name, schema_path="/name"),
        DocumentFact(label="Version", value=version, schema_path="/version"),
        DocumentFact(label="Display name", value=_text(root, "displayName"), schema_path="/displayName"),
        DocumentFact(label="Short description", value=_text(root, "shortDescription"), schema_path="/shortDescription"),
        DocumentFact(label="Description", value=_text(root, "description"), schema_path="/description"),
    ]


def _configuration_tables(root: etree._Element, prefix: str) -> list[DocumentTable]:
    """Project parameters, assertions and choices into renderer-neutral cells.

    Source paths remain attached to values so presentation does not become a second
    source model. Empty groups produce no table rather than fabricated defaults.
    """
    tables: list[DocumentTable] = []
    parameters: list[dict[str, DocumentCell]] = []
    for parameter in _descendants(root, "parameters/parameter"):
        value = _child(parameter, "value")
        parameters.append({
            "name": _cell(_text(parameter, "name"), "/parameters/parameter/name"),
            "value": _cell(_text(value), "/parameters/parameter/value", kind="expression"),
            "resolve": _cell(parameter.get("resolve", ""), "/parameters/parameter/@resolve", kind="enum"),
            "type": _cell(parameter.get("type", ""), "/parameters/parameter/@type", kind="enum"),
            "choice": _cell(parameter.get("choiceRef", ""), "/parameters/parameter/@choiceRef", kind="reference"),
            "minimum": _cell(parameter.get("minimum", ""), "/parameters/parameter/@minimum", kind="expression"),
            "maximum": _cell(parameter.get("maximum", ""), "/parameters/parameter/@maximum", kind="expression"),
            "description": _cell(_text(parameter, "description"), "/parameters/parameter/description", kind="multiline"),
        })
    if parameters:
        tables.append(_table(
            f"{prefix}-parameters",
            "parameters",
            "Parameters",
            _columns(
                ("name", "Name", "/parameters/parameter/name"),
                ("value", "Value", "/parameters/parameter/value"),
                ("resolve", "Resolve", "/parameters/parameter/@resolve"),
                ("type", "Type", "/parameters/parameter/@type"),
                ("choice", "Choice", "/parameters/parameter/@choiceRef"),
                ("minimum", "Minimum", "/parameters/parameter/@minimum"),
                ("maximum", "Maximum", "/parameters/parameter/@maximum"),
                ("description", "Description", "/parameters/parameter/description"),
            ),
            parameters,
        ))

    assertions = [{
        "name": _cell(_text(assertion, "name"), "/assertions/assertion/name"),
        "expression": _cell(_text(assertion, "assert"), "/assertions/assertion/assert", kind="expression"),
        "description": _cell(_text(assertion, "description"), "/assertions/assertion/description", kind="multiline"),
    } for assertion in _descendants(root, "assertions/assertion")]
    if assertions:
        tables.append(_table(
            f"{prefix}-assertions",
            "assertions",
            "Assertions",
            _columns(
                ("name", "Name", "/assertions/assertion/name"),
                ("expression", "Expression", "/assertions/assertion/assert"),
                ("description", "Description", "/assertions/assertion/description"),
            ),
            assertions,
        ))

    choices: list[dict[str, DocumentCell]] = []
    for choice in _descendants(root, "choices/choice"):
        enumerations = [
            _text(enumeration, "value") or _text(enumeration)
            for enumeration in _children(choice, "enumeration")
        ]
        choices.append({
            "name": _cell(_text(choice, "name"), "/choices/choice/name"),
            "values": _cell(", ".join(value for value in enumerations if value), "/choices/choice/enumeration", kind="text"),
            "description": _cell(_text(choice, "description"), "/choices/choice/description", kind="multiline"),
        })
    if choices:
        tables.append(_table(
            f"{prefix}-choices",
            "choices",
            "Choices",
            _columns(
                ("name", "Name", "/choices/choice/name"),
                ("values", "Values", "/choices/choice/enumeration"),
                ("description", "Description", "/choices/choice/description"),
            ),
            choices,
        ))
    return tables


def _qualifier(node: etree._Element | None) -> str:
    if node is None:
        return ""
    names: list[str] = []
    for child in node:
        name = etree.QName(child).localname
        value = (child.text or "").strip()
        if value and value.lower() not in {"true", "1"}:
            names.append(f"{name}={value}")
        elif value.lower() in {"true", "1"}:
            names.append(name)
    return ", ".join(names)


def _component_tables(
    component: ComponentIR,
    root: etree._Element,
    anchors_by_vlnv: dict[str, str],
) -> list[DocumentTable]:
    """Build component tables from preserved IP-XACT source and semantic references.

    The full projection may include protocol information hidden by the normal UI.
    Links use stable entity anchors; renderers never mutate the source XML here.
    """
    prefix = _anchor("component", component.ref.entity_id)
    tables = _configuration_tables(root, prefix)
    port_rows: list[dict[str, DocumentCell]] = []
    for port in _descendants(root, "model/ports/port"):
        wire = _child(port, "wire")
        transactional = _child(port, "transactional")
        structured = _child(port, "structured")
        family = "wire" if wire is not None else "transactional" if transactional is not None else "structured"
        vectors = _child(wire, "vectors") if wire is not None else None
        vector = _child(vectors, "vector") if vectors is not None else None
        struct = _child(structured, "struct") if structured is not None else None
        kind = _child(transactional, "kind") if transactional is not None else None
        name = _text(port, "name")
        left = _text(vector, "left")
        right = _text(vector, "right")
        range_display = format_wire_range(left or None, right or None)
        row = {
            "name": _cell(name, "/model/ports/port/name"),
            "family": _cell(family, "/model/ports/port/(wire|transactional|structured)", kind="enum"),
            "display_name": _cell(_text(port, "displayName"), "/model/ports/port/displayName"),
            "direction": _cell(
                _text(wire, "direction") if wire is not None else (struct.get("direction", "") if struct is not None else ""),
                "/model/ports/port/(wire/direction|structured/struct/@direction)",
                kind="enum",
            ),
            "range": _cell(range_display, "/model/ports/port/wire/vectors/vector", kind="expression"),
            "left": _cell(left, "/model/ports/port/wire/vectors/vector/left", kind="expression"),
            "right": _cell(right, "/model/ports/port/wire/vectors/vector/right", kind="expression"),
            "initiative": _cell(_text(transactional, "initiative"), "/model/ports/port/transactional/initiative", kind="enum"),
            "transaction_kind": _cell(_text(transactional, "kind"), "/model/ports/port/transactional/kind", kind="enum"),
            "custom_kind": _cell(kind.get("custom", "") if kind is not None else "", "/model/ports/port/transactional/kind/@custom"),
            "bus_width": _cell(_text(transactional, "busWidth"), "/model/ports/port/transactional/busWidth", kind="expression"),
            "structure": _cell("Packed struct" if structured is not None else "", "/model/ports/port/structured", kind="enum"),
            "description": _cell(_text(port, "description"), "/model/ports/port/description", kind="multiline"),
        }
        port_rows.append(row)
    tables.append(DocumentTable(
        table_id=f"{prefix}-ports",
        kind="component_ports",
        title="Ports",
        columns=_columns(
            ("name", "Name", "/model/ports/port/name"),
            ("family", "Family", "/model/ports/port/(wire|transactional|structured)"),
            ("display_name", "Display name", "/model/ports/port/displayName"),
            ("direction", "Direction", "/model/ports/port/(wire/direction|structured/struct/@direction)"),
            ("range", "Range", "/model/ports/port/wire/vectors/vector"),
            ("initiative", "Initiative", "/model/ports/port/transactional/initiative"),
            ("transaction_kind", "Kind", "/model/ports/port/transactional/kind"),
            ("custom_kind", "Custom kind", "/model/ports/port/transactional/kind/@custom"),
            ("bus_width", "Bus width", "/model/ports/port/transactional/busWidth"),
            ("structure", "Structure", "/model/ports/port/structured"),
            ("description", "Description", "/model/ports/port/description"),
        ),
        rows=[
            DocumentRow(row_id=f"{prefix}-ports-row-{_row_key(row, 'component_ports')}", cells=row)
            for row in port_rows
        ],
    ))

    interface_rows: list[dict[str, DocumentCell]] = []
    port_map_rows: list[dict[str, DocumentCell]] = []
    for interface in _descendants(root, "busInterfaces/busInterface"):
        name = _text(interface, "name")
        bus_type = _child(interface, "busType")
        abstraction_type = (_descendants(interface, "abstractionTypes/abstractionType") or [None])[0]
        abstraction_ref = _child(abstraction_type, "abstractionRef") if abstraction_type is not None else None
        role = next((candidate for candidate in ("initiator", "target", "system", "monitor") if _child(interface, candidate) is not None), "")
        bus_vlnv = _vlnv(bus_type)
        abstraction_vlnv = _vlnv(abstraction_ref)
        interface_rows.append({
            "name": _cell(name, "/busInterfaces/busInterface/name"),
            "role": _cell(role, "/busInterfaces/busInterface/(initiator|target|system|monitor)", kind="enum"),
            "bus": _cell(
                bus_vlnv,
                "/busInterfaces/busInterface/busType",
                kind="reference",
                reference_anchor=anchors_by_vlnv.get(bus_vlnv, ""),
            ),
            "abstraction": _cell(
                abstraction_vlnv,
                "/busInterfaces/busInterface/abstractionTypes/abstractionType/abstractionRef",
                kind="reference",
                reference_anchor=anchors_by_vlnv.get(abstraction_vlnv, ""),
            ),
            "required": _cell(_boolean(_text(interface, "connectionRequired")), "/busInterfaces/busInterface/connectionRequired", kind="boolean"),
            "bits": _cell(_text(interface, "bitsInLau"), "/busInterfaces/busInterface/bitsInLau", kind="expression"),
            "endianness": _cell(_text(interface, "endianness"), "/busInterfaces/busInterface/endianness", kind="enum", default="little"),
            "description": _cell(_text(interface, "description"), "/busInterfaces/busInterface/description", kind="multiline"),
        })
        if abstraction_type is not None:
            for port_map in _descendants(abstraction_type, "portMaps/portMap"):
                logical = _child(port_map, "logicalPort")
                physical = _child(port_map, "physicalPort")
                port_map_rows.append({
                    "interface": _cell(name, "/busInterfaces/busInterface/name", kind="reference"),
                    "logical": _cell(_text(logical, "name"), "/busInterfaces/busInterface/abstractionTypes/abstractionType/portMaps/portMap/logicalPort/name", kind="reference"),
                    "physical": _cell(_text(physical, "name"), "/busInterfaces/busInterface/abstractionTypes/abstractionType/portMaps/portMap/physicalPort/name", kind="reference"),
                    "tie_off": _cell(_text(port_map, "logicalTieOff"), "/busInterfaces/busInterface/abstractionTypes/abstractionType/portMaps/portMap/logicalTieOff", kind="expression"),
                    "invert": _cell(_boolean(port_map.get("invert")), "/busInterfaces/busInterface/abstractionTypes/abstractionType/portMaps/portMap/@invert", kind="boolean", default=False),
                    "informative": _cell(_boolean(_text(port_map, "isInformative")), "/busInterfaces/busInterface/abstractionTypes/abstractionType/portMaps/portMap/isInformative", kind="boolean", default=False),
                })
    tables.append(_table(
        f"{prefix}-interfaces",
        "bus_interfaces",
        "Bus interfaces",
        _columns(
            ("name", "Name", "/busInterfaces/busInterface/name"),
            ("role", "Role", "/busInterfaces/busInterface/(initiator|target|system|monitor)"),
            ("bus", "Bus type", "/busInterfaces/busInterface/busType"),
            ("abstraction", "Abstraction", "/busInterfaces/busInterface/abstractionTypes/abstractionType/abstractionRef"),
            ("required", "Connection required", "/busInterfaces/busInterface/connectionRequired"),
            ("bits", "Bits in LAU", "/busInterfaces/busInterface/bitsInLau"),
            ("endianness", "Endianness", "/busInterfaces/busInterface/endianness"),
            ("description", "Description", "/busInterfaces/busInterface/description"),
        ),
        interface_rows,
    ))
    if port_map_rows:
        tables.append(_table(
            f"{prefix}-port-maps",
            "port_maps",
            "Port maps",
            _columns(
                ("interface", "Interface", "/busInterfaces/busInterface/name"),
                ("logical", "Logical port", "/busInterfaces/busInterface/.../portMap/logicalPort/name"),
                ("physical", "Physical port", "/busInterfaces/busInterface/.../portMap/physicalPort/name"),
                ("tie_off", "Logical tie-off", "/busInterfaces/busInterface/.../portMap/logicalTieOff"),
                ("invert", "Invert", "/busInterfaces/busInterface/.../portMap/@invert"),
                ("informative", "Informative", "/busInterfaces/busInterface/.../portMap/isInformative"),
            ),
            port_map_rows,
        ))

    channel_rows: list[dict[str, DocumentCell]] = []
    for channel in _descendants(root, "channels/channel"):
        interface_refs = [node.get("localName", "") or _text(node) for node in _children(channel, "busInterfaceRef")]
        channel_rows.append({
            "name": _cell(_text(channel, "name"), "/channels/channel/name"),
            "interfaces": _cell(", ".join(filter(None, interface_refs)), "/channels/channel/busInterfaceRef", kind="reference"),
            "description": _cell(_text(channel, "description"), "/channels/channel/description", kind="multiline"),
        })
    if channel_rows:
        tables.append(_table(
            f"{prefix}-channels",
            "channels",
            "Channels",
            _columns(
                ("name", "Name", "/channels/channel/name"),
                ("interfaces", "Interfaces", "/channels/channel/busInterfaceRef"),
                ("description", "Description", "/channels/channel/description"),
            ),
            channel_rows,
        ))
    return tables


def _design_tables(
    design: DesignIR,
    root: etree._Element,
    anchors_by_vlnv: dict[str, str],
) -> list[DocumentTable]:
    """Project instances and connection rows while keeping source reference paths.

    The document tables remain authoritative when a visual Circuit projection
    cannot represent an otherwise preserved source connection.
    """
    prefix = _anchor("design", design.ref.entity_id)
    tables = _configuration_tables(root, prefix)
    instances = [{
        "name": _cell(instance.name, "/componentInstances/componentInstance/instanceName"),
        "component": _cell(
            instance.component_vlnv,
            "/componentInstances/componentInstance/componentRef",
            kind="reference",
            reference_anchor=anchors_by_vlnv.get(instance.component_vlnv, ""),
        ),
    } for instance in design.instances]
    tables.append(_table(
        f"{prefix}-instances",
        "design_instances",
        "Component instances",
        _columns(
            ("name", "Instance", "/componentInstances/componentInstance/instanceName"),
            ("component", "Component", "/componentInstances/componentInstance/componentRef"),
        ),
        instances,
    ))

    interface_rows: list[dict[str, DocumentCell]] = []
    ad_hoc_rows: list[dict[str, DocumentCell]] = []
    for connection in design.connections:
        if connection.kind == "interface":
            endpoints = ", ".join(f"{item.instance_name}.{item.interface_name}" for item in connection.interface_endpoints)
            interface_rows.append({
                "name": _cell(connection.name, "/interconnections/interconnection/name"),
                "endpoints": _cell(endpoints, "/interconnections/interconnection/activeInterface", kind="reference"),
                "hierarchy": _cell(", ".join(connection.hierarchy_interfaces), "/interconnections/interconnection/hierInterface", kind="reference"),
            })
        else:
            endpoints = ", ".join(f"{item.instance_name}.{item.port_name}" for item in connection.port_endpoints)
            ad_hoc_rows.append({
                "name": _cell(connection.name, "/adHocConnections/adHocConnection/name"),
                "endpoints": _cell(endpoints, "/adHocConnections/adHocConnection/portReferences/internalPortReference", kind="reference"),
                "external": _cell(", ".join(item.port_name for item in connection.external_ports), "/adHocConnections/adHocConnection/portReferences/externalPortReference", kind="reference"),
            })
    tables.append(_table(
        f"{prefix}-interface-connections",
        "interface_connections",
        "Interface connections",
        _columns(
            ("name", "Name", "/interconnections/interconnection/name"),
            ("endpoints", "Instance interfaces", "/interconnections/interconnection/activeInterface"),
            ("hierarchy", "Hierarchy interfaces", "/interconnections/interconnection/hierInterface"),
        ),
        interface_rows,
    ))
    tables.append(_table(
        f"{prefix}-ad-hoc-connections",
        "ad_hoc_connections",
        "Ad-hoc connections",
        _columns(
            ("name", "Name", "/adHocConnections/adHocConnection/name"),
            ("endpoints", "Instance ports", "/adHocConnections/adHocConnection/portReferences/internalPortReference"),
            ("external", "External ports", "/adHocConnections/adHocConnection/portReferences/externalPortReference"),
        ),
        ad_hoc_rows,
    ))
    return tables


def _bus_tables(
    bus: BusDefinitionIR,
    root: etree._Element,
    anchors_by_vlnv: dict[str, str],
) -> list[DocumentTable]:
    prefix = _anchor("bus-definition", bus.ref.entity_id)
    extended_vlnv = _vlnv(_child(root, "extends"))
    rows = [{
        "direct": _cell(_boolean(_text(root, "directConnection")), "/directConnection", kind="boolean"),
        "broadcast": _cell(_boolean(_text(root, "broadcast")), "/broadcast", kind="boolean"),
        "addressable": _cell(_boolean(_text(root, "isAddressable")), "/isAddressable", kind="boolean"),
        "extends": _cell(
            extended_vlnv,
            "/extends",
            kind="reference",
            reference_anchor=anchors_by_vlnv.get(extended_vlnv, ""),
        ),
        "initiators": _cell(_text(root, "maxInitiators"), "/maxInitiators", kind="expression"),
        "targets": _cell(_text(root, "maxTargets"), "/maxTargets", kind="expression"),
        "groups": _cell(", ".join(_text(node) for node in _descendants(root, "systemGroupNames/systemGroupName")), "/systemGroupNames/systemGroupName"),
    }]
    return [
        *_configuration_tables(root, prefix),
        _table(
            f"{prefix}-properties",
            "bus_properties",
            "Bus properties",
            _columns(
                ("direct", "Direct connection", "/directConnection"),
                ("broadcast", "Broadcast", "/broadcast"),
                ("addressable", "Addressable", "/isAddressable"),
                ("extends", "Extends", "/extends"),
                ("initiators", "Max initiators", "/maxInitiators"),
                ("targets", "Max targets", "/maxTargets"),
                ("groups", "System groups", "/systemGroupNames/systemGroupName"),
            ),
            rows,
        ),
    ]


def _abstraction_tables(abstraction: AbstractionDefinitionIR, root: etree._Element) -> list[DocumentTable]:
    """Expose protocol abstraction constraints without inferring physical connections.

    Initiative-specific source fields are carried as cells; missing data remains
    absent rather than choosing an implementation for the user.
    """
    prefix = _anchor("abstraction-definition", abstraction.ref.entity_id)
    rows: list[dict[str, DocumentCell]] = []
    for port in _descendants(root, "ports/port"):
        wire = _child(port, "wire")
        transactional = _child(port, "transactional")
        style = "wire" if wire is not None else "transactional"
        node = wire if wire is not None else transactional

        def format_mode(target: etree._Element | None) -> str:
            if target is None:
                return ""
            direction = _text(target, "direction") or _text(target, "initiative")
            presence = _text(target, "presence")
            width = _text(target, "width") or _text(target, "busWidth")
            group = target.get("group", "")
            return " · ".join(
                part
                for part in (
                    f"group {group}" if group else "",
                    direction,
                    presence,
                    f"width {width}" if width else "",
                )
                if part
            )

        rows.append({
            "name": _cell(_text(port, "logicalName"), "/ports/port/logicalName"),
            "style": _cell(style, "/ports/port/(wire|transactional)", kind="enum"),
            "match": _cell(_boolean(_text(port, "match")), "/ports/port/match", kind="boolean", default=False),
            "qualifier": _cell(_qualifier(_child(node, "qualifier") if node is not None else None), "/ports/port/*/qualifier"),
            "initiator": _cell(format_mode(_child(node, "onInitiator") if node is not None else None), "/ports/port/*/onInitiator"),
            "target": _cell(format_mode(_child(node, "onTarget") if node is not None else None), "/ports/port/*/onTarget"),
            "system": _cell(
                ", ".join(filter(None, (format_mode(child) for child in _children(node, "onSystem"))))
                if node is not None
                else "",
                "/ports/port/*/onSystem",
            ),
            "description": _cell(_text(port, "description"), "/ports/port/description", kind="multiline"),
        })
    return [
        *_configuration_tables(root, prefix),
        _table(
            f"{prefix}-ports",
            "abstraction_ports",
            "Logical ports",
            _columns(
                ("name", "Logical name", "/ports/port/logicalName"),
                ("style", "Style", "/ports/port/(wire|transactional)"),
                ("match", "Match", "/ports/port/match"),
                ("qualifier", "Qualifier", "/ports/port/*/qualifier"),
                ("initiator", "On initiator", "/ports/port/*/onInitiator"),
                ("target", "On target", "/ports/port/*/onTarget"),
                ("system", "On system", "/ports/port/*/onSystem"),
                ("description", "Description", "/ports/port/description"),
            ),
            rows,
        ),
    ]


def _split_narrative(blocks: list[NarrativeBlock]) -> tuple[list[NarrativeBlock], dict[str, list[NarrativeBlock]], list[NarrativeBlock]]:
    attached: dict[str, list[NarrativeBlock]] = {}
    cross_cutting: list[NarrativeBlock] = []

    def visit(block: NarrativeBlock) -> NarrativeBlock | None:
        if block.entity_refs:
            copied = block.model_copy(deep=True)
            if len(block.entity_refs) == 1:
                attached.setdefault(block.entity_refs[0].entity_id, []).append(copied)
            else:
                cross_cutting.append(copied)
            return None
        remaining: list[NarrativeBlock] = []
        for child in block.children:
            candidate = visit(child)
            if candidate is not None:
                remaining.append(candidate)
        if block.children and not remaining and block.type in {"section", "list"}:
            return None
        return block.model_copy(update={"children": remaining}, deep=True)

    overview = [candidate for block in blocks if (candidate := visit(block)) is not None]
    return overview, attached, cross_cutting


_TOPOLOGY_RENDERER_ID = "design.topology"
_DERIVED_TOPOLOGY_OPTION_KEYS = frozenset({
    "schema_version",
    "status",
    "circuit_document",
    "omitted_bus_items",
    "omitted_ports",
    "message",
})


def _topology_live_views(
    revision: SpecRevision,
    owner: EntityRef,
    blocks: list[NarrativeBlock],
    *,
    synthesize: bool,
) -> list[NarrativeBlock]:
    """Attach revision-derived circuit payloads without mutating package narrative."""
    result = [block.model_copy(deep=True) for block in blocks]
    topology_indexes = [
        index for index, block in enumerate(result)
        if block.type == "live_view" and block.renderer_id == _TOPOLOGY_RENDERER_ID
    ]
    if synthesize and not topology_indexes:
        used_ids = {block.block_id for block in result}
        block_id = f"derived_topology_{_slug(owner.entity_id)}"
        suffix = 2
        while block_id in used_ids:
            block_id = f"derived_topology_{_slug(owner.entity_id)}_{suffix}"
            suffix += 1
        result.append(NarrativeBlock(
            block_id=block_id,
            type="live_view",
            text="Circuit topology",
            renderer_id=_TOPOLOGY_RENDERER_ID,
            entity_refs=[owner],
        ))
        topology_indexes.append(len(result) - 1)
    if not topology_indexes:
        return result

    try:
        projection = project_source_to_circuit(
            revision,
            typing.cast(typing.Literal["component", "design"], owner.entity_kind),
            owner.entity_id,
        )
        design = typing.cast(dict[str, typing.Any], projection.document.get("design", {}))
        empty = not design.get("instances") and not design.get("nets") and not design.get("boundary_terminals")
        derived_options: dict[str, typing.Any] = {
            "schema_version": 1,
            "status": "empty" if empty else "ready",
            "omitted_bus_items": list(projection.omitted_bus_items),
            "omitted_ports": list(projection.omitted_ports),
        }
        if not empty:
            derived_options["circuit_document"] = projection.document
    except (CircuitAdapterError, KeyError, TypeError, ValueError) as exc:
        derived_options = {
            "schema_version": 1,
            "status": "unavailable",
            "omitted_bus_items": [],
            "omitted_ports": [],
            "message": str(exc),
        }

    for index in topology_indexes:
        block = result[index]
        authored_options = {
            key: value for key, value in block.options.items()
            if key not in _DERIVED_TOPOLOGY_OPTION_KEYS
        }
        result[index] = block.model_copy(update={"options": {**authored_options, **derived_options}}, deep=True)
    return result


def _editor_sections(sections: list[DocumentSection]) -> list[DocumentSection]:
    """Hide source-supported bus/protocol details from the focused editor UI."""
    visible: list[DocumentSection] = []
    for section in sections:
        if section.section_id == "protocols":
            continue
        if section.entity_ref and section.entity_ref.entity_kind in _EDITOR_HIDDEN_ENTITY_KINDS:
            continue
        visible.append(section.model_copy(update={
            "tables": [
                table for table in section.tables
                if table.kind not in _EDITOR_HIDDEN_TABLE_KINDS
            ],
        }))
    return visible


def _content_sections(
    revision: SpecRevision,
    owner: EntityRef,
    root: etree._Element,
    *,
    port_count: int | None = None,
) -> tuple[list[EntityContentSection], list[AvailableSectionType]]:
    """Project adapter-backed and persisted content in registry order."""
    values = [
        EntityContentSection(
            section_id=f"section_text_{owner.entity_id}",
            section_type="text",
            type_version=1,
            title=SECTION_TYPES["text"].title,
            owner=owner,
            payload={"content": _text(root, "description")},
            editable=True,
            deletable=False,
            validation_status="verified",
        )
    ]
    if port_count is not None:
        values.append(EntityContentSection(
            section_id=f"section_ports_{owner.entity_id}",
            section_type="ports",
            type_version=1,
            title=SECTION_TYPES["ports"].title,
            owner=owner,
            payload={"count": port_count},
            editable=True,
            deletable=False,
            validation_status="verified",
        ))
    persisted = revision.entity_sections_for(owner)
    validation = {
        item.section_id: item for item in validate_revision_sections(
            revision, {item.section_id for item in persisted}
        )
    }
    values.extend(EntityContentSection(
        section_id=item.section_id,
        section_type=item.section_type,
        type_version=item.type_version,
        title=item.title,
        owner=item.owner,
        payload={"content": item.content, "media_type": item.media_type, "source_path": item.source_path},
        editable=SECTION_TYPES[item.section_type].editable,
        deletable=SECTION_TYPES[item.section_type].deletable,
        validation_status=typing.cast(typing.Any, validation[item.section_id].status) if item.section_id in validation else "unverified",
        diagnostics=[SectionDiagnostic(**diagnostic.as_json()) for diagnostic in validation[item.section_id].diagnostics]
        if item.section_id in validation else [],
    ) for item in persisted)
    values.sort(key=lambda item: SECTION_TYPES[item.section_type].order)
    present = {item.section_type for item in values}
    available = [AvailableSectionType(
        section_type=definition.section_type,
        type_version=definition.version,
        title=definition.title,
    ) for definition in SECTION_TYPES.values()
        if definition.persisted and owner.entity_kind in definition.entity_kinds
        and definition.section_type not in present]
    available.sort(key=lambda item: SECTION_TYPES[item.section_type].order)
    return values, available


def build_document_projection(revision: SpecRevision) -> DocumentProjection:
    """Build the deterministic unified document from one validated revision."""
    roots = _document_roots(revision)
    def named_block(block: NarrativeBlock) -> dict[str, typing.Any]:
        value = block.model_dump(mode="json")
        refs = [*block.entity_refs, *(inline.entity_ref for inline in block.inlines if inline.entity_ref)]
        labels = {}
        for ref in refs:
            try:
                labels[f"{ref.entity_kind}:{ref.entity_id}"] = {
                    "name": reference_name(revision, ref),
                    "qualified_name": qualified_reference_name(revision, ref),
                    "anchor": _anchor(ref.entity_kind.replace("_", "-"), ref.entity_id),
                }
            except KeyError:
                labels[f"{ref.entity_kind}:{ref.entity_id}"] = {"name": "Unavailable reference", "anchor": ""}
        value["entity_labels"] = labels
        value["children"] = [named_block(child) for child in block.children]
        if block.type == "live_view":
            value["options"] = {**value["options"], "document_name": document_name(revision)}
        return value
    overview_narrative, attached, cross_cutting = _split_narrative(revision.narrative.blocks)
    sections: list[DocumentSection] = []

    sections.append(DocumentSection(
        section_id="overview",
        title="Overview",
        level=1,
        eyebrow="Unified source document",
        narrative=[named_block(block) for block in overview_narrative],
    ))

    sections.append(DocumentSection(section_id="designs", title="Designs", level=1, eyebrow="IP-XACT hierarchy"))
    entry_ids = [design.ref.entity_id for design in revision.entry_designs()]
    design_by_id = {design.ref.entity_id: design for design in revision.designs}
    anchors_by_vlnv = {
        entity.vlnv: _anchor(entity.ref.entity_kind, entity.ref.entity_id)
        for entity in (
            *revision.components,
            *revision.designs,
            *revision.bus_definitions,
            *revision.abstraction_definitions,
        )
    }
    ordered_designs = [
        *(design_by_id[entity_id] for entity_id in entry_ids),
        *(design for design in revision.designs if design.ref.entity_id not in set(entry_ids)),
    ]
    for design in ordered_designs:
        root = roots[design.ref.entity_id]
        content_sections, available_section_types = _content_sections(revision, design.ref, root)
        narrative = _topology_live_views(
            revision,
            design.ref,
            attached.pop(design.ref.entity_id, []),
            synthesize=True,
        )
        sections.append(DocumentSection(
            section_id=_anchor("design", design.ref.entity_id),
            title=entity_name(design),
            level=2,
            eyebrow="Entry design" if design.ref.entity_id in entry_ids else "Design",
            entity_ref=design.ref,
            facts=_identity_facts(root, design.vlnv),
            tables=_design_tables(design, root, anchors_by_vlnv),
            narrative=[named_block(block) for block in narrative],
            content_sections=content_sections,
            available_section_types=available_section_types,
        ))

    sections.append(DocumentSection(section_id="components", title="Components", level=1, eyebrow="Reusable hardware"))
    composition = {mapping.component.entity_id: mapping.internal_design.entity_id for mapping in revision.manifest.component_compositions}
    for component in revision.components:
        root = roots[component.ref.entity_id]
        content_sections, available_section_types = _content_sections(
            revision, component.ref, root, port_count=len(component.ports)
        )
        facts = _identity_facts(root, component.vlnv)
        if component.ref.entity_id in composition:
            design_id = composition[component.ref.entity_id]
            design = design_by_id[design_id]
            facts.append(DocumentFact(
                label="Internal design",
                value=design.vlnv,
                display_text=entity_name(design),
                reference_anchor=_anchor("design", design_id),
            ))
        narrative = _topology_live_views(
            revision,
            component.ref,
            attached.pop(component.ref.entity_id, []),
            synthesize=False,
        )
        sections.append(DocumentSection(
            section_id=_anchor("component", component.ref.entity_id),
            title=entity_name(component),
            level=2,
            eyebrow="Composite component" if component.ref.entity_id in composition else "Component",
            entity_ref=component.ref,
            facts=facts,
            tables=_component_tables(component, root, anchors_by_vlnv),
            narrative=[named_block(block) for block in narrative],
            content_sections=content_sections,
            available_section_types=available_section_types,
        ))

    sections.append(DocumentSection(section_id="protocols", title="Protocols", level=1, eyebrow="Bus and abstraction definitions"))
    for bus in revision.bus_definitions:
        root = roots[bus.ref.entity_id]
        sections.append(DocumentSection(
            section_id=_anchor("bus-definition", bus.ref.entity_id),
            title=entity_name(bus),
            level=2,
            eyebrow="Bus definition",
            entity_ref=bus.ref,
            facts=_identity_facts(root, bus.vlnv),
            tables=_bus_tables(bus, root, anchors_by_vlnv),
            narrative=[named_block(block) for block in attached.pop(bus.ref.entity_id, [])],
        ))
    for abstraction in revision.abstraction_definitions:
        root = roots[abstraction.ref.entity_id]
        facts = _identity_facts(root, abstraction.vlnv)
        facts.append(DocumentFact(
            label="Bus type",
            value=abstraction.bus_vlnv,
            schema_path="/busType",
            reference_anchor=anchors_by_vlnv.get(abstraction.bus_vlnv, ""),
        ))
        sections.append(DocumentSection(
            section_id=_anchor("abstraction-definition", abstraction.ref.entity_id),
            title=entity_name(abstraction),
            level=2,
            eyebrow="Abstraction definition",
            entity_ref=abstraction.ref,
            facts=facts,
            tables=_abstraction_tables(abstraction, root),
            narrative=[named_block(block) for block in attached.pop(abstraction.ref.entity_id, [])],
        ))

    for remaining in attached.values():
        cross_cutting.extend(remaining)
    if cross_cutting:
        sections.append(DocumentSection(
            section_id="cross-cutting-notes",
            title="Cross-cutting Notes",
            level=1,
            eyebrow="Multi-entity narrative",
            narrative=[named_block(block) for block in cross_cutting],
        ))

    names_by_vlnv = {item.vlnv: entity_name(item) for item in (*revision.components, *revision.designs, *revision.bus_definitions, *revision.abstraction_definitions)}
    for section in sections:
        section.qualified_name = qualified_reference_name(revision, section.entity_ref) if section.entity_ref else f"{document_name(revision)} › {section.title}"
        for fact in section.facts:
            if fact.reference_anchor:
                fact.display_text = names_by_vlnv.get(fact.value, "Unavailable reference")
        for table in section.tables:
            for row in table.rows:
                for cell in row.cells.values():
                    if cell.kind == "reference" and cell.reference_anchor:
                        cell.display_text = names_by_vlnv.get(str(cell.value), "Unavailable reference")
    sections = _editor_sections(sections)

    return DocumentProjection(
        document_id=revision.document_id,
        source_revision_hash=revision.source_revision_hash,
        title=document_name(revision),
        summary=f"{len(revision.components)} components · {len(revision.designs)} designs",
        toc=[TocEntry(section_id=section.section_id, title=section.title, level=section.level) for section in sections],
        sections=sections,
    )


def build_a2ui_batch(projection: DocumentProjection) -> A2UIDocumentBatch:
    """Compile a projection into a stable A2UI v0.9 adjacency-list surface."""
    surface_id = f"spec-document-{_slug(projection.document_id)}"
    components: list[dict[str, typing.Any]] = []
    section_component_ids: list[str] = []
    for section in projection.sections:
        section_component_id = f"section-{_slug(section.section_id)}"
        section_component_ids.append(section_component_id)
        child_ids: list[str] = []
        indexed_narrative = list(enumerate(section.narrative))
        topology_narrative = [
            item for item in indexed_narrative
            if item[1].get("type") == "live_view" and item[1].get("renderer_id") == _TOPOLOGY_RENDERER_ID
        ]
        remaining_narrative = [item for item in indexed_narrative if item not in topology_narrative]

        def append_narrative(index: int, block: dict[str, typing.Any]) -> None:
            component_id = f"narrative-{_slug(section.section_id)}-{index}"
            child_ids.append(component_id)
            component = {
                "entity_link": "EntityLink",
                "live_view": "LiveView",
            }.get(str(block.get("type")), "NarrativeBlock")
            components.append({
                "id": component_id,
                "component": component,
                "block": copy.deepcopy(block),
                "documentId": projection.document_id,
            })

        for index, block in topology_narrative:
            append_narrative(index, block)
        for table in section.tables:
            component_id = f"table-{_slug(table.table_id)}"
            child_ids.append(component_id)
            components.append({
                "id": component_id,
                "component": "SpecTable",
                "table": table.model_dump(mode="json"),
            })
        for index, block in remaining_narrative:
            append_narrative(index, block)
        for content_section in section.content_sections:
            if content_section.section_type != "sv":
                continue
            component_id = f"entity-section-{_slug(content_section.section_id)}"
            child_ids.append(component_id)
            components.append({
                "id": component_id,
                "component": "SpecEntitySection",
                "section": content_section.model_dump(mode="json"),
            })
        components.append({
            "id": section_component_id,
            "component": "SpecSection",
            "section": section.model_copy(update={"tables": [], "narrative": [], "content_sections": []}).model_dump(mode="json"),
            "children": child_ids,
        })
    components.append({
        # A2UI v0.9 renderers resolve the surface entry component by this ID.
        "id": "root",
        "component": "SpecDocument",
        "title": projection.title,
        "summary": projection.summary,
        "documentId": projection.document_id,
        "sourceRevisionHash": projection.source_revision_hash,
        "toc": [entry.model_dump(mode="json") for entry in projection.toc],
        "children": section_component_ids,
    })
    messages = [
        {
            "version": A2UI_PROTOCOL_VERSION,
            "createSurface": {"surfaceId": surface_id, "catalogId": A2UI_CATALOG_ID},
        },
        {
            "version": A2UI_PROTOCOL_VERSION,
            "updateComponents": {"surfaceId": surface_id, "components": components},
        },
        {
            "version": A2UI_PROTOCOL_VERSION,
            "updateDataModel": {
                "surfaceId": surface_id,
                "path": "/",
                "value": {
                    "documentId": projection.document_id,
                    "sourceRevisionHash": projection.source_revision_hash,
                    "schemaVersion": projection.schema_version,
                },
            },
        },
    ]
    return A2UIDocumentBatch(
        surface_id=surface_id,
        source_revision_hash=projection.source_revision_hash,
        messages=messages,
    )

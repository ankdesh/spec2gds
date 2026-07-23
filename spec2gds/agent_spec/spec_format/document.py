"""Renderer-neutral unified document projection and A2UI v0.9 messages.

The source of truth remains :class:`SpecRevision`.  This module only derives a
human-oriented, deterministic presentation contract from the validated IP-XACT
and narrative sources.  Browser renderers never receive XML nodes.
"""

from __future__ import annotations

import copy
import re
import typing

import lxml.etree as etree
import pydantic

from spec2gds.agent_spec.spec_format import ipxact
from spec2gds.agent_spec.spec_format.ir import (
    AbstractionDefinitionIR,
    BusDefinitionIR,
    ComponentIR,
    DesignIR,
    SpecRevision,
)
from spec2gds.agent_spec.spec_format.models import EntityRef, NarrativeBlock


A2UI_PROTOCOL_VERSION = "v0.9"
A2UI_CATALOG_ID = "urn:spec2gds:a2ui:document:v1"
DOCUMENT_SCHEMA_VERSION = "spec2gds.document.v1"

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


class DocumentSection(pydantic.BaseModel):
    """One ordered heading in the generated document."""

    model_config = pydantic.ConfigDict(extra="forbid")

    section_id: str
    title: str
    level: int
    eyebrow: str = ""
    entity_ref: EntityRef | None = None
    facts: list[DocumentFact] = pydantic.Field(default_factory=list)
    tables: list[DocumentTable] = pydantic.Field(default_factory=list)
    narrative: list[dict[str, typing.Any]] = pydantic.Field(default_factory=list)


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


def _table(table_id: str, kind: str, title: str, columns: list[DocumentColumn], rows: list[dict[str, DocumentCell]]) -> DocumentTable:
    return DocumentTable(
        table_id=table_id,
        kind=kind,
        title=title,
        columns=columns,
        rows=[DocumentRow(row_id=f"{table_id}-row-{index}", cells=row) for index, row in enumerate(rows)],
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
    tables: list[DocumentTable] = []
    parameters: list[dict[str, DocumentCell]] = []
    for parameter in _descendants(root, "parameters/parameter"):
        value = _child(parameter, "value")
        parameters.append({
            "name": _cell(_text(parameter, "name"), "/parameters/parameter/name"),
            "value": _cell(_text(value), "/parameters/parameter/value", kind="expression"),
            "resolve": _cell(value.get("resolve", "") if value is not None else "", "/parameters/parameter/value/@resolve", kind="enum"),
            "type": _cell(value.get("dataType", "") if value is not None else "", "/parameters/parameter/value/@dataType", kind="enum"),
            "choice": _cell(value.get("choiceRef", "") if value is not None else "", "/parameters/parameter/value/@choiceRef", kind="reference"),
            "minimum": _cell(value.get("minimum", "") if value is not None else "", "/parameters/parameter/value/@minimum", kind="expression"),
            "maximum": _cell(value.get("maximum", "") if value is not None else "", "/parameters/parameter/value/@maximum", kind="expression"),
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
                ("resolve", "Resolve", "/parameters/parameter/value/@resolve"),
                ("type", "Type", "/parameters/parameter/value/@dataType"),
                ("choice", "Choice", "/parameters/parameter/value/@choiceRef"),
                ("minimum", "Minimum", "/parameters/parameter/value/@minimum"),
                ("maximum", "Maximum", "/parameters/parameter/value/@maximum"),
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
    prefix = _anchor("component", component.ref.entity_id)
    tables = _configuration_tables(root, prefix)
    port_rows: list[dict[str, DocumentCell]] = []
    for port in _descendants(root, "model/ports/port"):
        wire = _child(port, "wire")
        transactional = _child(port, "transactional")
        style = "wire" if wire is not None else "transactional"
        style_node = wire if wire is not None else transactional
        vectors = _child(style_node, "vectors") if style_node is not None else None
        vector = _child(vectors, "vector") if vectors is not None else None
        port_rows.append({
            "name": _cell(_text(port, "name"), "/model/ports/port/name"),
            "style": _cell(style, "/model/ports/port/(wire|transactional)", kind="enum"),
            "direction": _cell(_text(style_node, "direction") or _text(style_node, "initiative"), "/model/ports/port/(wire/direction|transactional/initiative)", kind="enum"),
            "left": _cell(_text(vector, "left"), "/model/ports/port/wire/vectors/vector/left", kind="expression"),
            "right": _cell(_text(vector, "right"), "/model/ports/port/wire/vectors/vector/right", kind="expression"),
            "width": _cell(_text(style_node, "busWidth"), "/model/ports/port/transactional/busWidth", kind="expression"),
            "qualifier": _cell(_qualifier(_child(style_node, "qualifier") if style_node is not None else None), "/model/ports/port/*/qualifier"),
            "description": _cell(_text(port, "description"), "/model/ports/port/description", kind="multiline"),
        })
    tables.append(_table(
        f"{prefix}-ports",
        "component_ports",
        "Ports",
        _columns(
            ("name", "Name", "/model/ports/port/name"),
            ("style", "Style", "/model/ports/port/(wire|transactional)"),
            ("direction", "Direction / initiative", "/model/ports/port/*/(direction|initiative)"),
            ("left", "Left", "/model/ports/port/wire/vectors/vector/left"),
            ("right", "Right", "/model/ports/port/wire/vectors/vector/right"),
            ("width", "Bus width", "/model/ports/port/transactional/busWidth"),
            ("qualifier", "Qualifier", "/model/ports/port/*/qualifier"),
            ("description", "Description", "/model/ports/port/description"),
        ),
        port_rows,
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
            ("component", "Component VLNV", "/componentInstances/componentInstance/componentRef"),
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
                "external": _cell(", ".join(connection.external_ports), "/adHocConnections/adHocConnection/portReferences/externalPortReference", kind="reference"),
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


def build_document_projection(revision: SpecRevision) -> DocumentProjection:
    """Build the deterministic unified document from one validated revision."""
    roots = _document_roots(revision)
    overview_narrative, attached, cross_cutting = _split_narrative(revision.narrative.blocks)
    sections: list[DocumentSection] = []

    sections.append(DocumentSection(
        section_id="overview",
        title="Overview",
        level=1,
        eyebrow="Unified source document",
        facts=[
            DocumentFact(label="Document ID", value=revision.document_id),
            DocumentFact(label="Source revision", value=revision.source_revision_hash),
            DocumentFact(label="Components", value=str(len(revision.components))),
            DocumentFact(label="Designs", value=str(len(revision.designs))),
            DocumentFact(label="Entry designs", value=str(len(revision.entry_designs()))),
        ],
        narrative=[block.model_dump(mode="json") for block in overview_narrative],
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
        sections.append(DocumentSection(
            section_id=_anchor("design", design.ref.entity_id),
            title=design.vlnv.split(":")[-2],
            level=2,
            eyebrow="Entry design" if design.ref.entity_id in entry_ids else "Design",
            entity_ref=design.ref,
            facts=_identity_facts(root, design.vlnv),
            tables=_design_tables(design, root, anchors_by_vlnv),
            narrative=[block.model_dump(mode="json") for block in attached.pop(design.ref.entity_id, [])],
        ))

    sections.append(DocumentSection(section_id="components", title="Components", level=1, eyebrow="Reusable hardware"))
    composition = {mapping.component.entity_id: mapping.internal_design.entity_id for mapping in revision.manifest.component_compositions}
    for component in revision.components:
        root = roots[component.ref.entity_id]
        facts = _identity_facts(root, component.vlnv)
        if component.ref.entity_id in composition:
            design_id = composition[component.ref.entity_id]
            design = design_by_id[design_id]
            facts.append(DocumentFact(
                label="Internal design",
                value=design.vlnv,
                reference_anchor=_anchor("design", design_id),
            ))
        sections.append(DocumentSection(
            section_id=_anchor("component", component.ref.entity_id),
            title=component.vlnv.split(":")[-2],
            level=2,
            eyebrow="Composite component" if component.ref.entity_id in composition else "Component",
            entity_ref=component.ref,
            facts=facts,
            tables=_component_tables(component, root, anchors_by_vlnv),
            narrative=[block.model_dump(mode="json") for block in attached.pop(component.ref.entity_id, [])],
        ))

    sections.append(DocumentSection(section_id="protocols", title="Protocols", level=1, eyebrow="Bus and abstraction definitions"))
    for bus in revision.bus_definitions:
        root = roots[bus.ref.entity_id]
        sections.append(DocumentSection(
            section_id=_anchor("bus-definition", bus.ref.entity_id),
            title=bus.vlnv.split(":")[-2],
            level=2,
            eyebrow="Bus definition",
            entity_ref=bus.ref,
            facts=_identity_facts(root, bus.vlnv),
            tables=_bus_tables(bus, root, anchors_by_vlnv),
            narrative=[block.model_dump(mode="json") for block in attached.pop(bus.ref.entity_id, [])],
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
            title=abstraction.vlnv.split(":")[-2],
            level=2,
            eyebrow="Abstraction definition",
            entity_ref=abstraction.ref,
            facts=facts,
            tables=_abstraction_tables(abstraction, root),
            narrative=[block.model_dump(mode="json") for block in attached.pop(abstraction.ref.entity_id, [])],
        ))

    for remaining in attached.values():
        cross_cutting.extend(remaining)
    if cross_cutting:
        sections.append(DocumentSection(
            section_id="cross-cutting-notes",
            title="Cross-cutting Notes",
            level=1,
            eyebrow="Multi-entity narrative",
            narrative=[block.model_dump(mode="json") for block in cross_cutting],
        ))

    return DocumentProjection(
        document_id=revision.document_id,
        source_revision_hash=revision.source_revision_hash,
        title=revision.document_id.replace("_", " ").title(),
        summary=f"{len(revision.components)} components · {len(revision.designs)} designs · {len(revision.bus_definitions) + len(revision.abstraction_definitions)} protocol definitions",
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
        for table in section.tables:
            component_id = f"table-{_slug(table.table_id)}"
            child_ids.append(component_id)
            components.append({
                "id": component_id,
                "component": "SpecTable",
                "table": table.model_dump(mode="json"),
            })
        for index, block in enumerate(section.narrative):
            component_id = f"narrative-{_slug(section.section_id)}-{index}"
            child_ids.append(component_id)
            component = {
                "entity_link": "EntityLink",
                "live_view": "LiveView",
            }.get(str(block.get("type")), "NarrativeBlock")
            components.append({"id": component_id, "component": component, "block": copy.deepcopy(block)})
        components.append({
            "id": section_component_id,
            "component": "SpecSection",
            "section": section.model_copy(update={"tables": [], "narrative": []}).model_dump(mode="json"),
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

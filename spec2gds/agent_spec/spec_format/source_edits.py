"""Shared, typed mutations for profiled IP-XACT source documents.

These helpers operate on private transaction copies.  They deliberately know
nothing about HTTP clients, browser state, or assistant proposals so every
source-writing surface can share the same XML construction and validation.
"""

from __future__ import annotations

import typing

import lxml.etree as etree

from spec2gds.agent_spec.spec_format import ipxact
from spec2gds.agent_spec.spec_format.models import ID_PATTERN

_COMPONENT_ORDER = [
    "vendor",
    "library",
    "name",
    "version",
    "displayName",
    "shortDescription",
    "description",
    "busInterfaces",
    "channels",
    "model",
    "choices",
    "parameters",
    "assertions",
]


def set_entity_metadata(
    root: etree._Element,
    *,
    display_name: str | None,
    short_description: str | None,
    description: str | None,
) -> None:
    """Replace the three optional descriptive fields on one IP-XACT root."""
    order = _root_order(root)
    for name, value in (
        ("displayName", display_name),
        ("shortDescription", short_description),
        ("description", description),
    ):
        _set_optional(root, name, value, order)


_PORT_FIELDS = {
    "name",
    "family",
    "display_name",
    "description",
    "direction",
    "range",
    "initiative",
    "kind",
    "custom_kind",
    "bus_width",
}
_PORT_FAMILIES = {"wire", "transactional", "structured"}
_DIRECTIONS = {"in", "out", "inout"}
_INITIATIVES = {"requires", "provides", "both"}
_TRANSACTION_KINDS = {"tlm_port", "tlm_socket", "simple_socket", "multi_socket", "custom"}


def upsert_component_port(root: etree._Element, value: dict[str, typing.Any]) -> None:
    """Insert or replace a strictly typed editor-profiled component port."""
    normalized = _normalize_component_port(value, require_name=True)
    model = _ensure_ordered(root, "model", _COMPONENT_ORDER)
    ports = _child(model, "ports")
    if ports is None:
        ports = etree.SubElement(model, _q("ports"))
    existing = _named(ports, "port", "name", normalized["name"])
    if existing is not None and _port_family(existing) != normalized["family"]:
        raise ValueError("Port family cannot be changed by upsert_component_port.")
    node = _build_port(normalized)
    if existing is None:
        ports.append(node)
    else:
        ports.replace(existing, node)


def add_component_port(root: etree._Element, value: dict[str, typing.Any]) -> None:
    """Append a new editor-profiled component port without replacing one."""
    normalized = _normalize_component_port(value, require_name=True)
    model = _ensure_ordered(root, "model", _COMPONENT_ORDER)
    ports = _child(model, "ports")
    if ports is None:
        ports = etree.SubElement(model, _q("ports"))
    if _named(ports, "port", "name", normalized["name"]) is not None:
        raise ValueError(f"Component already has a port named {normalized['name']}.")
    ports.append(_build_port(normalized))


def update_component_port(root: etree._Element, *, name: str, value: dict[str, typing.Any]) -> None:
    """Replace editable fields while preserving a port's name, family, and order."""
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Port name is required.")
    normalized = _normalize_component_port({**value, "name": normalized_name}, require_name=True)
    model = _child(root, "model")
    ports = _child(model, "ports") if model is not None else None
    existing = _named(ports, "port", "name", normalized_name) if ports is not None else None
    if existing is None or ports is None:
        raise KeyError(f"Unknown component port: {normalized_name}")
    existing_family = _port_family(existing)
    if existing_family != normalized["family"]:
        raise ValueError("Port family cannot be changed by update_component_port.")
    index = list(ports).index(existing)
    ports.remove(existing)
    ports.insert(index, _build_port(normalized))


def _normalize_component_port(
    value: dict[str, typing.Any],
    *,
    require_name: bool,
) -> dict[str, typing.Any]:
    _reject_unknown_keys(value, _PORT_FIELDS, "component port")
    name = str(value.get("name", "")).strip()
    if require_name and not name:
        raise ValueError("Port name is required.")
    if name and not ID_PATTERN.fullmatch(name):
        raise ValueError("Port name must be an XML-compatible identifier.")
    family = str(value.get("family", "")).strip()
    if family not in _PORT_FAMILIES:
        raise ValueError("Port family must be wire, transactional, or structured.")
    normalized: dict[str, typing.Any] = {
        "name": name,
        "family": family,
        "display_name": _optional_text(value.get("display_name")),
        "description": _optional_text(value.get("description")),
    }
    if family == "wire":
        direction = str(value.get("direction", "")).strip()
        if direction not in _DIRECTIONS:
            raise ValueError("Wire port direction must be in, out, or inout.")
        left, right = parse_wire_range(value.get("range"))
        normalized.update(direction=direction, left=left, right=right)
    elif family == "transactional":
        initiative = str(value.get("initiative", "")).strip()
        if initiative not in _INITIATIVES:
            raise ValueError("Transactional port initiative must be requires, provides, or both.")
        kind = _optional_text(value.get("kind"))
        custom_kind = _optional_text(value.get("custom_kind"))
        if kind is not None and kind not in _TRANSACTION_KINDS:
            raise ValueError("Unknown transactional port kind.")
        if kind == "custom" and custom_kind is None:
            raise ValueError("Custom transactional ports require a custom kind name.")
        if kind != "custom" and custom_kind is not None:
            raise ValueError("Custom kind name is only valid when transactional kind is custom.")
        normalized.update(
            initiative=initiative,
            kind=kind,
            custom_kind=custom_kind,
            bus_width=_optional_text(value.get("bus_width")),
        )
    else:
        direction = str(value.get("direction", "")).strip()
        if direction not in _DIRECTIONS:
            raise ValueError("Structured port direction must be in, out, or inout.")
        normalized.update(direction=direction)
    return normalized


def parse_wire_range(value: typing.Any) -> tuple[str | None, str | None]:
    """Split the editor's compact range syntax into IP-XACT bounds."""
    expression = "" if value is None else str(value).strip()
    if not expression:
        return None, None
    if expression.startswith("[") and expression.endswith("]"):
        expression = expression[1:-1].strip()
        if not expression:
            raise ValueError("Wire port Range cannot be empty.")
    if expression.count(":") > 1:
        raise ValueError("Wire port Range must contain at most one colon.")
    if ":" not in expression:
        return expression, expression
    left, right = (item.strip() for item in expression.split(":", 1))
    if not left or not right:
        raise ValueError("Wire port Range requires expressions on both sides of the colon.")
    return left, right


def format_wire_range(left: str | None, right: str | None) -> str:
    """Return the compact editor display for one optional IP-XACT vector."""
    if left is None or right is None:
        return ""
    return left if left == right else f"{left}:{right}"


def _build_port(value: dict[str, typing.Any]) -> etree._Element:
    name = typing.cast(str, value["name"])
    family = typing.cast(str, value["family"])
    port = etree.Element(_q("port"))
    etree.SubElement(port, _q("name")).text = name
    if value.get("display_name") is not None:
        etree.SubElement(port, _q("displayName")).text = typing.cast(str, value["display_name"])
    if value.get("description") is not None:
        etree.SubElement(port, _q("description")).text = typing.cast(str, value["description"])
    style_node = etree.SubElement(port, _q(family))
    if family == "wire":
        etree.SubElement(style_node, _q("direction")).text = typing.cast(str, value["direction"])
        left = value.get("left")
        right = value.get("right")
        if left is not None and right is not None:
            vectors = etree.SubElement(style_node, _q("vectors"))
            vector = etree.SubElement(vectors, _q("vector"))
            etree.SubElement(vector, _q("left")).text = str(left)
            etree.SubElement(vector, _q("right")).text = str(right)
    elif family == "transactional":
        etree.SubElement(style_node, _q("initiative")).text = typing.cast(str, value["initiative"])
        kind = value.get("kind")
        if kind is not None:
            kind_node = etree.SubElement(style_node, _q("kind"))
            kind_node.text = typing.cast(str, kind)
            if kind == "custom":
                kind_node.set("custom", typing.cast(str, value["custom_kind"]))
        if value.get("bus_width") is not None:
            etree.SubElement(style_node, _q("busWidth")).text = typing.cast(str, value["bus_width"])
    else:
        style_node.set("packed", "true")
        struct = etree.SubElement(style_node, _q("struct"))
        struct.set("direction", typing.cast(str, value["direction"]))
        type_defs = etree.SubElement(style_node, _q("structPortTypeDefs"))
        type_def = etree.SubElement(type_defs, _q("structPortTypeDef"))
        etree.SubElement(type_def, _q("typeName")).text = f"{name}_struct_t"
    return port


def _port_family(port: etree._Element) -> str:
    for family in ("wire", "transactional", "structured"):
        if _child(port, family) is not None:
            return family
    raise ValueError(f"Port {_text(port, 'name')} has no supported family.")


def _optional_text(value: typing.Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value)


def _root_order(root: etree._Element) -> list[str]:
    local = etree.QName(root).localname
    orders = {
        "component": _COMPONENT_ORDER,
        "design": [
            "vendor", "library", "name", "version", "displayName",
            "shortDescription", "description", "componentInstances",
            "interconnections", "adHocConnections", "choices", "parameters", "assertions",
        ],
        "busDefinition": [
            "vendor", "library", "name", "version", "displayName",
            "shortDescription", "description", "directConnection", "broadcast",
            "isAddressable", "extends", "maxInitiators", "maxTargets",
            "systemGroupNames", "choices", "parameters", "assertions",
        ],
        "abstractionDefinition": [
            "vendor", "library", "name", "version", "displayName",
            "shortDescription", "description", "busType", "extends", "ports",
            "choices", "parameters", "assertions",
        ],
    }
    try:
        return orders[local]
    except KeyError as exc:
        raise ValueError(f"Unsupported IP-XACT metadata target: {local}") from exc


def _set_optional(parent: etree._Element, name: str, value: typing.Any, order: list[str]) -> None:
    existing = _child(parent, name)
    if value is None or str(value).strip() == "":
        if existing is not None:
            parent.remove(existing)
        return
    node = existing or _ensure_ordered(parent, name, order)
    node.text = str(value)


def _ensure_ordered(parent: etree._Element, name: str, order: list[str]) -> etree._Element:
    existing = _child(parent, name)
    if existing is not None:
        return existing
    node = etree.Element(_q(name))
    position = order.index(name)
    for index, child in enumerate(parent):
        child_name = etree.QName(child).localname
        if child_name in order and order.index(child_name) > position:
            parent.insert(index, node)
            return node
    parent.append(node)
    return node


def _child(root: etree._Element | None, name: str) -> etree._Element | None:
    if root is None:
        return None
    return next((child for child in root if etree.QName(child).localname == name), None)


def _named(
    container: etree._Element | None,
    tag: str,
    field: str,
    value: str,
) -> etree._Element | None:
    if container is None:
        return None
    for child in container:
        if etree.QName(child).localname == tag and _text(child, field) == value:
            return child
    return None


def _text(root: etree._Element, name: str) -> str:
    child = _child(root, name)
    return (child.text or "").strip() if child is not None else ""


def _reject_unknown_keys(value: dict[str, typing.Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"Unknown {label} fields: {', '.join(unknown)}")


def _q(name: str) -> str:
    return f"{{{ipxact.IPXACT_NAMESPACE}}}{name}"

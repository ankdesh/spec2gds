"""Shared, typed mutations for profiled IP-XACT source documents.

These helpers operate on private transaction copies.  They deliberately know
nothing about HTTP clients, browser state, or assistant proposals so every
source-writing surface can share the same XML construction and validation.
"""

from __future__ import annotations

import typing

import lxml.etree as etree

from spec2gds.agent_spec.spec_format import ipxact


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


def upsert_component_port(root: etree._Element, value: dict[str, typing.Any]) -> None:
    """Insert or replace one profiled wire or transactional component port."""
    allowed = {"name", "style", "direction", "left", "right", "bus_width", "description"}
    _reject_unknown_keys(value, allowed, "component port")
    name = str(value.get("name", "")).strip()
    style = str(value.get("style", "wire"))
    direction = str(value.get("direction", "")).strip()
    if not name or style not in {"wire", "transactional"} or not direction:
        raise ValueError("Component port requires name, wire/transactional style, and direction/initiative.")

    model = _ensure_ordered(root, "model", _COMPONENT_ORDER)
    ports = _child(model, "ports")
    if ports is None:
        ports = etree.SubElement(model, _q("ports"))
    existing = _named(ports, "port", "name", name)
    if existing is not None:
        ports.remove(existing)
    ports.append(_build_port(value, name=name, style=style, direction=direction))


def add_component_wire_port(
    root: etree._Element,
    *,
    name: str,
    direction: str,
    left: str | None,
    right: str | None,
    description: str | None,
) -> None:
    """Add a new physical wire port without silently replacing an existing one."""
    normalized_name = name.strip()
    _validate_wire_port(normalized_name, direction, left, right)
    model = _ensure_ordered(root, "model", _COMPONENT_ORDER)
    ports = _child(model, "ports")
    if ports is None:
        ports = etree.SubElement(model, _q("ports"))
    if _named(ports, "port", "name", normalized_name) is not None:
        raise ValueError(f"Component already has a port named {normalized_name}.")
    ports.append(_build_port({
        "left": left,
        "right": right,
        "description": description,
    }, name=normalized_name, style="wire", direction=direction))


def update_component_wire_port(
    root: etree._Element,
    *,
    name: str,
    direction: str,
    left: str | None,
    right: str | None,
    description: str | None,
) -> None:
    """Replace editable properties of an existing wire port, preserving its name."""
    normalized_name = name.strip()
    _validate_wire_port(normalized_name, direction, left, right)
    model = _child(root, "model")
    ports = _child(model, "ports") if model is not None else None
    existing = _named(ports, "port", "name", normalized_name) if ports is not None else None
    if existing is None or ports is None:
        raise KeyError(f"Unknown component port: {normalized_name}")
    if _child(existing, "wire") is None:
        raise ValueError("Transactional component ports are read-only in the editor.")
    index = list(ports).index(existing)
    ports.remove(existing)
    ports.insert(index, _build_port({
        "left": left,
        "right": right,
        "description": description,
    }, name=normalized_name, style="wire", direction=direction))


def _validate_wire_port(name: str, direction: str, left: str | None, right: str | None) -> None:
    if not name:
        raise ValueError("Port name is required.")
    if direction not in {"in", "out", "inout"}:
        raise ValueError("Wire port direction must be in, out, or inout.")
    has_left = left is not None and str(left).strip() != ""
    has_right = right is not None and str(right).strip() != ""
    if has_left != has_right:
        raise ValueError("Vector ports require both left and right bounds.")


def _build_port(
    value: dict[str, typing.Any],
    *,
    name: str,
    style: str,
    direction: str,
) -> etree._Element:
    port = etree.Element(_q("port"))
    etree.SubElement(port, _q("name")).text = name
    description = value.get("description")
    if description is not None and str(description).strip():
        etree.SubElement(port, _q("description")).text = str(description)
    style_node = etree.SubElement(port, _q(style))
    etree.SubElement(style_node, _q("direction" if style == "wire" else "initiative")).text = direction
    left = value.get("left")
    right = value.get("right")
    if style == "wire" and left not in (None, "") and right not in (None, ""):
        vectors = etree.SubElement(style_node, _q("vectors"))
        vector = etree.SubElement(vectors, _q("vector"))
        etree.SubElement(vector, _q("left")).text = str(left)
        etree.SubElement(vector, _q("right")).text = str(right)
    if style == "transactional" and value.get("bus_width") not in (None, ""):
        etree.SubElement(style_node, _q("busWidth")).text = str(value["bus_width"])
    return port


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

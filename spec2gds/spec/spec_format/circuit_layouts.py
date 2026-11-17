"""Versioned, source-semantic Circuit Designer layout annotations."""

from __future__ import annotations

import json
import math
import typing

import pydantic
from lxml import etree

from spec2gds.spec.spec_format.models import AnnotationSchemaEntry, EntityRef, StrictModel

LAYOUT_NAMESPACE = "spec2gds.circuit-layout"
LAYOUT_ROOT = "annotations/circuit-layout"
LAYOUT_MAX_BYTES = 2 * 1024 * 1024


def _number(value: typing.Any, label: str, *, positive: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Circuit layout {label} must be a finite number.")
    if positive and value <= 0:
        raise ValueError(f"Circuit layout {label} must be positive.")


def _exact(value: typing.Any, required: set[str], optional: set[str], label: str) -> dict[str, typing.Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Circuit layout {label} must be an object.")
    keys = set(value)
    if not required.issubset(keys) or not keys.issubset(required | optional):
        raise ValueError(f"Circuit layout {label} has invalid fields.")
    return value


def _validate_semantic_terminal_key(value: str) -> None:
    if value.startswith("boundary:") and value.removeprefix("boundary:"):
        return
    if value.startswith("instance:") and "/port:" in value:
        instance, port = value.removeprefix("instance:").split("/port:", 1)
        if instance and port:
            return
    raise ValueError(f"Circuit layout terminal key is invalid: {value}")


def _validate_layout_shapes(layout: "DesignCircuitLayoutV1") -> None:
    """Reject malformed geometry and route metadata before package admission.

    This validates layout shapes, not electrical connectivity; semantic references
    are checked by the surrounding annotation/package validation.
    """
    for name, raw in layout.instance_geometry.items():
        value = _exact(raw, {"x", "y", "width", "height"}, {"pinned"}, f"instance geometry {name}")
        _number(value["x"], "x")
        _number(value["y"], "y")
        _number(value["width"], "width", positive=True)
        _number(value["height"], "height", positive=True)
        if "pinned" in value and not isinstance(value["pinned"], bool):
            raise ValueError("Circuit layout pinned must be boolean.")
    for key, raw in layout.terminal_placements.items():
        _validate_semantic_terminal_key(key)
        value = _exact(raw, {"side", "order"}, {"locked"}, f"terminal placement {key}")
        if value["side"] not in {"NORTH", "EAST", "SOUTH", "WEST"}:
            raise ValueError("Circuit layout terminal side is invalid.")
        if isinstance(value["order"], bool) or not isinstance(value["order"], int) or value["order"] < 0:
            raise ValueError("Circuit layout terminal order must be a non-negative integer.")
        if "locked" in value and not isinstance(value["locked"], bool):
            raise ValueError("Circuit layout placement locked must be boolean.")
    for key, raw in layout.label_geometry.items():
        value = _exact(raw, {"x", "y"}, {"anchor"}, f"label geometry {key}")
        _number(value["x"], "label x")
        _number(value["y"], "label y")
        if value.get("anchor", "middle") not in {"start", "middle", "end"}:
            raise ValueError("Circuit layout label anchor is invalid.")
    for net_name, raw in layout.net_routes.items():
        route = _exact(raw, {"vertices", "segments"}, set(), f"route {net_name}")
        if not isinstance(route["vertices"], list) or not isinstance(route["segments"], list):
            raise ValueError("Circuit layout route vertices and segments must be arrays.")
        vertex_ids: set[str] = set()
        for raw_vertex in route["vertices"]:
            vertex = _exact(raw_vertex, {"id", "kind", "point"}, {"terminal_id", "locked"}, "route vertex")
            if not isinstance(vertex["id"], str) or not vertex["id"] or vertex["id"] in vertex_ids:
                raise ValueError("Circuit layout route vertex IDs must be unique non-empty strings.")
            vertex_ids.add(vertex["id"])
            if vertex["kind"] not in {"endpoint", "bend", "junction"}:
                raise ValueError("Circuit layout route vertex kind is invalid.")
            point = _exact(vertex["point"], {"x", "y"}, set(), "route point")
            _number(point["x"], "route x")
            _number(point["y"], "route y")
            terminal_id = vertex.get("terminal_id")
            if terminal_id is not None:
                if not isinstance(terminal_id, str):
                    raise ValueError("Circuit layout route terminal reference must be a string or null.")
                _validate_semantic_terminal_key(terminal_id)
            if "locked" in vertex and not isinstance(vertex["locked"], bool):
                raise ValueError("Circuit layout route vertex locked must be boolean.")
        segment_ids: set[str] = set()
        for raw_segment in route["segments"]:
            segment = _exact(raw_segment, {"from_vertex", "to_vertex"}, {"id", "locked"}, "route segment")
            start, end = segment["from_vertex"], segment["to_vertex"]
            if not isinstance(start, str) or not isinstance(end, str) or start not in vertex_ids or end not in vertex_ids:
                raise ValueError("Circuit layout route segment references an unknown vertex.")
            if start == end:
                raise ValueError("Circuit layout route segment cannot connect a vertex to itself.")
            segment_id = segment.get("id")
            if segment_id is not None:
                if not isinstance(segment_id, str) or not segment_id or segment_id in segment_ids:
                    raise ValueError("Circuit layout route segment IDs must be unique non-empty strings.")
                segment_ids.add(segment_id)
            if "locked" in segment and not isinstance(segment["locked"], bool):
                raise ValueError("Circuit layout route segment locked must be boolean.")


class DesignCircuitLayoutV1(StrictModel):
    """Persisted layout keyed by source instance, port, and connection names."""

    schema_version: typing.Literal[1] = 1
    design: EntityRef
    grid_size: float = 20
    direction: typing.Literal["RIGHT", "DOWN"] = "RIGHT"
    instance_geometry: dict[str, dict[str, typing.Any]] = pydantic.Field(default_factory=dict)
    terminal_placements: dict[str, dict[str, typing.Any]] = pydantic.Field(default_factory=dict)
    net_routes: dict[str, dict[str, typing.Any]] = pydantic.Field(default_factory=dict)
    label_geometry: dict[str, dict[str, typing.Any]] = pydantic.Field(default_factory=dict)

    @pydantic.model_validator(mode="after")
    def validate_payload(self) -> "DesignCircuitLayoutV1":
        if self.design.entity_kind != "design":
            raise ValueError("Circuit layouts must be attached to a Design.")
        if not math.isfinite(self.grid_size) or self.grid_size <= 0:
            raise ValueError("Circuit layout grid_size must be finite and positive.")

        def finite(value: typing.Any) -> None:
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Circuit layout coordinates must be finite.")
            if isinstance(value, dict):
                for child in value.values():
                    finite(child)
            elif isinstance(value, list):
                for child in value:
                    finite(child)

        finite(self.model_dump(mode="python"))
        _validate_layout_shapes(self)
        encoded = json.dumps(self.model_dump(mode="json"), separators=(",", ":")).encode()
        if len(encoded) > LAYOUT_MAX_BYTES:
            raise ValueError("Circuit layout exceeds the 2 MiB limit.")
        return self


def layout_path(design_id: str) -> str:
    return f"{LAYOUT_ROOT}/{design_id}.json"


def load_design_layout(revision: typing.Any, design: EntityRef) -> DesignCircuitLayoutV1 | None:
    """Load one validated layout annotation, returning automatic-layout absence."""
    path = layout_path(design.entity_id)
    annotation = next((item for item in revision.annotations if item.path == path), None)
    if annotation is None:
        return None
    value = DesignCircuitLayoutV1.model_validate_json(annotation.data)
    if value.design != design:
        raise ValueError(f"Circuit layout {path} does not match its owning design.")
    return value


def upsert_design_layout(package: typing.Any, layout: DesignCircuitLayoutV1) -> None:
    """Write one canonical annotation and register its namespace atomically."""
    path = layout_path(layout.design.entity_id)
    data = (json.dumps(layout.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()
    if len(data) > LAYOUT_MAX_BYTES:
        raise ValueError("Circuit layout exceeds the 2 MiB limit.")
    package.files[path] = data
    schemas = [item for item in package.manifest.annotation_schemas if item.namespace != LAYOUT_NAMESPACE]
    schemas.append(AnnotationSchemaEntry(namespace=LAYOUT_NAMESPACE, version=1, path_prefix=LAYOUT_ROOT))
    package.manifest = package.manifest.model_copy(update={"annotation_schemas": schemas})


def delete_design_layout(package: typing.Any, design_id: str) -> None:
    """Remove one layout and unregister the namespace when the last layout is gone."""
    package.files.pop(layout_path(design_id), None)
    if not any(path.startswith(f"{LAYOUT_ROOT}/") for path in package.files):
        package.manifest = package.manifest.model_copy(update={
            "annotation_schemas": [
                item for item in package.manifest.annotation_schemas if item.namespace != LAYOUT_NAMESPACE
            ]
        })


def validate_layout_annotations(manifest: typing.Any, files: typing.Mapping[str, bytes]) -> None:
    """Validate registration, paths, ownership, and every stored layout payload."""
    registered = any(item.namespace == LAYOUT_NAMESPACE for item in manifest.annotation_schemas)
    paths = sorted(path for path in files if path.startswith(f"{LAYOUT_ROOT}/"))
    if paths and not registered:
        raise ValueError("Circuit layout files require the spec2gds.circuit-layout registration.")
    if registered and not paths:
        raise ValueError("Circuit layout registration has no layout files.")
    known_designs = {item.entity_id for item in manifest.documents if item.kind == "design"}
    component_ports: dict[str, set[str]] = {}
    for entry in (item for item in manifest.documents if item.kind == "component"):
        root = etree.fromstring(files[entry.path])
        component_ports[entry.vlnv] = {
            str(node.text or "").strip()
            for node in root.xpath("./*[local-name()='model']/*[local-name()='ports']/*[local-name()='port']/*[local-name()='name']")
        }
    owner_vlnv_by_design: dict[str, str] = {}
    for mapping in manifest.component_compositions:
        owner_entry = next(
            (entry for entry in manifest.documents
             if entry.kind == "component" and entry.entity_id == mapping.component.entity_id),
            None,
        )
        if owner_entry is None:
            raise ValueError(f"Circuit layout ownership references unknown component {mapping.component.entity_id}.")
        owner_vlnv_by_design[mapping.internal_design.entity_id] = owner_entry.vlnv
    for path in paths:
        if not path.endswith(".json"):
            raise ValueError(f"Unexpected circuit layout file: {path}")
        value = DesignCircuitLayoutV1.model_validate_json(files[path])
        if value.design.document_id != manifest.document_id or value.design.entity_id not in known_designs:
            raise ValueError(f"Circuit layout {path} references an unknown design.")
        if path != layout_path(value.design.entity_id):
            raise ValueError(f"Circuit layout {path} is not stored at its canonical path.")
        design_entry = next(
            entry for entry in manifest.documents
            if entry.kind == "design" and entry.entity_id == value.design.entity_id
        )
        design_root = etree.fromstring(files[design_entry.path])
        instances: dict[str, str] = {}
        for instance in design_root.xpath("./*[local-name()='componentInstances']/*[local-name()='componentInstance']"):
            name = str(instance.xpath("string(./*[local-name()='instanceName'])")).strip()
            component_ref = next(iter(instance.xpath("./*[local-name()='componentRef']")), None)
            if component_ref is not None:
                instances[name] = ":".join(component_ref.get(field, "") for field in ("vendor", "library", "name", "version"))
        net_names = {
            str(node.xpath("string(./*[local-name()='name'])")).strip()
            for node in design_root.xpath("./*[local-name()='adHocConnections']/*[local-name()='adHocConnection']")
        }
        terminal_keys = {
            f"instance:{instance_name}/port:{port_name}"
            for instance_name, vlnv in instances.items()
            for port_name in component_ports.get(vlnv, set())
        }
        from .design_interfaces import read_interface
        terminal_keys.update(
            f"boundary:{port_name}"
            for port_name in component_ports.get(owner_vlnv_by_design.get(value.design.entity_id, ""),
                                                {p.name for p in read_interface(files, value.design).ports})
        )
        unknown_geometry = set(value.instance_geometry) - set(instances)
        unknown_placements = set(value.terminal_placements) - terminal_keys
        unknown_routes = set(value.net_routes) - net_names
        allowed_labels = {
            *(f"instance:{name}" for name in instances),
            *(f"net:{name}" for name in net_names),
            *terminal_keys,
        }
        unknown_labels = set(value.label_geometry) - allowed_labels
        route_terminals = {
            vertex["terminal_id"]
            for route in value.net_routes.values()
            for vertex in route["vertices"]
            if vertex.get("terminal_id") is not None
        }
        unknown_route_terminals = route_terminals - terminal_keys
        if unknown_geometry or unknown_placements or unknown_routes or unknown_labels or unknown_route_terminals:
            raise ValueError(
                f"Circuit layout {path} contains unknown semantic references: "
                + ", ".join(sorted({
                    *unknown_geometry,
                    *unknown_placements,
                    *unknown_routes,
                    *unknown_labels,
                    *unknown_route_terminals,
                }))
            )

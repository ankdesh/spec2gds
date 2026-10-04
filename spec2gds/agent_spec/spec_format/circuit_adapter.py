"""Adapter from canonical SpecIR/IP-XACT structure to Circuit Designer v1.

The adapter lives on the specification side of the boundary.  Its output uses
only Circuit Designer vocabulary and can be submitted to any compatible
Circuit Designer REST service.
"""

from __future__ import annotations

import hashlib
import json
import re
import typing
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from spec2gds.agent_spec.spec_format.circuit_layouts import (
    DesignCircuitLayoutV1,
    load_design_layout,
)
from spec2gds.agent_spec.spec_format.circuit_timings import (
    DesignCircuitTimingV1,
    DesignClockDomainV1,
    DesignClockSignalV1,
    DesignCycleEdgeV1,
    load_design_timing,
)
from spec2gds.agent_spec.spec_format.ir import ComponentIR, ConnectionIR, PortIR, SpecRevision
from spec2gds.agent_spec.spec_format.models import EntityRef
from spec2gds.agent_spec.spec_format.naming import (
    clean_name,
    document_name,
    entity_name,
    hardware_name,
)

_DIRECTION = {"in": "input", "out": "output", "inout": "inout"}
_PROJECTION_VERSION = "v2"


class CircuitAdapterError(ValueError):
    """Report a source construct that the direct-port adapter cannot preserve."""


class CircuitDesignerConnectionError(CircuitAdapterError):
    """Report an unavailable or incompatible Circuit Designer service."""


@dataclass(frozen=True)
class CircuitProjection:
    """One independent circuit document plus source-side projection metadata."""

    document: dict[str, typing.Any]
    source_entity_id: str
    source_entity_kind: typing.Literal["component", "design"]
    omitted_bus_items: tuple[str, ...]
    omitted_ports: tuple[str, ...]
    source_map: "CircuitSourceMap"
    editable_design_id: str | None
    owner_component_id: str | None


@dataclass(frozen=True)
class CircuitSourceMap:
    """Stable source identities corresponding to generated Circuit IDs."""

    component_vlnv_by_id: dict[str, str]
    component_entity_id_by_id: dict[str, str]
    instance_name_by_id: dict[str, str]
    instance_component_id_by_id: dict[str, str]
    terminal_name_by_component_id: dict[str, dict[str, str]]
    boundary_name_by_id: dict[str, str]
    net_name_by_id: dict[str, str]


@dataclass(frozen=True)
class CircuitLaunch:
    """Location of a published Circuit Designer session."""

    document_id: str
    editor_url: str
    reused_session: bool


class _Ids:
    """Create deterministic Circuit Designer slugs within one namespace."""

    def __init__(self) -> None:
        self._used: set[str] = set()

    def get(self, value: str, prefix: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
        if not normalized or not normalized[0].isalpha():
            normalized = f"{prefix}_{normalized}".rstrip("_")
        candidate = normalized
        if candidate in self._used:
            digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
            candidate = f"{normalized}_{digest}"
        suffix = 2
        unique = candidate
        while unique in self._used:
            unique = f"{candidate}_{suffix}"
            suffix += 1
        self._used.add(unique)
        return unique


def _terminal(port: PortIR, terminal_id: str) -> dict[str, typing.Any]:
    if port.style != "wire":
        raise CircuitAdapterError(
            f"Port {port.name} is {port.style}; Circuit Designer supports only physical wire ports."
        )
    direction = _DIRECTION.get(port.direction)
    if direction is None:
        raise CircuitAdapterError(f"Port {port.name} has unsupported direction {port.direction!r}.")
    if port.width is None:
        raise CircuitAdapterError(f"Port {port.name} has an unsupported multidimensional or incomplete vector width.")
    # SpecIR preserves vector ranges as text. Circuit Designer needs a numeric
    # width for concrete ranges so it can validate endpoint slices.
    width = port.width
    if isinstance(width, str) and (bounds := re.fullmatch(r"\[([0-9]+):([0-9]+)\]", width)):
        width = abs(int(bounds[1]) - int(bounds[2])) + 1
    return {
        "id": terminal_id,
        "label": port.name,
        "direction": direction,
        "width": width,
        "category": "port",
    }


def _component_port(component: ComponentIR, name: str) -> PortIR:
    port = next((item for item in component.ports if item.name == name), None)
    if port is None:
        raise CircuitAdapterError(f"Component {component.vlnv} has no port named {name}.")
    return port


def _component_definition(
    component: ComponentIR,
    component_id: str,
    terminals: list[dict[str, typing.Any]],
) -> dict[str, typing.Any]:
    """Build one read-only Circuit Designer component definition."""
    return {
        "id": component_id,
        "label": entity_name(component),
        "origin": "provider",
        "editable": False,
        "terminals": terminals,
        "parameters": [],
        "appearance": {"renderer_key": "generic", "properties": {}},
    }


def _terminal_source_key(terminal_key: str, source_map: CircuitSourceMap) -> str | None:
    if terminal_key.startswith("boundary:"):
        name = source_map.boundary_name_by_id.get(terminal_key.removeprefix("boundary:"))
        return f"boundary:{name}" if name else None
    instance_id, separator, terminal_id = terminal_key.partition(":")
    if not separator:
        return None
    instance_name = source_map.instance_name_by_id.get(instance_id)
    component_id = source_map.instance_component_id_by_id.get(instance_id)
    port_name = source_map.terminal_name_by_component_id.get(component_id or "", {}).get(terminal_id)
    return f"instance:{instance_name}/port:{port_name}" if instance_name and port_name else None


def _terminal_circuit_key(source_key: str, source_map: CircuitSourceMap) -> str | None:
    if source_key.startswith("boundary:"):
        name = source_key.removeprefix("boundary:")
        terminal_id = next((key for key, value in source_map.boundary_name_by_id.items() if value == name), None)
        return f"boundary:{terminal_id}" if terminal_id else None
    match = re.fullmatch(r"instance:(.+)/port:(.+)", source_key)
    if not match:
        return None
    instance_name, port_name = match.groups()
    instance_id = next((key for key, value in source_map.instance_name_by_id.items() if value == instance_name), None)
    if not instance_id:
        return None
    component_id = source_map.instance_component_id_by_id.get(instance_id)
    terminal_id = next((key for key, name in source_map.terminal_name_by_component_id.get(component_id or "", {}).items() if name == port_name), None)
    return f"{instance_id}:{terminal_id}" if terminal_id else None


def _project_layout(revision: SpecRevision, design: EntityRef, source_map: CircuitSourceMap) -> dict[str, typing.Any]:
    """Translate source-keyed saved geometry to this projection's transient Circuit IDs.

    Unmapped entries are omitted so stale geometry cannot attach to a different
    instance or terminal after topology changes.
    """
    stored = load_design_layout(revision, design)
    if stored is None:
        return {
            "grid_size": 20,
            "direction": "RIGHT",
            "instance_geometry": {},
            "terminal_placements": {},
            "net_routes": {},
            "label_geometry": {},
        }
    instance_geometry = {
        circuit_id: stored.instance_geometry[name]
        for circuit_id, name in source_map.instance_name_by_id.items()
        if name in stored.instance_geometry
    }
    terminal_placements: dict[str, typing.Any] = {}
    for source_key, placement in stored.terminal_placements.items():
        circuit_key = _terminal_circuit_key(source_key, source_map)
        if circuit_key:
            terminal_placements[circuit_key] = placement
    net_routes: dict[str, typing.Any] = {}
    for circuit_id, name in source_map.net_name_by_id.items():
        route = stored.net_routes.get(name)
        if not route:
            continue
        route = json.loads(json.dumps(route))
        for vertex in route.get("vertices", []):
            if vertex.get("terminal_id"):
                vertex["terminal_id"] = _terminal_circuit_key(vertex["terminal_id"], source_map)
        net_routes[circuit_id] = route
    label_geometry: dict[str, typing.Any] = {}
    for source_key, geometry in stored.label_geometry.items():
        if source_key.startswith("instance:") and "/port:" not in source_key:
            name = source_key.removeprefix("instance:")
            circuit_key = next((key for key, value in source_map.instance_name_by_id.items() if value == name), None)
        elif source_key.startswith("net:"):
            name = source_key.removeprefix("net:")
            circuit_key = next((key for key, value in source_map.net_name_by_id.items() if value == name), None)
        else:
            circuit_key = _terminal_circuit_key(source_key, source_map)
        if circuit_key:
            label_geometry[circuit_key] = geometry
    return {
        "grid_size": stored.grid_size,
        "direction": stored.direction,
        "instance_geometry": instance_geometry,
        "terminal_placements": terminal_placements,
        "net_routes": net_routes,
        "label_geometry": label_geometry,
    }


def _project_timing(revision: SpecRevision, design: EntityRef, source_map: CircuitSourceMap) -> dict[str, typing.Any] | None:
    stored = load_design_timing(revision, design)
    if stored is None:
        return None
    instance_id_by_name = {name: circuit_id for circuit_id, name in source_map.instance_name_by_id.items()}
    boundary_id_by_name = {name: circuit_id for circuit_id, name in source_map.boundary_name_by_id.items()}
    net_id_by_name = {name: circuit_id for circuit_id, name in source_map.net_name_by_id.items()}
    overrides: dict[str, str] = {}
    for key, domain_id in stored.subject_domain_overrides.items():
        kind, name = key.split(":", 1)
        circuit_id = instance_id_by_name.get(name) if kind == "instance" else boundary_id_by_name.get(name)
        if circuit_id:
            overrides[f"{kind}:{circuit_id}"] = domain_id
    domains: list[dict[str, typing.Any]] = []
    for domain in stored.clock_domains:
        value = domain.model_dump(mode="json", exclude_none=True)
        if domain.signal is not None:
            signal_id = boundary_id_by_name.get(domain.signal.id) if domain.signal.kind == "boundary" else net_id_by_name.get(domain.signal.id)
            if signal_id:
                value["signal"] = {"kind": domain.signal.kind, "id": signal_id}
            else:
                value.pop("signal", None)
        domains.append(value)
    return {
        "schema_version": 1,
        "clock_domains": domains,
        "cycle_edges": [item.model_dump(mode="json", exclude_none=True) for item in stored.cycle_edges],
        "subject_domain_overrides": overrides,
        **({"leading_stage_label": stored.leading_stage_label} if stored.leading_stage_label else {}),
    }


def project_design_to_circuit(
    revision: SpecRevision,
    design_id: str,
    *,
    session_document_id: str | None = None,
    include_catalog: bool = False,
) -> CircuitProjection:
    """Project one design's direct physical-port connections into a circuit."""
    design = next((item for item in revision.designs if item.ref.entity_id == design_id), None)
    if design is None:
        raise CircuitAdapterError(f"Unknown design entity id: {design_id}")

    component_by_vlnv = {component.vlnv: component for component in revision.components}
    instance_by_name = {instance.name: instance for instance in design.instances}
    direct_ports: dict[str, set[str]] = {}
    for connection in design.connections:
        if connection.kind != "ad_hoc":
            continue
        for endpoint in connection.port_endpoints:
            instance = instance_by_name.get(endpoint.instance_name)
            if instance is not None:
                direct_ports.setdefault(instance.component_vlnv, set()).add(endpoint.port_name)

    component_ids = _Ids()
    component_id_by_vlnv: dict[str, str] = {}
    component_entity_id_by_id: dict[str, str] = {}
    terminal_id_by_port: dict[tuple[str, str], str] = {}
    terminal_name_by_component_id: dict[str, dict[str, str]] = {}
    circuit_components: list[dict[str, typing.Any]] = []
    omitted_ports: list[str] = []
    referenced_vlnvs = list(dict.fromkeys(instance.component_vlnv for instance in design.instances))
    if include_catalog:
        referenced_vlnvs.extend(vlnv for vlnv in component_by_vlnv if vlnv not in referenced_vlnvs)
    for vlnv in referenced_vlnvs:
        component = component_by_vlnv.get(vlnv)
        if component is None:
            raise CircuitAdapterError(f"Design {design.vlnv} references missing component {vlnv}.")
        component_id = component_ids.get(component.ref.entity_id, "component")
        component_id_by_vlnv[vlnv] = component_id
        component_entity_id_by_id[component_id] = component.ref.entity_id
        terminal_name_by_component_id[component_id] = {}
        mapped_ports = {physical for interface in component.interfaces for _, physical in interface.port_maps}
        terminal_ids = _Ids()
        terminals: list[dict[str, typing.Any]] = []
        for port in component.ports:
            # Bus-mapped physical pins remain owned by the omitted bus interface,
            # unless the design also connects that pin explicitly as an ad-hoc port.
            if port.name in mapped_ports and port.name not in direct_ports.get(vlnv, set()):
                continue
            if port.style != "wire" or port.direction not in _DIRECTION or port.width is None:
                if port.name in direct_ports.get(vlnv, set()):
                    _terminal(port, "unreachable")  # raises a precise error
                if port.style != "wire":
                    omitted_ports.append(f"{component.vlnv.split(':')[2]}.{port.name}")
                continue
            terminal_id = terminal_ids.get(port.name, "port")
            terminal_id_by_port[(vlnv, port.name)] = terminal_id
            terminal_name_by_component_id[component_id][terminal_id] = port.name
            terminals.append(_terminal(port, terminal_id))
        circuit_components.append(_component_definition(component, component_id, terminals))

    instance_ids = _Ids()
    instance_id_by_name: dict[str, str] = {}
    circuit_instances: list[dict[str, typing.Any]] = []
    for instance in design.instances:
        instance_id = instance_ids.get(instance.name, "instance")
        instance_id_by_name[instance.name] = instance_id
        circuit_instances.append({
            "id": instance_id,
            "label": instance.name,
            "component_id": component_id_by_vlnv[instance.component_vlnv],
            "parameter_values": {},
        })

    owner_component = None
    for mapping in revision.manifest.component_compositions:
        if mapping.internal_design.entity_id == design.ref.entity_id:
            resolved = revision.resolve(mapping.component)
            if isinstance(resolved, ComponentIR):
                owner_component = resolved
            break
    referenced_external_ports = {
        endpoint.port_name
        for connection in design.connections
        if connection.kind == "ad_hoc"
        for endpoint in connection.external_ports
    }
    if referenced_external_ports and owner_component is None:
        raise CircuitAdapterError(
            f"Design {design.vlnv} exposes boundary ports but is not the internal design of a component."
        )
    external_port_names = [
        port.name for port in owner_component.ports
        if port.style == "wire" and port.direction in _DIRECTION and port.width is not None
    ] if owner_component else []
    boundary_ids = _Ids()
    boundary_id_by_port: dict[str, str] = {}
    boundary_terminals: list[dict[str, typing.Any]] = []
    for name in external_port_names:
        assert owner_component is not None
        port = _component_port(owner_component, name)
        terminal_id = boundary_ids.get(name, "port")
        boundary_id_by_port[name] = terminal_id
        boundary_terminals.append(_terminal(port, terminal_id))

    net_ids = _Ids()
    net_name_by_id: dict[str, str] = {}
    circuit_nets: list[dict[str, typing.Any]] = []
    for connection in design.connections:
        if connection.kind != "ad_hoc":
            continue
        endpoints: list[dict[str, str]] = []
        for endpoint in connection.port_endpoints:
            if endpoint.symbolic_slice:
                raise CircuitAdapterError(
                    f"Connection {connection.name} uses symbolic part-select {endpoint.symbolic_slice} on "
                    f"{endpoint.instance_name}.{endpoint.port_name}; Circuit Designer requires numeric bounds."
                )
            instance = instance_by_name.get(endpoint.instance_name)
            if instance is None:
                raise CircuitAdapterError(
                    f"Connection {connection.name} references missing instance {endpoint.instance_name}."
                )
            terminal_id = terminal_id_by_port.get((instance.component_vlnv, endpoint.port_name))
            if terminal_id is None:
                _terminal(_component_port(component_by_vlnv[instance.component_vlnv], endpoint.port_name), "unreachable")
                raise CircuitAdapterError(
                    f"Connection {connection.name} uses port {endpoint.instance_name}.{endpoint.port_name}, which was not projected."
                )
            endpoints.append({
                "kind": "instance",
                "instance_id": instance_id_by_name[endpoint.instance_name],
                "terminal_id": terminal_id,
                **({"slice": {"lsb": endpoint.slice.lsb, "width": endpoint.slice.width}} if endpoint.slice else {}),
            })
        for endpoint in connection.external_ports:
            if endpoint.symbolic_slice:
                raise CircuitAdapterError(
                    f"Connection {connection.name} uses symbolic part-select {endpoint.symbolic_slice} on "
                    f"boundary port {endpoint.port_name}; Circuit Designer requires numeric bounds."
                )
            terminal_id = boundary_id_by_port.get(endpoint.port_name)
            if terminal_id is None:
                raise CircuitAdapterError(
                    f"Connection {connection.name} uses boundary port {endpoint.port_name}, which cannot be projected."
                )
            endpoints.append({
                "kind": "boundary",
                "terminal_id": terminal_id,
                **({"slice": {"lsb": endpoint.slice.lsb, "width": endpoint.slice.width}} if endpoint.slice else {}),
            })
        if len(endpoints) < 2:
            raise CircuitAdapterError(f"Connection {connection.name} has fewer than two representable endpoints.")
        net_id = net_ids.get(connection.name, "net")
        net_name_by_id[net_id] = connection.name
        circuit_nets.append({
            "id": net_id,
            "label": connection.name,
            "endpoints": endpoints,
        })

    revision_tag = revision.source_revision_hash.removeprefix("sha256:")[:12]
    document_ids = _Ids()
    document_id = session_document_id or document_ids.get(
        f"{revision.document_id}_{design.ref.entity_id}_{revision_tag}_{_PROJECTION_VERSION}",
        "circuit",
    )
    design_ids = _Ids()
    circuit_design_id = design_ids.get(design.ref.entity_id, "design")
    label = entity_name(design)
    source_map = CircuitSourceMap(
        component_vlnv_by_id={component_id_by_vlnv[vlnv]: vlnv for vlnv in component_id_by_vlnv},
        component_entity_id_by_id=component_entity_id_by_id,
        instance_name_by_id={value: key for key, value in instance_id_by_name.items()},
        instance_component_id_by_id={
            instance_id_by_name[instance.name]: component_id_by_vlnv[instance.component_vlnv]
            for instance in design.instances
        },
        terminal_name_by_component_id=terminal_name_by_component_id,
        boundary_name_by_id={value: key for key, value in boundary_id_by_port.items()},
        net_name_by_id=net_name_by_id,
    )
    layout = _project_layout(revision, design.ref, source_map)
    timing = _project_timing(revision, design.ref, source_map)
    document = {
        "protocol_version": "circuit-designer.v1",
        "document_id": document_id,
        "label": f"{document_name(revision)} › {label}",
        "components": circuit_components,
        "design": {
            "id": circuit_design_id,
            "label": label,
            "boundary_terminals": boundary_terminals,
            "instances": circuit_instances,
            "nets": circuit_nets,
        },
        "layout": layout,
        **({"timing": timing} if timing is not None else {}),
    }
    return CircuitProjection(
        document=document,
        source_entity_id=design.ref.entity_id,
        source_entity_kind="design",
        omitted_bus_items=tuple(
            connection.name for connection in design.connections if connection.kind == "interface"
        ),
        omitted_ports=tuple(omitted_ports),
        source_map=source_map,
        editable_design_id=design.ref.entity_id,
        owner_component_id=owner_component.ref.entity_id if owner_component else None,
    )


def project_component_to_circuit(
    revision: SpecRevision,
    component_id: str,
    *,
    session_document_id: str | None = None,
    include_catalog: bool = False,
) -> CircuitProjection:
    """Project a component's internal design or its direct physical boundary."""
    component = next((item for item in revision.components if item.ref.entity_id == component_id), None)
    if component is None:
        raise CircuitAdapterError(f"Unknown component entity id: {component_id}")
    internal_design = revision.internal_design(component)
    if internal_design is not None:
        projected = project_design_to_circuit(
            revision,
            internal_design.ref.entity_id,
            session_document_id=session_document_id,
            include_catalog=include_catalog,
        )
        return CircuitProjection(
            document=projected.document,
            source_entity_id=component.ref.entity_id,
            source_entity_kind="component",
            omitted_bus_items=projected.omitted_bus_items,
            omitted_ports=projected.omitted_ports,
            source_map=projected.source_map,
            editable_design_id=projected.editable_design_id,
            owner_component_id=projected.owner_component_id,
        )

    mapped_ports = {physical for interface in component.interfaces for _, physical in interface.port_maps}
    terminal_ids = _Ids()
    terminals = [
        _terminal(port, terminal_ids.get(port.name, "port"))
        for port in component.ports
        if port.name not in mapped_ports
        and port.style == "wire"
        and port.direction in _DIRECTION
        and port.width is not None
    ]
    revision_tag = revision.source_revision_hash.removeprefix("sha256:")[:12]
    document_id = session_document_id or _Ids().get(
        f"{revision.document_id}_{component.ref.entity_id}_{revision_tag}_{_PROJECTION_VERSION}",
        "circuit",
    )
    component_definition_id = _Ids().get(component.ref.entity_id, "component")
    design_id = _Ids().get(component.ref.entity_id, "component")
    preview_instance_id = _Ids().get(f"{component.ref.entity_id}_preview", "instance")
    label = entity_name(component)
    source_map = CircuitSourceMap(
        component_vlnv_by_id={component_definition_id: component.vlnv},
        component_entity_id_by_id={component_definition_id: component.ref.entity_id},
        instance_name_by_id={},
        instance_component_id_by_id={},
        terminal_name_by_component_id={component_definition_id: {terminal["id"]: terminal["label"] for terminal in terminals}},
        boundary_name_by_id={},
        net_name_by_id={},
    )
    return CircuitProjection(
        document={
            "protocol_version": "circuit-designer.v1",
            "document_id": document_id,
            "label": label,
            "components": [
                _component_definition(component, component_definition_id, terminals)
            ],
            "design": {
                "id": design_id,
                "label": label,
                "boundary_terminals": [],
                "instances": [{
                    "id": preview_instance_id,
                    "label": label,
                    "component_id": component_definition_id,
                    "parameter_values": {},
                }],
                "nets": [],
            },
            "layout": {
                "grid_size": 20,
                "direction": "RIGHT",
                "instance_geometry": {},
                "terminal_placements": {},
                "net_routes": {},
                "label_geometry": {},
            },
        },
        source_entity_id=component.ref.entity_id,
        source_entity_kind="component",
        omitted_bus_items=tuple(interface.name for interface in component.interfaces),
        omitted_ports=tuple(port.name for port in component.ports if port.style != "wire"),
        source_map=source_map,
        editable_design_id=None,
        owner_component_id=None,
    )


def project_source_to_circuit(
    revision: SpecRevision,
    entity_kind: typing.Literal["component", "design"],
    entity_id: str,
    *,
    session_document_id: str | None = None,
    include_catalog: bool = False,
) -> CircuitProjection:
    """Dispatch a supported source document through the independent adapter."""
    if entity_kind == "component":
        return project_component_to_circuit(
            revision, entity_id, session_document_id=session_document_id, include_catalog=include_catalog
        )
    return project_design_to_circuit(
        revision, entity_id, session_document_id=session_document_id, include_catalog=include_catalog
    )


def source_session_document_id(revision: SpecRevision, design_id: str) -> str:
    """Return the stable ephemeral session ID for one source-owned design."""
    return _Ids().get(f"{revision.document_id}_{design_id}_source_{_PROJECTION_VERSION}", "circuit")


def _wire_range(width: typing.Any) -> str | None:
    if width == 1:
        return None
    if isinstance(width, int) and width > 1:
        return f"{width - 1}:0"
    if isinstance(width, str):
        text = width.strip()
        if text.startswith("[") and text.endswith("]"):
            return text[1:-1]
        if ":" in text:
            return text
        return f"{text}-1:0"
    raise CircuitAdapterError(f"Unsupported terminal width: {width!r}")


def _direction_to_source(value: str) -> typing.Literal["in", "out", "inout"]:
    reverse = {"input": "in", "output": "out", "inout": "inout"}
    if value not in reverse:
        raise CircuitAdapterError(f"Unsupported terminal direction: {value!r}")
    return typing.cast(typing.Literal["in", "out", "inout"], reverse[value])


def _candidate_source_map(candidate: dict[str, typing.Any]) -> CircuitSourceMap:
    components = {item["id"]: item for item in candidate["components"]}
    return CircuitSourceMap(
        component_vlnv_by_id={},
        component_entity_id_by_id={},
        instance_name_by_id={item["id"]: item["label"] for item in candidate["design"]["instances"]},
        instance_component_id_by_id={item["id"]: item["component_id"] for item in candidate["design"]["instances"]},
        terminal_name_by_component_id={
            component_id: {terminal["id"]: terminal["label"] for terminal in component["terminals"]}
            for component_id, component in components.items()
        },
        boundary_name_by_id={item["id"]: item["label"] for item in candidate["design"]["boundary_terminals"]},
        net_name_by_id={item["id"]: item["label"] for item in candidate["design"]["nets"]},
    )


def _semantic_layout(
    revision: SpecRevision,
    design_id: str,
    candidate: dict[str, typing.Any],
) -> DesignCircuitLayoutV1:
    """Translate candidate Circuit IDs back to stable source names for persistence.

    Geometry and connectivity have different ownership. Save only recognized
    instance/net/terminal mappings; do not persist ephemeral projection IDs.
    """
    source_map = _candidate_source_map(candidate)
    layout = candidate["layout"]
    geometry = {
        source_map.instance_name_by_id[key]: value
        for key, value in layout.get("instance_geometry", {}).items()
        if key in source_map.instance_name_by_id
    }
    placements: dict[str, typing.Any] = {}
    for key, value in layout.get("terminal_placements", {}).items():
        source_key = _terminal_source_key(key, source_map)
        if source_key:
            placements[source_key] = value
    routes: dict[str, typing.Any] = {}
    for net_id, route_value in layout.get("net_routes", {}).items():
        net_name = source_map.net_name_by_id.get(net_id)
        if not net_name:
            continue
        route = json.loads(json.dumps(route_value))
        for vertex in route.get("vertices", []):
            if vertex.get("terminal_id"):
                source_key = _terminal_source_key(vertex["terminal_id"], source_map)
                if source_key:
                    vertex["terminal_id"] = source_key
        routes[net_name] = route
    labels: dict[str, typing.Any] = {}
    for key, value in layout.get("label_geometry", {}).items():
        if key in source_map.instance_name_by_id:
            labels[f"instance:{source_map.instance_name_by_id[key]}"] = value
        elif key in source_map.net_name_by_id:
            labels[f"net:{source_map.net_name_by_id[key]}"] = value
        else:
            source_key = _terminal_source_key(key, source_map)
            if source_key:
                labels[source_key] = value
    return DesignCircuitLayoutV1(
        design=EntityRef(document_id=revision.document_id, entity_id=design_id, entity_kind="design"),
        grid_size=layout.get("grid_size", 20),
        direction=layout.get("direction", "RIGHT"),
        instance_geometry=geometry,
        terminal_placements=placements,
        net_routes=routes,
        label_geometry=labels,
    )


def _semantic_timing(revision: SpecRevision, design_id: str, candidate: dict[str, typing.Any]) -> DesignCircuitTimingV1 | None:
    raw = candidate.get("timing")
    if raw is None:
        return None
    source_map = _candidate_source_map(candidate)
    overrides: dict[str, str] = {}
    for key, domain_id in raw.get("subject_domain_overrides", {}).items():
        kind, separator, circuit_id = key.partition(":")
        if not separator:
            continue
        name = source_map.instance_name_by_id.get(circuit_id) if kind == "instance" else source_map.boundary_name_by_id.get(circuit_id)
        if name:
            overrides[f"{kind}:{name}"] = domain_id
    domains: list[DesignClockDomainV1] = []
    for raw_domain in raw.get("clock_domains", []):
        signal = raw_domain.get("signal")
        semantic_signal = None
        if signal:
            name = source_map.boundary_name_by_id.get(signal["id"]) if signal["kind"] == "boundary" else source_map.net_name_by_id.get(signal["id"])
            if name:
                semantic_signal = DesignClockSignalV1(kind=signal["kind"], id=name)
        domains.append(DesignClockDomainV1(
            id=raw_domain["id"], label=raw_domain["label"], color=raw_domain.get("color"), signal=semantic_signal,
        ))
    return DesignCircuitTimingV1(
        design=EntityRef(document_id=revision.document_id, entity_id=design_id, entity_kind="design"),
        clock_domains=tuple(domains),
        cycle_edges=tuple(DesignCycleEdgeV1.model_validate(item) for item in raw.get("cycle_edges", [])),
        subject_domain_overrides=overrides,
        leading_stage_label=raw.get("leading_stage_label"),
    )


def compile_circuit_sync_operations(
    revision: SpecRevision,
    projection: CircuitProjection,
    candidate: dict[str, typing.Any],
) -> tuple[typing.Any, ...]:
    """Compile a validated Circuit candidate into one atomic Spec transaction."""
    from spec2gds.agent_spec.spec_format.ir import (
        EndpointSliceIR,
        ExternalPortEndpointIR,
        InstanceIR,
        PortEndpointIR,
    )
    from spec2gds.agent_spec.spec_format.models import ID_PATTERN
    from spec2gds.agent_spec.spec_format.transactions import (
        AddComponentPort,
        CreateEntity,
        DeleteComponentPort,
        DeleteConnection,
        DeleteInstance,
        RenameComponentPort,
        RenameInstance,
        UpdateComponentPort,
        UpsertCircuitLayout,
        UpsertCircuitTiming,
        UpsertConnection,
        UpsertInstance,
        WirePortInput,
    )

    design_id = projection.editable_design_id
    if not design_id:
        raise CircuitAdapterError("This source projection has no editable internal design.")
    if candidate.get("document_id") != projection.document.get("document_id"):
        raise CircuitAdapterError("Candidate document does not match its source-bound Circuit session.")
    if candidate.get("label") != projection.document.get("label"):
        raise CircuitAdapterError("Rename the source document in Spec Editor before refreshing this Circuit view.")
    design = next(item for item in revision.designs if item.ref.entity_id == design_id)
    design_ref = design.ref
    operations: list[typing.Any] = []

    base_components = {item["id"]: item for item in projection.document["components"]}
    candidate_components = {item["id"]: item for item in candidate["components"]}
    for component_id, base_component in base_components.items():
        if component_id not in candidate_components:
            raise CircuitAdapterError("Specification component definitions cannot be deleted from a design canvas.")
        if candidate_components[component_id] != base_component:
            raise CircuitAdapterError(f"Existing component definition {base_component['label']} is source-owned and read-only.")

    component_vlnv = dict(projection.source_map.component_vlnv_by_id)
    for component_id, component in candidate_components.items():
        if component_id in base_components:
            continue
        display_name = clean_name(str(component.get("label", "")))
        name = hardware_name(display_name, (item.split(":")[2] for item in component_vlnv.values()))
        entity_id = component_id
        if any(item.ref.entity_id == entity_id for item in [*revision.components, *revision.designs]):
            entity_id = f"component_{component_id}"
        operations.append(CreateEntity("component", display_name, entity_id))
        component_ref = EntityRef(document_id=revision.document_id, entity_id=entity_id, entity_kind="component")
        for terminal in component.get("terminals", []):
            terminal_name = str(terminal.get("label", "")).strip()
            if not ID_PATTERN.fullmatch(terminal_name):
                raise CircuitAdapterError(f"New port name {terminal_name!r} must be an XML-compatible identifier.")
            operations.append(AddComponentPort(
                component_ref,
                terminal_name,
                WirePortInput(_direction_to_source(terminal["direction"]), _wire_range(terminal.get("width", 1))),
            ))
        component_vlnv[component_id] = f"spec2gds.local:work:{name}:1.0"

    base_instances = projection.source_map.instance_name_by_id
    candidate_instances = {item["id"]: item for item in candidate["design"]["instances"]}
    for instance_id, old_name in base_instances.items():
        current = candidate_instances.get(instance_id)
        if current is None:
            if any(
                endpoint.instance_name == old_name
                for connection in design.connections if connection.kind == "interface"
                for endpoint in connection.interface_endpoints
            ):
                raise CircuitAdapterError(
                    f"Instance {old_name} is used by an omitted interface connection and cannot be deleted here."
                )
            continue
        new_name = str(current["label"]).strip()
        if not ID_PATTERN.fullmatch(new_name):
            raise CircuitAdapterError(f"Instance name {new_name!r} must be an XML-compatible identifier.")
        if current["component_id"] != projection.source_map.instance_component_id_by_id[instance_id]:
            raise CircuitAdapterError("Changing an existing instance's component type is not supported.")
        if new_name != old_name:
            operations.append(RenameInstance(design_ref, old_name, new_name))

    for connection in design.connections:
        if connection.kind == "ad_hoc":
            operations.append(DeleteConnection(design_ref, connection.name))

    for instance_id, old_name in base_instances.items():
        if instance_id not in candidate_instances:
            operations.append(DeleteInstance(design_ref, old_name))

    candidate_map = _candidate_source_map(candidate)
    for instance_id, instance in candidate_instances.items():
        if instance_id in base_instances:
            continue
        name = str(instance["label"]).strip()
        if not ID_PATTERN.fullmatch(name):
            raise CircuitAdapterError(f"Instance name {name!r} must be an XML-compatible identifier.")
        vlnv = component_vlnv.get(instance["component_id"])
        if not vlnv:
            raise CircuitAdapterError(f"Unknown component for instance {name}.")
        operations.append(UpsertInstance(design_ref, InstanceIR(name, vlnv)))

    owner = next((item for item in revision.components if item.ref.entity_id == projection.owner_component_id), None)
    base_boundaries = projection.source_map.boundary_name_by_id
    candidate_boundaries = {item["id"]: item for item in candidate["design"]["boundary_terminals"]}
    if candidate_boundaries and owner is None:
        raise CircuitAdapterError("Entry designs do not own component boundary ports.")
    if owner is not None:
        owner_ports = {item.name: item for item in owner.ports}
        for terminal_id, old_name in base_boundaries.items():
            terminal = candidate_boundaries.get(terminal_id)
            if terminal is None:
                outside = [
                    f"{other.vlnv}:{connection.name}"
                    for other in revision.designs if other.ref.entity_id != design_id
                    for connection in other.connections if connection.kind == "ad_hoc"
                    for endpoint in connection.port_endpoints
                    for instance in other.instances
                    if endpoint.instance_name == instance.name and instance.component_vlnv == owner.vlnv and endpoint.port_name == old_name
                ]
                mapped = [interface.name for interface in owner.interfaces if any(physical == old_name for _, physical in interface.port_maps)]
                if outside or mapped:
                    raise CircuitAdapterError(
                        f"Boundary port {old_name} is referenced outside this design and cannot be deleted: "
                        + ", ".join([*outside, *mapped])
                    )
                operations.append(DeleteComponentPort(owner.ref, old_name))
                continue
            new_name = str(terminal["label"]).strip()
            if not ID_PATTERN.fullmatch(new_name):
                raise CircuitAdapterError(f"Boundary port name {new_name!r} must be an XML-compatible identifier.")
            active_name = old_name
            if new_name != old_name:
                operations.append(RenameComponentPort(owner.ref, old_name, new_name))
                active_name = new_name
            source_port = owner_ports[old_name]
            direction = _direction_to_source(terminal["direction"])
            port_range = _wire_range(terminal.get("width", 1))
            if direction != source_port.direction or (port_range or "") != source_port.range:
                operations.append(UpdateComponentPort(owner.ref, active_name, WirePortInput(direction, port_range), True))
        for terminal_id, terminal in candidate_boundaries.items():
            if terminal_id in base_boundaries:
                continue
            name = str(terminal["label"]).strip()
            if not ID_PATTERN.fullmatch(name):
                raise CircuitAdapterError(f"Boundary port name {name!r} must be an XML-compatible identifier.")
            operations.append(AddComponentPort(
                owner.ref,
                name,
                WirePortInput(_direction_to_source(terminal["direction"]), _wire_range(terminal.get("width", 1))),
                True,
            ))

    def endpoint_slice(value: dict[str, typing.Any]) -> EndpointSliceIR | None:
        part = value.get("slice")
        return EndpointSliceIR(int(part["lsb"]), int(part["width"])) if part else None

    for net in candidate["design"]["nets"]:
        name = str(net["label"]).strip()
        if not ID_PATTERN.fullmatch(name):
            raise CircuitAdapterError(f"Connection name {name!r} must be an XML-compatible identifier.")
        internal: list[PortEndpointIR] = []
        external: list[ExternalPortEndpointIR] = []
        for endpoint in net["endpoints"]:
            if endpoint["kind"] == "instance":
                instance_name = candidate_map.instance_name_by_id.get(endpoint["instance_id"])
                component_id = candidate_map.instance_component_id_by_id.get(endpoint["instance_id"])
                port_name = candidate_map.terminal_name_by_component_id.get(component_id or "", {}).get(endpoint["terminal_id"])
                if not instance_name or not port_name:
                    raise CircuitAdapterError(f"Connection {name} contains an unknown instance port.")
                internal.append(PortEndpointIR(instance_name, port_name, endpoint_slice(endpoint)))
            else:
                port_name = candidate_map.boundary_name_by_id.get(endpoint["terminal_id"])
                if not port_name:
                    raise CircuitAdapterError(f"Connection {name} contains an unknown boundary port.")
                external.append(ExternalPortEndpointIR(port_name, endpoint_slice(endpoint)))
        if len(internal) + len(external) < 2:
            raise CircuitAdapterError(f"Connection {name} needs at least two endpoints.")
        operations.append(UpsertConnection(
            design_ref,
            ConnectionIR(
                name=name, kind="ad_hoc", port_endpoints=tuple(internal), external_ports=tuple(external)
            ),
        ))
    operations.append(UpsertCircuitLayout(_semantic_layout(revision, design_id, candidate)))
    timing = _semantic_timing(revision, design_id, candidate)
    if timing is not None:
        operations.append(UpsertCircuitTiming(timing))
    return tuple(operations)


def publish_circuit_document(
    document: dict[str, typing.Any],
    *,
    service_url: str,
    editor_url: str,
    timeout: float = 3.0,
) -> CircuitLaunch:
    """Create or reuse one ephemeral Circuit Designer REST session."""
    base = service_url.rstrip("/")
    document_id = str(document["document_id"])
    request_id = f"spec_projection_{document_id}"
    document_url = f"{base}/documents/{urllib.parse.quote(document_id)}"
    existing_snapshot: dict[str, typing.Any] | None = None
    try:
        with urllib.request.urlopen(document_url, timeout=timeout) as response:
            existing_snapshot = json.loads(response.read())
            reused = True
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            body = exc.read().decode("utf-8", errors="replace")
            raise CircuitDesignerConnectionError(
                f"Circuit Designer service returned HTTP {exc.code}: {body}"
            ) from exc
        reused = False
    except (OSError, urllib.error.URLError) as exc:
        raise CircuitDesignerConnectionError(
            f"Circuit Designer is unavailable at {base}. Start it with 'cd circuit-designer && npm run dev'."
        ) from exc

    if reused:
        if existing_snapshot is not None and existing_snapshot.get("document") != document:
            replacement = urllib.request.Request(
                document_url,
                data=json.dumps({
                    "request_id": f"spec_refresh_{document_id}_{hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()[:12]}",
                    "expected_revision": existing_snapshot.get("revision"),
                    "document": document,
                }).encode(),
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                method="PUT",
            )
            try:
                with urllib.request.urlopen(replacement, timeout=timeout) as response:
                    refreshed = json.loads(response.read())
                if refreshed.get("status") != "accepted":
                    raise CircuitDesignerConnectionError(f"Circuit Designer rejected the refreshed source projection: {refreshed}")
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                raise CircuitDesignerConnectionError(
                    "The existing Circuit session has an active or stale draft. Save, cancel, or recover that draft before reopening the source. "
                    f"Circuit Designer returned HTTP {exc.code}: {body}"
                ) from exc
        query = urllib.parse.urlencode({"document_id": document_id})
        return CircuitLaunch(
            document_id=document_id,
            editor_url=f"{editor_url.rstrip('/')}?{query}",
            reused_session=True,
        )

    payload = json.dumps({"request_id": request_id, "document": document}).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/documents",
        data=payload,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read())
        if result.get("status") != "accepted":
            raise CircuitDesignerConnectionError(f"Circuit Designer rejected the projection: {result}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code != 409:
            raise CircuitDesignerConnectionError(
                f"Circuit Designer service returned HTTP {exc.code}: {body}"
            ) from exc
        # A source revision has a deterministic document id. Reopening the same
        # revision resumes its existing ephemeral circuit session.
        try:
            with urllib.request.urlopen(document_url, timeout=timeout):
                reused = True
        except (OSError, urllib.error.URLError) as lookup_error:
            raise CircuitDesignerConnectionError(
                f"Circuit Designer could not reopen session {document_id}: {body}"
            ) from lookup_error
    except (OSError, urllib.error.URLError) as exc:
        raise CircuitDesignerConnectionError(
            f"Circuit Designer is unavailable at {base}. Start it with 'cd circuit-designer && npm run dev'."
        ) from exc

    query = urllib.parse.urlencode({"document_id": document_id})
    return CircuitLaunch(
        document_id=document_id,
        editor_url=f"{editor_url.rstrip('/')}?{query}",
        reused_session=reused,
    )


def register_circuit_source_binding(
    document_id: str,
    binding: dict[str, typing.Any],
    *,
    service_url: str,
    callback_url: str,
    token: str,
    timeout: float = 3.0,
) -> None:
    """Register a server-side source callback without exposing its token to the browser."""
    base = service_url.rstrip("/")
    payload = json.dumps({
        "binding": binding,
        "callback_url": callback_url.rstrip("/") + "/",
        "token": token,
    }).encode()
    request = urllib.request.Request(
        f"{base}/documents/{urllib.parse.quote(document_id)}/source-binding",
        data=payload,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            return
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise CircuitDesignerConnectionError(
            f"Circuit Designer rejected the source binding with HTTP {exc.code}: {body}"
        ) from exc
    except (OSError, urllib.error.URLError) as exc:
        raise CircuitDesignerConnectionError(f"Circuit Designer could not register source binding: {exc}") from exc

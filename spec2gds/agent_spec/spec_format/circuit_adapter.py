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

from spec2gds.agent_spec.spec_format.ir import ComponentIR, PortIR, SpecRevision

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
    return {
        "id": terminal_id,
        "label": port.name,
        "direction": direction,
        "width": port.width,
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
        "label": component.vlnv.split(":")[2],
        "origin": "provider",
        "editable": False,
        "terminals": terminals,
        "parameters": [],
        "appearance": {"renderer_key": "generic", "properties": {}},
    }


def project_design_to_circuit(revision: SpecRevision, design_id: str) -> CircuitProjection:
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
    terminal_id_by_port: dict[tuple[str, str], str] = {}
    circuit_components: list[dict[str, typing.Any]] = []
    omitted_ports: list[str] = []
    referenced_vlnvs = list(dict.fromkeys(instance.component_vlnv for instance in design.instances))
    for vlnv in referenced_vlnvs:
        component = component_by_vlnv.get(vlnv)
        if component is None:
            raise CircuitAdapterError(f"Design {design.vlnv} references missing component {vlnv}.")
        component_id = component_ids.get(component.ref.entity_id, "component")
        component_id_by_vlnv[vlnv] = component_id
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
    external_port_names = list(dict.fromkeys(
        name
        for connection in design.connections
        if connection.kind == "ad_hoc"
        for name in connection.external_ports
    ))
    if external_port_names and owner_component is None:
        raise CircuitAdapterError(
            f"Design {design.vlnv} uses external ports but is not the internal design of a component."
        )
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
    circuit_nets: list[dict[str, typing.Any]] = []
    for connection in design.connections:
        if connection.kind != "ad_hoc":
            continue
        endpoints: list[dict[str, str]] = []
        for endpoint in connection.port_endpoints:
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
            })
        endpoints.extend(
            {"kind": "boundary", "terminal_id": boundary_id_by_port[name]}
            for name in connection.external_ports
        )
        if len(endpoints) < 2:
            raise CircuitAdapterError(f"Connection {connection.name} has fewer than two representable endpoints.")
        circuit_nets.append({
            "id": net_ids.get(connection.name, "net"),
            "label": connection.name,
            "endpoints": endpoints,
        })

    revision_tag = revision.source_revision_hash.removeprefix("sha256:")[:12]
    document_ids = _Ids()
    document_id = document_ids.get(
        f"{revision.document_id}_{design.ref.entity_id}_{revision_tag}_{_PROJECTION_VERSION}",
        "circuit",
    )
    design_ids = _Ids()
    circuit_design_id = design_ids.get(design.ref.entity_id, "design")
    label = design.vlnv.split(":")[2]
    document = {
        "protocol_version": "circuit-designer.v1",
        "document_id": document_id,
        "label": label,
        "components": circuit_components,
        "design": {
            "id": circuit_design_id,
            "label": label,
            "boundary_terminals": boundary_terminals,
            "instances": circuit_instances,
            "nets": circuit_nets,
        },
        "layout": {
            "grid_size": 20,
            "direction": "RIGHT",
            "instance_geometry": {},
            "terminal_placements": {},
            "net_routes": {},
            "label_geometry": {},
        },
    }
    return CircuitProjection(
        document=document,
        source_entity_id=design.ref.entity_id,
        source_entity_kind="design",
        omitted_bus_items=tuple(
            connection.name for connection in design.connections if connection.kind == "interface"
        ),
        omitted_ports=tuple(omitted_ports),
    )


def project_component_to_circuit(revision: SpecRevision, component_id: str) -> CircuitProjection:
    """Project a component's internal design or its direct physical boundary."""
    component = next((item for item in revision.components if item.ref.entity_id == component_id), None)
    if component is None:
        raise CircuitAdapterError(f"Unknown component entity id: {component_id}")
    internal_design = revision.internal_design(component)
    if internal_design is not None:
        projected = project_design_to_circuit(revision, internal_design.ref.entity_id)
        return CircuitProjection(
            document=projected.document,
            source_entity_id=component.ref.entity_id,
            source_entity_kind="component",
            omitted_bus_items=projected.omitted_bus_items,
            omitted_ports=projected.omitted_ports,
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
    document_id = _Ids().get(
        f"{revision.document_id}_{component.ref.entity_id}_{revision_tag}_{_PROJECTION_VERSION}",
        "circuit",
    )
    component_definition_id = _Ids().get(component.ref.entity_id, "component")
    design_id = _Ids().get(component.ref.entity_id, "component")
    preview_instance_id = _Ids().get(f"{component.ref.entity_id}_preview", "instance")
    label = component.vlnv.split(":")[2]
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
    )


def project_source_to_circuit(
    revision: SpecRevision,
    entity_kind: typing.Literal["component", "design"],
    entity_id: str,
) -> CircuitProjection:
    """Dispatch a supported source document through the independent adapter."""
    if entity_kind == "component":
        return project_component_to_circuit(revision, entity_id)
    return project_design_to_circuit(revision, entity_id)


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
    try:
        with urllib.request.urlopen(document_url, timeout=timeout):
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

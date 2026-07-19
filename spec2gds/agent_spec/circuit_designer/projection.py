"""Read-only projection from the authoritative SpecIR into circuit contracts."""

from __future__ import annotations

import typing

from spec2gds.agent_spec.circuit_designer.contracts import (
    CircuitCapabilities,
    CircuitComponentDefinition,
    CircuitDesignCatalog,
    CircuitDesignRef,
    CircuitEndpointRef,
    CircuitGraphSnapshot,
    CircuitNet,
    CircuitNode,
    CircuitTerminal,
    SourceRef,
)
from spec2gds.agent_spec.spec_format.ir import ComponentIR, DesignIR, SpecRevision


def _label(vlnv: str) -> str:
    """Use the IP name portion of a VLNV as a compact display fallback."""
    parts = vlnv.split(":")
    return parts[2] if len(parts) == 4 else vlnv


def _node_id(instance_name: str) -> str:
    return f"instance:{instance_name}"


def _terminal_id(instance_name: str, kind: str, name: str) -> str:
    return f"instance:{instance_name}:{kind}:{name}"


def _boundary_id(kind: str, name: str) -> str:
    return f"boundary:{kind}:{name}"


def _component_definition(component: ComponentIR) -> CircuitComponentDefinition:
    return CircuitComponentDefinition(
        id=component.ref.entity_id,
        label=_label(component.vlnv),
        vlnv=component.vlnv,
        source_ref=SourceRef(source_id=component.ref.entity_id, kind="component"),
    )


def _design_ref(design: DesignIR) -> CircuitDesignRef:
    return CircuitDesignRef(
        id=design.ref.entity_id,
        label=_label(design.vlnv),
        vlnv=design.vlnv,
        source_ref=SourceRef(source_id=design.ref.entity_id, kind="design"),
    )


def project_catalog(revision: SpecRevision) -> CircuitDesignCatalog:
    """List designs from one revision without leaking SpecIR objects."""
    return CircuitDesignCatalog(
        document_id=revision.document_id,
        source_revision_hash=revision.source_revision_hash,
        designs=tuple(_design_ref(design) for design in revision.designs),
        entry_design_ids=tuple(design.ref.entity_id for design in revision.entry_designs()),
    )


def project_design(revision: SpecRevision, design: DesignIR) -> CircuitGraphSnapshot:
    """Project one validated design without creating another source-of-truth graph."""
    component_by_vlnv = {component.vlnv: component for component in revision.components}
    terminals: list[CircuitTerminal] = []
    nodes: list[CircuitNode] = []

    for instance in design.instances:
        component = component_by_vlnv[instance.component_vlnv]
        node_id = _node_id(instance.name)
        terminal_ids: list[str] = []
        physical_ids = {port.name: _terminal_id(instance.name, "port", port.name) for port in component.ports}
        for interface in component.interfaces:
            terminal_id = _terminal_id(instance.name, "interface", interface.name)
            terminal_ids.append(terminal_id)
            terminals.append(
                CircuitTerminal(
                    id=terminal_id,
                    node_id=node_id,
                    label=interface.name,
                    kind="interface",
                    role=interface.role or None,
                    bus_vlnv=interface.bus_vlnv or None,
                    abstraction_vlnv=interface.abstraction_vlnv or None,
                    mapped_port_ids=tuple(
                        physical_ids[physical]
                        for _, physical in interface.port_maps
                        if physical in physical_ids
                    ),
                    source_ref=SourceRef(
                        source_id=f"{design.ref.entity_id}:{instance.name}:interface:{interface.name}",
                        kind="interface",
                    ),
                )
            )
        for port in component.ports:
            terminal_id = physical_ids[port.name]
            terminal_ids.append(terminal_id)
            terminals.append(
                CircuitTerminal(
                    id=terminal_id,
                    node_id=node_id,
                    label=port.name,
                    kind="port",
                    direction=port.direction or None,
                    source_ref=SourceRef(
                        source_id=f"{design.ref.entity_id}:{instance.name}:port:{port.name}",
                        kind="port",
                    ),
                )
            )
        nodes.append(
            CircuitNode(
                id=node_id,
                label=instance.name,
                component_id=component.ref.entity_id,
                component_vlnv=component.vlnv,
                terminal_ids=tuple(terminal_ids),
                source_ref=SourceRef(
                    source_id=f"{design.ref.entity_id}:{instance.name}",
                    kind="instance",
                ),
            )
        )

    boundary_terminals: dict[tuple[str, str], CircuitTerminal] = {}

    def boundary(kind: typing.Literal["interface", "port"], name: str) -> str:
        key = (kind, name)
        if key not in boundary_terminals:
            terminal_id = _boundary_id(kind, name)
            boundary_terminals[key] = CircuitTerminal(
                id=terminal_id,
                label=name,
                kind="boundary_interface" if kind == "interface" else "boundary_port",
                source_ref=SourceRef(
                    source_id=f"{design.ref.entity_id}:boundary:{kind}:{name}",
                    kind=f"boundary_{kind}",
                ),
            )
        return boundary_terminals[key].id

    nets: list[CircuitNet] = []
    for connection in design.connections:
        endpoint_ids: list[str] = []
        if connection.kind == "interface":
            endpoint_ids.extend(
                _terminal_id(endpoint.instance_name, "interface", endpoint.interface_name)
                for endpoint in connection.interface_endpoints
            )
            endpoint_ids.extend(boundary("interface", name) for name in connection.hierarchy_interfaces)
        else:
            endpoint_ids.extend(
                _terminal_id(endpoint.instance_name, "port", endpoint.port_name)
                for endpoint in connection.port_endpoints
            )
            endpoint_ids.extend(boundary("port", name) for name in connection.external_ports)
        nets.append(
            CircuitNet(
                id=f"net:{connection.kind}:{connection.name}",
                label=connection.name,
                kind=connection.kind,
                endpoints=tuple(CircuitEndpointRef(terminal_id=terminal_id) for terminal_id in endpoint_ids),
                source_ref=SourceRef(
                    source_id=f"{design.ref.entity_id}:connection:{connection.kind}:{connection.name}",
                    kind="connection",
                ),
            )
        )

    return CircuitGraphSnapshot(
        document_id=revision.document_id,
        source_revision_hash=revision.source_revision_hash,
        design=_design_ref(design),
        capabilities=CircuitCapabilities(),
        components=tuple(_component_definition(component) for component in revision.components),
        nodes=tuple(nodes),
        terminals=tuple([*terminals, *boundary_terminals.values()]),
        nets=tuple(nets),
    )

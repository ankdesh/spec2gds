"""Strict, renderer-neutral transport contracts for circuit-designer clients.

These models deliberately contain no IP-XACT parsing, persistence, or editing
behavior.  They define the JSON boundary shared by the FastAPI adapter and the
independent TypeScript packages.
"""

from __future__ import annotations

import typing

import pydantic


PROTOCOL_VERSION = "circuit-designer.v1"
ProtocolVersion = typing.Literal["circuit-designer.v1"]


class ContractModel(pydantic.BaseModel):
    """Base configuration shared by every public transport object."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)


class SourceRef(ContractModel):
    """Opaque adapter-owned locator for one source-backed graph element."""

    source_id: str = pydantic.Field(min_length=1)
    kind: str = pydantic.Field(min_length=1)


class CircuitDesignRef(ContractModel):
    """One design available to the circuit canvas."""

    id: str = pydantic.Field(min_length=1)
    label: str = pydantic.Field(min_length=1)
    vlnv: str | None = None
    source_ref: SourceRef


class CircuitComponentDefinition(ContractModel):
    """Reusable component definition exposed by the active adapter."""

    id: str = pydantic.Field(min_length=1)
    label: str = pydantic.Field(min_length=1)
    vlnv: str | None = None
    source_ref: SourceRef


class CircuitTerminal(ContractModel):
    """Interface, physical port, or design-boundary connection point."""

    id: str = pydantic.Field(min_length=1)
    node_id: str | None = None
    label: str = pydantic.Field(min_length=1)
    kind: typing.Literal["interface", "port", "boundary_interface", "boundary_port"]
    direction: str | None = None
    role: str | None = None
    bus_vlnv: str | None = None
    abstraction_vlnv: str | None = None
    mapped_port_ids: tuple[str, ...] = ()
    declared_bounds: tuple[str, ...] = ()
    source_ref: SourceRef


class CircuitNode(ContractModel):
    """One component instance in the selected design."""

    id: str = pydantic.Field(min_length=1)
    label: str = pydantic.Field(min_length=1)
    component_id: str = pydantic.Field(min_length=1)
    component_vlnv: str | None = None
    terminal_ids: tuple[str, ...] = ()
    display_name: str | None = None
    description: str | None = None
    configuration_values: dict[str, str] = pydantic.Field(default_factory=dict)
    source_ref: SourceRef


class CircuitEndpointRef(ContractModel):
    """Reference from a net to one terminal."""

    terminal_id: str = pydantic.Field(min_length=1)


class CircuitNet(ContractModel):
    """One interface or ad-hoc multi-endpoint connection."""

    id: str = pydantic.Field(min_length=1)
    label: str = pydantic.Field(min_length=1)
    kind: typing.Literal["interface", "ad_hoc"]
    endpoints: tuple[CircuitEndpointRef, ...] = pydantic.Field(min_length=2)
    source_ref: SourceRef

    @pydantic.model_validator(mode="after")
    def _unique_endpoints(self) -> "CircuitNet":
        ids = [endpoint.terminal_id for endpoint in self.endpoints]
        if len(ids) != len(set(ids)):
            raise ValueError("A circuit net cannot contain the same terminal twice.")
        return self


class CircuitCapabilities(ContractModel):
    """Operations supported by the active backend adapter."""

    edit_topology: bool = False
    edit_layout: bool = False
    replace_component: bool = False
    edit_instance_details: bool = False
    submit_agent_proposal: bool = False


class CircuitHierarchyLink(ContractModel):
    """Reusable component composition and designs that instantiate it."""

    component_id: str = pydantic.Field(min_length=1)
    internal_design_id: str = pydantic.Field(min_length=1)
    parent_design_ids: tuple[str, ...] = ()


class CircuitDesignCatalog(ContractModel):
    """Designs available from one immutable source revision."""

    protocol_version: ProtocolVersion = PROTOCOL_VERSION
    document_id: str = pydantic.Field(min_length=1)
    source_revision_hash: str = pydantic.Field(min_length=1)
    designs: tuple[CircuitDesignRef, ...]
    entry_design_ids: tuple[str, ...] = ()
    hierarchy_links: tuple[CircuitHierarchyLink, ...] = ()


class Point(ContractModel):
    """Canvas-space point."""

    x: float
    y: float


class NodeGeometry(ContractModel):
    """Persistable node placement independent of a renderer."""

    x: float
    y: float
    width: float = pydantic.Field(gt=0)
    height: float = pydantic.Field(gt=0)
    pinned: bool = True


class TerminalPlacement(ContractModel):
    """Optional semantic-terminal placement override."""

    side: typing.Literal["NORTH", "EAST", "SOUTH", "WEST"]
    order: int = pydantic.Field(ge=0)
    locked: bool = True


class RouteVertex(ContractModel):
    """Endpoint, bend, or electrical junction in an orthogonal route tree."""

    id: str = pydantic.Field(min_length=1)
    kind: typing.Literal["endpoint", "bend", "junction"]
    point: Point
    terminal_id: str | None = None
    locked: bool = False

    @pydantic.model_validator(mode="after")
    def _endpoint_requires_terminal(self) -> "RouteVertex":
        if (self.kind == "endpoint") != (self.terminal_id is not None):
            raise ValueError("Only endpoint route vertices must reference a terminal.")
        return self


class RouteSegment(ContractModel):
    """One edge between vertices in an orthogonal route tree."""

    id: str | None = None
    from_vertex: str = pydantic.Field(min_length=1)
    to_vertex: str = pydantic.Field(min_length=1)
    locked: bool = False


class NetRoute(ContractModel):
    """Renderer-neutral route tree for a possibly multi-endpoint net."""

    vertices: tuple[RouteVertex, ...]
    segments: tuple[RouteSegment, ...]

    @pydantic.model_validator(mode="after")
    def _validate_tree_references_and_geometry(self) -> "NetRoute":
        by_id = {vertex.id: vertex for vertex in self.vertices}
        if len(by_id) != len(self.vertices):
            raise ValueError("Route vertex ids must be unique.")
        segment_ids = [segment.id for segment in self.segments if segment.id is not None]
        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError("Defined route segment ids must be unique.")
        segment_keys: set[tuple[str, str]] = set()
        adjacency = {vertex_id: set() for vertex_id in by_id}
        for segment in self.segments:
            if segment.from_vertex not in by_id or segment.to_vertex not in by_id:
                raise ValueError("Route segments must reference known vertices.")
            if segment.from_vertex == segment.to_vertex:
                raise ValueError("Route segments cannot connect a vertex to itself.")
            key = tuple(sorted((segment.from_vertex, segment.to_vertex)))
            if key in segment_keys:
                raise ValueError("A route cannot contain duplicate segments.")
            segment_keys.add(key)
            adjacency[segment.from_vertex].add(segment.to_vertex)
            adjacency[segment.to_vertex].add(segment.from_vertex)
            start = by_id[segment.from_vertex].point
            end = by_id[segment.to_vertex].point
            if start.x != end.x and start.y != end.y:
                raise ValueError("Circuit route segments must be orthogonal.")
            if start.x == end.x and start.y == end.y:
                raise ValueError("Circuit route segments must have non-zero length.")
        if self.vertices:
            visited: set[str] = set()
            stack = [self.vertices[0].id]
            while stack:
                vertex_id = stack.pop()
                if vertex_id in visited:
                    continue
                visited.add(vertex_id)
                stack.extend(adjacency[vertex_id] - visited)
            if visited != set(by_id):
                raise ValueError("A circuit route tree must be connected.")
            if len(self.segments) != len(self.vertices) - 1:
                raise ValueError("A circuit route must be an acyclic tree.")
        for vertex in self.vertices:
            degree = len(adjacency[vertex.id])
            if vertex.kind == "junction" and degree < 3:
                raise ValueError("A junction route vertex must have electrical degree three or greater.")
        return self


class DiagramLayout(ContractModel):
    """One canonical renderer-neutral layout for a design."""

    direction: typing.Literal["RIGHT", "DOWN"] = "RIGHT"
    node_geometry: dict[str, NodeGeometry] = pydantic.Field(default_factory=dict)
    terminal_placements: dict[str, TerminalPlacement] = pydantic.Field(default_factory=dict)
    net_routes: dict[str, NetRoute] = pydantic.Field(default_factory=dict)


class CircuitGraphSnapshot(ContractModel):
    """Complete immutable graph payload for one design revision."""

    protocol_version: ProtocolVersion = PROTOCOL_VERSION
    document_id: str = pydantic.Field(min_length=1)
    source_revision_hash: str = pydantic.Field(min_length=1)
    design: CircuitDesignRef
    breadcrumbs: tuple[CircuitDesignRef, ...] = ()
    capabilities: CircuitCapabilities = CircuitCapabilities()
    components: tuple[CircuitComponentDefinition, ...]
    nodes: tuple[CircuitNode, ...]
    terminals: tuple[CircuitTerminal, ...]
    nets: tuple[CircuitNet, ...]
    layout: DiagramLayout | None = None

    @pydantic.model_validator(mode="after")
    def _validate_graph_references(self) -> "CircuitGraphSnapshot":
        def unique(values: typing.Iterable[str], label: str) -> set[str]:
            items = list(values)
            if len(items) != len(set(items)):
                raise ValueError(f"{label} ids must be unique.")
            return set(items)

        component_ids = unique((item.id for item in self.components), "Component")
        node_ids = unique((item.id for item in self.nodes), "Node")
        terminal_ids = unique((item.id for item in self.terminals), "Terminal")
        unique((item.id for item in self.nets), "Net")
        terminal_by_id = {item.id: item for item in self.terminals}

        for node in self.nodes:
            if node.component_id not in component_ids:
                raise ValueError(f"Node {node.id} references an unknown component.")
            if any(terminal_id not in terminal_ids for terminal_id in node.terminal_ids):
                raise ValueError(f"Node {node.id} references an unknown terminal.")
            if any(terminal_by_id[terminal_id].node_id != node.id for terminal_id in node.terminal_ids):
                raise ValueError(f"Node {node.id} references a terminal owned by another node.")
        for terminal in self.terminals:
            if terminal.node_id is not None and terminal.node_id not in node_ids:
                raise ValueError(f"Terminal {terminal.id} references an unknown node.")
        for net in self.nets:
            if any(endpoint.terminal_id not in terminal_ids for endpoint in net.endpoints):
                raise ValueError(f"Net {net.id} references an unknown terminal.")
        return self


class CommandBase(ContractModel):
    """Common identity carried by every proposed designer operation."""

    command_id: str = pydantic.Field(min_length=1)
    design_id: str = pydantic.Field(min_length=1)


class AddInstanceCommand(CommandBase):
    type: typing.Literal["add_instance"] = "add_instance"
    node_id: str = pydantic.Field(min_length=1)
    name: str = pydantic.Field(min_length=1)
    component_id: str = pydantic.Field(min_length=1)


class UpdateInstanceCommand(CommandBase):
    type: typing.Literal["update_instance"] = "update_instance"
    node_id: str = pydantic.Field(min_length=1)
    name: str | None = None
    component_id: str | None = None
    display_name: str | None = None
    description: str | None = None
    configuration_values: dict[str, str] | None = None


class DuplicateInstancesCommand(CommandBase):
    type: typing.Literal["duplicate_instances"] = "duplicate_instances"
    node_ids: tuple[str, ...] = pydantic.Field(min_length=1)
    offset: Point = Point(x=24, y=24)


class DeleteInstanceCommand(CommandBase):
    type: typing.Literal["delete_instance"] = "delete_instance"
    node_id: str = pydantic.Field(min_length=1)
    cascade: bool = True


class AddTerminalCommand(CommandBase):
    """Create a minimally described port or interface on one instance."""

    type: typing.Literal["add_terminal"] = "add_terminal"
    terminal_id: str = pydantic.Field(min_length=1)
    node_id: str = pydantic.Field(min_length=1)
    name: str = pydantic.Field(min_length=1)
    kind: typing.Literal["port", "interface"] = "port"
    direction: typing.Literal["in", "out", "inout"] | None = None


class DeleteTerminalCommand(CommandBase):
    """Remove a terminal and optionally clean up its connected nets."""

    type: typing.Literal["delete_terminal"] = "delete_terminal"
    terminal_id: str = pydantic.Field(min_length=1)
    cascade: bool = True


class CreateNetCommand(CommandBase):
    type: typing.Literal["create_net"] = "create_net"
    net_id: str = pydantic.Field(min_length=1)
    name: str = pydantic.Field(min_length=1)
    kind: typing.Literal["interface", "ad_hoc"]
    terminal_ids: tuple[str, ...] = pydantic.Field(min_length=2)


class RenameNetCommand(CommandBase):
    type: typing.Literal["rename_net"] = "rename_net"
    net_id: str = pydantic.Field(min_length=1)
    name: str = pydantic.Field(min_length=1)


class NetEndpointCommand(CommandBase):
    net_id: str = pydantic.Field(min_length=1)
    terminal_id: str = pydantic.Field(min_length=1)


class AddNetEndpointCommand(NetEndpointCommand):
    type: typing.Literal["add_net_endpoint"] = "add_net_endpoint"


class RemoveNetEndpointCommand(NetEndpointCommand):
    type: typing.Literal["remove_net_endpoint"] = "remove_net_endpoint"


class DeleteNetCommand(CommandBase):
    type: typing.Literal["delete_net"] = "delete_net"
    net_id: str = pydantic.Field(min_length=1)


class SetNodeGeometryCommand(CommandBase):
    type: typing.Literal["set_node_geometry"] = "set_node_geometry"
    node_id: str = pydantic.Field(min_length=1)
    geometry: NodeGeometry


class SetTerminalPlacementCommand(CommandBase):
    type: typing.Literal["set_terminal_placement"] = "set_terminal_placement"
    terminal_id: str = pydantic.Field(min_length=1)
    placement: TerminalPlacement | None


class SetNetRouteCommand(CommandBase):
    type: typing.Literal["set_net_route"] = "set_net_route"
    net_id: str = pydantic.Field(min_length=1)
    route: NetRoute | None


class SetLayoutDirectionCommand(CommandBase):
    type: typing.Literal["set_layout_direction"] = "set_layout_direction"
    direction: typing.Literal["RIGHT", "DOWN"]


DesignerCommand = typing.Annotated[
    typing.Union[
        AddInstanceCommand,
        UpdateInstanceCommand,
        DuplicateInstancesCommand,
        DeleteInstanceCommand,
        AddTerminalCommand,
        DeleteTerminalCommand,
        CreateNetCommand,
        RenameNetCommand,
        AddNetEndpointCommand,
        RemoveNetEndpointCommand,
        DeleteNetCommand,
        SetNodeGeometryCommand,
        SetTerminalPlacementCommand,
        SetNetRouteCommand,
        SetLayoutDirectionCommand,
    ],
    pydantic.Field(discriminator="type"),
]


class CommandBatch(ContractModel):
    """Ordered, revision-guarded set of proposed commands."""

    batch_id: str = pydantic.Field(min_length=1)
    expected_source_revision_hash: str = pydantic.Field(min_length=1)
    commands: tuple[DesignerCommand, ...] = pydantic.Field(min_length=1)


class ValidationDiagnostic(ContractModel):
    """Machine-addressable validation finding."""

    severity: typing.Literal["info", "warning", "error"]
    code: str = pydantic.Field(min_length=1)
    message: str = pydantic.Field(min_length=1)
    element_id: str | None = None
    command_id: str | None = None


class ChangePreview(ContractModel):
    """Non-persisted result of validating one command batch."""

    batch: CommandBatch
    diagnostics: tuple[ValidationDiagnostic, ...]
    candidate: CircuitGraphSnapshot | None = None


class EditLease(ContractModel):
    """Exclusive edit ownership advertised by the application layer."""

    lease_id: str = pydantic.Field(min_length=1)
    owner_id: str = pydantic.Field(min_length=1)
    owner_kind: typing.Literal["human", "agent"]
    expires_at: str = pydantic.Field(min_length=1)


class AgentProposal(ContractModel):
    """Persistable, whole-batch agent change proposal."""

    proposal_id: str = pydantic.Field(min_length=1)
    status: typing.Literal["pending", "accepted", "rejected", "stale"] = "pending"
    title: str = pydantic.Field(min_length=1)
    batch: CommandBatch
    diagnostics: tuple[ValidationDiagnostic, ...] = ()


class CircuitDesignerProtocol(ContractModel):
    """Schema bundle used to generate language-neutral client contracts."""

    graph: CircuitGraphSnapshot
    catalog: CircuitDesignCatalog
    batch: CommandBatch
    preview: ChangePreview
    lease: EditLease
    proposal: AgentProposal

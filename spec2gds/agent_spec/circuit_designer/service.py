"""Stateful command service shared by human UI and programmatic agents."""

from __future__ import annotations

import copy
import datetime
import json
from pathlib import Path
import secrets
import typing

from spec2gds.agent_spec.circuit_designer.contracts import (
    AddInstanceCommand,
    AddNetEndpointCommand,
    AgentProposal,
    ChangePreview,
    CircuitCapabilities,
    CommandBatch,
    CreateNetCommand,
    DeleteInstanceCommand,
    DeleteNetCommand,
    DiagramLayout,
    DuplicateInstancesCommand,
    EditLease,
    RemoveNetEndpointCommand,
    RenameNetCommand,
    SetLayoutDirectionCommand,
    SetNetRouteCommand,
    SetNodeGeometryCommand,
    SetTerminalPlacementCommand,
    UpdateInstanceCommand,
    ValidationDiagnostic,
)
from spec2gds.agent_spec.circuit_designer.projection import project_design
from spec2gds.agent_spec.spec_format.ir import (
    ConnectionIR,
    DesignIR,
    InstanceIR,
    InterfaceEndpointIR,
    PortEndpointIR,
    SpecRevision,
)
from spec2gds.agent_spec.spec_format.transactions import (
    DeleteConnection,
    DeleteInstance,
    SpecEditTransaction,
    UpsertConnection,
    UpsertInstance,
)


class MutableSpecSession(typing.Protocol):
    """Minimum active-session surface required by the circuit adapter."""

    path: str
    revision: SpecRevision

    def commit_revision(self, revision: SpecRevision) -> None: ...


class CircuitDesignerConflict(ValueError):
    """Revision, lease, or proposal state conflicts."""


class CircuitDesignerSession:
    """Command evaluation, layout sidecar, history, lease, and proposals."""

    def __init__(self, session: MutableSpecSession) -> None:
        self.session = session
        self.layout_path = Path(f"{session.path}.circuit-layout.json")
        self.proposal_path = Path(f"{session.path}.circuit-proposals.json")
        self.layouts = self._load_layouts()
        self.undo_stack: list[tuple[SpecRevision, dict[str, DiagramLayout]]] = []
        self.redo_stack: list[tuple[SpecRevision, dict[str, DiagramLayout]]] = []
        self.history_head_hash = session.revision.source_revision_hash
        self.lease: EditLease | None = None
        self.proposals = self._load_proposals()

    @property
    def capabilities(self) -> CircuitCapabilities:
        return CircuitCapabilities(
            edit_topology=True,
            edit_layout=True,
            replace_component=True,
            edit_instance_details=False,
            submit_agent_proposal=True,
        )

    def graph(self, design_id: str, revision: SpecRevision | None = None, layouts: dict[str, DiagramLayout] | None = None):
        active_revision = revision or self.session.revision
        design = _design(active_revision, design_id)
        layout_source = self.layouts if layouts is None else layouts
        return project_design(
            active_revision,
            design,
            capabilities=self.capabilities,
            layout=layout_source.get(design_id),
        )

    def acquire_lease(self, owner_id: str, owner_kind: typing.Literal["human", "agent"], ttl_seconds: int = 300) -> EditLease:
        current = self.active_lease()
        if current and (current.owner_id != owner_id or current.owner_kind != owner_kind):
            raise CircuitDesignerConflict(f"Circuit is locked by {current.owner_kind} '{current.owner_id}'.")
        expires = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=max(30, min(ttl_seconds, 3600)))
        self.lease = EditLease(
            lease_id=current.lease_id if current else f"lease_{secrets.token_hex(12)}",
            owner_id=owner_id,
            owner_kind=owner_kind,
            expires_at=expires.isoformat(),
        )
        return self.lease

    def active_lease(self) -> EditLease | None:
        if self.lease and datetime.datetime.fromisoformat(self.lease.expires_at) <= datetime.datetime.now(datetime.UTC):
            self.lease = None
        return self.lease

    def release_lease(self, lease_id: str) -> None:
        self._require_lease(lease_id)
        self.lease = None

    def preview(self, batch: CommandBatch) -> ChangePreview:
        revision, layouts, diagnostics = self._evaluate(batch)
        candidate = None
        if not any(item.severity == "error" for item in diagnostics):
            candidate = self.graph(batch.commands[0].design_id, revision, layouts)
        return ChangePreview(batch=batch, diagnostics=tuple(diagnostics), candidate=candidate)

    def apply(self, batch: CommandBatch, lease_id: str) -> ChangePreview:
        self._require_lease(lease_id)
        previous = (self.session.revision, copy.deepcopy(self.layouts))
        revision, layouts, diagnostics = self._evaluate(batch)
        preview = ChangePreview(
            batch=batch,
            diagnostics=tuple(diagnostics),
            candidate=None if any(item.severity == "error" for item in diagnostics) else self.graph(batch.commands[0].design_id, revision, layouts),
        )
        if preview.candidate is None:
            return preview
        if revision.source_revision_hash != self.session.revision.source_revision_hash:
            self.session.commit_revision(revision)
        self.layouts = layouts
        self._save_layouts()
        self.undo_stack.append(previous)
        self.redo_stack.clear()
        self.history_head_hash = self.session.revision.source_revision_hash
        return preview.model_copy(update={"candidate": self.graph(batch.commands[0].design_id)})

    def undo(self, lease_id: str, design_id: str):
        self._require_lease(lease_id)
        self._require_history_head()
        if not self.undo_stack:
            raise CircuitDesignerConflict("Nothing to undo.")
        self.redo_stack.append((self.session.revision, copy.deepcopy(self.layouts)))
        revision, self.layouts = self.undo_stack.pop()
        if revision.source_revision_hash != self.session.revision.source_revision_hash:
            self.session.commit_revision(revision)
        self._save_layouts()
        self.history_head_hash = self.session.revision.source_revision_hash
        return self.graph(design_id)

    def redo(self, lease_id: str, design_id: str):
        self._require_lease(lease_id)
        self._require_history_head()
        if not self.redo_stack:
            raise CircuitDesignerConflict("Nothing to redo.")
        self.undo_stack.append((self.session.revision, copy.deepcopy(self.layouts)))
        revision, self.layouts = self.redo_stack.pop()
        if revision.source_revision_hash != self.session.revision.source_revision_hash:
            self.session.commit_revision(revision)
        self._save_layouts()
        self.history_head_hash = self.session.revision.source_revision_hash
        return self.graph(design_id)

    def history_status(self) -> dict[str, bool]:
        if self.session.revision.source_revision_hash != self.history_head_hash:
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.history_head_hash = self.session.revision.source_revision_hash
        return {"can_undo": bool(self.undo_stack), "can_redo": bool(self.redo_stack)}

    def submit_proposal(self, proposal: AgentProposal) -> AgentProposal:
        if proposal.proposal_id in self.proposals:
            raise CircuitDesignerConflict(f"Proposal already exists: {proposal.proposal_id}")
        preview = self.preview(proposal.batch)
        stored = proposal.model_copy(update={"diagnostics": preview.diagnostics})
        self.proposals[stored.proposal_id] = stored
        self._save_proposals()
        return stored

    def decide_proposal(self, proposal_id: str, decision: typing.Literal["accepted", "rejected"], lease_id: str | None = None) -> AgentProposal:
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)
        if proposal.status != "pending":
            raise CircuitDesignerConflict(f"Proposal is already {proposal.status}.")
        if decision == "accepted":
            if lease_id is None:
                raise CircuitDesignerConflict("An edit lease is required to accept a proposal.")
            result = self.apply(proposal.batch, lease_id)
            if result.candidate is None:
                proposal = proposal.model_copy(update={"status": "stale", "diagnostics": result.diagnostics})
            else:
                proposal = proposal.model_copy(update={"status": "accepted", "diagnostics": result.diagnostics})
        else:
            proposal = proposal.model_copy(update={"status": "rejected"})
        self.proposals[proposal_id] = proposal
        self._save_proposals()
        return proposal

    def _require_lease(self, lease_id: str) -> EditLease:
        lease = self.active_lease()
        if lease is None or lease.lease_id != lease_id:
            raise CircuitDesignerConflict("A valid active edit lease is required.")
        return lease

    def _require_history_head(self) -> None:
        if self.session.revision.source_revision_hash != self.history_head_hash:
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.history_head_hash = self.session.revision.source_revision_hash
            raise CircuitDesignerConflict("History was invalidated by an external source change.")

    def _evaluate(self, batch: CommandBatch) -> tuple[SpecRevision, dict[str, DiagramLayout], list[ValidationDiagnostic]]:
        revision = self.session.revision
        layouts = copy.deepcopy(self.layouts)
        diagnostics: list[ValidationDiagnostic] = []
        if batch.expected_source_revision_hash != revision.source_revision_hash:
            return revision, layouts, [_error("stale_revision", "The source revision changed; refresh before editing.")]
        design_ids = {command.design_id for command in batch.commands}
        if len(design_ids) != 1:
            return revision, layouts, [_error("mixed_design_batch", "One command batch must target exactly one design.")]
        design_id = next(iter(design_ids))
        active_command_id: str | None = None
        try:
            _design(revision, design_id)
            for command in batch.commands:
                active_command_id = command.command_id
                if isinstance(command, (SetNodeGeometryCommand, SetTerminalPlacementCommand, SetNetRouteCommand, SetLayoutDirectionCommand)):
                    layouts[design_id] = _apply_layout(command, self.graph(design_id, revision, layouts), layouts.get(design_id))
                    continue
                operations, layout_update = _source_operations(command, revision, layouts.get(design_id))
                result = SpecEditTransaction(revision.source_revision_hash, tuple(operations)).apply(revision)
                if not result.succeeded or result.revision is None:
                    diagnostics.extend(_error("specir_validation", message, command.command_id) for message in result.diagnostics)
                    break
                revision = result.revision
                if layout_update is not None:
                    layouts[design_id] = layout_update
        except (KeyError, ValueError) as exc:
            diagnostics.append(_error("invalid_command", str(exc), active_command_id))
        return revision, layouts, diagnostics

    def _load_layouts(self) -> dict[str, DiagramLayout]:
        if not self.layout_path.is_file():
            return {}
        try:
            raw = json.loads(self.layout_path.read_text(encoding="utf-8"))
            return {key: DiagramLayout.model_validate(value) for key, value in raw.get("designs", {}).items()}
        except (OSError, ValueError):
            return {}

    def _save_layouts(self) -> None:
        payload = {"format": "circuit-designer-layout-v1", "designs": {key: value.model_dump(mode="json") for key, value in sorted(self.layouts.items())}}
        self.layout_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _load_proposals(self) -> dict[str, AgentProposal]:
        if not self.proposal_path.is_file():
            return {}
        try:
            raw = json.loads(self.proposal_path.read_text(encoding="utf-8"))
            values = (AgentProposal.model_validate(value) for value in raw.get("proposals", []))
            return {value.proposal_id: value for value in values}
        except (OSError, ValueError):
            return {}

    def _save_proposals(self) -> None:
        payload = {"format": "circuit-designer-proposals-v1", "proposals": [value.model_dump(mode="json") for _, value in sorted(self.proposals.items())]}
        self.proposal_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _error(code: str, message: str, command_id: str | None = None) -> ValidationDiagnostic:
    return ValidationDiagnostic(severity="error", code=code, message=message, command_id=command_id)


def _design(revision: SpecRevision, design_id: str) -> DesignIR:
    return typing.cast(DesignIR, _entity(revision, "design", design_id))


def _entity(revision: SpecRevision, kind: str, entity_id: str):
    collections = {"design": revision.designs, "component": revision.components}
    item = next((value for value in collections[kind] if value.ref.entity_id == entity_id), None)
    if item is None:
        raise KeyError(f"Unknown {kind}: {entity_id}")
    return item


def _node_name(node_id: str) -> str:
    if not node_id.startswith("instance:"):
        raise ValueError(f"Invalid instance node ID: {node_id}")
    return node_id.removeprefix("instance:")


def _connection(design: DesignIR, net_id: str) -> ConnectionIR:
    graph = {f"net:{item.kind}:{item.name}": item for item in design.connections}
    if net_id not in graph:
        raise KeyError(f"Unknown net: {net_id}")
    return graph[net_id]


def _connection_from_terminals(revision: SpecRevision, design: DesignIR, name: str, kind: str, terminal_ids: typing.Iterable[str]) -> ConnectionIR:
    graph = project_design(revision, design)
    terminals = {terminal.id: terminal for terminal in graph.terminals}
    interfaces: list[InterfaceEndpointIR] = []
    ports: list[PortEndpointIR] = []
    external: list[str] = []
    hierarchy: list[str] = []
    for terminal_id in terminal_ids:
        terminal = terminals.get(terminal_id)
        if terminal is None:
            raise KeyError(f"Unknown terminal: {terminal_id}")
        if kind == "interface" and terminal.kind not in ("interface", "boundary_interface"):
            raise ValueError("Interface nets may contain only interface terminals.")
        if kind == "ad_hoc" and terminal.kind not in ("port", "boundary_port"):
            raise ValueError("Ad-hoc nets may contain only port terminals.")
        if terminal.node_id:
            instance_name = _node_name(terminal.node_id)
            if kind == "interface":
                interfaces.append(InterfaceEndpointIR(instance_name, terminal.label))
            else:
                ports.append(PortEndpointIR(instance_name, terminal.label))
        elif kind == "interface":
            hierarchy.append(terminal.label)
        else:
            external.append(terminal.label)
    if len(interfaces) + len(ports) + len(external) + len(hierarchy) < 2:
        raise ValueError("A net requires at least two endpoints.")
    return ConnectionIR(name=name, kind=typing.cast(typing.Any, kind), interface_endpoints=tuple(interfaces), port_endpoints=tuple(ports), external_ports=tuple(external), hierarchy_interfaces=tuple(hierarchy))


def _terminal_ids(connection: ConnectionIR) -> list[str]:
    if connection.kind == "interface":
        return [f"instance:{item.instance_name}:interface:{item.interface_name}" for item in connection.interface_endpoints] + [f"boundary:interface:{name}" for name in connection.hierarchy_interfaces]
    return [f"instance:{item.instance_name}:port:{item.port_name}" for item in connection.port_endpoints] + [f"boundary:port:{name}" for name in connection.external_ports]


def _source_operations(command: typing.Any, revision: SpecRevision, layout: DiagramLayout | None):
    design = _design(revision, command.design_id)
    design_ref = design.ref
    next_layout = layout
    if isinstance(command, AddInstanceCommand):
        component = _entity(revision, "component", command.component_id)
        if command.node_id != f"instance:{command.name}":
            raise ValueError("Instance node_id must be 'instance:<name>'.")
        if any(item.name == command.name for item in design.instances):
            raise ValueError(f"Instance already exists: {command.name}")
        return [UpsertInstance(design_ref, InstanceIR(command.name, component.vlnv))], next_layout
    if isinstance(command, UpdateInstanceCommand):
        name = _node_name(command.node_id)
        current = next((item for item in design.instances if item.name == name), None)
        if current is None:
            raise KeyError(f"Unknown instance: {command.node_id}")
        if command.name and command.name != name:
            raise ValueError("Instance rename is deferred; duplicate and delete the instance instead.")
        if command.display_name is not None or command.description is not None or command.configuration_values is not None:
            raise ValueError("The active IP-XACT profile does not persist instance display metadata or configuration values.")
        vlnv = _entity(revision, "component", command.component_id).vlnv if command.component_id else current.component_vlnv
        return [UpsertInstance(design_ref, InstanceIR(name, vlnv))], next_layout
    if isinstance(command, DuplicateInstancesCommand):
        existing = {item.name for item in design.instances}
        operations = []
        geometry = dict(layout.node_geometry) if layout else {}
        for node_id in command.node_ids:
            source_name = _node_name(node_id)
            source = next((item for item in design.instances if item.name == source_name), None)
            if source is None:
                raise KeyError(f"Unknown instance: {node_id}")
            index = 1
            candidate = f"{source_name}_copy"
            while candidate in existing:
                index += 1
                candidate = f"{source_name}_copy{index}"
            existing.add(candidate)
            operations.append(UpsertInstance(design_ref, InstanceIR(candidate, source.component_vlnv)))
            if node_id in geometry:
                value = geometry[node_id]
                geometry[f"instance:{candidate}"] = value.model_copy(update={"x": value.x + command.offset.x, "y": value.y + command.offset.y})
        if layout:
            next_layout = layout.model_copy(update={"node_geometry": geometry})
        return operations, next_layout
    if isinstance(command, DeleteInstanceCommand):
        name = _node_name(command.node_id)
        affected = [item for item in design.connections if name in {endpoint.instance_name for endpoint in (*item.interface_endpoints, *item.port_endpoints)}]
        if affected and not command.cascade:
            raise ValueError("Instance is connected; enable cascade or disconnect it first.")
        operations: list[typing.Any] = []
        for item in affected:
            ids = [value for value in _terminal_ids(item) if not value.startswith(f"instance:{name}:")]
            operations.append(DeleteConnection(design_ref, item.name) if len(ids) < 2 else UpsertConnection(design_ref, _connection_from_terminals(revision, design, item.name, item.kind, ids)))
        operations.append(DeleteInstance(design_ref, name))
        if layout:
            geometry = dict(layout.node_geometry); geometry.pop(command.node_id, None)
            routes = dict(layout.net_routes)
            for item in affected: routes.pop(f"net:{item.kind}:{item.name}", None)
            next_layout = layout.model_copy(update={"node_geometry": geometry, "net_routes": routes})
        return operations, next_layout
    if isinstance(command, CreateNetCommand):
        if command.net_id != f"net:{command.kind}:{command.name}":
            raise ValueError("Net net_id must be 'net:<kind>:<name>'.")
        if any(item.name == command.name for item in design.connections):
            raise ValueError(f"Net already exists: {command.name}")
        connection = _connection_from_terminals(revision, design, command.name, command.kind, command.terminal_ids)
        return [UpsertConnection(design_ref, connection)], next_layout
    if isinstance(command, RenameNetCommand):
        current = _connection(design, command.net_id)
        if any(item.name == command.name for item in design.connections):
            raise ValueError(f"Net already exists: {command.name}")
        renamed = ConnectionIR(command.name, current.kind, current.interface_endpoints, current.port_endpoints, current.external_ports, current.hierarchy_interfaces)
        if layout and command.net_id in layout.net_routes:
            routes = dict(layout.net_routes); routes[f"net:{current.kind}:{command.name}"] = routes.pop(command.net_id)
            next_layout = layout.model_copy(update={"net_routes": routes})
        return [UpsertConnection(design_ref, renamed), DeleteConnection(design_ref, current.name)], next_layout
    if isinstance(command, (AddNetEndpointCommand, RemoveNetEndpointCommand)):
        current = _connection(design, command.net_id)
        ids = _terminal_ids(current)
        if isinstance(command, AddNetEndpointCommand):
            if command.terminal_id in ids:
                raise ValueError("Terminal is already connected to this net.")
            ids.append(command.terminal_id)
        else:
            if command.terminal_id not in ids:
                raise ValueError("Terminal is not connected to this net.")
            ids.remove(command.terminal_id)
        replacement = _connection_from_terminals(revision, design, current.name, current.kind, ids)
        if layout:
            routes = dict(layout.net_routes); routes.pop(command.net_id, None)
            next_layout = layout.model_copy(update={"net_routes": routes})
        return [UpsertConnection(design_ref, replacement)], next_layout
    if isinstance(command, DeleteNetCommand):
        current = _connection(design, command.net_id)
        if layout:
            routes = dict(layout.net_routes); routes.pop(command.net_id, None)
            next_layout = layout.model_copy(update={"net_routes": routes})
        return [DeleteConnection(design_ref, current.name)], next_layout
    raise ValueError(f"Unsupported command type: {command.type}")


def _apply_layout(command: typing.Any, graph: typing.Any, layout: DiagramLayout | None) -> DiagramLayout:
    current = layout or DiagramLayout()
    if isinstance(command, SetNodeGeometryCommand):
        if command.node_id not in {node.id for node in graph.nodes}:
            raise KeyError(f"Unknown node: {command.node_id}")
        values = dict(current.node_geometry); values[command.node_id] = command.geometry
        return current.model_copy(update={"node_geometry": values})
    if isinstance(command, SetTerminalPlacementCommand):
        if command.terminal_id not in {terminal.id for terminal in graph.terminals}:
            raise KeyError(f"Unknown terminal: {command.terminal_id}")
        values = dict(current.terminal_placements); values[command.terminal_id] = command.placement
        return current.model_copy(update={"terminal_placements": values})
    if isinstance(command, SetNetRouteCommand):
        if command.net_id not in {net.id for net in graph.nets}:
            raise KeyError(f"Unknown net: {command.net_id}")
        values = dict(current.net_routes)
        if command.route is None: values.pop(command.net_id, None)
        else: values[command.net_id] = command.route
        return current.model_copy(update={"net_routes": values})
    if isinstance(command, SetLayoutDirectionCommand):
        return current.model_copy(update={"direction": command.direction})
    raise ValueError(f"Unsupported layout command: {command.type}")

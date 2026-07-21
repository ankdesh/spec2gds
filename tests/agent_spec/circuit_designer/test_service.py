"""Mutation, layout, history, lease, and proposal acceptance tests."""

from pathlib import Path

from spec2gds.agent_spec.circuit_designer.contracts import (
    AddNetEndpointCommand,
    AddInstanceCommand,
    AgentProposal,
    CommandBatch,
    CreateNetCommand,
    DeleteNetCommand,
    NetRoute,
    NodeGeometry,
    Point,
    RouteSegment,
    RouteVertex,
    SetNetRouteCommand,
    SetNodeGeometryCommand,
    SetTerminalPlacementCommand,
    TerminalPlacement,
    RenameNetCommand,
    RemoveNetEndpointCommand,
)
from spec2gds.agent_spec.circuit_designer.service import CircuitDesignerSession
from spec2gds.agent_spec.spec_format.samples import write_v1_sample
from spec2gds.agent_spec.spec_format.v1_api import V1Session


def _service(tmp_path: Path) -> CircuitDesignerSession:
    path = tmp_path / "circuit.spec"
    write_v1_sample(path)
    return CircuitDesignerSession(V1Session(str(path)))


def test_layout_commands_require_a_lease_persist_and_support_history(tmp_path: Path) -> None:
    service = _service(tmp_path)
    lease = service.acquire_lease("browser", "human")
    revision_hash = service.session.revision.source_revision_hash
    batch = CommandBatch(
        batch_id="layout_1",
        expected_source_revision_hash=revision_hash,
        commands=(
            SetNodeGeometryCommand(
                command_id="move_1",
                design_id="design_subsystem_internal",
                node_id="instance:leaf0",
                geometry=NodeGeometry(x=40, y=60, width=180, height=84),
            ),
        ),
    )

    preview = service.preview(batch)
    assert preview.candidate is not None
    assert preview.candidate.layout.node_geometry["instance:leaf0"].x == 40
    applied = service.apply(batch, lease.lease_id)
    assert applied.candidate.layout.node_geometry["instance:leaf0"].y == 60
    assert service.session.revision.source_revision_hash == revision_hash
    assert service.layout_path.is_file()

    undone = service.undo(lease.lease_id, "design_subsystem_internal")
    assert undone.layout is None
    redone = service.redo(lease.lease_id, "design_subsystem_internal")
    assert redone.layout.node_geometry["instance:leaf0"].x == 40


def test_layout_changes_invalidate_attached_routes_until_batch_restores_them(tmp_path: Path) -> None:
    service = _service(tmp_path)
    lease = service.acquire_lease("browser", "human")
    design_id = "design_subsystem_internal"
    net_id = "net:interface:link0"
    route = NetRoute(
        vertices=(
            RouteVertex(id="a", kind="endpoint", terminal_id="instance:leaf0:interface:link", point=Point(x=100, y=80)),
            RouteVertex(id="b", kind="endpoint", terminal_id="instance:sink0:interface:link", point=Point(x=300, y=80)),
        ),
        segments=(RouteSegment(id="segment:a:b", from_vertex="a", to_vertex="b", locked=True),),
    )

    def apply(commands, batch_id):
        result = service.apply(CommandBatch(
            batch_id=batch_id,
            expected_source_revision_hash=service.session.revision.source_revision_hash,
            commands=commands,
        ), lease.lease_id)
        assert result.candidate is not None, result.diagnostics
        return result.candidate.layout

    layout = apply((SetNetRouteCommand(command_id="route", design_id=design_id, net_id=net_id, route=route),), "route")
    assert layout.net_routes[net_id].segments[0].locked is True

    layout = apply((SetNodeGeometryCommand(
        command_id="move",
        design_id=design_id,
        node_id="instance:leaf0",
        geometry=NodeGeometry(x=40, y=60, width=180, height=84),
    ),), "move")
    assert net_id not in layout.net_routes

    layout = apply((
        SetNodeGeometryCommand(
            command_id="move_again",
            design_id=design_id,
            node_id="instance:leaf0",
            geometry=NodeGeometry(x=80, y=60, width=180, height=84),
        ),
        SetNetRouteCommand(command_id="restore", design_id=design_id, net_id=net_id, route=route),
    ), "move_and_restore")
    assert layout.net_routes[net_id] == route


def test_terminal_placement_can_be_locked_and_restored_to_automatic(tmp_path: Path) -> None:
    service = _service(tmp_path)
    lease = service.acquire_lease("browser", "human")
    design_id = "design_subsystem_internal"
    terminal_id = "instance:leaf0:interface:link"

    def apply(placement, command_id):
        result = service.apply(CommandBatch(
            batch_id=f"batch_{command_id}",
            expected_source_revision_hash=service.session.revision.source_revision_hash,
            commands=(SetTerminalPlacementCommand(
                command_id=command_id,
                design_id=design_id,
                terminal_id=terminal_id,
                placement=placement,
            ),),
        ), lease.lease_id)
        assert result.candidate is not None, result.diagnostics
        return result.candidate.layout

    layout = apply(TerminalPlacement(side="NORTH", order=1, locked=True), "place")
    assert layout.terminal_placements[terminal_id].side == "NORTH"
    assert layout.terminal_placements[terminal_id].locked is True

    layout = apply(None, "automatic")
    assert terminal_id not in layout.terminal_placements


def test_topology_batch_commits_through_specir_and_undoes(tmp_path: Path) -> None:
    service = _service(tmp_path)
    lease = service.acquire_lease("browser", "human")
    before = service.session.revision.source_revision_hash
    batch = CommandBatch(
        batch_id="topology_1",
        expected_source_revision_hash=before,
        commands=(
            AddInstanceCommand(
                command_id="add_1",
                design_id="design_top_b",
                node_id="instance:leaf2",
                name="leaf2",
                component_id="component_leaf",
            ),
        ),
    )

    applied = service.apply(batch, lease.lease_id)
    assert applied.candidate is not None
    assert {node.label for node in applied.candidate.nodes} == {"leaf1", "leaf2"}
    assert service.session.revision.source_revision_hash != before

    service.undo(lease.lease_id, "design_top_b")
    assert {node.label for node in service.graph("design_top_b").nodes} == {"leaf1"}
    service.redo(lease.lease_id, "design_top_b")
    assert {node.label for node in service.graph("design_top_b").nodes} == {"leaf1", "leaf2"}


def test_agent_proposal_uses_same_batch_and_becomes_stale_on_revision_change(tmp_path: Path) -> None:
    service = _service(tmp_path)
    lease = service.acquire_lease("agent-review", "human")
    batch = CommandBatch(
        batch_id="proposal_batch",
        expected_source_revision_hash=service.session.revision.source_revision_hash,
        commands=(
            AddInstanceCommand(
                command_id="proposal_add",
                design_id="design_top_b",
                node_id="instance:leaf2",
                name="leaf2",
                component_id="component_leaf",
            ),
        ),
    )
    proposal = service.submit_proposal(AgentProposal(proposal_id="proposal_1", title="Add leaf", batch=batch))
    assert proposal.status == "pending"
    reopened = CircuitDesignerSession(V1Session(service.session.path))
    assert reopened.proposals["proposal_1"].title == "Add leaf"
    accepted = service.decide_proposal("proposal_1", "accepted", lease.lease_id)
    assert accepted.status == "accepted"


def test_net_command_lifecycle_uses_profiled_ad_hoc_connections(tmp_path: Path) -> None:
    service = _service(tmp_path)
    lease = service.acquire_lease("browser", "human")
    design_id = "design_subsystem_internal"

    def apply(command):
        result = service.apply(CommandBatch(
            batch_id=f"batch_{command.command_id}",
            expected_source_revision_hash=service.session.revision.source_revision_hash,
            commands=(command,),
        ), lease.lease_id)
        assert result.candidate is not None, result.diagnostics

    apply(CreateNetCommand(command_id="create", design_id=design_id, net_id="net:ad_hoc:irq_bus", name="irq_bus", kind="ad_hoc", terminal_ids=("instance:leaf0:port:irq", "instance:sink0:port:payload_in")))
    apply(AddNetEndpointCommand(command_id="extend", design_id=design_id, net_id="net:ad_hoc:irq_bus", terminal_id="instance:leaf0:port:irq_in"))
    apply(RemoveNetEndpointCommand(command_id="remove", design_id=design_id, net_id="net:ad_hoc:irq_bus", terminal_id="instance:leaf0:port:irq_in"))
    apply(RenameNetCommand(command_id="rename", design_id=design_id, net_id="net:ad_hoc:irq_bus", name="interrupt"))
    assert "net:ad_hoc:interrupt" in {net.id for net in service.graph(design_id).nets}
    apply(DeleteNetCommand(command_id="delete", design_id=design_id, net_id="net:ad_hoc:interrupt"))
    assert "net:ad_hoc:interrupt" not in {net.id for net in service.graph(design_id).nets}

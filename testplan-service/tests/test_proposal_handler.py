"""Direct tests for AI Assistant proposal preview and application handling."""

from __future__ import annotations

import pytest
from testplan_service.exceptions import ProposalValidationError
from testplan_service.models.operations import PlanOperation, ProposalArtifact
from testplan_service.models.testplan import TestPlanDocument
from testplan_service.service.manager import TestPlanManager
from testplan_service.service.proposal_handler import ProposalHandler


def test_preview_valid_proposal(
    proposal_handler: ProposalHandler,
    sample_plan: TestPlanDocument,
) -> None:
    proposal = ProposalArtifact(
        proposal_id="prop_01",
        document_id=sample_plan.id,
        base_revision=sample_plan.revision,
        title="Add Reset Testpoint",
        summary="Adds dedicated reset stimulus check",
        operations=[
            PlanOperation(
                action="add_node",
                parent_id="grp_arithmetic",
                node_data={
                    "id": "tc_reset_glitch",
                    "title": "Reset Glitch Filter",
                    "kind": "testcase",
                    "category": "reset_behavior",
                },
            ),
            PlanOperation(
                action="update_node",
                node_id="tc_add_basic",
                node_data={"priority": "critical"},
            ),
        ],
    )

    result = proposal_handler.preview(proposal)
    assert result.valid is True
    assert result.nodes_added == 1
    assert result.nodes_modified == 1
    assert result.nodes_deleted == 0
    assert len(result.summary_diff) == 2


def test_preview_proposal_nonexistent_doc(proposal_handler: ProposalHandler) -> None:
    proposal = ProposalArtifact(
        proposal_id="prop_err",
        document_id="nonexistent_plan",
        base_revision=1,
        title="Err",
        summary="Err",
        operations=[],
    )
    result = proposal_handler.preview(proposal)
    assert result.valid is False
    assert any("does not exist" in d for d in result.diagnostics)


def test_preview_proposal_invalid_operations(
    proposal_handler: ProposalHandler,
    sample_plan: TestPlanDocument,
) -> None:
    proposal = ProposalArtifact(
        proposal_id="prop_inv",
        document_id=sample_plan.id,
        base_revision=sample_plan.revision,
        title="Invalid Ops",
        summary="Testing errors",
        operations=[
            PlanOperation(
                action="add_node",
                parent_id="nonexistent_parent",
                node_data={"id": "tc_new", "title": "Orphan Test"},
            ),
            PlanOperation(
                action="update_node",
                node_id="nonexistent_node",
                node_data={"title": "No such node"},
            ),
        ],
    )
    result = proposal_handler.preview(proposal)
    assert result.valid is False
    assert any("Parent 'nonexistent_parent' does not exist" in d for d in result.diagnostics)
    assert any("Node 'nonexistent_node' does not exist" in d for d in result.diagnostics)


def test_apply_valid_proposal(
    proposal_handler: ProposalHandler,
    manager: TestPlanManager,
    sample_plan: TestPlanDocument,
) -> None:
    proposal = ProposalArtifact(
        proposal_id="prop_apply",
        document_id=sample_plan.id,
        base_revision=sample_plan.revision,
        title="Apply Changes",
        summary="Add node and update priority",
        operations=[
            PlanOperation(
                action="add_node",
                parent_id="grp_arithmetic",
                node_data={
                    "id": "tc_applied_test",
                    "title": "Newly Applied Test",
                    "kind": "testcase",
                },
            )
        ],
    )

    prev_rev = sample_plan.revision
    res = proposal_handler.apply(proposal)
    assert res.applied is True
    assert res.previous_revision == prev_rev
    assert res.new_revision > prev_rev

    # Verify node exists in document
    node = manager.get_node(sample_plan.id, "tc_applied_test")
    assert node.title == "Newly Applied Test"


def test_apply_invalid_proposal_raises(
    proposal_handler: ProposalHandler,
    sample_plan: TestPlanDocument,
) -> None:
    proposal = ProposalArtifact(
        proposal_id="prop_fail",
        document_id=sample_plan.id,
        base_revision=sample_plan.revision,
        title="Failing Proposal",
        summary="Will fail",
        operations=[
            PlanOperation(
                action="add_node",
                parent_id="nonexistent_parent_id",
                node_data={"id": "bad_node", "title": "Bad"},
            )
        ],
    )
    with pytest.raises(ProposalValidationError):
        proposal_handler.apply(proposal)

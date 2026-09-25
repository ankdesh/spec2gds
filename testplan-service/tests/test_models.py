"""Direct tests for Testplan domain models, validation, and summary metrics."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from testplan_service.models.enums import (
    CoverageCategory,
    NodeKind,
    NodePriority,
    NodeStatus,
    VerificationMethodology,
    VerificationStage,
)
from testplan_service.models.node import TestPlanNode
from testplan_service.models.operations import PlanOperation, ProposalArtifact
from testplan_service.models.summary import TestPlanSummary
from testplan_service.models.testplan import TestPlanDocument


def test_node_creation_and_defaults() -> None:
    node = TestPlanNode(id="node_1", title="Test Node")
    assert node.id == "node_1"
    assert node.title == "Test Node"
    assert node.kind == NodeKind.TESTCASE
    assert node.category == CoverageCategory.GENERAL
    assert node.status == NodeStatus.PLANNED
    assert node.priority == NodePriority.MEDIUM
    assert node.stage == VerificationStage.V1
    assert node.methodology == VerificationMethodology.DIRECTED
    assert node.parent_id is None
    assert node.coverage_bins == []
    assert node.children == []


def test_node_validation_errors() -> None:
    # Empty ID should fail validation
    with pytest.raises(ValidationError):
        TestPlanNode(id="", title="Invalid")

    # Extra disallowed field should fail validation (extra='forbid')
    with pytest.raises(ValidationError):
        TestPlanNode.model_validate({"id": "n1", "title": "T1", "unexpected_field": 123})


def test_document_tree_building() -> None:
    doc = TestPlanDocument(id="doc_1", name="Doc 1")
    root_group = TestPlanNode(id="root_grp", title="Root Group", kind=NodeKind.GROUP)
    child_feat = TestPlanNode(
        id="child_feat",
        parent_id="root_grp",
        title="Child Feature",
        kind=NodeKind.FEATURE,
        order=0,
    )
    leaf_tc = TestPlanNode(
        id="leaf_tc",
        parent_id="child_feat",
        title="Leaf TestCase",
        kind=NodeKind.TESTCASE,
        order=0,
    )
    doc.nodes = {
        "root_grp": root_group,
        "child_feat": child_feat,
        "leaf_tc": leaf_tc,
    }

    tree = doc.build_tree()
    assert len(tree) == 1
    assert tree[0].id == "root_grp"
    assert len(tree[0].children) == 1
    assert tree[0].children[0].id == "child_feat"
    assert len(tree[0].children[0].children) == 1
    assert tree[0].children[0].children[0].id == "leaf_tc"


def test_document_depth_calculation() -> None:
    doc = TestPlanDocument(id="doc_depth", name="Doc Depth")
    doc.nodes = {
        "n0": TestPlanNode(id="n0", title="Root"),
        "n1": TestPlanNode(id="n1", parent_id="n0", title="Level 1"),
        "n2": TestPlanNode(id="n2", parent_id="n1", title="Level 2"),
    }
    assert doc.get_node_depth("n0") == 0
    assert doc.get_node_depth("n1") == 1
    assert doc.get_node_depth("n2") == 2


def test_summary_metrics_aggregation() -> None:
    doc = TestPlanDocument(id="doc_sum", name="Doc Summary")
    doc.nodes = {
        "tc_pass": TestPlanNode(
            id="tc_pass",
            title="Passing Test",
            kind=NodeKind.TESTCASE,
            status=NodeStatus.PASSED,
            category=CoverageCategory.PORT_BOUNDARY,
            coverage_bins=["boundary:a:min", "boundary:a:max"],
        ),
        "tc_fail": TestPlanNode(
            id="tc_fail",
            title="Failing Test",
            kind=NodeKind.TESTCASE,
            status=NodeStatus.FAILED,
            category=CoverageCategory.PORT_BOUNDARY,
            coverage_bins=["boundary:b:zero"],
        ),
        "tc_planned": TestPlanNode(
            id="tc_planned",
            title="Planned Test",
            kind=NodeKind.TESTCASE,
            status=NodeStatus.PLANNED,
            category=CoverageCategory.RESET_BEHAVIOR,
            coverage_bins=["reset:rst_n"],
        ),
        "grp": TestPlanNode(
            id="grp",
            title="Group",
            kind=NodeKind.GROUP,
            status=NodeStatus.DRAFT,
        ),
    }

    summary = TestPlanSummary.from_document(doc)
    assert summary.total_nodes == 4
    # 3 testcases: 1 passed, 1 failed, 1 planned -> pass rate = 1/3 = 33.3%
    assert summary.pass_rate_percent == 33.3
    # completed = passed (1) + failed (1) = 2/3 = 66.7%
    assert summary.completion_rate_percent == 66.7
    assert summary.total_coverage_bins == 4
    assert sorted(summary.unique_coverage_bins) == [
        "boundary:a:max",
        "boundary:a:min",
        "boundary:b:zero",
        "reset:rst_n",
    ]
    assert summary.nodes_by_kind["testcase"] == 3
    assert summary.nodes_by_kind["group"] == 1
    assert summary.nodes_by_category["port_boundary"] == 2
    assert summary.nodes_by_category["reset_behavior"] == 1


def test_proposal_artifact_model() -> None:
    op = PlanOperation(
        action="add_node",
        parent_id="grp_1",
        node_data={"id": "tc_new", "title": "Proposed Test"},
    )
    proposal = ProposalArtifact(
        proposal_id="prop_01",
        document_id="doc_01",
        base_revision=1,
        title="Add Edge Tests",
        summary="Expanding testbench with edge cases",
        operations=[op],
    )
    assert proposal.proposal_id == "prop_01"
    assert len(proposal.operations) == 1
    assert proposal.operations[0].action == "add_node"

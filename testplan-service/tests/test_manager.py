"""Direct unit tests for TestPlanManager business logic and tree operations."""

from __future__ import annotations

import pytest
from testplan_service.exceptions import (
    CycleDetectedError,
    DuplicateNodeError,
    NodeNotFoundError,
    TestPlanAlreadyExistsError,
    TestPlanNotFoundError,
)
from testplan_service.models.enums import NodeKind, NodeStatus
from testplan_service.models.node import TestPlanNode
from testplan_service.models.operations import PlanOperation
from testplan_service.service.manager import TestPlanManager


def test_create_and_get_plan(manager: TestPlanManager) -> None:
    doc = manager.create_plan(
        plan_id="plan_core",
        name="Core Plan",
        description="Core testbench plan",
        target_design="core_top",
    )
    assert doc.id == "plan_core"
    assert doc.name == "Core Plan"
    assert doc.revision == 1

    fetched = manager.get_plan("plan_core")
    assert fetched.id == "plan_core"
    assert fetched.name == "Core Plan"

    with pytest.raises(TestPlanAlreadyExistsError):
        manager.create_plan("plan_core", "Duplicate")

    with pytest.raises(TestPlanNotFoundError):
        manager.get_plan("nonexistent_plan")


def test_list_and_filter_plans(manager: TestPlanManager) -> None:
    manager.create_plan("p1", "Plan 1", target_design="uart", tags=["serial"])
    manager.create_plan("p2", "Plan 2", target_design="spi", tags=["serial"])
    manager.create_plan("p3", "Plan 3", target_design="uart", tags=["network"])

    all_plans = manager.list_plans()
    assert len(all_plans) == 3

    uart_plans = manager.list_plans(target_design="uart")
    assert len(uart_plans) == 2
    assert {p.id for p in uart_plans} == {"p1", "p3"}

    serial_plans = manager.list_plans(tag="serial")
    assert len(serial_plans) == 2
    assert {p.id for p in serial_plans} == {"p1", "p2"}


def test_update_and_clone_plan(manager: TestPlanManager) -> None:
    doc = manager.create_plan("p_orig", "Original Title", version="1.0.0")
    assert doc.id == "p_orig"
    updated = manager.update_plan("p_orig", name="New Title", version="1.1.0")
    assert updated.name == "New Title"
    assert updated.version == "1.1.0"
    assert updated.revision == 2

    cloned = manager.clone_plan("p_orig", "p_clone", "Cloned Plan")
    assert cloned.id == "p_clone"
    assert cloned.name == "Cloned Plan"
    assert cloned.version == "1.1.0"
    assert cloned.revision == 1


def test_delete_plan(manager: TestPlanManager) -> None:
    manager.create_plan("to_del", "To Delete")
    manager.delete_plan("to_del")
    with pytest.raises(TestPlanNotFoundError):
        manager.get_plan("to_del")

    with pytest.raises(TestPlanNotFoundError):
        manager.delete_plan("to_del")


def test_add_and_get_node(manager: TestPlanManager) -> None:
    doc = manager.create_plan("doc_node", "Node Plan")
    grp = TestPlanNode(id="grp1", title="Group 1", kind=NodeKind.GROUP)
    manager.add_node(doc.id, grp)

    tc = TestPlanNode(id="tc1", parent_id="grp1", title="Test 1")
    manager.add_node(doc.id, tc)

    fetched_tc = manager.get_node(doc.id, "tc1")
    assert fetched_tc.title == "Test 1"
    assert fetched_tc.parent_id == "grp1"

    # Duplicate node in same plan
    with pytest.raises(DuplicateNodeError):
        manager.add_node(doc.id, TestPlanNode(id="tc1", title="Duplicate"))

    # Parent does not exist
    with pytest.raises(NodeNotFoundError):
        manager.add_node(doc.id, TestPlanNode(id="tc_orphan", parent_id="no_such_parent", title="Orphan"))


def test_update_node(manager: TestPlanManager) -> None:
    doc = manager.create_plan("doc_update", "Update Plan")
    node = TestPlanNode(id="n1", title="Initial", status=NodeStatus.PLANNED)
    manager.add_node(doc.id, node)

    updated = manager.update_node(doc.id, "n1", {"title": "Updated", "status": "passed"})
    assert updated.title == "Updated"
    assert updated.status == NodeStatus.PASSED


def test_delete_node_cascade(manager: TestPlanManager) -> None:
    doc = manager.create_plan("doc_del_cascade", "Delete Cascade")
    manager.add_node(doc.id, TestPlanNode(id="parent", title="Parent", kind=NodeKind.GROUP))
    manager.add_node(doc.id, TestPlanNode(id="child1", parent_id="parent", title="Child 1"))
    manager.add_node(doc.id, TestPlanNode(id="child2", parent_id="parent", title="Child 2"))
    manager.add_node(doc.id, TestPlanNode(id="grandchild", parent_id="child1", title="Grandchild"))

    deleted = manager.delete_node(doc.id, "parent", cascade=True)
    assert set(deleted) == {"parent", "child1", "child2", "grandchild"}

    plan = manager.get_plan(doc.id)
    assert len(plan.nodes) == 0


def test_delete_node_without_cascade(manager: TestPlanManager) -> None:
    doc = manager.create_plan("doc_del_nocascade", "Delete No Cascade")
    manager.add_node(doc.id, TestPlanNode(id="gp", title="Grandparent"))
    manager.add_node(doc.id, TestPlanNode(id="parent", parent_id="gp", title="Parent"))
    manager.add_node(doc.id, TestPlanNode(id="child", parent_id="parent", title="Child"))

    deleted = manager.delete_node(doc.id, "parent", cascade=False)
    assert deleted == ["parent"]

    child = manager.get_node(doc.id, "child")
    # Child should have been re-parented to grandparent 'gp'
    assert child.parent_id == "gp"


def test_move_node_and_cycle_prevention(manager: TestPlanManager) -> None:
    doc = manager.create_plan("doc_move", "Move Plan")
    manager.add_node(doc.id, TestPlanNode(id="a", title="Node A"))
    manager.add_node(doc.id, TestPlanNode(id="b", parent_id="a", title="Node B"))
    manager.add_node(doc.id, TestPlanNode(id="c", parent_id="b", title="Node C"))

    # Moving a node under itself is a cycle
    with pytest.raises(CycleDetectedError):
        manager.move_node(doc.id, "a", target_parent_id="a")

    # Moving node A under its child B or grandchild C is a cycle
    with pytest.raises(CycleDetectedError):
        manager.move_node(doc.id, "a", target_parent_id="b")
    with pytest.raises(CycleDetectedError):
        manager.move_node(doc.id, "a", target_parent_id="c")

    # Valid move: moving C under A directly
    moved = manager.move_node(doc.id, "c", target_parent_id="a", target_order=5)
    assert moved.parent_id == "a"
    assert moved.order == 5


def test_execute_batch_operations(manager: TestPlanManager) -> None:
    doc = manager.create_plan("doc_batch", "Batch Plan")
    ops = [
        PlanOperation(
            action="add_node",
            node_data={"id": "grp1", "title": "Group 1", "kind": "group"},
        ),
        PlanOperation(
            action="add_node",
            parent_id="grp1",
            node_data={"id": "tc1", "title": "Test 1", "kind": "testcase"},
        ),
        PlanOperation(
            action="update_node",
            node_id="tc1",
            node_data={"status": "passed"},
        ),
    ]

    log = manager.execute_batch(doc.id, ops)
    assert len(log) == 3

    plan = manager.get_plan(doc.id)
    assert len(plan.nodes) == 2
    assert plan.nodes["tc1"].status == NodeStatus.PASSED

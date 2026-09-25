"""Direct tests for hierarchical node REST API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_api_node_crud_lifecycle(client: TestClient) -> None:
    client.post("/api/v1/testplans", json={"id": "node_plan", "name": "Node Plan"})

    # Add Root Group
    res_grp = client.post(
        "/api/v1/testplans/node_plan/nodes",
        json={"id": "grp_main", "title": "Main Group", "kind": "group"},
    )
    assert res_grp.status_code == 201
    assert res_grp.json()["id"] == "grp_main"

    # Add Child TestCase
    res_tc = client.post(
        "/api/v1/testplans/node_plan/nodes",
        json={
            "id": "tc_01",
            "parent_id": "grp_main",
            "title": "Test 01",
            "kind": "testcase",
            "category": "port_boundary",
            "status": "planned",
        },
    )
    assert res_tc.status_code == 201
    assert res_tc.json()["parent_id"] == "grp_main"

    # Get node
    get_res = client.get("/api/v1/testplans/node_plan/nodes/tc_01")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Test 01"

    # Update node
    up_res = client.put(
        "/api/v1/testplans/node_plan/nodes/tc_01",
        json={"status": "passed", "title": "Test 01 (Passed)"},
    )
    assert up_res.status_code == 200
    assert up_res.json()["status"] == "passed"
    assert up_res.json()["title"] == "Test 01 (Passed)"

    # Delete node
    del_res = client.delete("/api/v1/testplans/node_plan/nodes/tc_01")
    assert del_res.status_code == 200
    assert del_res.json()["count"] == 1


def test_api_move_node_and_cycle_error(client: TestClient) -> None:
    client.post("/api/v1/testplans", json={"id": "cycle_plan", "name": "Cycle Plan"})
    client.post("/api/v1/testplans/cycle_plan/nodes", json={"id": "n_a", "title": "Node A"})
    client.post(
        "/api/v1/testplans/cycle_plan/nodes",
        json={"id": "n_b", "parent_id": "n_a", "title": "Node B"},
    )

    # Valid move
    move_res = client.post(
        "/api/v1/testplans/cycle_plan/nodes/n_b/move",
        json={"target_parent_id": None, "target_order": 1},
    )
    assert move_res.status_code == 200
    assert move_res.json()["parent_id"] is None

    # Put B under A again
    client.post(
        "/api/v1/testplans/cycle_plan/nodes/n_b/move",
        json={"target_parent_id": "n_a"},
    )

    # Attempt cycle: moving A under B should return 422 CycleDetected
    cycle_res = client.post(
        "/api/v1/testplans/cycle_plan/nodes/n_a/move",
        json={"target_parent_id": "n_b"},
    )
    assert cycle_res.status_code == 422
    assert cycle_res.json()["error"] == "CycleDetected"


def test_api_batch_operations(client: TestClient) -> None:
    client.post("/api/v1/testplans", json={"id": "batch_plan", "name": "Batch Plan"})
    batch_payload = {
        "operations": [
            {
                "action": "add_node",
                "node_data": {"id": "g1", "title": "Batch Group 1", "kind": "group"},
            },
            {
                "action": "add_node",
                "parent_id": "g1",
                "node_data": {"id": "tc1", "title": "Batch TC 1", "kind": "testcase"},
            },
        ]
    }
    res = client.post("/api/v1/testplans/batch_plan/batch", json=batch_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["applied_operations"] == 2

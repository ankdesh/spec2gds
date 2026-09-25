"""Direct tests for Testplan document REST API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_api_create_and_get_testplan(client: TestClient) -> None:
    payload = {
        "id": "api_plan_1",
        "name": "API Test Plan",
        "description": "Created via API",
        "target_design": "spi_master",
        "tags": ["spi", "controller"],
    }
    res = client.post("/api/v1/testplans", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["id"] == "api_plan_1"
    assert created["name"] == "API Test Plan"
    assert created["revision"] == 1

    # Fetch
    get_res = client.get("/api/v1/testplans/api_plan_1")
    assert get_res.status_code == 200
    assert get_res.json()["target_design"] == "spi_master"


def test_api_duplicate_testplan_conflict(client: TestClient) -> None:
    client.post("/api/v1/testplans", json={"id": "dupe", "name": "Dupe 1"})
    res = client.post("/api/v1/testplans", json={"id": "dupe", "name": "Dupe 2"})
    assert res.status_code == 409
    assert res.json()["error"] == "TestPlanAlreadyExists"


def test_api_update_testplan(client: TestClient) -> None:
    client.post("/api/v1/testplans", json={"id": "to_up", "name": "Initial Name"})
    res = client.put("/api/v1/testplans/to_up", json={"name": "Updated Name", "version": "2.0.0"})
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Updated Name"
    assert data["version"] == "2.0.0"
    assert data["revision"] == 2


def test_api_delete_testplan(client: TestClient) -> None:
    client.post("/api/v1/testplans", json={"id": "to_del", "name": "Del"})
    del_res = client.delete("/api/v1/testplans/to_del")
    assert del_res.status_code == 204

    get_res = client.get("/api/v1/testplans/to_del")
    assert get_res.status_code == 404
    assert get_res.json()["error"] == "TestPlanNotFound"


def test_api_clone_testplan(client: TestClient) -> None:
    client.post("/api/v1/testplans", json={"id": "base_plan", "name": "Base"})
    res = client.post(
        "/api/v1/testplans/base_plan/clone",
        json={"new_id": "cloned_plan", "new_name": "Cloned"},
    )
    assert res.status_code == 201
    assert res.json()["id"] == "cloned_plan"


def test_api_summary_and_tree(client: TestClient) -> None:
    client.post("/api/v1/testplans", json={"id": "sum_plan", "name": "Sum Plan"})
    # Summary
    sum_res = client.get("/api/v1/testplans/sum_plan/summary")
    assert sum_res.status_code == 200
    assert sum_res.json()["total_nodes"] == 0

    # Tree
    tree_res = client.get("/api/v1/testplans/sum_plan/tree")
    assert tree_res.status_code == 200
    assert tree_res.json() == []

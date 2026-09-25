"""Direct tests for export and import REST API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_api_export_markdown_and_json(client: TestClient) -> None:
    # Create testplan
    client.post(
        "/api/v1/testplans",
        json={"id": "exp_plan", "name": "Export Plan", "target_design": "top"},
    )
    client.post(
        "/api/v1/testplans/exp_plan/nodes",
        json={"id": "tc_exp", "title": "Export TC", "category": "reset_behavior"},
    )

    # Markdown export
    md_res = client.get("/api/v1/testplans/exp_plan/export/markdown")
    assert md_res.status_code == 200
    assert "text/markdown" in md_res.headers["content-type"]
    assert "# Testplan: Export Plan" in md_res.text
    assert "[TESTCASE] Export TC" in md_res.text

    # JSON export
    json_res = client.get("/api/v1/testplans/exp_plan/export/json")
    assert json_res.status_code == 200
    assert json_res.json()["id"] == "exp_plan"
    assert "tc_exp" in json_res.json()["nodes"]


def test_api_import_json(client: TestClient) -> None:
    import_payload = {
        "id": "imported_plan",
        "name": "Imported Testplan",
        "target_design": "imported_core",
        "version": "1.0.0",
        "nodes": {
            "imp_grp": {
                "id": "imp_grp",
                "parent_id": None,
                "title": "Imported Group",
                "kind": "group",
                "category": "functional_mode",
            },
            "imp_tc": {
                "id": "imp_tc",
                "parent_id": "imp_grp",
                "title": "Imported TC",
                "kind": "testcase",
                "category": "port_boundary",
            },
        },
    }

    res = client.post("/api/v1/testplans/import", json=import_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "imported_plan"
    assert len(data["nodes"]) == 2
    assert data["nodes"]["imp_tc"]["parent_id"] == "imp_grp"

"""Direct tests for AI Assistant contract compatibility endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_api_health_and_capabilities(client: TestClient) -> None:
    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"

    cap_res = client.get("/capabilities")
    assert cap_res.status_code == 200
    caps = cap_res.json()["capabilities"]
    assert "hierarchical_testplan" in caps
    assert "coverage_taxonomy" in caps


def test_api_documents_discovery(client: TestClient) -> None:
    client.post(
        "/api/v1/testplans",
        json={"id": "doc_disc", "name": "Discovery Doc", "target_design": "uart"},
    )
    res = client.get("/documents")
    assert res.status_code == 200
    docs = res.json()["documents"]
    assert any(d["document_id"] == "doc_disc" for d in docs)


def test_api_assistant_context(client: TestClient) -> None:
    client.post(
        "/api/v1/testplans",
        json={"id": "doc_ctx", "name": "Context Doc", "target_design": "alu"},
    )
    client.post(
        "/api/v1/testplans/doc_ctx/nodes",
        json={"id": "tc_sample", "title": "Sample TC", "category": "port_boundary"},
    )

    res = client.get("/assistant/context?document_id=doc_ctx")
    assert res.status_code == 200
    data = res.json()
    assert data["document_id"] == "doc_ctx"
    assert data["title"] == "Context Doc"
    assert "markdown_overview" in data
    assert "hierarchy_tree" in data
    assert len(data["hierarchy_tree"]) == 1
    assert "proposal_instructions" in data


def test_api_proposals_preview_and_apply(client: TestClient) -> None:
    client.post(
        "/api/v1/testplans",
        json={"id": "doc_prop", "name": "Proposal Doc", "target_design": "core"},
    )

    proposal = {
        "proposal_id": "prop_test_01",
        "document_id": "doc_prop",
        "base_revision": 1,
        "title": "Add Boundary Tests",
        "summary": "AI proposed boundary coverage items",
        "rationale": "High priority boundary check",
        "operations": [
            {
                "action": "add_node",
                "parent_id": None,
                "node_data": {
                    "id": "tc_ai_bound",
                    "title": "AI Boundary Test",
                    "kind": "testcase",
                    "category": "port_boundary",
                },
            }
        ],
    }

    # Preview
    preview_res = client.post("/assistant/proposals/preview", json=proposal)
    assert preview_res.status_code == 200
    preview_data = preview_res.json()
    assert preview_data["valid"] is True
    assert preview_data["nodes_added"] == 1

    # Apply
    apply_res = client.post("/assistant/proposals/apply", json=proposal)
    assert apply_res.status_code == 200
    apply_data = apply_res.json()
    assert apply_data["applied"] is True
    assert apply_data["new_revision"] == 2

    # Verify node in plan
    get_node = client.get("/api/v1/testplans/doc_prop/nodes/tc_ai_bound")
    assert get_node.status_code == 200
    assert get_node.json()["title"] == "AI Boundary Test"

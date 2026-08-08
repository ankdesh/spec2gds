from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from spec2gds_assistant.agents.circuit_editor import CircuitEditingAgent
from spec2gds_assistant.app import create_app
from spec2gds_assistant.config import Settings
from spec2gds_assistant.models import CircuitProposalArtifact


def test_service_directory_reports_configured_health(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        is_success = True
        status_code = 200

    class FakeHttpClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> "FakeHttpClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            pass

        async def get(self, _: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("spec2gds_assistant.app.httpx.AsyncClient", FakeHttpClient)
    app = create_app(
        Settings(
            host="127.0.0.1",
            port=4200,
            database_path=tmp_path / "assistant.db",
            openai_api_key=None,
            openai_model="gpt-4o-mini",
            web_dist_path=tmp_path / "missing",
            circuit_request_timeout_seconds=5,
        )
    )

    with TestClient(app) as client:
        directory = client.get("/api/services").json()
    assert directory["services"]["spec_editor"]["available"] is True
    assert directory["services"]["circuit_designer"]["service_url"].endswith(
        "/api/circuit-designer/v1"
    )


def test_circuit_launch_creates_a_bound_chat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_snapshot(*_: object) -> dict[str, object]:
        return {"revision": "1", "document": {"document_id": "demo"}}

    monkeypatch.setattr(
        "spec2gds_assistant.circuit_client.CircuitDesignerClient.snapshot",
        fake_snapshot,
    )
    app = create_app(
        Settings(
            host="127.0.0.1",
            port=4200,
            database_path=tmp_path / "assistant.db",
            openai_api_key=None,
            openai_model="gpt-4o-mini",
            web_dist_path=tmp_path / "missing",
            circuit_request_timeout_seconds=5,
        )
    )

    with TestClient(app) as client:
        response = client.get(
            "/launch/circuit",
            params={
                "service_base_url": "http://127.0.0.1:4100/api/circuit-designer/v1",
                "document_id": "demo",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        thread_id = response.headers["location"].split("thread=")[1]
        thread = client.get(f"/api/threads/{thread_id}").json()
    assert thread["domain"] == "circuit"
    assert thread["document_id"] == "demo"


def test_spec_document_launch_creates_a_read_only_bound_chat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_document_context(
        *_: object,
    ) -> dict[str, object]:
        return {
            "scope": "document",
            "document_id": "demo",
            "source_revision_hash": "sha256:base",
        }

    monkeypatch.setattr(
        "spec2gds_assistant.spec_client.SpecEditorClient.document_context",
        fake_document_context,
    )
    app = create_app(
        Settings(
            host="127.0.0.1",
            port=4200,
            database_path=tmp_path / "assistant.db",
            openai_api_key=None,
            openai_model="gpt-4o-mini",
            web_dist_path=tmp_path / "missing",
            circuit_request_timeout_seconds=5,
        )
    )

    with TestClient(app) as client:
        response = client.get(
            "/launch/spec-document",
            params={
                "service_base_url": "http://127.0.0.1:8000",
                "document_id": "demo",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        thread_id = response.headers["location"].split("thread=")[1]
        thread = client.get(f"/api/threads/{thread_id}").json()
    assert thread["domain"] == "spec"
    assert thread["binding_scope"] == "document"
    assert thread["document_id"] == "demo"
    assert thread["entity_id"] is None


def test_app_serves_built_web_assets_before_a2a_tenant_routes(
    tmp_path: Path,
) -> None:
    web_dist_path = tmp_path / "web" / "dist"
    assets_path = web_dist_path / "assets"
    assets_path.mkdir(parents=True)
    (web_dist_path / "index.html").write_text(
        '<script type="module" src="/assets/index-test.js"></script>',
        encoding="utf-8",
    )
    (assets_path / "index-test.js").write_text(
        'document.body.dataset.loaded = "true";',
        encoding="utf-8",
    )

    app = create_app(
        Settings(
            host="127.0.0.1",
            port=4200,
            database_path=tmp_path / "assistant.db",
            openai_api_key=None,
            openai_model="gpt-4o-mini",
            web_dist_path=web_dist_path,
            circuit_request_timeout_seconds=5,
        )
    )

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        asset = client.get("/assets/index-test.js")
        assert asset.status_code == 200
        assert asset.text == 'document.body.dataset.loaded = "true";'


def test_app_exposes_health_and_a2a_agent_card(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            host="127.0.0.1",
            port=4200,
            database_path=tmp_path / "assistant.db",
            openai_api_key=None,
            openai_model="gpt-4o-mini",
            web_dist_path=tmp_path / "missing",
            circuit_request_timeout_seconds=5,
        )
    )
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        card = client.get("/.well-known/agent-card.json")
        assert card.status_code == 200
        assert card.json()["name"] == "spec2gds AI Assistant"
        assert any(
            skill["id"] == "propose_circuit_changes"
            for skill in card.json()["skills"]
        )


def test_a2a_message_send_returns_a_typed_proposal_artifact(
    tmp_path: Path,
    circuit_snapshot: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = CircuitProposalArtifact.model_validate(
        {
            "proposal_id": "proposal_a2a",
            "document_id": "fixture_simple",
            "base_revision": "1",
            "title": "Add a consumer",
            "summary": "Add one consumer.",
            "rationale": "The request calls for another sink.",
            "assumptions": [],
            "batch": {
                "request_id": "request_a2a",
                "expected_revision": "1",
                "operations": [
                    {
                        "operation_id": "add_consumer",
                        "type": "add_instance",
                        "instance": {
                            "id": "consumer_1",
                            "label": "Consumer 1",
                            "component_id": "consumer",
                            "parameter_values": {},
                        },
                    }
                ],
            },
        }
    )

    async def fake_propose(
        _self: CircuitEditingAgent, _request: object
    ) -> CircuitProposalArtifact:
        return artifact

    monkeypatch.setattr(CircuitEditingAgent, "propose", fake_propose)
    app = create_app(
        Settings(
            host="127.0.0.1",
            port=4200,
            database_path=tmp_path / "assistant.db",
            openai_api_key=None,
            openai_model="gpt-4o-mini",
            web_dist_path=tmp_path / "missing",
            circuit_request_timeout_seconds=5,
        )
    )
    with TestClient(app) as client:
        response = client.post(
            "/a2a/message:send",
            headers={
                "A2A-Version": "1.0",
                "Content-Type": "application/a2a+json",
            },
            json={
                "message": {
                    "messageId": "message_a2a",
                    "role": "ROLE_USER",
                    "parts": [
                        {"text": "Add another consumer."},
                        {
                            "data": {
                                "kind": "circuit_context",
                                "snapshot": circuit_snapshot,
                                "svg": '<svg viewBox="0 0 100 100"></svg>',
                                "png_base64": None,
                            }
                        },
                    ],
                }
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()["task"]
        assert body["status"]["state"] == "TASK_STATE_COMPLETED"
        proposal_part = body["artifacts"][0]["parts"][0]["data"]
        assert proposal_part["kind"] == "circuit_change_proposal"
        assert proposal_part["proposal_id"] == "proposal_a2a"

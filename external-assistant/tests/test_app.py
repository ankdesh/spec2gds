from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from spec2gds_assistant.agents.circuit_editor import CircuitEditingAgent
from spec2gds_assistant.app import create_app
from spec2gds_assistant.config import Settings
from spec2gds_assistant.models import CircuitProposalArtifact


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
        assert card.json()["name"] == "spec2gds Circuit Editing Agent"
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

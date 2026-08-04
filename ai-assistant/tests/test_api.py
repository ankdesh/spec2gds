from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from spec2gds_assistant.api import create_api_router
from spec2gds_assistant.circuit_client import normalize_circuit_base_url
from spec2gds_assistant.database import AssistantDatabase
from spec2gds_assistant.spec_client import SpecServiceError, normalize_spec_base_url


class FakeCircuitClient:
    def __init__(self, snapshot: dict[str, Any]) -> None:
        self.current = snapshot
        self.submitted: dict[str, Any] | None = None

    async def snapshot(self, _base: str, _document_id: str) -> dict[str, Any]:
        return self.current

    async def png(self, _base: str, _document_id: str) -> bytes:
        return b"\x89PNG\r\n\x1a\n"

    async def svg(self, _base: str, _document_id: str) -> str:
        return '<svg viewBox="0 0 100 100"></svg>'

    async def preview(
        self, _base: str, _document_id: str, _batch: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "status": "accepted",
            "candidate": self.current["document"],
            "diagnostics": [],
            "diff": {
                "added": [],
                "removed": [],
                "changed": [],
                "connections_changed": [],
            },
        }

    async def submit_proposal(
        self, _base: str, _document_id: str, proposal: dict[str, Any]
    ) -> dict[str, Any]:
        self.submitted = proposal
        return {
            **proposal,
            "status": "pending",
            "diagnostics": [],
            "diff": {
                "added": [],
                "removed": [],
                "changed": [],
                "connections_changed": [],
            },
            "created_at": "2026-07-30T00:00:00Z",
        }


class FakeSpecClient:
    def __init__(self) -> None:
        self.applied: dict[str, Any] | None = None
        self.apply_error: SpecServiceError | None = None

    def normalize(self, value: str) -> str:
        if value != "http://127.0.0.1:8000":
            raise ValueError("not allowlisted")
        return value

    async def context(
        self,
        _base: str,
        document_id: str,
        entity_kind: str,
        entity_id: str,
    ) -> dict[str, Any]:
        return {
            "document_id": document_id,
            "source_revision_hash": "sha256:base",
            "target": {
                "document_id": document_id,
                "entity_kind": entity_kind,
                "entity_id": entity_id,
            },
            "writable": {"entity_refs": [], "sections": []},
            "read_only": {},
            "available_references": {},
            "diagnostics": [],
        }

    async def preview(self, _base: str, proposal: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "valid",
            "diagnostics": [],
            "current_sections": [{"section_id": "component-leaf"}],
            "candidate_sections": [{"section_id": "component-leaf", "title": "Changed"}],
            "diff": [{"path": "$.component-leaf.title", "change": "added", "before": None, "after": "Changed"}],
        }

    async def apply(self, _base: str, proposal: dict[str, Any]) -> dict[str, Any]:
        if self.apply_error is not None:
            raise self.apply_error
        self.applied = proposal
        return {
            "status": "applied",
            "proposal_id": proposal["proposal_id"],
            "source_revision_hash": "sha256:result",
        }

def test_review_then_send_flow(
    tmp_path: Path,
    circuit_snapshot: dict[str, Any],
) -> None:
    database = AssistantDatabase(tmp_path / "assistant.db")
    database.initialize()
    circuit = FakeCircuitClient(circuit_snapshot)
    app = FastAPI()
    app.include_router(
        create_api_router(
            database=database,
            circuit_client=circuit,  # type: ignore[arg-type]
        )
    )
    client = TestClient(app)
    thread = client.post(
        "/api/threads",
        json={"local_id": "thread_1", "title": "Test chat"},
    ).json()
    connected = client.put(
        f"/api/threads/{thread['id']}/circuit",
        json={
            "base_url": "http://127.0.0.1:4100/api/circuit-designer/v1",
            "document_id": "fixture_simple",
        },
    )
    assert connected.status_code == 200

    artifact = {
        "kind": "circuit_change_proposal",
        "schema_version": "1",
        "proposal_id": "proposal_1",
        "document_id": "fixture_simple",
        "base_revision": "1",
        "title": "Add a consumer",
        "summary": "Add one consumer.",
        "rationale": "The request needs another sink.",
        "assumptions": [],
        "batch": {
            "request_id": "request_1",
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
    preview = client.post(
        f"/api/threads/{thread['id']}/circuit/preview",
        json={
            "proposal_id": "proposal_1",
            "message_id": "assistant_1",
            "artifact": artifact,
        },
    )
    assert preview.status_code == 200
    assert preview.json()["review"]["state"] == "ready"
    assert circuit.submitted is None

    sent = client.post(
        f"/api/threads/{thread['id']}/circuit/proposals",
        json={"proposal_id": "proposal_1"},
    )
    assert sent.status_code == 200
    assert sent.json()["review"]["state"] == "sent"
    assert circuit.submitted
    assert "status" not in circuit.submitted
    assert "diagnostics" not in circuit.submitted


def test_circuit_services_require_loopback_or_explicit_configuration() -> None:
    assert normalize_circuit_base_url(
        "http://localhost:4100/api/circuit-designer/v1/"
    ) == "http://localhost:4100/api/circuit-designer/v1"
    for value in (
        "https://localhost:4100/api/circuit-designer/v1",
        "http://example.com/api/circuit-designer/v1",
        "http://127.0.0.1:4100/wrong",
    ):
        try:
            normalize_circuit_base_url(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected URL to be rejected: {value}")
    remote = "http://192.0.2.10:4100/api/circuit-designer/v1"
    assert normalize_circuit_base_url(remote, (remote,)) == remote


def test_spec_service_must_be_allowlisted() -> None:
    allowlist = ("http://127.0.0.1:8000",)
    assert normalize_spec_base_url("http://127.0.0.1:8000/", allowlist) == allowlist[0]
    for value in (
        "http://localhost:8000",
        "https://127.0.0.1:8000",
        "http://example.com:8000",
        "http://127.0.0.1:8000/arbitrary-path",
    ):
        with pytest.raises(ValueError):
            normalize_spec_base_url(value, allowlist)
    remote = "http://192.0.2.10:8000"
    assert normalize_spec_base_url(remote, (remote,)) == remote


def test_spec_launch_preview_and_immediate_apply_flow(
    tmp_path: Path,
    circuit_snapshot: dict[str, Any],
) -> None:
    database = AssistantDatabase(tmp_path / "assistant.db")
    database.initialize()
    spec = FakeSpecClient()
    app = FastAPI()
    app.include_router(
        create_api_router(
            database=database,
            circuit_client=FakeCircuitClient(circuit_snapshot),  # type: ignore[arg-type]
            spec_client=spec,  # type: ignore[arg-type]
        )
    )
    client = TestClient(app)
    launch_body = {
        "base_url": "http://127.0.0.1:8000",
        "document_id": "spec_demo",
        "entity_kind": "component",
        "entity_id": "component_leaf",
    }
    first = client.post("/api/spec/launch", json=launch_body)
    second = client.post("/api/spec/launch", json=launch_body)
    assert first.status_code == 201
    assert second.status_code == 201
    thread = first.json()["thread"]
    assert thread["id"] != second.json()["thread"]["id"]
    assert thread["domain"] == "spec"
    context = client.get(f"/api/threads/{thread['id']}/spec/context")
    assert context.status_code == 200
    assert context.json()["context"]["target"]["entity_id"] == "component_leaf"

    target = {
        "document_id": "spec_demo",
        "entity_kind": "component",
        "entity_id": "component_leaf",
    }
    artifact = {
        "kind": "spec_change_proposal",
        "schema_version": "1.0",
        "proposal_id": "proposal_spec",
        "document_id": "spec_demo",
        "target": target,
        "base_source_revision_hash": "sha256:base",
        "title": "Clarify component",
        "summary": "Update its description.",
        "rationale": "Capture intent.",
        "assumptions": [],
        "operations": [
            {
                "operation_id": "describe",
                "type": "set_entity_metadata",
                "entity": target,
                "description": "Updated",
            }
        ],
    }
    preview = client.post(
        f"/api/threads/{thread['id']}/spec/preview",
        json={"proposal_id": "proposal_spec", "artifact": artifact},
    )
    assert preview.status_code == 200
    assert preview.json()["review"]["state"] == "ready"
    assert spec.applied is None
    applied = client.post(
        f"/api/threads/{thread['id']}/spec/proposals",
        json={"proposal_id": "proposal_spec"},
    )
    assert applied.status_code == 200
    assert applied.json()["review"]["state"] == "applied"
    assert spec.applied == artifact


def test_failed_spec_apply_disables_further_approval(
    tmp_path: Path,
    circuit_snapshot: dict[str, Any],
) -> None:
    database = AssistantDatabase(tmp_path / "assistant.db")
    database.initialize()
    spec = FakeSpecClient()
    app = FastAPI()
    app.include_router(
        create_api_router(
            database=database,
            circuit_client=FakeCircuitClient(circuit_snapshot),  # type: ignore[arg-type]
            spec_client=spec,  # type: ignore[arg-type]
        )
    )
    client = TestClient(app)
    thread = client.post(
        "/api/spec/launch",
        json={
            "base_url": "http://127.0.0.1:8000",
            "document_id": "spec_demo",
            "entity_kind": "component",
            "entity_id": "component_leaf",
        },
    ).json()["thread"]
    target = {
        "document_id": "spec_demo",
        "entity_kind": "component",
        "entity_id": "component_leaf",
    }
    artifact = {
        "kind": "spec_change_proposal",
        "schema_version": "1.0",
        "proposal_id": "proposal_failed",
        "document_id": "spec_demo",
        "target": target,
        "base_source_revision_hash": "sha256:base",
        "title": "Clarify component",
        "summary": "Update its description.",
        "rationale": "Capture intent.",
        "assumptions": [],
        "operations": [
            {
                "operation_id": "describe",
                "type": "set_entity_metadata",
                "entity": target,
                "description": "Updated",
            }
        ],
    }
    preview = client.post(
        f"/api/threads/{thread['id']}/spec/preview",
        json={"proposal_id": artifact["proposal_id"], "artifact": artifact},
    )
    assert preview.json()["review"]["state"] == "ready"
    spec.apply_error = SpecServiceError(422, ["Source validation failed."])
    failed = client.post(
        f"/api/threads/{thread['id']}/spec/proposals",
        json={"proposal_id": artifact["proposal_id"]},
    )
    assert failed.status_code == 200
    assert failed.json()["review"]["state"] == "invalid"
    retry = client.post(
        f"/api/threads/{thread['id']}/spec/proposals",
        json={"proposal_id": artifact["proposal_id"]},
    )
    assert retry.status_code == 409

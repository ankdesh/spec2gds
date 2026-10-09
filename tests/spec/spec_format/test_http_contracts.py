"""HTTP contracts through request validation, middleware, and durable source storage."""

import pytest
from fastapi.testclient import TestClient

from spec2gds.spec.spec_format.assistant import SpecChangeProposal
from spec2gds.spec.spec_format.assistant_integration import ASSISTANT_ACTIONS
from spec2gds.spec.spec_format.testing import write_test_package
from spec2gds.spec.spec_format.v1_api import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        yield client


def create(client, tmp_path, name="source"):
    response = client.post("/documents/create", json={
        "path": str(tmp_path / f"{name}.spec"), "document_id": name, "title": name,
    })
    assert response.status_code == 200, response.text
    return response.json()


def transaction(client, snapshot, operations):
    return client.post("/transactions", params={"service_document_key": snapshot["owner_document_key"]}, json={
        "expected_source_revision_hash": snapshot["source_revision_hash"], "operations": operations,
    })


@pytest.mark.parametrize("path,body", [
    ("/documents/create", {}), ("/documents/open", {}),
    ("/transactions", {"operations": []}),
    ("/transactions", {"expected_source_revision_hash": "x", "operations": {}}),
])
def test_http_request_validation_has_serialized_errors_and_request_id(client, path, body):
    response = client.post(path, json=body, headers={"x-request-id": "contract-validation"})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert response.headers["x-request-id"] == "contract-validation"


def test_http_document_selection_canonical_alias_wins_and_unknown_key_is_rejected(client, tmp_path):
    first = create(client, tmp_path, "first")
    second = create(client, tmp_path, "second")
    response = client.get("/documents/snapshot", params={
        "service_document_key": first["owner_document_key"],
        "owner_document_key": second["owner_document_key"],
    })
    assert response.status_code == 200
    assert response.json()["document_id"] == "first"
    invalid = client.get("/documents/snapshot", params={"service_document_key": "missing"})
    assert invalid.status_code == 404
    assert "detail" in invalid.json()
    assert client.get("/documents/snapshot").json()["document_id"] == "second"


@pytest.mark.parametrize("invalid", [
    {"type": "unsupported_operation"},
    {"type": "create_entity", "kind": "component", "name": ""},
    {"type": "add_component_port", "component": {"document_id": "source", "entity_kind": "component", "entity_id": "missing"}, "port": {"name": "bad", "family": "unsupported"}},
])
def test_http_invalid_batch_is_atomic_on_disk_and_in_memory(client, tmp_path, invalid):
    before = create(client, tmp_path)
    path = tmp_path / "source.spec"
    source = path.read_bytes()
    response = transaction(client, before, [
        {"type": "create_entity", "kind": "component", "name": "must_not_persist"}, invalid,
    ])
    assert response.status_code == 422, response.text
    assert "detail" in response.json()
    assert path.read_bytes() == source
    current = client.get("/documents/snapshot").json()
    assert current["source_revision_hash"] == before["source_revision_hash"]
    assert current["components"] == []


def test_http_stale_writer_rejected_and_saved_port_survives_app_restart(client, tmp_path):
    before = create(client, tmp_path)
    response = transaction(client, before, [{"type": "create_entity", "kind": "component", "name": "counter"}])
    assert response.status_code == 200, response.text
    saved = response.json()["snapshot"]
    ref = saved["components"][0]["ref"]
    response = transaction(client, saved, [{
        "type": "add_component_port", "component": ref,
        "port": {"name": "count", "family": "wire", "direction": "out", "range": "7:0"},
    }])
    assert response.status_code == 200, response.text
    final = response.json()["snapshot"]
    source = (tmp_path / "source.spec").read_bytes()
    stale = transaction(client, before, [{"type": "create_entity", "kind": "component", "name": "stale"}])
    assert stale.status_code == 409
    assert (tmp_path / "source.spec").read_bytes() == source
    with TestClient(create_app()) as reopened:
        result = reopened.post("/documents/open", json={"path": str(tmp_path / "source.spec")})
        assert result.status_code == 200
        snapshot = result.json()
        assert snapshot["source_revision_hash"] == final["source_revision_hash"]
        assert snapshot["components"][0]["ports"][0]["name"] == "count"


@pytest.mark.parametrize("name", ["missing.spec", "malformed.spec"])
def test_http_failed_open_preserves_active_document(client, tmp_path, name):
    before = create(client, tmp_path)
    (tmp_path / "malformed.spec").write_bytes(b"invalid archive")
    response = client.post("/documents/open", json={"path": str(tmp_path / name)})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert client.get("/documents/snapshot").json()["source_revision_hash"] == before["source_revision_hash"]


def test_http_existing_destination_is_not_overwritten(client, tmp_path):
    create(client, tmp_path)
    path = tmp_path / "source.spec"
    source = path.read_bytes()
    response = client.post("/documents/create", json={"path": str(path), "document_id": "replacement"})
    assert response.status_code == 422
    assert path.read_bytes() == source


def test_http_proposal_preview_replay_and_conflicting_replay_preserve_source(client, tmp_path):
    path = tmp_path / "proposal.spec"
    write_test_package(path)
    opened = client.post("/documents/open", json={"path": str(path)}).json()
    target = next(item["ref"] for item in opened["components"] if item["ref"]["entity_id"] == "component_leaf")
    proposal = SpecChangeProposal(
        proposal_id="http_description", document_id=opened["document_id"], target=target,
        base_source_revision_hash=opened["source_revision_hash"], title="Describe leaf",
        summary="Clarify behaviour", rationale="Public HTTP contract", assumptions=[],
        operations=[{"operation_id": "describe", "type": "set_entity_metadata", "entity": target, "description": "Durable HTTP description"}],
    ).model_dump(mode="json")
    before = path.read_bytes()
    preview = client.post(ASSISTANT_ACTIONS["preview_proposal"]["path"], json=proposal)
    assert preview.status_code == 200
    assert preview.json()["status"] == "valid"
    assert path.read_bytes() == before
    first = client.post(ASSISTANT_ACTIONS["submit_proposal"]["path"], json=proposal)
    assert first.status_code == 200, first.text
    assert not first.json()["idempotent_replay"]
    saved = path.read_bytes()
    replay = client.post(ASSISTANT_ACTIONS["submit_proposal"]["path"], json=proposal)
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"]
    assert path.read_bytes() == saved
    proposal["operations"][0]["description"] = "Conflicting replay"
    conflict = client.post(ASSISTANT_ACTIONS["submit_proposal"]["path"], json=proposal)
    assert conflict.status_code == 409
    assert path.read_bytes() == saved


def test_http_sdk_snapshot_handoff_is_immutable_after_a_later_spec_edit(client, tmp_path):
    from testplan_service.api.app import create_app as planner_app

    from spec2gds.spec.activities import ActivitySnapshot
    from spec2gds.spec.spec_format.ir import SpecRevision
    from spec2gds.spec.spec_format.models import EntityRef

    opened = create(client, tmp_path)
    saved = transaction(client, opened, [{"type": "create_entity", "kind": "component", "name": "snapshot_core"}]).json()["snapshot"]
    target = EntityRef.model_validate(saved["components"][0]["ref"])
    exported = ActivitySnapshot.create(SpecRevision.load(tmp_path / "source.spec"), target)
    with TestClient(planner_app(storage_dir=tmp_path / "planner")) as planner:
        imported = planner.post("/api/verification/v1/source-imports", content=exported.to_bytes())
        assert imported.status_code == 201, imported.text
        snapshot_id = imported.json()["snapshot_id"]
        plan = planner.post("/api/verification/v1/plans", json={
            "name": "Imported Spec source", "snapshot_id": snapshot_id, "root_scope_id": target.entity_id,
        })
        assert plan.status_code == 201, plan.text
        plan_id = plan.json()["id"]
        before = planner.get(f"/api/verification/v1/plans/{plan_id}").json()
        change = transaction(client, saved, [{"type": "set_entity_metadata", "entity": target.model_dump(mode="json"), "description": "Later Spec change"}])
        assert change.status_code == 200
        assert change.json()["snapshot"]["source_revision_hash"] != saved["source_revision_hash"]
        assert planner.get(f"/api/verification/v1/plans/{plan_id}").json() == before
    with TestClient(planner_app(storage_dir=tmp_path / "planner")) as restarted:
        assert restarted.get(f"/api/verification/v1/plans/{plan_id}").json() == before

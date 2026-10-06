"""Deterministic Spec service correctness; no model, UI, or API key required."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import fastapi
import pytest

from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.assistant import SpecChangeProposal
from spec2gds.spec.spec_format.proposal_service import (
    ProposalApplyError,
    apply_assistant_proposal,
)
from spec2gds.spec.spec_format.v1_api import (
    AssistantDocumentLaunchRequest,
    AssistantLaunchRequest,
    CreateDocumentRequest,
    OpenDocumentRequest,
    TransactionRequest,
    V1Session,
    create_app,
)


def endpoints(review=False):
    return {route.name: route.endpoint for route in create_app(review).routes if hasattr(route, "endpoint")}


def proposal(snapshot, id="p1", operations=None, **values):
    return SpecChangeProposal.model_validate({"proposal_id": id, "document_id": snapshot["document_id"],
        "scope": "document", "target": None, "base_source_revision_hash": snapshot["source_revision_hash"],
        "title": "Refine source", "summary": "Deterministic refinement", "rationale": "Requested change",
        "assumptions": ["Use proposed defaults"], "operations": operations or [{"operation_id": "create",
            "type": "create_entity", "kind": "component", "name": id, "entity_id": f"component_{id}"}], **values})


def create(e, path, document_id="iterative"):
    return e["create_document"](CreateDocumentRequest(path=str(path), document_id=document_id, title="Iterative"))


def test_default_policy_applies_once_and_returns_saved_revision(tmp_path):
    e = endpoints()
    s = create(e, tmp_path / "auto.spec")
    key = s["owner_document_key"]
    assert e["assistant_capabilities"]()["approval_policy"] == "automatic"
    p = proposal(s)
    result = e["assistant_proposal_submit"](p, key, "chat-one")
    assert result["application_mode"] == "automatic"
    assert result["source_revision_hash"] == V1Session(str(tmp_path / "auto.spec")).revision.source_revision_hash
    saved_bytes = (tmp_path / "auto.spec").read_bytes()
    assert e["assistant_proposal_submit"](p, key)["idempotent_replay"]
    assert (tmp_path / "auto.spec").read_bytes() == saved_bytes
    assert len([event for event in e["source_event_history"](key)["events"] if event.get("event_type", "source.changed") == "source.changed"]) == 1
    receipt = e["assistant_submission"]("p1", key)
    assert receipt["state"] == "applied" and receipt["session_id"] == "chat-one"
    assert receipt["service_result"]["diff"]
    for change in ({"base_source_revision_hash": "old"}, {"summary": "changed"},
                   {"scope": "entity", "target": {"document_id": s["document_id"], "entity_id": "component_p1", "entity_kind": "component"}},
                   {"operations": [{"operation_id": "create", "type": "create_entity", "kind": "component", "name": "other"}]}):
        with pytest.raises(fastapi.HTTPException) as error:
            e["assistant_proposal_submit"](p.model_copy(update=change), key)
        assert error.value.status_code == 409
    assert (tmp_path / "auto.spec").read_bytes() == saved_bytes


def test_restricted_policy_stores_exact_artifact_and_revalidates(tmp_path, monkeypatch):
    monkeypatch.setenv("SPEC2GDS_REQUIRE_HUMAN_APPROVAL", "1")
    e = {r.name: r.endpoint for r in create_app().routes if hasattr(r, "endpoint")}
    s = create(e, tmp_path / "review.spec")
    key = s["owner_document_key"]
    before = (tmp_path / "review.spec").read_bytes()
    p = proposal(s)
    assert e["assistant_proposal_submit"](p, key)["status"] == "approval_required"
    assert (tmp_path / "review.spec").read_bytes() == before
    with pytest.raises(fastapi.HTTPException) as bypass:
        e["assistant_proposal_apply"](p, key)
    assert bypass.value.status_code == 403
    restarted = {r.name: r.endpoint for r in create_app().routes if hasattr(r, "endpoint")}
    assert restarted["assistant_capabilities"]()["approval_policy"] == "review"
    assert restarted["assistant_submission"]("p1", key)["state"] == "ready"
    assert endpoints()["assistant_proposal_submit"](p, key)["status"] == "approval_required"  # Upgrade cannot authorize an old review.
    assert restarted["assistant_submission_reject"]("p1", key)["state"] == "discarded"
    assert (tmp_path / "review.spec").read_bytes() == before
    p2 = proposal(s, "p2")
    restarted["assistant_proposal_submit"](p2, key)
    result = restarted["assistant_submission_approve"]("p2", key)
    assert result["application_mode"] == "review"
    assert restarted["assistant_submission_approve"]("p2", key)["idempotent_replay"]
    current = restarted["document_snapshot"](key)
    restarted["assistant_proposal_submit"](proposal(current, "p3"), key)
    restarted["transaction"](TransactionRequest(expected_source_revision_hash=current["source_revision_hash"], operations=[{"type": "set_document_title", "title": "Human edit"}]), key)
    with pytest.raises(fastapi.HTTPException) as stale:
        restarted["assistant_submission_approve"]("p3", key)
    assert stale.value.status_code == 409
    assert restarted["assistant_submission"]("p3", key)["state"] == "stale"


def test_binding_survives_document_switch_copy_and_restart(tmp_path):
    e = endpoints()
    a = create(e, tmp_path / "a.spec", "same-document-id")
    (tmp_path / "b.spec").write_bytes((tmp_path / "a.spec").read_bytes())
    b = e["open_document"](OpenDocumentRequest(path=str(tmp_path / "b.spec")))
    assert a["owner_document_key"] != b["owner_document_key"]
    with pytest.raises(fastapi.HTTPException):
        e["assistant_document_context"](a["document_id"])
    e["assistant_proposal_submit"](proposal(a), a["owner_document_key"])
    launch = e["launch_assistant"](AssistantLaunchRequest(entity_kind="component", entity_id="component_p1"), a["owner_document_key"])
    assert a["owner_document_key"] in launch["assistant_url"]
    document_launch = e["launch_document_assistant"](AssistantDocumentLaunchRequest(), a["owner_document_key"])
    assert a["owner_document_key"] in document_launch["assistant_url"]
    assert len(e["document_snapshot"](a["owner_document_key"])["components"]) == 1
    assert not e["document_snapshot"](b["owner_document_key"])["components"]
    restarted = endpoints()
    assert len(restarted["assistant_document_context"](a["document_id"], a["owner_document_key"])["available_references"]["components"]) == 1
    (tmp_path / "a.spec").unlink()
    with pytest.raises(fastapi.HTTPException) as missing:
        restarted["document_snapshot"](a["owner_document_key"])
    assert missing.value.detail["error_code"] == "BINDING_UNAVAILABLE"


def test_external_update_stales_authored_revision_and_emits_event(tmp_path):
    e = endpoints()
    path = tmp_path / "external.spec"
    a = create(e, path)
    key = a["owner_document_key"]
    other = V1Session(str(path))
    other.package.narrative = other.package.narrative.model_copy(update={"title": "CLI update"})
    other.save()
    bytes_after_cli = path.read_bytes()
    with pytest.raises(fastapi.HTTPException) as stale:
        e["assistant_proposal_submit"](proposal(a), key)
    assert stale.value.status_code == 409
    assert stale.value.detail["base_source_revision_hash"] == a["source_revision_hash"]
    assert path.read_bytes() == bytes_after_cli
    view = e["document_view"](key)
    assert view["snapshot"]["narrative"]["title"] == "CLI update"
    assert view["source_revision_hash"] == view["a2ui"]["source_revision_hash"]
    assert any(event["origin"] == "external" for event in e["source_event_history"](key)["events"])


def test_mixed_local_writers_accept_exactly_one_authored_revision(tmp_path):
    from spec2gds.spec.spec_format.actions import ActivityExecutionRecord
    from spec2gds.spec.spec_format.activity_jobs import JobEnvelope
    app = create_app(False)
    e = {route.name: route.endpoint for route in app.routes if hasattr(route, "endpoint")}
    path = tmp_path / "race.spec"
    s = create(e, path)
    e["assistant_proposal_submit"](proposal(s), s["owner_document_key"])
    s = e["document_snapshot"](s["owner_document_key"])
    record = ActivityExecutionRecord(execution_id="activity-race", activity_id="rtl.generate", activity_version="1.0.0",
        snapshot_id="race-snapshot", source_revision_hash=s["source_revision_hash"], target=s["components"][0]["ref"],
        status="succeeded", created_at="2026-01-01T00:00:00Z")
    envelope = JobEnvelope(record, str(path), f"{path}.artifacts", str(tmp_path / "snapshot"), str(tmp_path / "generated"))
    barrier = Barrier(11)
    def write(index):
        offline = V1Session(str(path))
        p = proposal(s, f"race_{index}")
        barrier.wait()
        try:
            if index % 3 == 0:
                e["transaction"](TransactionRequest(expected_source_revision_hash=s["source_revision_hash"], operations=[{"type": "set_document_title", "title": f"Editor {index}"}]), s["owner_document_key"])
            elif index % 3 == 1:
                e["assistant_proposal_submit"](p, s["owner_document_key"])
            else:
                apply_assistant_proposal(offline, p)
            return True
        except (fastapi.HTTPException, ProposalApplyError, ValueError):
            return False
    def finalize():
        barrier.wait()
        return app.state.activity_jobs.finalize(envelope, None)
    with ThreadPoolExecutor(max_workers=11) as pool:
        finalization = pool.submit(finalize)
        results = list(pool.map(write, range(10)))
        assert finalization.result().execution_id == "activity-race"
    assert sum(results) == 1
    reopened = V1Session(str(path))
    assert reopened.revision.source_revision_hash != s["source_revision_hash"]
    assert [item.execution_id for item in reopened.activity.state.activity_executions] == ["activity-race"]
    app.state.activity_jobs.close()


def test_saved_receipt_recovers_interrupted_journal_and_lost_response(tmp_path, monkeypatch):
    from spec2gds.spec.spec_format.spec_service_store import SpecServiceJournal
    e = endpoints()
    path = tmp_path / "recovery.spec"
    s = create(e, path)
    key = s["owner_document_key"]
    original_update = SpecServiceJournal.update
    def interrupted(self, id, **values):
        if values.get("state") == "applied":
            raise OSError("Interrupted after package save")
        return original_update(self, id, **values)
    with monkeypatch.context() as patch:
        patch.setattr(SpecServiceJournal, "update", interrupted)
        with pytest.raises(OSError):
            e["assistant_proposal_submit"](proposal(s), key)
    saved = path.read_bytes()
    restarted = endpoints()
    receipt = restarted["assistant_submission"]("p1", key)
    assert receipt["state"] == "applied"
    assert restarted["assistant_proposal_submit"](proposal(s), key)["idempotent_replay"]
    assert path.read_bytes() == saved
    assert len(V1Session(str(path)).activity.state.assistant_changes) == 1
    assert len([event for event in restarted["source_event_history"](key)["events"] if event.get("event_type", "source.changed") == "source.changed"]) == 1


def test_100_refinements_have_complete_paginated_history_and_replay(tmp_path):
    e = endpoints()
    path = tmp_path / "repeat.spec"
    s = create(e, path)
    key = s["owner_document_key"]
    contract = e["assistant_operation_schema"](s["document_id"], "document", owner_document_key=key)["digest"]
    for index in range(100):
        operations = None if index == 0 else [{"operation_id": "refine", "type": "set_entity_metadata",
            "entity": {"document_id": s["document_id"], "entity_kind": "component", "entity_id": "component_step_0"},
            "description": f"Iteration {index}"}]
        p = proposal(s, f"step_{index}", operations)
        result = e["assistant_proposal_submit"](p, key)
        assert result["status"] == "applied"
        assert e["assistant_proposal_submit"](p, key)["idempotent_replay"]
        s = e["document_snapshot"](key)
        SpecPackage.load(str(path))
    assert e["assistant_operation_schema"](s["document_id"], "document", owner_document_key=key)["digest"] == contract
    ids = []
    cursor = None
    while True:
        page = e["assistant_history"](key, cursor, 13)
        assert len(page["items"]) <= 13
        ids.extend(item["proposal_id"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None: break
    assert len(set(ids)) == len(ids) == 100
    events = []
    after = 0
    while True:
        page = e["source_event_history"](key, after)
        if not page["events"]: break
        events.extend(page["events"])
        after = page["events"][-1]["sequence"]
    assert len([event for event in events if event.get("event_type", "source.changed") == "source.changed"]) == 100
    assert [item["sequence"] for item in events] == list(range(1, after + 1))
    assert not e["source_event_history"](key, after)["events"]
    assert len(e["document_view"](key)["activity"]["assistant_changes"]) == 50
    assert len(V1Session(str(path)).activity.state.assistant_changes) == 100


def test_creation_receipt_replays_exact_input_without_overwriting(tmp_path):
    e = endpoints()
    path = tmp_path / "receipt.spec"
    request = CreateDocumentRequest(path=str(path), document_id="receipt", title="Receipt", request_id="request-one")
    first = e["create_document"](request)
    saved = path.read_bytes()
    assert endpoints()["create_document"](request)["owner_document_key"] == first["owner_document_key"]
    assert path.read_bytes() == saved
    with pytest.raises(fastapi.HTTPException):
        e["create_document"](request.model_copy(update={"title": "Different"}))
    with pytest.raises(fastapi.HTTPException):
        e["create_document"](request.model_copy(update={"request_id": "new-request"}))
    assert path.read_bytes() == saved


def test_cli_history_recovers_saved_decision_without_assistant_database(tmp_path, capsys):
    import json

    from scripts.spec2gds_spec import main as spec_main
    e = endpoints()
    path = tmp_path / "cli-history.spec"
    s = create(e, path)
    apply_assistant_proposal(V1Session(str(path)), proposal(s), application_mode="automatic", session_id="offline-chat")
    saved = path.read_bytes()
    assert spec_main(["history", str(path), "--limit", "1", "--json"]) == 0
    history = json.loads(capsys.readouterr().out)
    assert history["items"][0]["state"] == "applied"
    assert history["items"][0]["session_id"] == "offline-chat"
    assert history["items"][0]["service_result"]["source_revision_hash"] == V1Session(str(path)).revision.source_revision_hash
    assert path.read_bytes() == saved


def test_document_conversation_creates_then_refines_ports_parameters_sections_topology_and_narrative(tmp_path):
    e = endpoints()
    path = tmp_path / "vocabulary.spec"
    s = create(e, path)
    key = s["owner_document_key"]
    def submit(id, operations):
        nonlocal s
        result = e["assistant_proposal_submit"](proposal(s, id, operations), key)
        assert result["status"] == "applied"
        s = e["document_snapshot"](key)
    submit("create-leaf", [{"operation_id": "create", "type": "create_entity", "kind": "component", "name": "leaf", "entity_id": "component_leaf",
        "ports": [{"name": "clk", "direction": "in", "family": "wire"}, {"name": "out", "direction": "out", "family": "wire"}]}])
    leaf = s["components"][0]
    submit("refine-leaf", [
        {"operation_id": "port", "type": "upsert_component_port", "component": leaf["ref"], "port": {"name": "enable", "direction": "in", "family": "wire", "range": "3:0"}},
        {"operation_id": "parameter", "type": "upsert_parameter", "entity": leaf["ref"], "parameter": {"name": "WIDTH", "value": "4"}},
        {"operation_id": "section", "type": "upsert_entity_section", "owner": leaf["ref"], "section_type": "sv", "type_version": 1, "payload": {"content": "assign out = clk;"}},
        {"operation_id": "narrative", "type": "upsert_narrative_block", "block": {"block_id": "intent", "type": "paragraph", "text": "Iteratively refined", "entity_refs": [leaf["ref"]]}},
    ])
    assert next(port for port in s["components"][0]["ports"] if port["name"] == "enable")["range"] == "3:0"
    assert s["entity_sections"][0]["content"] == "assign out = clk;"
    assert s["narrative"]["blocks"][0]["text"] == "Iteratively refined"
    context = e["assistant_document_context"](s["document_id"], key)
    assert "WIDTH" in str(context["writable"]["sections"])
    submit("create-design", [{"operation_id": "create", "type": "create_entity", "kind": "design", "name": "top", "entity_id": "design_top"}])
    design = s["designs"][0]["ref"]
    submit("instances", [{"operation_id": f"instance-{name}", "type": "upsert_instance", "design": design, "instance": {"name": name, "component_vlnv": leaf["vlnv"]}} for name in ("first", "second")])
    submit("connect", [{"operation_id": "connect", "type": "upsert_connection", "design": design, "connection": {"name": "clock_link", "kind": "ad_hoc", "port_endpoints": [{"instance_name": "first", "port_name": "out"}, {"instance_name": "second", "port_name": "clk"}]}}])
    assert len(s["designs"][0]["instances"]) == 2
    assert s["designs"][0]["connections"][0]["name"] == "clock_link"
    before = path.read_bytes()
    invalid = proposal(s, "bad-reference", [{"operation_id": "bad", "type": "upsert_instance", "design": design,
        "instance": {"name": "bad", "component_vlnv": "missing:lib:component:1.0"}}])
    with pytest.raises(fastapi.HTTPException) as error:
        e["assistant_proposal_submit"](invalid, key)
    assert error.value.status_code == 422 and path.read_bytes() == before


def test_document_scope_keeps_composite_ports_and_entity_boundaries_protected(tmp_path):
    from spec2gds.spec.spec_format.testing import write_test_package
    e = endpoints()
    path = tmp_path / "boundaries.spec"
    write_test_package(path)
    s = e["open_document"](OpenDocumentRequest(path=str(path)))
    key = s["owner_document_key"]
    refs = {item["ref"]["entity_id"]: item["ref"] for item in s["components"]}
    before = path.read_bytes()
    composite = proposal(s, "composite", [{"operation_id": "port", "type": "upsert_component_port", "component": refs["component_subsystem"],
        "port": {"name": "forbidden", "family": "wire", "direction": "in"}}])
    with pytest.raises(fastapi.HTTPException): e["assistant_proposal_submit"](composite, key)
    crossing = proposal(s, "crossing", [{"operation_id": "metadata", "type": "set_entity_metadata", "entity": refs["component_sink"], "description": "Forbidden"}],
        scope="entity", target=refs["component_leaf"])
    with pytest.raises(fastapi.HTTPException): e["assistant_proposal_submit"](crossing, key)
    assert path.read_bytes() == before

"""End-to-end checks for the two exclusive workspace commands."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from scripts.spec2gds_assistant import main as assistant_main
from scripts.spec2gds_spec import main as spec_main
from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.review_store import list_spec_reviews
from spec2gds.agent_spec.spec_format.v1_api import V1Session
from spec2gds.agent_spec.spec_format.workspace_target import (
    assistant_state_root,
    resolve_spec_target,
)


@contextmanager
def model_fixture():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            calls = sum(message.get("role") == "tool" for message in body["messages"])
            import re
            approved = re.search(r"Approved architecture_review_id: ([^\n]+)", "\n".join(str(message.get("content", "")) for message in body["messages"] if message.get("role") == "user"))
            if calls == 0:
                delta = {"tool_calls": [{"index": 0, "id": "call_context", "type": "function", "function": {
                    "name": "get_bound_context", "arguments": "{}"}}]}
            elif calls == 1:
                content = next(message["content"] for message in body["messages"] if message.get("role") == "tool")
                if isinstance(content, list):
                    content = "".join(part.get("text", "") for part in content)
                context = json.loads(content)
                revision = context["authoritative_context"]["source_revision_hash"]
                if not approved:
                    delta = {"tool_calls": [{"index": 0, "id": "call_architecture", "type": "function", "function": {
                        "name": "prepare_architecture_review", "arguments": json.dumps({
                            "title": "Timer architecture", "components": [{"name": "timer", "purpose": "Timing control"}],
                            "designs": [], "interfaces": [{"component": "timer", "ports": [], "status": "unconfigured"}],
                            "clocks_resets": [], "decomposition_rationale": "Keep a cohesive timer component.",
                            "assumptions": ["Interface and implementation will be refined later."], "open_questions": [],
                            "concrete_configuration": {"implemented": False},
                        })}}]}
                else:
                    delta = {"tool_calls": [{"index": 0, "id": "call_proposal", "type": "function", "function": {
                    "name": "prepare_spec_proposal", "arguments": json.dumps({
                        "architecture_review_id": approved[1], "supported": True, "unsupported_reason": None, "title": "Add timer",
                        "base_source_revision_hash": revision,
                        "summary": "Adds a timer component.", "rationale": "Timing control is required.",
                        "assumptions": [], "operations": [{"operation_id": "create_timer",
                            "type": "create_entity", "kind": "component", "name": "timer", "entity_id": "local_timer",
                            "instances": []}, {"operation_id": "explanation", "type": "set_entity_metadata",
                            "entity": {"document_id": context["authoritative_context"]["document_id"], "entity_kind": "component", "entity_id": "local_timer"},
                            "description": "Timing control component. Interface and functional RTL are not implemented yet."}],
                    })}}]}
            else:
                delta = {"content": "The timer proposal is ready for review."}
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for index, chunk in enumerate(({"role": "assistant"}, delta, {})):
                event = {"id": "fixture", "object": "chat.completion.chunk", "created": 1,
                         "model": "gpt-4o-mini", "choices": [{"index": 0, "delta": chunk,
                         "finish_reason": ("tool_calls" if calls < 2 else "stop") if index == 2 else None}]}
                self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def reviewed_assistant_run(argv):
    """Exercise both explicit architecture approval and the final owner policy."""
    assert assistant_main(argv) == 0
    path = resolve_spec_target(argv[0])
    run = json.loads((assistant_state_root(path) / "last-run.json").read_text())
    review = run["architecture_reviews"][-1]
    assert review["status"] == "pending"
    assert spec_main(["approve-architecture", str(path), review["reviewId"]]) == 0
    split = argv.index("--")
    return assistant_main([*argv[:split], "--architecture-review-id", review["reviewId"], *argv[split:]])


def test_workspace_discovery_and_explicit_target(tmp_path):
    workspace = tmp_path / "my design"
    assert resolve_spec_target(str(workspace), create=True) == workspace / "my_design.spec"
    first = workspace / "first.spec"
    second = workspace / "second.spec"
    SpecPackage.create().save(str(first))
    assert resolve_spec_target(str(workspace)) == first
    SpecPackage.create().save(str(second))
    with pytest.raises(ValueError, match="first.spec.*second.spec"):
        resolve_spec_target(str(workspace))
    assert resolve_spec_target(str(second)) == second
    assert resolve_spec_target(str(workspace / "exact.spec"), create=True) == workspace / "exact.spec"


def test_focused_turn_review_and_approval(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / "timer-design"
    with model_fixture() as endpoint:
        monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
        monkeypatch.setenv("OPENAI_BASE_URL", endpoint)
        monkeypatch.setenv("SPEC2GDS_SESSION_COMPRESSION", "none")
        assert reviewed_assistant_run([str(workspace), "--require-human-approval", "--preset", "focused", "--", "Propose a timer"]) == 0
    path = workspace / "timer-design.spec"
    run = json.loads((assistant_state_root(path) / "last-run.json").read_text())
    assert run["session_id"]
    assert (assistant_state_root(path) / "runs" / f"{run['session_id']}.json").exists()
    assert Path(run["events_path"]).exists()
    assert len(run["proposals"]) == 1
    assert run["proposals"][0]["state"] == "ready"
    assert not [item for item in SpecPackage.load(str(path)).manifest.documents if item.kind == "component"]
    assert spec_main(["reviews", str(workspace)]) == 0
    open_editor = V1Session(str(path))
    assert spec_main(["approve", str(workspace)]) == 0
    with pytest.raises(ValueError, match="refresh from disk"):
        open_editor.save()
    assert [item for item in SpecPackage.load(str(path)).manifest.documents if item.kind == "component"]
    reviews = list_spec_reviews(assistant_state_root(path), run["document_id"])
    assert reviews[0]["state"] == "applied"
    assert "timer proposal is ready" in capsys.readouterr().out


def test_preset_rejected_before_creation(tmp_path, capsys):
    workspace = tmp_path / "design"
    assert assistant_main([str(workspace), "--preset", "goal", "--", "Help"]) == 2
    assert not workspace.exists()
    assert "focused" in capsys.readouterr().err


def test_editor_save_rejects_changed_disk(tmp_path):
    path = tmp_path / "design.spec"
    SpecPackage.create().save(str(path))
    editor = V1Session(str(path))
    other = V1Session(str(path))
    other.package.narrative = other.package.narrative.model_copy(update={"title": "Changed in another session"})
    other.save()
    with pytest.raises(ValueError, match="changed on disk"):
        editor.save()


def test_multiple_reviews_require_id_and_stale_after_apply(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / "multi"
    with model_fixture() as endpoint:
        monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
        monkeypatch.setenv("OPENAI_BASE_URL", endpoint)
        monkeypatch.setenv("SPEC2GDS_SESSION_COMPRESSION", "none")
        for _ in range(3):
            assert reviewed_assistant_run([str(workspace), "--require-human-approval", "--", "Propose a timer"]) == 0
    path = workspace / "multi.spec"
    root = assistant_state_root(path)
    document_id = SpecPackage.load(str(path)).manifest.document_id
    ids = [item["proposalId"] for item in list_spec_reviews(root, document_id)]
    assert len(ids) == 3
    assert len(list((root / "workspaces" / "design-sources").iterdir())) == 1
    assert spec_main(["approve", str(workspace)]) == 2
    assert "Multiple proposals" in capsys.readouterr().err
    assert spec_main(["reject", str(workspace), ids[0]]) == 0
    assert spec_main(["approve", str(workspace)]) == 2
    assert spec_main(["approve", str(workspace), ids[1]]) == 0
    assert spec_main(["approve", str(workspace), ids[2]]) == 2
    states = {item["proposalId"]: item["state"] for item in list_spec_reviews(root, document_id)}
    assert states == {ids[0]: "discarded", ids[1]: "applied", ids[2]: "stale"}


def test_interrupted_approval_reconciles_saved_proposal(tmp_path, monkeypatch):
    from spec2gds.agent_spec.spec_format.assistant import SpecChangeProposal
    from spec2gds.agent_spec.spec_format.proposal_service import apply_assistant_proposal
    from spec2gds.agent_spec.spec_format.review_store import review_bridge

    workspace = tmp_path / "retry"
    with model_fixture() as endpoint:
        monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
        monkeypatch.setenv("OPENAI_BASE_URL", endpoint)
        assert reviewed_assistant_run([str(workspace), "--require-human-approval", "--", "Propose a timer"]) == 0
    path = workspace / "retry.spec"
    root = assistant_state_root(path)
    document_id = SpecPackage.load(str(path)).manifest.document_id
    review = list_spec_reviews(root, document_id)[0]
    review_bridge(root, "begin", review["proposalId"])
    first = apply_assistant_proposal(V1Session(str(path)), SpecChangeProposal.model_validate(review["artifact"]))
    assert first["status"] == "applied"
    assert list_spec_reviews(root, document_id)[0]["state"] == "applying"
    assert spec_main(["approve", str(workspace)]) == 0
    assert list_spec_reviews(root, document_id)[0]["state"] == "applied"
    assert len(V1Session(str(path)).activity.state.assistant_changes) == 1


def test_editor_http_save_conflict_requires_refresh(tmp_path):
    from urllib.error import HTTPError

    from scripts.spec2gds_assistant import _private_owner, _request

    path = tmp_path / "editor.spec"
    SpecPackage.create().save(str(path))
    with _private_owner() as url:
        opened = _request(url, "/documents/open", {"path": str(path)})
        revision = opened["source_revision_hash"]
        other = V1Session(str(path))
        other.package.narrative = other.package.narrative.model_copy(update={"title": "Updated outside editor"})
        other.save()
        with pytest.raises(HTTPError) as conflict:
            _request(url, "/transactions", {"expected_source_revision_hash": revision, "operations": []})
        assert conflict.value.code == 409
        assert "stale" in conflict.value.read().decode().lower()


def test_focused_turn_saves_automatically_by_default(tmp_path, monkeypatch):
    workspace = tmp_path / "automatic"
    with model_fixture() as endpoint:
        monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
        monkeypatch.setenv("OPENAI_BASE_URL", endpoint)
        monkeypatch.setenv("SPEC2GDS_SESSION_COMPRESSION", "none")
        assert reviewed_assistant_run([str(workspace), "--", "Add a timer"]) == 0
    path = workspace / "automatic.spec"
    run = json.loads((assistant_state_root(path) / "last-run.json").read_text())
    assert run["approval_policy"] == "automatic"
    assert run["proposals"][0]["state"] == "applied"
    session = V1Session(str(path))
    assert len(session.revision.components) == 1
    assert len(session.activity.state.assistant_changes) == 1
    assert session.journal.history()["items"][0]["owner_result"]["source_revision_hash"] == session.revision.source_revision_hash


def test_assistant_creates_exact_spec_path(tmp_path, monkeypatch):
    path = tmp_path / "workspace" / "chosen.spec"
    with model_fixture() as endpoint:
        monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
        monkeypatch.setenv("OPENAI_BASE_URL", endpoint)
        assert reviewed_assistant_run([str(path), "--", "Propose a timer"]) == 0
    assert path.is_file()
    assert sorted(path.parent.glob("*.spec")) == [path]
    assert len(json.loads((assistant_state_root(path) / "last-run.json").read_text())["proposals"]) == 1

"""Workspace inspection and flow-only Assistant command checks."""
from __future__ import annotations

import json
import subprocess
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scripts.spec2gds_assistant import main as assistant_main, _private_spec_service
from scripts.spec2gds_spec import main as spec_main
from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.review_store import review_bridge, node_executable, _BRIDGE
from spec2gds.spec.spec_format.v1_api import V1Session
from spec2gds.spec.spec_format.workspace_target import assistant_state_root, resolve_spec_target


@contextmanager
def model_fixture():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            tools = {tool["function"]["name"] for tool in body["tools"]}
            assert not tools & {"prepare_spec_proposal", "prepare_architecture_review", "prepare_spec_document_creation"}
            if tools == {"structured_output"}:
                name = "structured_output"
                args = {"title": "Timer architecture", "components": [{"name": "timer", "purpose": "Replicate the input."}],
                        "designs": [], "interfaces": [{"component": "timer", "ports": [{"name": "a", "direction": "in", "range": None, "description": "Input signal"}, {"name": "q", "direction": "out", "range": None, "description": "Replicated output"}], "parameters": [], "constant_context": ""}],
                        "clocks_resets": [], "decomposition_rationale": "One combinational leaf.", "assumptions": [], "open_questions": [], "concrete_configuration": {"width": 1}}
            elif not any(message.get("role") == "tool" for message in body["messages"]):
                name, args = "get_bound_context", {}
            else:
                assert "flow_add_component" in tools
                name, args = "flow_add_component", {"title": "Add timer", "request": "Add timer with scalar a input, q output and assign q = a."}
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            delta = {"tool_calls": [{"index": 0, "id": f"cli_{len(requests)}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}
            for index, chunk in enumerate(({"role": "assistant"}, delta, {})):
                event = {"id": "fixture", "object": "chat.completion.chunk", "created": 1, "model": "gpt-4o-mini", "choices": [{"index": 0, "delta": chunk, "finish_reason": "tool_calls" if index == 2 else None}]}
                self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_workspace_discovery_and_explicit_target(tmp_path):
    workspace = tmp_path / "my design"
    assert resolve_spec_target(str(workspace), create=True) == workspace / "my_design.spec"
    first, second = workspace / "first.spec", workspace / "second.spec"
    SpecPackage.create().save(str(first))
    assert resolve_spec_target(str(workspace)) == first
    SpecPackage.create().save(str(second))
    with pytest.raises(ValueError, match="first.spec.*second.spec"):
        resolve_spec_target(str(workspace))
    assert resolve_spec_target(str(second)) == second


@pytest.mark.extensive
@pytest.mark.parametrize("restricted", [False, True])
def test_focused_cli_returns_correlated_flow_wait(tmp_path, monkeypatch, restricted):
    path = tmp_path / "timer.spec"
    assert spec_main(["create", "--output", str(path), "--name", "Timer"]) == 0
    before = path.read_bytes()
    with _private_spec_service(restricted) as service_url, model_fixture() as (endpoint, requests):
        monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
        monkeypatch.setenv("OPENAI_BASE_URL", endpoint)
        monkeypatch.setenv("SPEC2GDS_SESSION_COMPRESSION", "none")
        assert assistant_main([str(path), "--service-url", service_url, "--", "Add timer with scalar a input, q output and assign q = a."]) == 2
    run = json.loads((assistant_state_root(path) / "last-run.json").read_text())
    assert run["schema_version"] == "spec2gds.assistant-workspace-run.v2"
    assert run["flow"]["status"] == "waiting"
    assert run["flow"]["pending"]["request"]["kind"] == "architecture"
    assert run["flow"]["flow_execution_id"]
    assert len(requests) == 3
    assert path.read_bytes() == before
    assert run["proposals"] == []


@pytest.mark.parametrize("command", ["approve", "reject", "approve-architecture", "revise-architecture", "cancel-architecture"])
def test_legacy_cli_decisions_are_not_commands(tmp_path, command):
    path = tmp_path / "design.spec"
    SpecPackage.create().save(str(path))
    before = path.read_bytes()
    with pytest.raises(SystemExit) as error:
        spec_main([command, str(path)])
    assert error.value.code == 2
    assert path.read_bytes() == before


@pytest.mark.parametrize("action", ["begin", "complete", "discard", "recover", "architecture-approved", "architecture-require"])
def test_review_bridge_cannot_advance_product_state(tmp_path, action):
    with pytest.raises(ValueError, match="read-only"):
        review_bridge(tmp_path, action, "old")
    assert not (tmp_path / "assistant.sqlite3").exists()


def test_node_review_bridge_also_rejects_direct_mutation(tmp_path):
    result = subprocess.run([node_executable(), str(_BRIDGE), "architecture-approved", str(tmp_path), "old"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "revision-checked flow controls" in result.stderr
    assert not (tmp_path / "assistant.sqlite3").exists()


def test_assistant_cannot_create_a_spec_outside_a_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    path = tmp_path / "workspace" / "chosen.spec"
    assert assistant_main([str(path), "--", "Create a Spec"]) == 2
    assert not path.exists()
    assert not path.parent.exists()


def test_legacy_architecture_flag_is_removed(tmp_path):
    with pytest.raises(SystemExit) as error:
        assistant_main([str(tmp_path), "--architecture-review-id", "old", "--", "Add timer"])
    assert error.value.code == 2


def test_preset_rejected_before_creation(tmp_path, capsys):
    workspace = tmp_path / "design"
    assert assistant_main([str(workspace), "--preset", "goal", "--", "Help"]) == 2
    assert not workspace.exists()
    assert "focused" in capsys.readouterr().err


def test_editor_save_rejects_changed_disk(tmp_path):
    path = tmp_path / "design.spec"
    SpecPackage.create().save(str(path))
    editor, other = V1Session(str(path)), V1Session(str(path))
    other.package.narrative = other.package.narrative.model_copy(update={"title": "Changed in another conversation"})
    other.save()
    with pytest.raises(ValueError, match="changed on disk"):
        editor.save()


def test_editor_http_save_conflict_requires_refresh(tmp_path):
    from urllib.error import HTTPError
    from scripts.spec2gds_assistant import _private_spec_service, _request
    path = tmp_path / "editor.spec"
    SpecPackage.create().save(str(path))
    with _private_spec_service() as url:
        opened = _request(url, "/documents/open", {"path": str(path)})
        other = V1Session(str(path))
        other.package.narrative = other.package.narrative.model_copy(update={"title": "Updated outside editor"})
        other.save()
        with pytest.raises(HTTPError) as conflict:
            _request(url, "/transactions", {"expected_source_revision_hash": opened["source_revision_hash"], "operations": []})
        assert conflict.value.code == 409

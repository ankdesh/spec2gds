"""Focused Assistant requests and bounded flows against an existing Spec."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import uvicorn
from spec2gds_runtime.service_config import listener_overrides, resolve_config

from spec2gds.service_registry import load_service_registry
from spec2gds.spec.spec_format.review_store import (
    _REPO_ROOT,
    list_spec_reviews,
    node_executable,
    review_bridge,
)
from spec2gds.spec.spec_format.v1_api import create_app
from spec2gds.spec.spec_format.workspace_target import (
    assistant_state_root,
    resolve_spec_target,
)


def _request(url: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = Request(
        f"{url}{path}",
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json"} if payload is not None else {},
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response)


@contextmanager
def _private_spec_service(require_designer_approval: bool = False) -> Iterator[str]:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    port = sock.getsockname()[1]
    registry = load_service_registry(overrides=listener_overrides("spec_editor", host="127.0.0.1", port=port))
    config = uvicorn.Config(create_app(require_designer_approval, service_registry=registry), host="127.0.0.1", port=port, log_level="error", access_log=False)
    server = uvicorn.Server(config)
    worker = threading.Thread(target=lambda: asyncio.run(server.serve(sockets=[sock])), daemon=True)
    worker.start()
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if not worker.is_alive():
                raise RuntimeError("Private Spec service stopped during startup.")
            try:
                if _request(url, "/health").get("status") == "ok":
                    break
            except (URLError, OSError):
                time.sleep(0.1)
        else:
            raise RuntimeError("Private Spec service did not become ready.")
        yield url
    finally:
        server.should_exit = True
        worker.join(timeout=10)
        sock.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spec2gds-assistant", description="Run one focused assistant turn against a workspace specification.")
    parser.add_argument("target", help="Workspace directory or exact .spec path")
    parser.add_argument("--preset", default="focused", help="Assistant preset (currently focused only)")
    parser.add_argument("--service-config", type=Path)
    parser.add_argument("--service-url", help="Running Spec service URL; its policy and receipts remain authoritative")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run a Focused request against a running Spec service for an existing package.

    Persist native session/run output for later review and evaluation. Only the
    Focused preset is admitted. A flow returns its first wait or terminal result;
    later controls use a supported Harness profile or SDK.
    """
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = _parser()
    if "--" not in raw:
        parser.parse_args(raw)  # Let argparse handle --help and missing targets.
        parser.error("Place the request after --.")
    separator = raw.index("--")
    args = parser.parse_args(raw[:separator])
    prompt = " ".join(raw[separator + 1:]).strip()
    try:
        if args.preset != "focused":
            raise ValueError("Only the focused single-turn preset is supported by this CLI.")
        if not prompt:
            raise ValueError("A request is required after --.")
        node = node_executable()
        assistant_root = _REPO_ROOT / "ai-assistant"
        if not (assistant_root / "lib/index.js").exists():
            raise RuntimeError("Build the assistant first: cd ai-assistant && npm run build")
        if not os.environ.get("OPENAI_API_KEY") and not (assistant_root / ".env").exists():
            raise RuntimeError("Set OPENAI_API_KEY before running the assistant.")
        spec_path = resolve_spec_target(args.target)
        if not spec_path.is_file():
            raise ValueError("The Assistant CLI requires an existing Spec. Create a new Spec through a creation flow.")
        if not args.service_url:
            raise ValueError("A running Spec service is required. Pass --service-url; flow waits must retain their service authority.")
        owner_url = args.service_url.rstrip("/")
        policy = _request(owner_url, "/assistant/capabilities")["approval_policy"]
        if policy not in {"automatic", "review"}:
            raise ValueError("The Spec service did not publish a valid approval policy.")
        state_root = assistant_state_root(spec_path)
        state_root.mkdir(parents=True, exist_ok=True)
        identity_owner = f"spec2gds-cli:{spec_path}"
        snapshot = _request(owner_url, "/documents/open", {"path": str(spec_path)})
        document_id = snapshot["document_id"]
        workspace_key = hashlib.sha256(
            json.dumps({"domain": "spec", "ownerUrl": identity_owner, "documentId": document_id},
                       ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        cwd = state_root / "workspaces" / "design-sources" / workspace_key
        cwd.mkdir(parents=True, exist_ok=True)
        env = {
            **os.environ,
            "PATH": f"{Path(node).parent}:{os.environ.get('PATH', '')}",
            "ASSISTANT_PROFILE": "spec2gds-headless",
            "ASSISTANT_STATE": str(state_root),
            "SPEC2GDS_SCRATCH_ROOT": str(state_root / "workspaces"),
            "SPEC_DOCUMENT_ROOT": str(state_root / "documents"),
            "SPEC2GDS_CLI_WORKSPACE_IDENTITY": identity_owner,
            "SPEC2GDS_BINDING_JSON": json.dumps({
                "domain": "spec", "preset": "focused", "serviceBaseUrl": owner_url,
                "documentId": document_id, "scope": "document",
                "serviceDocumentKey": snapshot["owner_document_key"],
            }),
            "DSH_PRODUCT_RUN_CWD": str(cwd),
        }
        # The explicit service URL is the CLI override for this request.
        selected = urlsplit(owner_url)
        endpoint = {"scheme": selected.scheme, "host": selected.hostname,
                    "port": selected.port or (443 if selected.scheme == "https" else 80)}
        config = resolve_config(args.service_config, overrides={"spec_editor": {surface: endpoint for surface in ("service", "ui")}})
        run = _REPO_ROOT / "temp" / "TEMP_serve-all" / ("request_" + uuid4().hex)
        run.mkdir(parents=True)
        snapshot = run / "services.json"
        snapshot.write_text(json.dumps(config))
        result = subprocess.run(
            [node, str(assistant_root / "scripts/dev.mjs"), "--service-config", str(snapshot), "--json", prompt],
            cwd=cwd, env=env, text=True, capture_output=True, check=False,
        )
        events = []
        for line in result.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        session_id = next((item["sessionId"] for item in events if item.get("type") == "session"), None)
        final = next((item["text"] for item in reversed(events) if item.get("type") == "final"), "")
        try:
            flow_result = json.loads(final)
        except (json.JSONDecodeError, TypeError):
            flow_result = None
        reviews = [item for item in list_spec_reviews(state_root, document_id) if item["sessionId"] == session_id]
        runs = state_root / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        event_path = runs / f"{session_id or 'failed-turn'}.jsonl"
        event_path.write_text(result.stdout, encoding="utf-8")
        architecture_reviews = review_bridge(state_root, "architecture-list")["architecture_reviews"]
        run = {
            "schema_version": "spec2gds.assistant-workspace-run.v2",
            "flow": flow_result if isinstance(flow_result, dict) and "flow_execution_id" in flow_result else None,
            "spec_path": str(spec_path), "document_id": document_id,
            "session_id": session_id, "preset": "focused", "exit_code": result.returncode,
            "approval_policy": policy,
            "service_url": owner_url,
            "answer": final, "events_path": str(event_path),
            "architecture_reviews": [item for item in architecture_reviews if item["sessionId"] == session_id],
            "proposals": [{"proposal_id": item["proposalId"], "state": item["state"]} for item in reviews],
        }
        output = state_root / "last-run.json"
        temporary = output.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output)
        if session_id:
            (runs / f"{session_id}.json").write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
        print(final or result.stderr.strip() or "Assistant produced no final answer.")
        print(f"Specification: {spec_path}")
        for item in reviews:
            print(f"Proposal {item['proposalId']}: {item['state']}")
        return result.returncode
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

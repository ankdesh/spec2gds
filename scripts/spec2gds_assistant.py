"""Workspace-oriented Python command for one focused assistant turn."""

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
from urllib.request import Request, urlopen

import uvicorn

from spec2gds.agent_spec.spec_format.review_store import (
    _REPO_ROOT,
    list_spec_reviews,
    node_executable,
)
from spec2gds.agent_spec.spec_format.v1_api import create_app
from spec2gds.agent_spec.spec_format.workspace_target import (
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
def _private_owner() -> Iterator[str]:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    port = sock.getsockname()[1]
    config = uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="error", access_log=False)
    server = uvicorn.Server(config)
    worker = threading.Thread(target=lambda: asyncio.run(server.serve(sockets=[sock])), daemon=True)
    worker.start()
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if not worker.is_alive():
                raise RuntimeError("Private Spec owner stopped during startup.")
            try:
                if _request(url, "/health").get("status") == "ok":
                    break
            except (URLError, OSError):
                time.sleep(0.1)
        else:
            raise RuntimeError("Private Spec owner did not become ready.")
        yield url
    finally:
        server.should_exit = True
        worker.join(timeout=10)
        sock.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spec2gds-assistant", description="Run one focused assistant turn against a workspace specification.")
    parser.add_argument("target", help="Workspace directory or exact .spec path")
    parser.add_argument("--preset", default="focused", help="Assistant preset (currently focused only)")
    return parser


def main(argv: list[str] | None = None) -> int:
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
        spec_path = resolve_spec_target(args.target, create=True)
        state_root = assistant_state_root(spec_path)
        state_root.mkdir(parents=True, exist_ok=True)
        identity_owner = f"spec2gds-cli:{spec_path}"
        with _private_owner() as owner_url:
            snapshot = _request(
                owner_url,
                "/documents/open" if spec_path.exists() else "/documents/create",
                {"path": str(spec_path)} if spec_path.exists() else
                {"path": str(spec_path), "title": spec_path.stem},
            )
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
                "SPEC_SERVICE_ALLOWLIST": owner_url,
                "SPEC2GDS_CLI_WORKSPACE_IDENTITY": identity_owner,
                "SPEC2GDS_BINDING_JSON": json.dumps({
                    "domain": "spec", "preset": "focused", "serviceBaseUrl": owner_url,
                    "documentId": document_id, "scope": "document",
                }),
                "DSH_PRODUCT_RUN_CWD": str(cwd),
            }
            result = subprocess.run(
                [node, str(assistant_root / "scripts/dev.mjs"), "--json", prompt],
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
        reviews = [item for item in list_spec_reviews(state_root, document_id) if item["sessionId"] == session_id]
        runs = state_root / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        event_path = runs / f"{session_id or 'failed-turn'}.jsonl"
        event_path.write_text(result.stdout, encoding="utf-8")
        run = {
            "schema_version": "spec2gds.assistant-workspace-run.v1",
            "spec_path": str(spec_path), "document_id": document_id,
            "session_id": session_id, "preset": "focused", "exit_code": result.returncode,
            "answer": final, "events_path": str(event_path),
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

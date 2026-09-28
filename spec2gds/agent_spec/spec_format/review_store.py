"""Python access to the Harness-owned review store through its internal bridge."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BRIDGE = _REPO_ROOT / "scripts" / "spec2gds_review_bridge.mjs"


def node_executable() -> str:
    candidates = [shutil.which("node")]
    candidates.extend(str(path) for path in (Path.home() / ".nvm/versions/node").glob("*/bin/node"))
    for candidate in reversed([item for item in candidates if item]):
        result = subprocess.run([candidate, "--version"], capture_output=True, text=True, check=False)
        if result.returncode:
            continue
        try:
            major, minor, *_ = (int(part) for part in result.stdout.strip().lstrip("v").split("."))
        except ValueError:
            continue
        if major >= 24 or (major == 22 and minor >= 19):
            return candidate
    raise RuntimeError("Node.js 22.19+ or 24+ is required for the assistant Harness runtime.")


def review_bridge(
    state_root: Path, action: str, proposal_id: str | None = None, payload: Any = None
) -> dict[str, Any]:
    command = [node_executable(), str(_BRIDGE), action, str(state_root)]
    if proposal_id is not None:
        command.append(proposal_id)
    result = subprocess.run(
        command,
        input=json.dumps(payload) if payload is not None else None,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "PATH": f"{Path(command[0]).parent}:{os.environ.get('PATH', '')}"},
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or "Review bridge failed.")
    return json.loads(result.stdout)


def list_spec_reviews(state_root: Path, document_id: str) -> list[dict[str, Any]]:
    return [
        item for item in review_bridge(state_root, "list")["reviews"]
        if item["documentId"] == document_id and item["domain"] == "spec"
    ]

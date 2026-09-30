"""Durable local package bindings, submission receipts, and source event cursors.

The package remains authoritative for source and committed assistant decisions.
This journal stores pending reviews and presentation data, never a second source
document. A save interrupted before journal completion is reconciled from the
decision saved atomically inside the package.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator

from spec2gds.agent_spec.spec_format.workspace_target import assistant_state_root


def document_key(path: str, document_id: str) -> str:
    identity = f"{Path(path).expanduser().resolve()}\0{document_id}"
    return "spec_" + sha256(identity.encode()).hexdigest()[:32]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class _Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA synchronous=FULL")
            with connection:
                yield connection
        finally:
            connection.close()


class OwnerBindings(_Database):
    """Service-local catalog used to reopen exact packages after a restart."""

    def __init__(self, root: str | Path | None = None) -> None:
        super().__init__(Path(root or os.environ.get("SPEC_EDITOR_STATE_ROOT", ".spec2gds/editor")) / "bindings.sqlite3")
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS bindings (key TEXT PRIMARY KEY, path TEXT NOT NULL, document_id TEXT NOT NULL, sidecar_root TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS creations (request_id TEXT PRIMARY KEY, input_json TEXT NOT NULL)")

    def register(self, path: str, document_id: str, sidecar_root: str | None = None) -> str:
        path = str(Path(path).expanduser().resolve())
        key = document_key(path, document_id)
        with self.connection() as db:
            db.execute("INSERT INTO bindings VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET sidecar_root=excluded.sidecar_root", (key, path, document_id, sidecar_root))
        return key

    def get(self, key: str) -> dict[str, Any] | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM bindings WHERE key=?", (key,)).fetchone()
        return dict(row) if row else None

    def matching(self, document_id: str) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM bindings WHERE document_id=? ORDER BY key", (document_id,)).fetchall()
        return [dict(row) for row in rows if Path(row["path"]).is_file()]

    def creation(self, request_id: str, values: dict[str, Any]) -> bool:
        """Reserve the exact creation input before writing the package."""
        encoded = _json(values)
        with self.connection() as db:
            existing = db.execute("SELECT input_json FROM creations WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                if existing[0] != encoded:
                    raise ValueError("Creation request ID was reused with different values.")
                return True
            if Path(values["path"]).expanduser().resolve().exists():
                raise ValueError("Creation destination already exists.")
            db.execute("INSERT INTO creations VALUES (?,?)", (request_id, encoded))
        return False


class OwnerJournal(_Database):
    def __init__(self, path: str) -> None:
        self.spec_path = path
        super().__init__(assistant_state_root(Path(path)) / "owner.sqlite3")
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS submissions (ordinal INTEGER PRIMARY KEY AUTOINCREMENT, proposal_id TEXT UNIQUE NOT NULL, artifact_json TEXT NOT NULL, record_json TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_json TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL)")

    def register(self, artifact: dict[str, Any], session_id: str | None = None, *, recovered: bool = False) -> dict[str, Any]:
        encoded = _json(artifact)
        timestamp = datetime.now(UTC).isoformat()
        record = {"proposal_id": artifact["proposal_id"], "session_id": session_id,
                  "state": "previewing", "artifact": artifact, "preview": None,
                  "diagnostics": [], "owner_result": None,
                  "created_at": timestamp, "updated_at": timestamp, "recovered": recovered}
        with self.connection() as db:
            existing = db.execute("SELECT artifact_json,record_json FROM submissions WHERE proposal_id=?", (artifact["proposal_id"],)).fetchone()
            if existing:
                saved = json.loads(existing[1])
                if existing[0] != encoded:
                    # Old decision records did not retain presentation metadata.
                    # They still retain the complete identity of the mutation.
                    fields = ("document_id", "scope", "target", "base_source_revision_hash", "operations")
                    if not saved.get("recovered") or any(saved["artifact"].get(key) != artifact.get(key) for key in fields):
                        raise ValueError("Proposal ID was reused with a different artifact.")
                    saved.update(artifact=artifact, recovered=False)
                    db.execute("UPDATE submissions SET artifact_json=?,record_json=? WHERE proposal_id=?", (encoded, _json(saved), artifact["proposal_id"]))
                return saved
            db.execute("INSERT INTO submissions(proposal_id,artifact_json,record_json) VALUES (?,?,?)", (artifact["proposal_id"], encoded, _json(record)))
        return record

    def get(self, proposal_id: str) -> dict[str, Any] | None:
        with self.connection() as db:
            row = db.execute("SELECT record_json FROM submissions WHERE proposal_id=?", (proposal_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def update(self, proposal_id: str, **values: Any) -> dict[str, Any]:
        with self.connection() as db:
            row = db.execute("SELECT record_json FROM submissions WHERE proposal_id=?", (proposal_id,)).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            previous = json.loads(row[0])
            record = {**previous, **values, "updated_at": datetime.now(UTC).isoformat()}
            db.execute("UPDATE submissions SET record_json=? WHERE proposal_id=?", (_json(record), proposal_id))
            if record["state"] != previous["state"] and record["state"] in {"ready", "applied", "discarded", "stale", "rejected"}:
                artifact = record["artifact"]
                result = record.get("owner_result") or {}
                db.execute("INSERT INTO events(event_json) VALUES (?)", (_json({
                    "event_type": "assistant.submission.changed", "proposal_id": proposal_id,
                    "state": record["state"], "document_id": artifact["document_id"],
                    "owner_document_key": document_key(self.spec_path, artifact["document_id"]),
                    "source_revision_hash": result.get("source_revision_hash", artifact["base_source_revision_hash"]),
                    "origin": "assistant", "affected_entities": [],
                }),))
        return record

    def history(self, before: int | None = None, limit: int = 50) -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise ValueError("History limit must be between 1 and 100.")
        with self.connection() as db:
            rows = db.execute("SELECT ordinal,record_json FROM submissions WHERE (? IS NULL OR ordinal<?) ORDER BY ordinal DESC LIMIT ?", (before, before, limit + 1)).fetchall()
        items = []
        for row in rows[:limit]:
            record = json.loads(row["record_json"])
            artifact = record.pop("artifact")
            record.pop("preview", None)
            result = record.get("owner_result") or {}
            record["owner_result"] = {key: result[key] for key in ("status", "source_revision_hash", "saved_at", "application_mode") if key in result}
            items.append({**record, "ordinal": row["ordinal"], "title": artifact["title"],
                          "summary": artifact["summary"], "scope": artifact["scope"],
                          "target": artifact["target"], "assumptions": artifact["assumptions"],
                          "base_source_revision_hash": artifact["base_source_revision_hash"],
                          "operation_count": len(artifact["operations"])})
        return {"items": items, "next_cursor": rows[limit - 1]["ordinal"] if len(rows) > limit else None}

    def observe(self, event: dict[str, Any], *, seed: bool = False) -> int:
        """Record only a new authoritative revision, including external writes."""
        with self.connection() as db:
            row = db.execute("SELECT value FROM metadata WHERE name='revision'").fetchone()
            revision = event["source_revision_hash"]
            if row is None or row[0] != revision:
                db.execute("INSERT INTO metadata VALUES ('revision',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value", (revision,))
                if not (seed and row is None):
                    db.execute("INSERT INTO events(event_json) VALUES (?)", (_json(event),))
            cursor = db.execute("SELECT COALESCE(MAX(sequence),0) FROM events").fetchone()[0]
        return int(cursor)

    def events_after(self, sequence: int, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("SELECT sequence,event_json FROM events WHERE sequence>? ORDER BY sequence LIMIT ?", (sequence, limit)).fetchall()
        return [{**json.loads(row["event_json"]), "sequence": row["sequence"]} for row in rows]

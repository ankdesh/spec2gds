"""Durable local package bindings, submission receipts, and source event cursors.

The package remains authoritative for source and committed assistant decisions.
This journal stores pending reviews and presentation data, never a second source
document. A save interrupted before journal completion is reconciled from the
decision saved atomically inside the package.

Reviewer path: service keys include canonical package path and document ID,
so copied packages do not share authority merely because their IDs match.
Journal receipts/events supplement package decisions; they never replace source.
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

from spec2gds.spec.spec_format.naming import name_key, require_unique_name, unique_name
from spec2gds.spec.spec_format.workspace_target import assistant_state_root


def document_key(path: str, document_id: str) -> str:
    identity = f"{Path(path).expanduser().resolve()}\0{document_id}"
    return "spec_" + sha256(identity.encode()).hexdigest()[:32]


def _receipt(value: dict[str, Any]) -> dict[str, Any]:
    """Expose canonical receipt data and retain the earlier transport alias."""
    result = value.get("service_result", value.get("owner_result"))
    return {**value, "service_result": result, "owner_result": result}


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


class SpecServiceBindings(_Database):
    """Service-local catalog used to reopen exact packages after a restart."""

    def __init__(self, root: str | Path | None = None, *, filesystem=None) -> None:
        self.filesystem = filesystem
        super().__init__(Path(root or os.environ.get("SPEC_SERVICE_STATE_ROOT", os.environ.get("SPEC_EDITOR_STATE_ROOT", ".spec2gds/editor"))) / "bindings.sqlite3")
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS bindings (key TEXT PRIMARY KEY, path TEXT NOT NULL, document_id TEXT NOT NULL, sidecar_root TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS creations (request_id TEXT PRIMARY KEY, input_json TEXT NOT NULL)")
            creation_columns = {row["name"] for row in db.execute("PRAGMA table_info(creations)")}
            for column in ("destination", "document_id", "edit_access_json"):
                if column not in creation_columns:
                    db.execute(f"ALTER TABLE creations ADD COLUMN {column} TEXT")
            columns = {row["name"] for row in db.execute("PRAGMA table_info(bindings)")}
            for column in ("display_name", "name_key", "directory"):
                if column not in columns:
                    db.execute(f"ALTER TABLE bindings ADD COLUMN {column} TEXT")
            db.execute("DROP INDEX IF EXISTS binding_name")
            for row in db.execute("SELECT key,path FROM bindings WHERE directory IS NULL").fetchall():
                db.execute("UPDATE bindings SET directory=? WHERE key=?", (str(Path(row["path"]).parent), row["key"]))
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS binding_directory_name ON bindings(directory,name_key)")

    def register(self, path: str, document_id: str, sidecar_root: str | None = None) -> str:
        path = str(Path(path).expanduser().resolve())
        key = document_key(path, document_id)
        with self.connection() as db:
            db.execute("INSERT INTO bindings(key,path,document_id,sidecar_root,directory) VALUES (?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET sidecar_root=COALESCE(excluded.sidecar_root,bindings.sidecar_root),directory=excluded.directory", (key, path, document_id, sidecar_root,str(Path(path).parent)))
        return key

    @contextmanager
    def reserve_name(self, path: str, document_id: str, title: str, *, normalize: bool = False) -> Iterator[str]:
        """Hold a service-wide name reservation across the guarded package save.

        SQLite serializes concurrent admissions/renames; failed saves roll back
        their reservation. Missing package paths do not reserve visible names.
        """
        path = str(Path(path).expanduser().resolve())
        key = document_key(path, document_id)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            names = []
            if self.filesystem:
                from .archive import SpecPackage
                for item in self.filesystem.listing(str(Path(path).parent))["specifications"]:
                    if item["path"] == path:
                        continue
                    try:
                        names.append(SpecPackage.from_bytes(self.filesystem.read(item["path"])).narrative.title)
                    except (OSError, ValueError):
                        continue
            for row in db.execute("SELECT key,path,display_name FROM bindings WHERE directory=?", (str(Path(path).parent),)).fetchall():
                if row["key"] == key:
                    continue
                if Path(row["path"]).is_file():
                    from .archive import SpecPackage
                    try:
                        title_on_disk = (SpecPackage.from_bytes(self.filesystem.read(row["path"])) if self.filesystem else SpecPackage.load(row["path"])).narrative.title
                    except (OSError, ValueError):
                        title_on_disk = row["display_name"]
                    if title_on_disk:
                        names.append(title_on_disk)
                else:
                    db.execute("UPDATE bindings SET display_name=NULL,name_key=NULL WHERE key=?", (row["key"],))
            name = unique_name(title, names) if normalize else require_unique_name(title, names)
            db.execute("INSERT INTO bindings(key,path,document_id,display_name,name_key,directory) VALUES (?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET display_name=excluded.display_name,name_key=excluded.name_key,directory=excluded.directory", (key, path, document_id, name, name_key(name),str(Path(path).parent)))
            yield name

    def catalog(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM bindings ORDER BY path").fetchall()
        return [dict(row) for row in rows if Path(row["path"]).is_file()]

    def get(self, key: str) -> dict[str, Any] | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM bindings WHERE key=?", (key,)).fetchone()
        return dict(row) if row else None

    def matching(self, document_id: str) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM bindings WHERE document_id=? ORDER BY key", (document_id,)).fetchall()
        return [dict(row) for row in rows if Path(row["path"]).is_file()]

    def creation_receipt(self, request_id: str) -> dict[str, Any] | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM creations WHERE request_id=?", (request_id,)).fetchone()
        return dict(row) if row else None

    def remember_creation_access(self, request_id: str, grant: dict) -> None:
        with self.connection() as db:
            db.execute("UPDATE creations SET edit_access_json=? WHERE request_id=?", (_json(grant), request_id))

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
            db.execute("INSERT INTO creations(request_id,input_json) VALUES (?,?)", (request_id, encoded))
        return False

    def reserve_creation(self, request_id: str, values: dict[str, Any]) -> tuple[str, str, bool]:
        """Reserve identity and readable destination before any network retry."""
        from spec2gds.spec.spec_format.models import new_entity_id
        from spec2gds.spec.spec_format.naming import filename_stem
        encoded = _json(values)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM creations WHERE request_id=?", (request_id,)).fetchone()
            if row:
                if row["input_json"] != encoded:
                    raise ValueError("Creation request ID was reused with different values.")
                destination = row["destination"] or values["path"]
                identity = row["document_id"] or values.get("document_id") or new_entity_id("spec")
                db.execute("UPDATE creations SET destination=?,document_id=? WHERE request_id=?",
                           (destination, identity, request_id))
                return destination, identity, True
            identity = values.get("document_id") or new_entity_id("spec")
            destination = Path(values["path"]).expanduser().resolve()
            if values.get("derive_named_path"):
                base = destination.with_name(filename_stem(values.get("title") or destination.stem) + ".spec")
                destination, number = base, 2
                reserved = {item[0] for item in db.execute("SELECT destination FROM creations WHERE destination IS NOT NULL")}
                while destination.exists() or str(destination) in reserved:
                    destination = base.with_name(f"{base.stem}-{number}.spec")
                    number += 1
            elif destination.exists():
                raise ValueError("Creation destination already exists.")
            db.execute("INSERT INTO creations(request_id,input_json,destination,document_id) VALUES (?,?,?,?)",
                       (request_id, encoded, str(destination), identity))
            return str(destination), identity, False


class SpecServiceJournal(_Database):
    def __init__(self, path: str) -> None:
        self.spec_path = path
        state_root = assistant_state_root(Path(path))
        legacy_path = state_root / "owner.sqlite3"
        super().__init__(legacy_path if legacy_path.exists() else state_root / "spec_service.sqlite3")
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS submissions (ordinal INTEGER PRIMARY KEY AUTOINCREMENT, proposal_id TEXT UNIQUE NOT NULL, artifact_json TEXT NOT NULL, record_json TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_json TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL)")

    def register(self, artifact: dict[str, Any], session_id: str | None = None, *, recovered: bool = False) -> dict[str, Any]:
        encoded = _json(artifact)
        timestamp = datetime.now(UTC).isoformat()
        record = {"proposal_id": artifact["proposal_id"], "session_id": session_id,
                  "state": "previewing", "artifact": artifact, "preview": None,
                  "diagnostics": [], "service_result": None,
                  "created_at": timestamp, "updated_at": timestamp, "recovered": recovered}
        with self.connection() as db:
            existing = db.execute("SELECT artifact_json,record_json FROM submissions WHERE proposal_id=?", (artifact["proposal_id"],)).fetchone()
            if existing:
                saved = _receipt(json.loads(existing[1]))
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
        return _receipt(record)

    def get(self, proposal_id: str) -> dict[str, Any] | None:
        with self.connection() as db:
            row = db.execute("SELECT record_json,ordinal FROM submissions WHERE proposal_id=?", (proposal_id,)).fetchone()
        return {**_receipt(json.loads(row[0])), "ordinal": row[1]} if row else None

    def update(self, proposal_id: str, **values: Any) -> dict[str, Any]:
        with self.connection() as db:
            row = db.execute("SELECT record_json FROM submissions WHERE proposal_id=?", (proposal_id,)).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            previous = _receipt(json.loads(row[0]))
            record = {**previous, **values, "updated_at": datetime.now(UTC).isoformat()}
            db.execute("UPDATE submissions SET record_json=? WHERE proposal_id=?", (_json(record), proposal_id))
            if record["state"] != previous["state"] and record["state"] in {"ready", "applied", "discarded", "stale", "rejected"}:
                artifact = record["artifact"]
                result = record.get("service_result") or {}
                db.execute("INSERT INTO events(event_json) VALUES (?)", (_json({
                    "event_type": "assistant.submission.changed", "proposal_id": proposal_id,
                    "state": record["state"], "document_id": artifact["document_id"],
                    "owner_document_key": document_key(self.spec_path, artifact["document_id"]),
                    "source_revision_hash": result.get("source_revision_hash", artifact["base_source_revision_hash"]),
                    "origin": "assistant", "affected_entities": [],
                }),))
        return self.get(proposal_id)

    def pending_review_ids(self) -> set[str]:
        """Return all ready submissions, independently of history pagination."""
        with self.connection() as db:
            rows = db.execute("SELECT proposal_id,record_json FROM submissions").fetchall()
        return {row["proposal_id"] for row in rows
                if _receipt(json.loads(row["record_json"]))["state"] == "ready"}

    def history(self, before: int | None = None, limit: int = 50) -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise ValueError("History limit must be between 1 and 100.")
        with self.connection() as db:
            rows = db.execute("SELECT ordinal,record_json FROM submissions WHERE (? IS NULL OR ordinal<?) ORDER BY ordinal DESC LIMIT ?", (before, before, limit + 1)).fetchall()
        items = []
        for row in rows[:limit]:
            record = _receipt(json.loads(row["record_json"]))
            artifact = record.pop("artifact")
            record.pop("preview", None)
            result = record.get("service_result") or {}
            record["service_result"] = {key: result[key] for key in ("status", "source_revision_hash", "saved_at", "application_mode") if key in result}
            record["owner_result"] = record["service_result"]
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

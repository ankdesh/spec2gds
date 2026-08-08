from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class AssistantDatabase:
    """Small SQLite repository for assistant-ui threads and review artifacts."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'regular'
                        CHECK (status IN ('regular', 'archived')),
                    domain TEXT NOT NULL DEFAULT 'circuit',
                    service_base_url TEXT,
                    circuit_base_url TEXT,
                    document_id TEXT,
                    entity_kind TEXT,
                    entity_id TEXT,
                    include_png INTEGER NOT NULL DEFAULT 0,
                    conversation_summary TEXT,
                    summary_message_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
                    parent_id TEXT,
                    role TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS messages_thread_created
                    ON messages(thread_id, created_at);

                CREATE TABLE IF NOT EXISTS proposal_reviews (
                    proposal_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
                    message_id TEXT,
                    state TEXT NOT NULL,
                    artifact_json TEXT NOT NULL,
                    base_document_json TEXT,
                    candidate_json TEXT,
                    diff_json TEXT,
                    diagnostics_json TEXT,
                    submitted_proposal_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS proposal_reviews_thread
                    ON proposal_reviews(thread_id, created_at);
                """
            )
            self._ensure_column(connection, "threads", "domain", "TEXT NOT NULL DEFAULT 'circuit'")
            self._ensure_column(connection, "threads", "service_base_url", "TEXT")
            self._ensure_column(connection, "threads", "entity_kind", "TEXT")
            self._ensure_column(connection, "threads", "entity_id", "TEXT")
            self._ensure_column(connection, "threads", "conversation_summary", "TEXT")
            self._ensure_column(connection, "threads", "summary_message_count", "INTEGER NOT NULL DEFAULT 0")
            connection.execute(
                """
                UPDATE threads
                SET domain = COALESCE(domain, 'circuit'),
                    service_base_url = COALESCE(service_base_url, circuit_base_url)
                """
            )

    def list_threads(self, *, include_archived: bool = True) -> list[dict[str, Any]]:
        query = "SELECT * FROM threads"
        parameters: tuple[object, ...] = ()
        if not include_archived:
            query += " WHERE status = ?"
            parameters = ("regular",)
        query += " ORDER BY updated_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._thread(row) for row in rows]

    def create_thread(
        self,
        *,
        thread_id: str | None = None,
        title: str = "New circuit chat",
        domain: str = "circuit",
    ) -> dict[str, Any]:
        if domain not in {"circuit", "spec"}:
            raise ValueError("Thread domain must be circuit or spec.")
        now = utc_now()
        identifier = thread_id or f"thread_{uuid4().hex}"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO threads(id, title, status, domain, created_at, updated_at)
                VALUES (?, ?, 'regular', ?, ?, ?)
                """,
                (identifier, title, domain, now, now),
            )
            row = connection.execute(
                "SELECT * FROM threads WHERE id = ?", (identifier,)
            ).fetchone()
        assert row is not None
        return self._thread(row)

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM threads WHERE id = ?", (thread_id,)
            ).fetchone()
        return self._thread(row) if row else None

    def update_thread(
        self,
        thread_id: str,
        *,
        title: str | None = None,
        status: str | None = None,
        include_png: bool | None = None,
    ) -> dict[str, Any] | None:
        assignments: list[str] = []
        values: list[object] = []
        if title is not None:
            assignments.append("title = ?")
            values.append(title)
        if status is not None:
            assignments.append("status = ?")
            values.append(status)
        if include_png is not None:
            assignments.append("include_png = ?")
            values.append(int(include_png))
        if not assignments:
            return self.get_thread(thread_id)
        assignments.append("updated_at = ?")
        values.append(utc_now())
        values.append(thread_id)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE threads SET {', '.join(assignments)} WHERE id = ?",
                values,
            )
            row = connection.execute(
                "SELECT * FROM threads WHERE id = ?", (thread_id,)
            ).fetchone()
        return self._thread(row) if row else None

    def bind_circuit(
        self, thread_id: str, *, base_url: str, document_id: str
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            current = connection.execute(
                "SELECT * FROM threads WHERE id = ?", (thread_id,)
            ).fetchone()
            if current is None:
                return None
            if current["service_base_url"] and (
                current["domain"] != "circuit"
                or current["service_base_url"] != base_url
                or current["document_id"] != document_id
            ):
                raise ValueError("This chat is already bound to a different target.")
            connection.execute(
                """
                UPDATE threads
                SET domain = 'circuit', service_base_url = ?, circuit_base_url = ?,
                    document_id = ?, entity_kind = NULL, entity_id = NULL, updated_at = ?
                WHERE id = ?
                """,
                (base_url, base_url, document_id, utc_now(), thread_id),
            )
            row = connection.execute(
                "SELECT * FROM threads WHERE id = ?", (thread_id,)
            ).fetchone()
        return self._thread(row) if row else None

    def bind_spec(
        self,
        thread_id: str,
        *,
        base_url: str,
        document_id: str,
        entity_kind: str,
        entity_id: str,
    ) -> dict[str, Any] | None:
        """Permanently bind one chat to one Spec document/entity."""
        with self._connect() as connection:
            current = connection.execute(
                "SELECT * FROM threads WHERE id = ?", (thread_id,)
            ).fetchone()
            if current is None:
                return None
            existing = current["service_base_url"]
            if existing and (
                current["domain"] != "spec"
                or existing != base_url
                or current["document_id"] != document_id
                or current["entity_kind"] != entity_kind
                or current["entity_id"] != entity_id
            ):
                raise ValueError("This chat is already bound to a different target.")
            connection.execute(
                """
                UPDATE threads
                SET domain = 'spec', service_base_url = ?, circuit_base_url = NULL,
                    document_id = ?, entity_kind = ?, entity_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (base_url, document_id, entity_kind, entity_id, utc_now(), thread_id),
            )
            row = connection.execute(
                "SELECT * FROM threads WHERE id = ?", (thread_id,)
            ).fetchone()
        return self._thread(row) if row else None

    def bind_spec_document(
        self,
        thread_id: str,
        *,
        base_url: str,
        document_id: str,
    ) -> dict[str, Any] | None:
        """Permanently bind one chat to one complete Spec document."""
        with self._connect() as connection:
            current = connection.execute(
                "SELECT * FROM threads WHERE id = ?", (thread_id,)
            ).fetchone()
            if current is None:
                return None
            existing = current["service_base_url"]
            if existing and (
                current["domain"] != "spec"
                or existing != base_url
                or current["document_id"] != document_id
                or current["entity_kind"] is not None
                or current["entity_id"] is not None
            ):
                raise ValueError("This chat is already bound to a different target.")
            connection.execute(
                """
                UPDATE threads
                SET domain = 'spec', service_base_url = ?, circuit_base_url = NULL,
                    document_id = ?, entity_kind = NULL, entity_id = NULL, updated_at = ?
                WHERE id = ?
                """,
                (base_url, document_id, utc_now(), thread_id),
            )
            row = connection.execute(
                "SELECT * FROM threads WHERE id = ?", (thread_id,)
            ).fetchone()
        return self._thread(row) if row else None

    def delete_thread(self, thread_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM threads WHERE id = ?", (thread_id,)
            )
        return cursor.rowcount > 0

    def list_messages(self, thread_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM messages
                WHERE thread_id = ?
                ORDER BY created_at, rowid
                """,
                (thread_id,),
            ).fetchall()
        return [self._message(row) for row in rows]

    def append_message(
        self,
        thread_id: str,
        *,
        message_id: str,
        parent_id: str | None,
        role: str,
        content: object,
    ) -> dict[str, Any]:
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO messages(
                    id, thread_id, parent_id, role, content_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    thread_id,
                    parent_id,
                    role,
                    json.dumps(content, separators=(",", ":")),
                    now,
                    now,
                ),
            )
            connection.execute(
                "UPDATE threads SET updated_at = ? WHERE id = ?",
                (now, thread_id),
            )
            self._refresh_summary(connection, thread_id)
            row = connection.execute(
                "SELECT * FROM messages WHERE id = ?", (message_id,)
            ).fetchone()
        assert row is not None
        return self._message(row)

    def update_message(
        self, thread_id: str, message_id: str, *, role: str, content: object
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE messages
                SET role = ?, content_json = ?, updated_at = ?
                WHERE id = ? AND thread_id = ?
                """,
                (
                    role,
                    json.dumps(content, separators=(",", ":")),
                    utc_now(),
                    message_id,
                    thread_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM messages WHERE id = ? AND thread_id = ?",
                (message_id, thread_id),
            ).fetchone()
            self._refresh_summary(connection, thread_id)
        return self._message(row) if row else None

    def delete_message(self, thread_id: str, message_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM messages WHERE id = ? AND thread_id = ?",
                (message_id, thread_id),
            )
            self._refresh_summary(connection, thread_id)
        return cursor.rowcount > 0

    def conversation_context(self, thread_id: str) -> dict[str, Any]:
        """Return the running compact transcript plus the latest eight messages."""
        thread = self.get_thread(thread_id)
        if thread is None:
            raise KeyError(f"Unknown thread: {thread_id}")
        messages = self.list_messages(thread_id)
        return {
            "summary": thread["conversation_summary"],
            "summarized_message_count": thread["summary_message_count"],
            "recent_messages": messages[-8:],
        }

    def upsert_review(
        self,
        *,
        proposal_id: str,
        thread_id: str,
        state: str,
        artifact: object,
        message_id: str | None = None,
        base_document: object | None = None,
        candidate: object | None = None,
        diff: object | None = None,
        diagnostics: object | None = None,
        submitted_proposal_id: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        values = (
            proposal_id,
            thread_id,
            message_id,
            state,
            self._dump(artifact),
            self._dump(base_document),
            self._dump(candidate),
            self._dump(diff),
            self._dump(diagnostics),
            submitted_proposal_id,
            now,
            now,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO proposal_reviews(
                    proposal_id, thread_id, message_id, state, artifact_json,
                    base_document_json, candidate_json, diff_json,
                    diagnostics_json, submitted_proposal_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    message_id = excluded.message_id,
                    state = excluded.state,
                    artifact_json = excluded.artifact_json,
                    base_document_json = excluded.base_document_json,
                    candidate_json = excluded.candidate_json,
                    diff_json = excluded.diff_json,
                    diagnostics_json = excluded.diagnostics_json,
                    submitted_proposal_id = excluded.submitted_proposal_id,
                    updated_at = excluded.updated_at
                """,
                values,
            )
            row = connection.execute(
                "SELECT * FROM proposal_reviews WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        assert row is not None
        return self._review(row)

    def get_review(
        self, thread_id: str, proposal_id: str
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM proposal_reviews
                WHERE proposal_id = ? AND thread_id = ?
                """,
                (proposal_id, thread_id),
            ).fetchone()
        return self._review(row) if row else None

    def list_reviews(self, thread_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM proposal_reviews
                WHERE thread_id = ?
                ORDER BY created_at, rowid
                """,
                (thread_id,),
            ).fetchall()
        return [self._review(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table: str,
        name: str,
        declaration: str,
    ) -> None:
        columns = {
            str(row[1])
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if name not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")

    def _refresh_summary(self, connection: sqlite3.Connection, thread_id: str) -> None:
        rows = connection.execute(
            """
            SELECT role, content_json FROM messages
            WHERE thread_id = ? ORDER BY created_at, rowid
            """,
            (thread_id,),
        ).fetchall()
        total_chars = sum(len(self._message_text(json.loads(row["content_json"]))) for row in rows)
        if len(rows) <= 12 and total_chars <= 12_000:
            summary = None
            count = 0
        else:
            older = rows[:-8]
            lines = [
                f"{row['role']}: {self._message_text(json.loads(row['content_json']))}"
                for row in older
            ]
            summary = "\n".join(line for line in lines if line.rstrip(": "))
            if len(summary) > 6_000:
                summary = "[Earlier conversation omitted]\n" + summary[-6_000:]
            count = len(older)
        connection.execute(
            """
            UPDATE threads
            SET conversation_summary = ?, summary_message_count = ?
            WHERE id = ?
            """,
            (summary, count, thread_id),
        )

    def _message_text(self, value: Any) -> str:
        fragments: list[str] = []

        def visit(item: Any) -> None:
            if isinstance(item, str):
                fragments.append(item)
            elif isinstance(item, list):
                for child in item:
                    visit(child)
            elif isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    fragments.append(item["text"])
                else:
                    for key, child in item.items():
                        if key not in {"id", "createdAt", "role", "type"}:
                            visit(child)

        visit(value)
        return " ".join(fragment.strip() for fragment in fragments if fragment.strip())

    def _thread(self, row: sqlite3.Row) -> dict[str, Any]:
        binding_scope = None
        if row["document_id"] is not None:
            binding_scope = (
                "entity"
                if row["domain"] == "spec"
                and row["entity_kind"] is not None
                and row["entity_id"] is not None
                else "document"
            )
        return {
            "id": row["id"],
            "title": row["title"],
            "status": row["status"],
            "domain": row["domain"],
            "service_base_url": row["service_base_url"],
            "circuit_base_url": row["circuit_base_url"],
            "document_id": row["document_id"],
            "entity_kind": row["entity_kind"],
            "entity_id": row["entity_id"],
            "binding_scope": binding_scope,
            "include_png": bool(row["include_png"]),
            "conversation_summary": row["conversation_summary"],
            "summary_message_count": int(row["summary_message_count"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _message(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "thread_id": row["thread_id"],
            "parent_id": row["parent_id"],
            "role": row["role"],
            "content": json.loads(row["content_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _review(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "proposal_id": row["proposal_id"],
            "thread_id": row["thread_id"],
            "message_id": row["message_id"],
            "state": row["state"],
            "artifact": json.loads(row["artifact_json"]),
            "base_document": self._load(row["base_document_json"]),
            "candidate": self._load(row["candidate_json"]),
            "diff": self._load(row["diff_json"]),
            "diagnostics": self._load(row["diagnostics_json"]),
            "submitted_proposal_id": row["submitted_proposal_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _dump(self, value: object | None) -> str | None:
        if value is None:
            return None
        return json.dumps(value, separators=(",", ":"))

    def _load(self, value: str | None) -> object | None:
        return json.loads(value) if value is not None else None

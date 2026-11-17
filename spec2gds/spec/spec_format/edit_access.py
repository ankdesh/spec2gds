"""Anonymous, expiring edit participation for exact hosted Spec bindings."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable, Iterator
from uuid import uuid4

from .spec_service_store import _Database


class EditAccessError(RuntimeError):
    """The requesting application cannot write this Spec."""


class SpecEditAccess(_Database):
    ttl = 300

    def __init__(self, path, *, now: Callable[[], float] = time.time):
        super().__init__(path)
        self.now = now
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS edit_contexts (document_key TEXT PRIMARY KEY, context_id TEXT UNIQUE NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS edit_participants (context_id TEXT NOT NULL, participant_id TEXT NOT NULL, expires REAL NOT NULL, PRIMARY KEY(context_id,participant_id))")
            db.execute("CREATE TABLE IF NOT EXISTS ended_edit_contexts (context_id TEXT PRIMARY KEY, document_key TEXT NOT NULL)")

    def _current(self, db, key: str):
        db.execute("DELETE FROM edit_participants WHERE expires<=?", (self.now(),))
        db.execute("DELETE FROM edit_contexts WHERE context_id NOT IN (SELECT context_id FROM edit_participants)")
        return db.execute("SELECT context_id FROM edit_contexts WHERE document_key=?", (key,)).fetchone()

    def acquire(self, key: str, context_id: str | None = None, participant_id: str | None = None) -> dict:
        participant_id = participant_id or uuid4().hex
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if context_id and db.execute("SELECT 1 FROM ended_edit_contexts WHERE context_id=?", (context_id,)).fetchone():
                return {"mode": "read_only"}
            current = self._current(db, key)
            if current and current[0] != context_id:
                return {"mode": "read_only"}
            # An expired context cannot be revived. Explicit acquire creates a
            # fresh fencing identity, even when the old token was supplied.
            context_id = current[0] if current else uuid4().hex
            expires = self.now() + self.ttl
            db.execute("INSERT OR IGNORE INTO edit_contexts VALUES (?,?)", (key, context_id))
            db.execute("INSERT INTO edit_participants VALUES (?,?,?) ON CONFLICT(context_id,participant_id) DO UPDATE SET expires=excluded.expires", (context_id, participant_id, expires))
            return {"mode": "edit", "context_id": context_id, "participant_id": participant_id, "expires_at": expires}

    def status(self, key: str, context_id: str | None, participant_id: str | None) -> dict:
        with self.connection() as db:
            current = self._current(db, key)
            row = db.execute("SELECT expires FROM edit_participants WHERE context_id=? AND participant_id=?", (context_id, participant_id)).fetchone()
            if not current or current[0] != context_id or not row:
                return {"mode": "read_only"}
            return {"mode": "edit", "context_id": context_id, "participant_id": participant_id, "expires_at": row[0]}

    def renew(self, key: str, context_id: str, participant_id: str) -> dict:
        with self.guard(key, context_id, participant_id):
            pass
        return self.status(key, context_id, participant_id)

    @contextmanager
    def guard(self, key: str, context_id: str | None, participant_id: str | None) -> Iterator[None]:
        # Keep admission and the entire mutation under the same SQLite writer
        # transaction. A successor cannot acquire access during an old save.
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self._current(db, key)
            row = db.execute("SELECT expires FROM edit_participants WHERE context_id=? AND participant_id=?", (context_id, participant_id)).fetchone()
            if not current or current[0] != context_id or not row:
                raise EditAccessError("This Spec is read-only. Resume editing or create a copy.")
            db.execute("UPDATE edit_participants SET expires=? WHERE context_id=? AND participant_id=?", (self.now() + self.ttl, context_id, participant_id))
            yield

    def release(self, key: str, context_id: str, participant_id: str) -> None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self._current(db, key)
            if current and current[0] == context_id:
                db.execute("DELETE FROM edit_participants WHERE context_id=? AND participant_id=?", (context_id, participant_id))
                self._current(db, key)

    def end_session(self, key: str, context_id: str, participant_id: str) -> None:
        """Fence every participant; retries cannot revoke a successor context."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self._current(db, key)
            if not current or current[0] != context_id:
                return
            participant = db.execute("SELECT 1 FROM edit_participants WHERE context_id=? AND participant_id=?", (context_id, participant_id)).fetchone()
            if not participant:
                raise EditAccessError("Valid edit participation is required to close this editing session.")
            db.execute("INSERT OR IGNORE INTO ended_edit_contexts VALUES (?,?)", (context_id, key))
            db.execute("DELETE FROM edit_participants WHERE context_id=?", (context_id,))
            db.execute("DELETE FROM edit_contexts WHERE context_id=?", (context_id,))

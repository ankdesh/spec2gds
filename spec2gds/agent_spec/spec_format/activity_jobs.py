"""Persistent single-worker host for UI-launched Activity executions."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import typing
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from spec2gds.agent_spec.activities import (
    ActivitySnapshot,
    LocalActivityWorkspace,
    SpecExtensionRegistry,
    invoke_activity,
)
from spec2gds.agent_spec.activities.contracts import (
    ActivityResult,
    ActivityWorkspaceWriter,
    CancellationToken,
    PublishedDirectory,
)
from spec2gds.agent_spec.spec_format.actions import ActionEvent, ActivityExecutionRecord
from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.models import new_entity_id


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ActivityCancelled(RuntimeError):
    """Raised when a durable cancellation request reaches a safe boundary."""


@dataclass(frozen=True)
class JobEnvelope:
    record: ActivityExecutionRecord
    package_path: str
    sidecar_root: str
    snapshot_path: str
    workspace_root: str


FinalizeCallback = typing.Callable[
    [JobEnvelope, ActivityResult | None],
    ActivityExecutionRecord,
]


class _JobCancellation(CancellationToken):
    def __init__(self, manager: "ActivityJobManager", execution_id: str) -> None:
        self.manager = manager
        self.execution_id = execution_id

    @property
    def cancelled(self) -> bool:
        return self.manager.is_cancel_requested(self.execution_id)

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise ActivityCancelled("Activity execution was cancelled.")


class _CancellationWorkspace(ActivityWorkspaceWriter):
    def __init__(self, delegate: LocalActivityWorkspace, token: _JobCancellation) -> None:
        self.delegate = delegate
        self.token = token

    def replace_directory(self, **kwargs: typing.Any) -> PublishedDirectory:
        self.token.raise_if_cancelled()
        result = self.delegate.replace_directory(**kwargs)
        return result


class ActivityJobManager:
    """Persist, resume, execute, cancel, and stream local Activity jobs."""

    def __init__(
        self,
        registry: SpecExtensionRegistry,
        workspace_root: str | Path,
        finalize: FinalizeCallback,
    ) -> None:
        self.registry = registry
        self.workspace = LocalActivityWorkspace(workspace_root)
        self.finalize = finalize
        self.runtime_root = self.workspace.root / ".spec2gds"
        self.snapshot_root = self.runtime_root / "snapshots"
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        self.database_path = self.runtime_root / "activity-jobs.sqlite3"
        self._condition = threading.Condition()
        self._events: list[dict[str, typing.Any]] = []
        self._event_sequence = 0
        self._stopping = False
        self._thread: threading.Thread | None = None
        self._initialize_database()
        self._recover_running_jobs()

    def close(self) -> None:
        with self._condition:
            self._stopping = True
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def enqueue(
        self,
        *,
        activity_id: str,
        snapshot: ActivitySnapshot,
        package_path: str,
        sidecar_root: str,
        workspace_root: str | Path | None = None,
    ) -> ActivityExecutionRecord:
        """Persist the immutable run input before making a queued job visible to the worker.

        The content-addressed snapshot survives restart independently of the live package.
        Workspace and package paths are host capabilities, not plugin-selected targets.
        """
        definition = self.registry.activity(activity_id).definition
        execution_id = new_entity_id("activity_execution")
        snapshot_path = self.snapshot_root / f"{snapshot.manifest.snapshot_id.removeprefix('sha256:')}.activity-snapshot"
        if not snapshot_path.exists():
            temporary = snapshot_path.with_suffix(".tmp")
            temporary.write_bytes(snapshot.to_bytes())
            temporary.replace(snapshot_path)
        record = ActivityExecutionRecord(
            execution_id=execution_id,
            activity_id=definition.activity_id,
            activity_version=definition.version,
            snapshot_id=snapshot.manifest.snapshot_id,
            source_revision_hash=snapshot.manifest.source.source_revision_hash,
            target=typing.cast(typing.Any, snapshot.target),
            status="queued",
            created_at=utc_now(),
            events=(ActionEvent(sequence=1, event_type="activity.execution.queued", timestamp=utc_now()),),
        )
        resolved_workspace = (
            Path(workspace_root).expanduser().resolve()
            if workspace_root
            else self.workspace.root
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs(
                    execution_id, package_path, sidecar_root,
                    snapshot_path, workspace_root, record_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    execution_id,
                    str(Path(package_path).resolve()),
                    sidecar_root,
                    str(snapshot_path),
                    str(resolved_workspace),
                    self._json(record),
                ),
            )
        self._publish(record)
        self._ensure_worker()
        return record

    def list_for_package(self, package_path: str) -> tuple[ActivityExecutionRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM jobs WHERE package_path = ? ORDER BY rowid",
                (str(Path(package_path).resolve()),),
            ).fetchall()
        return tuple(ActivityExecutionRecord.model_validate_json(row[0]) for row in rows)

    def get(self, execution_id: str) -> JobEnvelope | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT package_path, sidecar_root, snapshot_path, workspace_root, record_json
                FROM jobs WHERE execution_id = ?
                """,
                (execution_id,),
            ).fetchone()
        if row is None:
            return None
        return JobEnvelope(
            record=ActivityExecutionRecord.model_validate_json(row[4]),
            package_path=row[0],
            sidecar_root=row[1],
            snapshot_path=row[2],
            workspace_root=row[3] or str(self.workspace.root),
        )

    def cancel(self, execution_id: str) -> ActivityExecutionRecord:
        envelope = self.get(execution_id)
        if envelope is None:
            raise KeyError(f"Unknown Activity execution: {execution_id}")
        record = envelope.record
        if record.status in {"succeeded", "failed", "cancelled"}:
            return record
        if record.status == "queued":
            updated = self._terminal(record, "cancelled", "Activity execution was cancelled before it started.")
            envelope = replace(envelope, record=updated)
            self._store(envelope)
            try:
                updated = self.finalize(envelope, None)
                envelope = replace(envelope, record=updated)
                self._store(envelope)
            finally:
                self._publish(envelope.record)
            return envelope.record
        updated = record.model_copy(update={"cancel_requested": True})
        self._store(replace(envelope, record=updated))
        self._publish(updated)
        return updated

    def is_cancel_requested(self, execution_id: str) -> bool:
        envelope = self.get(execution_id)
        return bool(envelope and envelope.record.cancel_requested)

    def events_after(self, sequence: int, timeout: float = 15.0) -> tuple[dict[str, typing.Any], ...]:
        deadline = time.monotonic() + timeout
        with self._condition:
            while not self._stopping and self._event_sequence <= sequence:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return ()
                self._condition.wait(remaining)
            return tuple(item for item in self._events if int(item["sequence"]) > sequence)

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs(
                    execution_id TEXT PRIMARY KEY,
                    package_path TEXT NOT NULL,
                    sidecar_root TEXT NOT NULL,
                    snapshot_path TEXT NOT NULL,
                    workspace_root TEXT,
                    record_json TEXT NOT NULL
                )
                """
            )
            columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "workspace_root" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN workspace_root TEXT")
            legacy_jobs = connection.execute(
                """
                SELECT execution_id, package_path FROM jobs
                WHERE workspace_root IS NULL OR workspace_root = ''
                """
            ).fetchall()
            for execution_id, package_path in legacy_jobs:
                connection.execute(
                    "UPDATE jobs SET workspace_root = ? WHERE execution_id = ?",
                    (str(Path(package_path).expanduser().resolve().parent), execution_id),
                )

    def _recover_running_jobs(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("SELECT execution_id, record_json FROM jobs").fetchall()
            for execution_id, raw in rows:
                record = ActivityExecutionRecord.model_validate_json(raw)
                if record.status == "running":
                    event = ActionEvent(
                        sequence=len(record.events) + 1,
                        event_type="activity.execution.recovered",
                        timestamp=utc_now(),
                    )
                    recovered = record.model_copy(update={
                        "status": "queued",
                        "started_at": "",
                        "events": (*record.events, event),
                    })
                    connection.execute(
                        "UPDATE jobs SET record_json = ? WHERE execution_id = ?",
                        (self._json(recovered), execution_id),
                    )
        self._ensure_worker()

    def _ensure_worker(self) -> None:
        with self._condition:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._worker, name="spec2gds-activity-worker", daemon=True)
                self._thread.start()
            self._condition.notify_all()

    def _worker(self) -> None:
        while True:
            if self._stopping:
                return
            envelope = self._next_queued()
            if envelope is None:
                with self._condition:
                    self._condition.wait(timeout=1)
                continue
            self._run(envelope)

    def _next_queued(self) -> JobEnvelope | None:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT execution_id FROM jobs ORDER BY rowid"
            ).fetchall()
        for (execution_id,) in rows:
            envelope = self.get(execution_id)
            if envelope is not None and envelope.record.status == "queued":
                return envelope
        return None

    def _run(self, envelope: JobEnvelope) -> None:
        """Execute one saved snapshot and publish its terminal result back through the host.

        Check the installed Activity version and package identity before invocation.
        Finalization records provenance; exceptions become durable failure records.
        """
        record = envelope.record
        if record.cancel_requested:
            self.cancel(record.execution_id)
            return
        running = record.model_copy(update={
            "status": "running",
            "started_at": utc_now(),
            "events": (*record.events, ActionEvent(
                sequence=len(record.events) + 1,
                event_type="activity.execution.started",
                timestamp=utc_now(),
            )),
        })
        envelope = replace(envelope, record=running)
        self._store(envelope)
        self._publish(running)
        result: ActivityResult | None = None
        try:
            definition = self.registry.activity(running.activity_id).definition
            if definition.version != running.activity_version:
                raise ValueError(
                    f"Activity version changed from {running.activity_version} to {definition.version}."
                )
            package_path = Path(envelope.package_path)
            if not package_path.is_file():
                raise FileNotFoundError(f"Activity source package no longer exists: {package_path}")
            revision = SpecRevision.from_package(SpecPackage.load(package_path))
            if revision.document_id != running.target.document_id:
                raise ValueError("Activity source package identity changed after enqueue.")
            snapshot = ActivitySnapshot.read(envelope.snapshot_path)
            token = _JobCancellation(self, running.execution_id)
            token.raise_if_cancelled()
            output_workspace = LocalActivityWorkspace(envelope.workspace_root)
            workspace = _CancellationWorkspace(output_workspace, token)
            result = invoke_activity(
                self.registry,
                running.activity_id,
                snapshot,
                workspace,
                cancellation=token,
            )
            relative_output = str(result.report.get("output_path", ""))
            output_path = str(output_workspace.root / relative_output) if relative_output else ""
            finished = running.model_copy(update={
                "status": "succeeded",
                "finished_at": utc_now(),
                "report": {"summary": result.summary, **result.report},
                "diagnostics": result.diagnostics,
                "workspace_output_path": output_path,
                "events": (*running.events, ActionEvent(
                    sequence=len(running.events) + 1,
                    event_type="activity.execution.succeeded",
                    timestamp=utc_now(),
                )),
            })
        except ActivityCancelled as exc:
            finished = self._terminal(running, "cancelled", str(exc))
        except Exception as exc:
            finished = self._terminal(running, "failed", f"{type(exc).__name__}: {exc}")
        terminal = replace(envelope, record=finished)
        try:
            finished = self.finalize(terminal, result if finished.status == "succeeded" else None)
            terminal = replace(envelope, record=finished)
        except Exception as exc:
            finished = self._terminal(
                finished,
                "failed",
                f"Could not persist Activity result: {type(exc).__name__}: {exc}",
            )
            terminal = replace(envelope, record=finished)
            try:
                finished = self.finalize(terminal, None)
                terminal = replace(envelope, record=finished)
            except Exception:
                pass
        self._store(terminal)
        self._publish(terminal.record)

    def _terminal(
        self,
        record: ActivityExecutionRecord,
        status: typing.Literal["failed", "cancelled"],
        diagnostic: str,
    ) -> ActivityExecutionRecord:
        return record.model_copy(update={
            "status": status,
            "finished_at": utc_now(),
            "diagnostics": (*record.diagnostics, diagnostic),
            "events": (*record.events, ActionEvent(
                sequence=len(record.events) + 1,
                event_type=f"activity.execution.{status}",
                timestamp=utc_now(),
                payload={"diagnostic": diagnostic},
            )),
        })

    def _store(self, envelope: JobEnvelope) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET record_json = ? WHERE execution_id = ?",
                (self._json(envelope.record), envelope.record.execution_id),
            )

    def _publish(self, record: ActivityExecutionRecord) -> None:
        with self._condition:
            self._event_sequence += 1
            self._events.append({
                "sequence": self._event_sequence,
                "execution": record.model_dump(mode="json"),
            })
            self._events = self._events[-512:]
            self._condition.notify_all()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _json(record: ActivityExecutionRecord) -> str:
        return json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)

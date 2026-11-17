"""Durable background Activity host checks."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pydantic

from spec2gds.spec.activities import (
    ActivityContext,
    ActivityResult,
    ActivityScopes,
    ActivitySnapshot,
    SpecExtensionRegistry,
    activity,
)
from spec2gds.spec.spec_format.actions import ActivityExecutionRecord
from spec2gds.spec.spec_format.activity_jobs import ActivityJobManager
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.testing import write_test_package


class SlowReport(pydantic.BaseModel):
    completed: bool


@activity(
    activity_id="tests.slow",
    version="1.0.0",
    title="Slow test",
    description="Exercise cancellation and recovery.",
    scopes=ActivityScopes(entity_kinds=("design",)),
    report_model=SlowReport,
)
def slow_activity(context: ActivityContext) -> ActivityResult:
    for _ in range(40):
        context.cancellation.raise_if_cancelled()
        time.sleep(0.005)
    return ActivityResult(summary="Completed.", report={"completed": True})


def wait_terminal(manager: ActivityJobManager, execution_id: str) -> ActivityExecutionRecord:
    for _ in range(200):
        envelope = manager.get(execution_id)
        assert envelope is not None
        if envelope.record.status in {"succeeded", "failed", "cancelled"}:
            return envelope.record
        time.sleep(0.01)
    raise AssertionError("Activity did not reach a terminal state")


def setup_job(tmp_path: Path):
    package = tmp_path / "source.spec"
    write_test_package(package)
    revision = SpecRevision.load(package)
    snapshot = ActivitySnapshot.create(revision, revision.entry_designs()[0].ref)
    registry = SpecExtensionRegistry()
    registry.register_activity(slow_activity)
    finalized: list[ActivityExecutionRecord] = []

    def finalize(envelope, result):
        finalized.append(envelope.record)
        return envelope.record

    return package, snapshot, registry, finalized, finalize


def test_activity_job_manager_cancels_queued_and_running_jobs(tmp_path: Path) -> None:
    package, snapshot, registry, finalized, finalize = setup_job(tmp_path)
    manager = ActivityJobManager(registry, tmp_path / "generated", finalize)
    first = manager.enqueue(
        activity_id="tests.slow",
        snapshot=snapshot,
        package_path=str(package),
        sidecar_root=str(tmp_path / "artifacts"),
    )
    second = manager.enqueue(
        activity_id="tests.slow",
        snapshot=snapshot,
        package_path=str(package),
        sidecar_root=str(tmp_path / "artifacts"),
        workspace_root=tmp_path / "document-outputs",
    )
    second_envelope = manager.get(second.execution_id)
    assert second_envelope is not None
    assert Path(second_envelope.workspace_root) == tmp_path / "document-outputs"
    for _ in range(100):
        current = manager.get(first.execution_id)
        assert current is not None
        if current.record.status == "running":
            break
        time.sleep(0.005)
    assert current.record.status == "running"
    assert manager.cancel(second.execution_id).status == "cancelled"
    manager.cancel(first.execution_id)
    assert wait_terminal(manager, first.execution_id).status == "cancelled"
    assert {item.status for item in finalized} == {"cancelled"}
    manager.close()


def test_activity_job_manager_resumes_a_running_record(tmp_path: Path) -> None:
    package, snapshot, registry, finalized, finalize = setup_job(tmp_path)
    root = tmp_path / "generated"
    stopped = ActivityJobManager(registry, root, finalize)
    stopped.close()
    queued = stopped.enqueue(
        activity_id="tests.slow",
        snapshot=snapshot,
        package_path=str(package),
        sidecar_root=str(tmp_path / "artifacts"),
    )
    envelope = stopped.get(queued.execution_id)
    assert envelope is not None
    interrupted = envelope.record.model_copy(update={"status": "running", "started_at": "interrupted"})
    with sqlite3.connect(stopped.database_path) as connection:
        connection.execute(
            "UPDATE jobs SET record_json = ? WHERE execution_id = ?",
            (json.dumps(interrupted.model_dump(mode="json")), interrupted.execution_id),
        )

    resumed = ActivityJobManager(registry, root, finalize)
    completed = wait_terminal(resumed, interrupted.execution_id)
    assert completed.status == "succeeded"
    assert any(event.event_type == "activity.execution.recovered" for event in completed.events)
    resumed.close()


def test_activity_job_manager_migrates_existing_database(tmp_path: Path) -> None:
    _, _, registry, _, finalize = setup_job(tmp_path)
    root = tmp_path / "generated"
    runtime = root / ".spec2gds"
    runtime.mkdir(parents=True)
    database = runtime / "activity-jobs.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE jobs(
                execution_id TEXT PRIMARY KEY,
                package_path TEXT NOT NULL,
                sidecar_root TEXT NOT NULL,
                snapshot_path TEXT NOT NULL,
                record_json TEXT NOT NULL
            )
            """
        )

    manager = ActivityJobManager(registry, root, finalize)
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
    assert "workspace_root" in columns
    manager.close()


def test_end_session_fences_running_job_finalization(tmp_path):
    from spec2gds.spec.spec_format.edit_access import SpecEditAccess
    from spec2gds.spec.spec_format.spec_service_store import document_key

    package, snapshot, registry, _, _ = setup_job(tmp_path)
    key = document_key(str(package), snapshot.manifest.source.document_id)
    access = SpecEditAccess(tmp_path / "access.sqlite3")
    grant = access.acquire(key)
    before = package.read_bytes()

    def publish(envelope, result):
        with access.guard(key, envelope.edit_context_id, envelope.record.execution_id):
            package.write_bytes(b"An old job must not publish this result.")
        return envelope.record

    manager = ActivityJobManager(registry, tmp_path / "generated", publish, edit_access=access)
    try:
        job = manager.enqueue(activity_id="tests.slow", snapshot=snapshot, package_path=str(package),
                              sidecar_root=str(tmp_path / "artifacts"), edit_context_id=grant["context_id"])
        for _ in range(100):
            if manager.get(job.execution_id).record.status == "running":
                break
            time.sleep(.001)
        assert manager.get(job.execution_id).record.status == "running"
        access.end_session(key, grant["context_id"], grant["participant_id"])
        successor = access.acquire(key)
        assert wait_terminal(manager, job.execution_id).status == "failed"
        assert package.read_bytes() == before
        assert access.status(key, successor["context_id"], successor["participant_id"])["mode"] == "edit"
    finally:
        manager.close()

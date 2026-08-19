"""Durable background Activity host checks."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pydantic

from spec2gds.agent_spec.activities import (
    ActivityContext,
    ActivityResult,
    ActivityScopes,
    ActivitySnapshot,
    SpecExtensionRegistry,
    activity,
)
from spec2gds.agent_spec.spec_format.actions import ActivityExecutionRecord
from spec2gds.agent_spec.spec_format.activity_jobs import ActivityJobManager
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.testing import write_test_package


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
    )
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

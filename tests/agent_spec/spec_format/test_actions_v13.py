"""V1.3 snapshot, external-action, artifact, and proposal acceptance tests."""

from pathlib import Path
import sys
import tempfile

from spec2gds.agent_spec.spec_format.actions import (
    ActionDefinition,
    ActionRegistry,
    ActionService,
    ActivityStore,
    ArtifactSidecar,
    ChangeProposal,
    create_reference_registry,
)
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.testing import build_test_package


def _context() -> tuple[SpecRevision, ActivityStore, ActionService]:
    package = build_test_package()
    revision = SpecRevision.from_package(package)
    temporary = tempfile.TemporaryDirectory()
    # Retain the temporary owner on the store for this short test helper's caller.
    sidecar = ArtifactSidecar(Path(temporary.name) / "sidecar")
    store = ActivityStore(package, sidecar)
    store._test_temporary = temporary  # type: ignore[attr-defined]
    return revision, store, ActionService(create_reference_registry(), sidecar)


def test_snapshot_is_deterministic_and_bundle_matches_sdk() -> None:
    revision, activity, service = _context()
    try:
        action = service.registry.get("reference.snapshot_summary")
        target = revision.entry_designs()[0].ref
        first = service.create_snapshot(revision, action, target, activity=activity)
        second = service.create_snapshot(revision, action, target, activity=activity)
        assert first.snapshot_id == second.snapshot_id
        assert first.sdk().target.ref == target
        assert first.sdk().closure() == first.dependency_closure
        mutable_inputs = first.normalized_inputs
        mutable_inputs["mutated"] = True
        assert first.normalized_inputs == {}
        with tempfile.TemporaryDirectory() as temporary:
            bundle = first.write_bundle(temporary, activity.sidecar)
            manifest = (bundle / "snapshot.json").read_text(encoding="utf-8")
            assert first.snapshot_id in manifest
            assert (bundle / "source" / "manifest.json").is_file()
    finally:
        activity._test_temporary.cleanup()  # type: ignore[attr-defined]


def test_out_of_process_summary_transform_and_activity_persistence() -> None:
    revision, activity, service = _context()
    try:
        target = revision.entry_designs()[0].ref
        source_hash = revision.source_revision_hash
        summary = service.execute(revision, activity, "reference.snapshot_summary", target)
        assert summary.status == "succeeded"
        assert revision.source_revision_hash == source_hash
        assert activity.package.source_hash() == source_hash
        artifact = activity.state.artifacts[0]
        transformed = service.execute(
            revision,
            activity,
            "reference.artifact_transform",
            target,
            input_artifact_ids=(artifact.artifact_id,),
        )
        assert transformed.status == "succeeded"
        child = activity.state.artifacts[-1]
        assert child.parent_artifact_ids == (artifact.artifact_id,)
        assert [item.artifact_id for item in activity.artifact_lineage(child.artifact_id)] == [child.artifact_id, artifact.artifact_id]

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "activity.spec"
            activity.package.save(str(path))
            reopened = SpecRevision.load(str(path))
            restored = ActivityStore(reopened.to_package(), activity.sidecar)
            assert len(restored.state.executions) == 2
            assert restored.artifact_diagnostics() == ()
            assert ActivityStore(reopened.to_package(), ArtifactSidecar(Path(temporary) / "missing-sidecar")).artifact_diagnostics()
    finally:
        activity._test_temporary.cleanup()  # type: ignore[attr-defined]


def test_reviewed_proposal_requires_acceptance_and_rechecks_base_revision() -> None:
    revision, activity, service = _context()
    try:
        target = revision.entry_designs()[0].ref
        execution = service.execute(revision, activity, "reference.narrative_proposal", target)
        assert execution.status == "succeeded"
        proposal = activity.state.proposals[0]
        preview = service.preview_proposal(revision, activity, proposal.proposal_id)
        assert preview.succeeded
        accepted = service.accept_proposal(revision, activity, proposal.proposal_id)
        assert accepted.succeeded
        assert accepted.revision is not None
        assert accepted.revision.source_revision_hash != revision.source_revision_hash
        assert activity.state.proposals[0].review_status == "accepted"
        stale_preview = service.preview_proposal(accepted.revision, activity, proposal.proposal_id)
        assert not stale_preview.succeeded
        assert "stale" in stale_preview.diagnostics[0]

        rejected_execution = service.execute(revision, activity, "reference.narrative_proposal", target)
        rejected = service.reject_proposal(activity, activity.state.proposals[-1].proposal_id)
        assert rejected_execution.status == "succeeded"
        assert rejected.review_status == "rejected"
    finally:
        activity._test_temporary.cleanup()  # type: ignore[attr-defined]


def test_invalid_input_and_executor_failures_are_explicit() -> None:
    revision, activity, service = _context()
    try:
        target = revision.entry_designs()[0].ref
        action = service.registry.get("reference.snapshot_summary")
        try:
            service.create_snapshot(revision, action, target, inputs={"unexpected": True}, activity=activity)
        except ValueError as exc:
            assert "input schema" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Invalid action inputs were accepted.")

        requires_input = ActionDefinition(
            action_id="test.requires_input",
            version="1",
            title="requires input",
            target_entity_kinds=("design",),
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            report_schema={"type": "object", "properties": {}, "additionalProperties": True},
            executor=(sys.executable, "-c", "pass"),
            preconditions=("has_input_artifacts",),
        )
        try:
            service.create_snapshot(revision, requires_input, target, activity=activity)
        except ValueError as exc:
            assert "precondition failed" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Action precondition was not enforced.")

        report_schema = {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}
        actions = ActionRegistry(
            (
                ActionDefinition(
                    action_id="test.nonzero",
                    version="1",
                    title="nonzero",
                    target_entity_kinds=("design",),
                    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                    report_schema=report_schema,
                    executor=(sys.executable, "-c", "raise SystemExit(7)"),
                ),
                ActionDefinition(
                    action_id="test.malformed",
                    version="1",
                    title="malformed",
                    target_entity_kinds=("design",),
                    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                    report_schema=report_schema,
                    executor=(sys.executable, "-c", "pass"),
                ),
                ActionDefinition(
                    action_id="test.timeout",
                    version="1",
                    title="timeout",
                    target_entity_kinds=("design",),
                    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                    report_schema=report_schema,
                    executor=(sys.executable, "-c", "import time; time.sleep(1)"),
                    timeout_seconds=0.01,
                ),
            )
        )
        failures = ActionService(actions, activity.sidecar)
        for action_id in ("test.nonzero", "test.malformed", "test.timeout"):
            execution = failures.execute(revision, activity, action_id, target)
            assert execution.status == "failed"
            assert execution.diagnostics
    finally:
        activity._test_temporary.cleanup()  # type: ignore[attr-defined]


def test_invalid_proposal_patch_is_rejected_before_review() -> None:
    revision, activity, service = _context()
    try:
        proposal = ChangeProposal(
            proposal_id="proposal_invalid",
            base_source_revision_hash=revision.source_revision_hash,
            producer_execution_id="execution_test",
            rationale="Invalid test patch.",
            operations=({"type": "unknown"},),
        )
        activity._append_proposals((proposal,))
        activity.save()
        result = service.preview_proposal(revision, activity, proposal.proposal_id)
        assert not result.succeeded
        assert "Unsupported V1.3 proposal operation" in result.diagnostics[0]
    finally:
        activity._test_temporary.cleanup()  # type: ignore[attr-defined]

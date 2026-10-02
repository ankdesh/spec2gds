"""Shared, revision-guarded application of reviewed assistant proposals."""

from __future__ import annotations

import typing
from contextlib import nullcontext
from datetime import UTC, datetime

from spec2gds.agent_spec.spec_format.actions import AssistantChangeDecision
from spec2gds.agent_spec.spec_format.assistant import SpecChangeProposal, preview_assistant_proposal
from spec2gds.agent_spec.spec_format.ir import SpecRevision


class ProposalApplyError(ValueError):
    def __init__(self, status: int, detail: typing.Any) -> None:
        super().__init__(str(detail))
        self.status = status
        self.detail = detail


class ProposalSession(typing.Protocol):
    revision: SpecRevision
    activity: typing.Any

    def commit_assistant_revision(
        self, revision: SpecRevision, decision: AssistantChangeDecision
    ) -> None: ...


def reconcile_assistant_receipts(session: typing.Any) -> None:
    """Recover owner presentation state from atomically saved package decisions."""
    with session.lock:
        for decision in session.activity.state.assistant_changes:
            if decision.proposal_id in session.reconciled_proposals:
                continue
            record = session.journal.get(decision.proposal_id)
            if record is None:
                artifact = {
                    "schema_version": "1.0", "kind": "spec_change_proposal",
                    "proposal_id": decision.proposal_id, "document_id": session.revision.document_id,
                    "scope": decision.scope,
                    "target": decision.target.model_dump(mode="json") if decision.target else None,
                    "base_source_revision_hash": decision.base_source_revision_hash,
                    "title": decision.title or "Accepted assistant change", "summary": decision.summary,
                    "rationale": decision.rationale or "Recovered from saved package decision",
                    "assumptions": list(decision.assumptions), "operations": list(decision.operations),
                }
                record = session.journal.register(artifact, decision.session_id, recovered=not bool(decision.title))
            if record["state"] != "applied":
                session.journal.update(decision.proposal_id, state="applied", owner_result={
                    "status": "applied", "idempotent_replay": True,
                    "proposal_id": decision.proposal_id, "source_revision_hash": decision.result_source_revision_hash,
                    "saved_at": decision.applied_at, "application_mode": decision.application_mode,
                    "diff": list(decision.diff),
                }, diagnostics=[])
            session.reconciled_proposals.add(decision.proposal_id)


def apply_assistant_proposal(
    session: ProposalSession, proposal: SpecChangeProposal, *,
    application_mode: typing.Literal["automatic", "review"] = "review",
    session_id: str | None = None,
) -> dict[str, typing.Any]:
    """Apply once, or reconcile a prior successful save by proposal identity."""
    with getattr(session, "lock", nullcontext()):
        refresh = getattr(session, "refresh_from_disk", None)
        if refresh is not None:
            refresh()
        return _apply(session, proposal, application_mode, session_id)


def _apply(
    session: ProposalSession, proposal: SpecChangeProposal,
    application_mode: typing.Literal["automatic", "review"], session_id: str | None,
) -> dict[str, typing.Any]:
    """Revalidate or replay a proposal while the caller holds the package lock.

    Check saved decisions before stale preview: a successful retry has an old base
    revision but must return its original receipt. Source and decision save together.
    """
    if proposal.document_id != session.revision.document_id:
        raise ProposalApplyError(409, "Proposal targets a different specification document.")
    digest = proposal.operations_digest()
    existing = next(
        (
            item
            for item in session.activity.state.assistant_changes
            if item.proposal_id == proposal.proposal_id
        ),
        None,
    )
    # Replay precedes preview: the old authored revision is expected after a prior
    # successful save. Compare the complete mutation identity before returning it.
    if existing is not None:
        if (existing.operations_digest != digest or existing.scope != proposal.scope
                or existing.target != proposal.target
                or existing.base_source_revision_hash != proposal.base_source_revision_hash
                or (existing.owner_document_key is not None
                    and existing.owner_document_key != getattr(session, "owner_document_key", None))):
            raise ProposalApplyError(409, "Proposal ID was reused with a different mutation envelope.")
        return {
            "status": "applied",
            "idempotent_replay": True,
            "proposal_id": proposal.proposal_id,
            "source_revision_hash": existing.result_source_revision_hash,
            "saved_at": existing.applied_at,
            "application_mode": existing.application_mode,
            "diff": list(existing.diff),
        }
    result = preview_assistant_proposal(session.revision, proposal)
    if result["status"] == "stale":
        raise ProposalApplyError(409, result)
    if result["status"] != "valid" or result.get("_revision") is None:
        raise ProposalApplyError(422, result)
    revision = typing.cast(SpecRevision, result.pop("_revision"))
    applied_at = datetime.now(UTC).isoformat()
    decision = AssistantChangeDecision(
        proposal_id=proposal.proposal_id,
        scope=proposal.scope,
        target=proposal.target,
        base_source_revision_hash=proposal.base_source_revision_hash,
        result_source_revision_hash=revision.source_revision_hash,
        operations_digest=digest,
        operations=tuple(proposal.operations),
        applied_at=applied_at,
        application_mode=application_mode,
        title=proposal.title,
        summary=proposal.summary,
        rationale=proposal.rationale,
        assumptions=tuple(proposal.assumptions),
        session_id=session_id,
        owner_document_key=getattr(session, "owner_document_key", None),
        diff=tuple(result["diff"]),
    )
    # The decision is committed with source, allowing a later journal reconciliation
    # after a crash between package replacement and external receipt persistence.
    session.commit_assistant_revision(revision, decision)
    return {
        "status": "applied",
        "idempotent_replay": False,
        "proposal_id": proposal.proposal_id,
        "source_revision_hash": session.revision.source_revision_hash,
        "saved_at": applied_at,
        "application_mode": application_mode,
        "sections": result["candidate_sections"],
        "diff": result["diff"],
    }

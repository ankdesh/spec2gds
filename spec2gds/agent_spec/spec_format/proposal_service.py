"""Shared, revision-guarded application of reviewed assistant proposals."""

from __future__ import annotations

import typing
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


def apply_assistant_proposal(
    session: ProposalSession, proposal: SpecChangeProposal
) -> dict[str, typing.Any]:
    """Apply once, or reconcile a prior successful save by proposal identity."""
    digest = proposal.operations_digest()
    existing = next(
        (
            item
            for item in session.activity.state.assistant_changes
            if item.proposal_id == proposal.proposal_id
        ),
        None,
    )
    if existing is not None:
        if existing.operations_digest != digest:
            raise ProposalApplyError(409, "Proposal ID was reused with different operations.")
        return {
            "status": "applied",
            "idempotent_replay": True,
            "proposal_id": proposal.proposal_id,
            "source_revision_hash": existing.result_source_revision_hash,
            "saved_at": existing.applied_at,
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
    )
    session.commit_assistant_revision(revision, decision)
    return {
        "status": "applied",
        "idempotent_replay": False,
        "proposal_id": proposal.proposal_id,
        "source_revision_hash": session.revision.source_revision_hash,
        "saved_at": applied_at,
        "sections": result["candidate_sections"],
        "diff": result["diff"],
    }

"""Models representing atomic testplan operations and AI Assistant proposals."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlanOperation(BaseModel):
    """A single discrete mutation on a testplan hierarchy."""

    model_config = ConfigDict(extra="forbid")

    action: str = Field(
        ...,
        description="Action type: add_node, update_node, delete_node, or move_node.",
    )
    node_id: str | None = Field(
        default=None,
        description="Target node identifier for update, delete, or move operations.",
    )
    parent_id: str | None = Field(
        default=None,
        description="Parent node identifier for add_node or move_node.",
    )
    node_data: dict[str, Any] | None = Field(
        default=None,
        description="Node payload for add_node or field updates for update_node.",
    )
    target_order: int | None = Field(
        default=None,
        description="Target sibling order index for move_node.",
    )


class ProposalArtifact(BaseModel):
    """An AI Assistant proposal containing a batch of proposed changes."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(..., description="Unique identifier for the proposal.")
    document_id: str = Field(..., description="Target testplan document identifier.")
    base_revision: int = Field(..., description="Testplan revision this proposal is based on.")
    title: str = Field(..., description="Short title describing the proposed changes.")
    summary: str = Field(..., description="Detailed explanation of the verification improvements.")
    rationale: str = Field(default="", description="Technical rationale for the changes.")
    operations: list[PlanOperation] = Field(
        default_factory=list,
        description="Sequence of operations to preview or apply.",
    )


class ProposalPreviewResult(BaseModel):
    """Outcome of previewing an AI Assistant proposal."""

    model_config = ConfigDict(extra="forbid")

    valid: bool
    diagnostics: list[str] = Field(default_factory=list)
    nodes_added: int = 0
    nodes_modified: int = 0
    nodes_deleted: int = 0
    summary_diff: list[str] = Field(default_factory=list)


class ProposalApplyResult(BaseModel):
    """Outcome of applying an AI Assistant proposal to the testplan."""

    model_config = ConfigDict(extra="forbid")

    applied: bool
    document_id: str
    previous_revision: int
    new_revision: int
    message: str
    diagnostics: list[str] = Field(default_factory=list)

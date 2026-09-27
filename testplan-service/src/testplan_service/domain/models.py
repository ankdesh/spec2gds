"""Domain entities and value objects for Verification Planner."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from testplan_service.constants import (
    MAX_TAG_LENGTH,
    MAX_TAGS_COUNT,
    MAX_TEXT_LENGTH,
    MAX_TITLE_LENGTH,
    SCHEMA_VERSION_PLAN,
)
from testplan_service.domain.enums import (
    AuthoringState,
    IntentOrigin,
    IssueKind,
    IssueSeverity,
    IssueState,
    Priority,
    RequirementDisposition,
    SourceAuditDisposition,
)


class SourceLocator(BaseModel):
    """Pinpoint reference into an Activity Snapshot section or structured fact."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    entity_ref: dict[str, str]
    section_id: str
    text_range: tuple[int, int] | None = None
    quoted_text: str | None = None
    structured_path: str | None = None
    structured_value: Any | None = None
    section_digest: str


class SourceAuditEntry(BaseModel):
    """Audit status and requirement mapping for one source section."""

    model_config = ConfigDict(extra="forbid")

    section_id: str
    disposition: SourceAuditDisposition = SourceAuditDisposition.UNREVIEWED
    reason: str | None = None
    linked_requirement_ids: list[str] = Field(default_factory=list)
    reviewer_label: str = "author"
    source_digest: str = ""
    updated_at: str = ""


class Requirement(BaseModel):
    """User-curated atomic behavioral statement linked to source."""

    model_config = ConfigDict(extra="ignore")

    id: str
    key: str
    record_type: str = "requirement"
    record_revision: int = 1
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    statement: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    source_locators: list[SourceLocator] = Field(min_length=1)
    interpretation_note: str | None = Field(default=None, max_length=MAX_TEXT_LENGTH)
    scope_id: str
    disposition: RequirementDisposition = RequirementDisposition.UNASSESSED
    disposition_reason: str | None = Field(default=None, max_length=MAX_TEXT_LENGTH)
    issue_ids: list[str] = Field(default_factory=list)
    copied_from: str | None = None
    archived: bool = False
    created_at: str
    updated_at: str


class Section(BaseModel):
    """Hierarchical grouping of verification intents within a scope."""

    model_config = ConfigDict(extra="ignore")

    id: str
    key: str
    record_type: str = "section"
    record_revision: int = 1
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    description: str = Field(default="", max_length=MAX_TEXT_LENGTH)
    scope_id: str
    parent_section_id: str | None = None
    child_ids: list[str] = Field(default_factory=list)
    default_priority: Priority = Priority.MEDIUM
    tags: list[str] = Field(default_factory=list, max_length=MAX_TAGS_COUNT)
    copied_from: str | None = None
    archived: bool = False
    created_at: str
    updated_at: str


class Observation(BaseModel):
    """Named semantic observation for verifying an intent."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    description: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    source_locator: SourceLocator | None = None


class Intent(BaseModel):
    """Atomic verification obligation with Given/When/Then specification."""

    model_config = ConfigDict(extra="ignore")

    id: str
    key: str
    record_type: str = "intent"
    record_revision: int = 1
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    scope_id: str
    parent_section_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    preconditions: str = Field(default="", max_length=MAX_TEXT_LENGTH)  # Given
    trigger: str = Field(default="", max_length=MAX_TEXT_LENGTH)  # When
    expected_behavior: str = Field(default="", max_length=MAX_TEXT_LENGTH)  # Then
    observations: list[Observation] = Field(default_factory=list)
    rationale: str | None = Field(default=None, max_length=MAX_TEXT_LENGTH)
    origin: IntentOrigin = IntentOrigin.DIRECT_REQUIREMENT
    priority_override: Priority | None = None
    tags: list[str] = Field(default_factory=list, max_length=MAX_TAGS_COUNT)
    participants: list[str] = Field(default_factory=list)  # Scope IDs for composition
    dependency_ids: list[str] = Field(default_factory=list)  # Other intent IDs
    issue_ids: list[str] = Field(default_factory=list)
    authoring_state: AuthoringState = AuthoringState.DRAFT
    copied_from: str | None = None
    archived: bool = False
    created_at: str
    updated_at: str


class Issue(BaseModel):
    """Source ambiguity, missing detail, or contradiction."""

    model_config = ConfigDict(extra="ignore")

    id: str
    key: str
    record_type: str = "issue"
    record_revision: int = 1
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    kind: IssueKind
    description: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    linked_record_ids: list[str] = Field(default_factory=list)
    severity: IssueSeverity
    state: IssueState = IssueState.OPEN
    resolution_text: str | None = Field(default=None, max_length=MAX_TEXT_LENGTH)
    resolver_label: str | None = None
    resolved_at: str | None = None
    archived: bool = False
    created_at: str
    updated_at: str


class PlanHeader(BaseModel):
    """Plan metadata, revision, and pinned snapshot reference."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    description: str = Field(default="", max_length=MAX_TEXT_LENGTH)
    snapshot_id: str
    root_scope_id: str
    owner_label: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=MAX_TAGS_COUNT)
    source_audit: dict[str, SourceAuditEntry] = Field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION_PLAN
    edit_revision: int = 1
    created_at: str
    updated_at: str


class PlanCheckpoint(BaseModel):
    """Immutable checkpoint recording a reviewed Layer 1 plan baseline."""

    model_config = ConfigDict(extra="forbid")

    id: str
    key: str  # e.g. "P1"
    layer: str = "plan"
    plan_id: str
    created_at: str
    reviewer_label: str
    comment: str
    upstream_checkpoint_id: str | None = None
    snapshot_id: str
    root_scope_id: str
    checklist: dict[str, Any]
    acknowledged_warnings: list[str] = Field(default_factory=list)
    content_hash: str
    payload: dict[str, Any]

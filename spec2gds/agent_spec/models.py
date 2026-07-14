"""Pydantic contracts for the agent-spec v1 architecture.

These models are the durable JSON shapes stored inside `.spec` archives under
`spec_data/agent-spec/` and exchanged by the local API. Keep them boring and
explicit: migrations, UI rendering, and run replay all depend on these field
names remaining understandable.
"""

import typing

import pydantic


# Persisted state machines for run execution and artifact writeback.
RUN_STATES: set[str] = {"queued", "running", "completed", "failed"}
WRITEBACK_STATES: set[str] = {"auto_applied", "needs_human_feedback"}


class AgentSpecDiagnostic(pydantic.BaseModel):
    """Diagnostic emitted by the v1 server flow."""

    severity: str
    source: str
    message: str
    target_id: str = ""


class SourceTrace(pydantic.BaseModel):
    """Traceability from an artifact back to source block versions and nodes."""

    block_id: str
    version_id: str
    artifact_refs: list[str] = pydantic.Field(default_factory=list)
    spec_refs: list[str] = pydantic.Field(default_factory=list)


class ArtifactRef(pydantic.BaseModel):
    """agent-spec-stored metadata for an externally stored or compact artifact."""

    artifact_id: str
    artifact_kind: str
    media_type: str
    summary: str
    sha256: str
    external_uri: str
    producer: str
    source_trace: SourceTrace
    role: str
    created_at: str


class AttachmentRecord(pydantic.BaseModel):
    """Relationship from a block to one artifact."""

    attachment_id: str
    block_id: str
    artifact_id: str
    role: str
    run_id: str
    created_at: str


class BlockVersionRecord(pydantic.BaseModel):
    """Immutable snapshot metadata for a block."""

    version_id: str
    block_id: str
    content_hash: str
    block_ids: list[str] = pydantic.Field(default_factory=list)
    artifact_ref_ids: list[str] = pydantic.Field(default_factory=list)
    created_at: str


class BlockRecord(pydantic.BaseModel):
    """One heading/subheading-backed section in an agent-spec document."""

    block_id: str
    heading_id: str
    title: str
    level: int
    versions: list[BlockVersionRecord] = pydantic.Field(default_factory=list)


class SpecGraph(pydantic.BaseModel):
    """The agent-spec-persisted graph of blocks, versions, and artifacts."""

    version: int = 2
    blocks: dict[str, BlockRecord] = pydantic.Field(default_factory=dict)
    active_versions: dict[str, str] = pydantic.Field(default_factory=dict)
    artifact_refs: dict[str, ArtifactRef] = pydantic.Field(default_factory=dict)
    attachments: dict[str, list[AttachmentRecord]] = pydantic.Field(default_factory=dict)


class AgentSpecManifest(pydantic.BaseModel):
    """Document-level agent-spec metadata."""

    document_id: str
    schema_version: int = 1
    created_at: str
    updated_at: str
    user_identity: str
    sidecar_root: str


class InputSnapshot(pydantic.BaseModel):
    """Immutable run input captured at action trigger time."""

    snapshot_id: str
    document_id: str
    source_document_hash: str
    created_at: str
    selected_versions: list[BlockVersionRecord]
    artifact_refs: list[ArtifactRef] = pydantic.Field(default_factory=list)
    inputs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    precondition_report: "PreconditionReport | None" = None


class RunEvent(pydantic.BaseModel):
    """Durable audit event for a run."""

    event_id: str
    event_type: str
    document_id: str
    aggregate_id: str
    sequence: int
    created_at: str
    actor: dict[str, str] = pydantic.Field(default_factory=dict)
    payload: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


class RunRecord(pydantic.BaseModel):
    """Execution record for one action run."""

    run_id: str
    action_id: str
    status: str
    input_snapshot_id: str
    read_set: list[SourceTrace] = pydantic.Field(default_factory=list)
    produced_artifact_ids: list[str] = pydantic.Field(default_factory=list)
    diagnostics: list[AgentSpecDiagnostic] = pydantic.Field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""

    @pydantic.field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        """Reject unknown run states before they are persisted."""
        if value not in RUN_STATES:
            raise ValueError(f"Unsupported run status: {value}")
        return value


class WritebackRecord(pydantic.BaseModel):
    """Server-owned record of applying or rejecting executor artifact metadata."""

    writeback_id: str
    run_id: str
    document_id: str
    base_document_hash: str
    read_set: list[SourceTrace] = pydantic.Field(default_factory=list)
    artifact_ids: list[str] = pydantic.Field(default_factory=list)
    diagnostics: list[AgentSpecDiagnostic] = pydantic.Field(default_factory=list)
    status: str
    created_at: str

    @pydantic.field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        """Reject unknown writeback states before they are persisted."""
        if value not in WRITEBACK_STATES:
            raise ValueError(f"Unsupported writeback status: {value}")
        return value


class ConditionCheck(pydantic.BaseModel):
    """One human-readable precondition or postcondition result."""

    check_id: str
    severity: str
    message: str
    passed: bool


class PreconditionReport(pydantic.BaseModel):
    """Checks evaluated before an action run may be dispatched."""

    action_id: str
    block_id: str
    can_execute: bool
    checks: list[ConditionCheck] = pydantic.Field(default_factory=list)
    checked_at: str


class PostconditionReport(pydantic.BaseModel):
    """Checks evaluated after executor completion and artifact validation."""

    action_id: str
    run_id: str
    review_required: bool
    checks: list[ConditionCheck] = pydantic.Field(default_factory=list)
    checked_at: str


class ActionReport(pydantic.BaseModel):
    """Durable executor report and the derived, read-only A2UI surface."""

    run_id: str
    action_id: str
    executor_outcome: str
    data: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    artifact_ids: list[str] = pydantic.Field(default_factory=list)
    postcondition_report: PostconditionReport
    review_required: bool
    surface_id: str


class ActionSpec(pydantic.BaseModel):
    """Action metadata used by the registry, API, and UI."""

    action_id: str
    title: str
    summary: str
    version: str
    provider: str
    executor_id: str
    input_schema: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    report_schema: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    report_catalog_id: str = "agent-spec.report.v1"
    output_roles: list[str] = pydantic.Field(default_factory=list)
    enabled: bool = True


class ActionLaunch(pydantic.BaseModel):
    """Run creation response consumed by the editor and future executors."""

    run: RunRecord
    snapshot: InputSnapshot
    completion_url: str


class ActionResult(pydantic.BaseModel):
    """Result returned by a Python action handler."""

    artifacts: list[ArtifactRef] = pydantic.Field(default_factory=list)
    diagnostics: list[AgentSpecDiagnostic] = pydantic.Field(default_factory=list)

"""Pydantic contracts for the agent-spec v1 architecture.

These models are the durable JSON shapes stored inside `.spec` archives under
`spec_data/agent-spec/` and exchanged by the local API. Keep them boring and
explicit: migrations, UI rendering, and run replay all depend on these field
names remaining understandable.
"""

import typing

import pydantic


# Tags are intentionally constrained because they drive action discovery and
# should remain stable across documents and editor sessions.
V1_TAGS: set[str] = {
    "systemc-perf",
    "systemc-bitaccurate",
    "rtl",
    "ip",
    "interface",
    "configuration",
}

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
    tags: list[str] = pydantic.Field(default_factory=list)
    versions: list[BlockVersionRecord] = pydantic.Field(default_factory=list)


class SpecGraph(pydantic.BaseModel):
    """The agent-spec-persisted graph of blocks, versions, tags, and artifacts."""

    version: int = 1
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
    parameters: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


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
    """Server-owned record of applying or rejecting pipeline artifact metadata."""

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


class ActionParameter(pydantic.BaseModel):
    """UI-renderable action parameter metadata."""

    name: str
    parameter_type: str
    required: bool = False
    enum_values: list[str] = pydantic.Field(default_factory=list)
    default: typing.Any = None


class ActionSpec(pydantic.BaseModel):
    """Action metadata used by the registry, API, and UI."""

    action_id: str
    title: str
    summary: str
    version: str
    provider: str
    required_tags: list[str] = pydantic.Field(default_factory=list)
    context: list[str] = pydantic.Field(default_factory=lambda: ["block"])
    parameters: list[ActionParameter] = pydantic.Field(default_factory=list)
    output_roles: list[str] = pydantic.Field(default_factory=list)
    enabled: bool = True


class ActionRunContext(pydantic.BaseModel):
    """Data passed to a Python action handler."""

    action: ActionSpec
    snapshot: InputSnapshot
    run_id: str
    sidecar_root: str
    user_identity: str


class ActionResult(pydantic.BaseModel):
    """Result returned by a Python action handler."""

    artifacts: list[ArtifactRef] = pydantic.Field(default_factory=list)
    diagnostics: list[AgentSpecDiagnostic] = pydantic.Field(default_factory=list)

"""Command batch operations schemas and envelope definitions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from testplan_service.domain.enums import (
    AuthoringState,
    IntentOrigin,
    IssueKind,
    IssueSeverity,
    Priority,
    RequirementDisposition,
    SourceAuditDisposition,
)
from testplan_service.domain.models import Observation, SourceLocator


class OperationBase(BaseModel):
    """Base model for typed command operations."""

    model_config = ConfigDict(extra="forbid")
    op: str


class PlanUpdateOp(OperationBase):
    op: Literal["plan.update"] = "plan.update"
    changes: dict[str, Any]


class SourceSectionAssessOp(OperationBase):
    op: Literal["source_section.assess"] = "source_section.assess"
    section_id: str
    disposition: SourceAuditDisposition
    reason: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)


class RequirementCreateOp(OperationBase):
    op: Literal["requirement.create"] = "requirement.create"
    id: str | None = None
    title: str
    statement: str
    source_locators: list[SourceLocator]
    interpretation_note: str | None = None
    scope_id: str
    disposition: RequirementDisposition = RequirementDisposition.UNASSESSED
    disposition_reason: str | None = None
    issue_ids: list[str] = Field(default_factory=list)


class RequirementUpdateOp(OperationBase):
    op: Literal["requirement.update"] = "requirement.update"
    id: str
    changes: dict[str, Any]


class SectionCreateOp(OperationBase):
    op: Literal["section.create"] = "section.create"
    id: str | None = None
    title: str
    description: str = ""
    scope_id: str
    parent_section_id: str | None = None
    before_id: str | None = None
    default_priority: Priority = Priority.MEDIUM
    tags: list[str] = Field(default_factory=list)


class SectionUpdateOp(OperationBase):
    op: Literal["section.update"] = "section.update"
    id: str
    changes: dict[str, Any]


class IntentCreateOp(OperationBase):
    op: Literal["intent.create"] = "intent.create"
    id: str | None = None
    title: str
    scope_id: str
    parent_section_id: str | None = None
    before_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    preconditions: str = ""
    trigger: str = ""
    expected_behavior: str = ""
    observations: list[Observation] = Field(default_factory=list)
    rationale: str | None = None
    origin: IntentOrigin = IntentOrigin.DIRECT_REQUIREMENT
    priority_override: Priority | None = None
    tags: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    dependency_ids: list[str] = Field(default_factory=list)
    issue_ids: list[str] = Field(default_factory=list)
    authoring_state: AuthoringState = AuthoringState.DRAFT


class IntentUpdateOp(OperationBase):
    op: Literal["intent.update"] = "intent.update"
    id: str
    changes: dict[str, Any]


class IntentSetStateOp(OperationBase):
    op: Literal["intent.set_state"] = "intent.set_state"
    id: str
    state: AuthoringState


class IntentLinkRequirementOp(OperationBase):
    op: Literal["intent.link_requirement"] = "intent.link_requirement"
    intent_id: str
    requirement_id: str


class IntentUnlinkRequirementOp(OperationBase):
    op: Literal["intent.unlink_requirement"] = "intent.unlink_requirement"
    intent_id: str
    requirement_id: str


class ItemMoveOp(OperationBase):
    op: Literal["item.move"] = "item.move"
    id: str
    target_scope_id: str
    parent_section_id: str | None = None
    before_id: str | None = None


class SectionCopyOp(OperationBase):
    op: Literal["section.copy"] = "section.copy"
    source_id: str
    target_scope_id: str
    source_ref_map: dict[str, str] = Field(default_factory=dict)
    dependency_map: dict[str, str] = Field(default_factory=dict)


class RecordArchiveOp(OperationBase):
    op: Literal["record.archive"] = "record.archive"
    id: str
    descendant_ids: list[str] = Field(default_factory=list)


class RecordRestoreOp(OperationBase):
    op: Literal["record.restore"] = "record.restore"
    id: str
    destination_parent_id: str | None = None


class RecordDeleteDraftOp(OperationBase):
    op: Literal["record.delete_draft"] = "record.delete_draft"
    id: str


class IssueCreateOp(OperationBase):
    op: Literal["issue.create"] = "issue.create"
    id: str | None = None
    title: str
    kind: IssueKind
    description: str
    linked_record_ids: list[str] = Field(default_factory=list)
    severity: IssueSeverity


class IssueUpdateOp(OperationBase):
    op: Literal["issue.update"] = "issue.update"
    id: str
    changes: dict[str, Any]


class IssueResolveOp(OperationBase):
    op: Literal["issue.resolve"] = "issue.resolve"
    id: str
    resolution_text: str
    resolver_label: str = "author"


class IssueReopenOp(OperationBase):
    op: Literal["issue.reopen"] = "issue.reopen"
    id: str
    reason: str


class SourceUpdateOp(OperationBase):
    op: Literal["source.update"] = "source.update"
    staged_import_id: str
    locator_map: dict[str, str] = Field(default_factory=dict)
    expected_preview_digest: str | None = None


# --- Layer 2 Coverage Operations ---

class DimensionCreateOp(OperationBase):
    op: Literal["dimension.create"] = "dimension.create"
    id: str | None = None
    title: str
    semantic_description: str = ""
    scope_id: str
    dimension_type: Any  # DimensionType
    unit: str | None = None
    value_classes: list[dict[str, Any]] = Field(default_factory=list)
    allow_overlap: bool = False
    rationale: str | None = None


class DimensionUpdateOp(OperationBase):
    op: Literal["dimension.update"] = "dimension.update"
    id: str
    changes: dict[str, Any]


class DimensionArchiveOp(OperationBase):
    op: Literal["dimension.archive"] = "dimension.archive"
    id: str


class ObjectiveCreateOp(OperationBase):
    op: Literal["objective.create"] = "objective.create"
    id: str | None = None
    title: str
    description: str = ""
    scope_id: str
    participant_scope_ids: list[str] = Field(default_factory=list)
    family: Any  # CoverageFamily
    semantic_definition: str = ""
    dimension_ids: list[str] = Field(default_factory=list)
    bins: list[dict[str, Any]] = Field(default_factory=list)
    acceptance: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = None
    authoring_state: AuthoringState = AuthoringState.DRAFT
    supplemental: bool = False


class ObjectiveUpdateOp(OperationBase):
    op: Literal["objective.update"] = "objective.update"
    id: str
    changes: dict[str, Any]


class ObjectiveArchiveOp(OperationBase):
    op: Literal["objective.archive"] = "objective.archive"
    id: str


class BinAddOp(OperationBase):
    op: Literal["bin.add"] = "bin.add"
    objective_id: str
    bin: dict[str, Any]


class BinUpdateOp(OperationBase):
    op: Literal["bin.update"] = "bin.update"
    objective_id: str
    bin_id: str
    changes: dict[str, Any]


class BinRemoveOp(OperationBase):
    op: Literal["bin.remove"] = "bin.remove"
    objective_id: str
    bin_id: str


class PolicySetOp(OperationBase):
    op: Literal["policy.set"] = "policy.set"
    intent_id: str
    branches: list[dict[str, Any]] = Field(default_factory=list)
    supplemental_objective_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None


class ExclusionProposeOp(OperationBase):
    op: Literal["exclusion.propose"] = "exclusion.propose"
    id: str | None = None
    objective_id: str
    bin_id: str | None = None
    reason_kind: Any  # ExclusionReason
    rationale: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)


class ExclusionUpdateOp(OperationBase):
    op: Literal["exclusion.update"] = "exclusion.update"
    id: str
    changes: dict[str, Any]


class CoverageRebaseOp(OperationBase):
    op: Literal["coverage.rebase"] = "coverage.rebase"
    target_plan_checkpoint_id: str
    resolved_relations: dict[str, str] = Field(default_factory=dict)


class ImplementationRebaseOp(OperationBase):
    op: Literal["implementation.rebase"] = "implementation.rebase"
    target_coverage_checkpoint_id: str


# --- Layer 3 Implementation & Recipe Operations ---

class BindingSetCreateOp(OperationBase):
    op: Literal["binding_set.create"] = "binding_set.create"
    title: str = ""
    id: str | None = None
    source_snapshot_id: str
    root_scope_id: str
    dut_language: str = "verilog"
    top_module: str
    dut_manifest_digest: str | None = None
    resolved_parameters: dict[str, Any] = Field(default_factory=dict)
    clocks: list[dict[str, Any]] = Field(default_factory=list)
    resets: list[dict[str, Any]] = Field(default_factory=list)
    bindings: list[dict[str, Any]] = Field(default_factory=list)
    authoring_state: AuthoringState = AuthoringState.DRAFT


class BindingSetUpdateOp(OperationBase):
    op: Literal["binding_set.update"] = "binding_set.update"
    id: str
    changes: dict[str, Any]


class BindingSetArchiveOp(OperationBase):
    op: Literal["binding_set.archive"] = "binding_set.archive"
    id: str


class RecipeCreateOp(OperationBase):
    op: Literal["recipe.create"] = "recipe.create"
    id: str | None = None
    title: str
    description: str = ""
    kind: Any  # RecipeKind
    coverage_checkpoint_id: str
    intent_ids: list[str] = Field(default_factory=list)
    objective_ids: list[str] = Field(default_factory=list)
    target_binding_set_id: str | None = None
    test_ir: dict[str, Any] | None = None
    backend_configuration_id: str | None = None
    evidence_bindings: list[dict[str, Any]] = Field(default_factory=list)
    oracle_provenance: dict[str, Any] = Field(default_factory=dict)
    authoring_state: Any = "draft"  # RecipeState


class RecipeUpdateOp(OperationBase):
    op: Literal["recipe.update"] = "recipe.update"
    id: str
    changes: dict[str, Any]


class RecipeSetStateOp(OperationBase):
    op: Literal["recipe.set_state"] = "recipe.set_state"
    id: str
    state: Any  # RecipeState


class RecipeBindEvidenceOp(OperationBase):
    op: Literal["recipe.bind_evidence"] = "recipe.bind_evidence"
    id: str
    evidence_bindings: list[dict[str, Any]]


class RecipeArchiveOp(OperationBase):
    op: Literal["recipe.archive"] = "recipe.archive"
    id: str


class BackendConfigurationCreateOp(OperationBase):
    op: Literal["backend_configuration.create"] = "backend_configuration.create"
    title: str = ""
    id: str | None = None
    plugin_id: str
    plugin_version: str
    package_digest: str | None = None
    toolchain_identifier: str = "reference"
    version_constraints: str = ">=1.0"
    config_json: dict[str, Any] = Field(default_factory=dict)
    capability_snapshot: dict[str, Any] = Field(default_factory=dict)


class ExternalImplementationRegisterOp(OperationBase):
    op: Literal["external_implementation.register"] = "external_implementation.register"
    id: str | None = None
    title: str
    description: str = ""
    coverage_checkpoint_id: str
    intent_ids: list[str] = Field(default_factory=list)
    objective_ids: list[str] = Field(default_factory=list)
    toolchain_identifier: str = "external"
    artifact_manifest: dict[str, Any] = Field(default_factory=dict)
    evidence_bindings: list[dict[str, Any]] = Field(default_factory=list)
    oracle_provenance: dict[str, Any] = Field(default_factory=dict)


CommandOperation = (
    PlanUpdateOp
    | SourceSectionAssessOp
    | RequirementCreateOp
    | RequirementUpdateOp
    | SectionCreateOp
    | SectionUpdateOp
    | IntentCreateOp
    | IntentUpdateOp
    | IntentSetStateOp
    | IntentLinkRequirementOp
    | IntentUnlinkRequirementOp
    | ItemMoveOp
    | SectionCopyOp
    | RecordArchiveOp
    | RecordRestoreOp
    | RecordDeleteDraftOp
    | IssueCreateOp
    | IssueUpdateOp
    | IssueResolveOp
    | IssueReopenOp
    | SourceUpdateOp
    | DimensionCreateOp
    | DimensionUpdateOp
    | DimensionArchiveOp
    | ObjectiveCreateOp
    | ObjectiveUpdateOp
    | ObjectiveArchiveOp
    | BinAddOp
    | BinUpdateOp
    | BinRemoveOp
    | PolicySetOp
    | ExclusionProposeOp
    | ExclusionUpdateOp
    | CoverageRebaseOp
    | ImplementationRebaseOp
    | BindingSetCreateOp
    | BindingSetUpdateOp
    | BindingSetArchiveOp
    | RecipeCreateOp
    | RecipeUpdateOp
    | RecipeSetStateOp
    | RecipeBindEvidenceOp
    | RecipeArchiveOp
    | BackendConfigurationCreateOp
    | ExternalImplementationRegisterOp
)


class CommandBatchRequest(BaseModel):
    """Atomic command transaction request envelope."""

    model_config = ConfigDict(extra="forbid")

    base_edit_revision: int
    request_id: str
    operations: list[dict[str, Any]]


class CommandBatchResponse(BaseModel):
    """Result of a successfully committed command transaction."""

    model_config = ConfigDict(extra="forbid")

    edit_revision: int
    changed_records: list[dict[str, Any]]
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    request_id: str
    created_at: str | None = None

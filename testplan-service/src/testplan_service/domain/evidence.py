"""Evaluation profiles, campaigns, runs, and observations domain models."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from testplan_service.constants import MAX_TEXT_LENGTH, MAX_TITLE_LENGTH
from testplan_service.domain.policies import IntentWaiver


class CampaignPurpose(str, Enum):
    """Campaign purpose classification."""

    VERIFICATION = "verification"
    FIXTURE = "fixture"


class CampaignState(str, Enum):
    """Campaign lifecycle state."""

    OPEN = "open"
    FROZEN = "frozen"


class RunStatus(str, Enum):
    """Execution status of an imported verification run."""

    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"
    CANCELLED = "cancelled"
    INCOMPLETE = "incomplete"


class RunDispositionKind(str, Enum):
    """Audited resolution for an invalid or superseded run."""

    INVALID_TOOL_RUN = "invalid_tool_run"
    SUPERSEDED_AFTER_FIX = "superseded_after_fix"


class ObservationOutcome(str, Enum):
    """Outcome classification for a single observation."""

    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"
    ERROR = "error"
    PROVEN = "proven"
    BOUNDED_PASS = "bounded_pass"
    COUNTEREXAMPLE = "counterexample"
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"
    REACHED = "reached"
    UNREACHABLE = "unreachable"
    KILLED = "killed"
    SURVIVED = "survived"
    EQUIVALENT = "equivalent"
    INVALID = "invalid"
    HIT = "hit"
    UNHIT = "unhit"


class RealizationDescriptor(BaseModel):
    """Realization descriptor pinning producer, tool version, and build digests."""

    model_config = ConfigDict(extra="ignore")

    producer_id: str
    tool_name: str
    tool_version: str
    build_artifact_hash: str
    assumption_set_hash: str | None = None


class EvaluationProfile(BaseModel):
    """Immutable parameter configuration and realization descriptors for a DUT."""

    model_config = ConfigDict(extra="ignore")

    id: str
    plan_id: str
    display_name: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    coverage_checkpoint_id: str
    source_snapshot_id: str
    source_snapshot_hash: str
    dut_source_hash: str
    root_occurrence_id: str
    resolved_parameters: dict[str, Any] = Field(default_factory=dict)
    clock_reset_config: dict[str, Any] = Field(default_factory=dict)
    realization_descriptors: list[RealizationDescriptor] = Field(default_factory=list)
    content_hash: str = ""
    created_at: str


class RunDisposition(BaseModel):
    """Audited disposition explaining run exclusion or replacement."""

    model_config = ConfigDict(extra="ignore")

    run_id: str
    disposition: RunDispositionKind
    reason: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    reviewer_label: str
    replacement_run_id: str | None = None
    created_at: str


class EvidenceCampaign(BaseModel):
    """Campaign defining the exact run population used for closure status."""

    model_config = ConfigDict(extra="ignore")

    id: str
    plan_id: str
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    coverage_checkpoint_id: str
    required_profile_ids: list[str] = Field(min_length=1)
    included_run_ids: list[str] = Field(default_factory=list)
    run_dispositions: dict[str, RunDisposition] = Field(default_factory=dict)
    waivers: list[IntentWaiver] = Field(default_factory=list)
    purpose: CampaignPurpose = CampaignPurpose.VERIFICATION
    state: CampaignState = CampaignState.OPEN
    campaign_revision: int = 1
    created_at: str
    updated_at: str


class EvidenceObservation(BaseModel):
    """Atomic normalized verification observation."""

    model_config = ConfigDict(extra="ignore")

    id: str
    run_id: str
    producer_observation_id: str
    objective_id: str
    objective_definition_hash: str
    scope_id: str
    bin_id: str | None = None
    family: str
    outcome: ObservationOutcome
    evaluation_count: int = 0
    hit_count: int = 0
    structural_elements: list[str] = Field(default_factory=list)
    correctness_association_id: str | None = None
    property_fields: dict[str, Any] = Field(default_factory=dict)
    artifact_anchors: list[dict[str, Any]] = Field(default_factory=list)
    diagnostic_message: str | None = None


class EvidenceRun(BaseModel):
    """Immutable execution record from a verification producer."""

    model_config = ConfigDict(extra="ignore")

    id: str
    plan_id: str
    producer_id: str
    external_run_id: str
    attempt_id: str
    profile_id: str
    coverage_checkpoint_id: str
    producer_manifest_digest: str = ""
    dut_source_hash: str
    configuration_hash: str
    tool_name: str
    tool_version: str
    seed: int | None = None
    synthetic: bool = False
    producer_kind: str = "generated"  # "generated" or "external"
    trust_label: str = "imported_local"
    status: RunStatus = RunStatus.COMPLETED
    raw_artifact_digests: list[str] = Field(default_factory=list)
    parser_adapter_id: str = "verification.results.v1"
    validation_diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    start_time: str | None = None
    end_time: str | None = None
    imported_at: str
    payload_hash: str = ""


class EvidenceReport(BaseModel):
    """Frozen read-only report at C1 + campaign_revision + evidence_sequence."""

    model_config = ConfigDict(extra="ignore")

    id: str
    plan_id: str
    coverage_checkpoint_id: str
    campaign_id: str
    campaign_revision: int
    evidence_sequence: int
    status: str  # "Complete evidence", "Incomplete evidence", "Complete with waivers"
    report_data: dict[str, Any]
    created_at: str

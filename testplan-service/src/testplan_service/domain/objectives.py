"""Coverage objectives, dimensions, bins, and exclusions domain models."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from testplan_service.constants import MAX_TEXT_LENGTH, MAX_TITLE_LENGTH
from testplan_service.domain.enums import AuthoringState


class CoverageFamily(str, Enum):
    """The 6 fundamental coverage and evidence families."""

    SCENARIO = "scenario"
    FUNCTIONAL = "functional"
    CORRECTNESS = "correctness"
    PROPERTY = "property"
    STRUCTURAL = "structural"
    MUTATION = "mutation"


class DimensionType(str, Enum):
    """Data representation for a coverage dimension."""

    ENUM = "enum"
    INTEGER_RANGE = "integer_range"
    BOOLEAN = "boolean"


class BinStatus(str, Enum):
    """Status of an individual coverage bin."""

    REQUIRED = "required"
    EXCLUDED = "excluded"


class ExclusionReason(str, Enum):
    """Reason for proposing or approving a coverage exclusion."""

    NOT_APPLICABLE = "not_applicable"
    UNREACHABLE = "unreachable"
    OUT_OF_SCOPE = "out_of_scope"


class StructuralMetricKind(str, Enum):
    """Structural coverage metric classification."""

    LINE = "line"
    BRANCH = "branch"
    TOGGLE = "toggle"
    FSM = "fsm"
    EXPRESSION = "expression"


class PropertyClaimKind(str, Enum):
    """Property proof claim scope."""

    UNBOUNDED = "unbounded"
    BOUNDED = "bounded"


class CoverageDimension(BaseModel):
    """Selected parameter or scenario axis for binning."""

    model_config = ConfigDict(extra="ignore")

    id: str
    key: str
    record_type: str = "dimension"
    record_revision: int = 1
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    semantic_description: str = Field(default="", max_length=MAX_TEXT_LENGTH)
    scope_id: str
    dimension_type: DimensionType
    unit: str | None = None
    value_classes: list[dict[str, Any]] = Field(default_factory=list)
    allow_overlap: bool = False
    rationale: str | None = None
    archived: bool = False
    created_at: str
    updated_at: str


class CoverageBin(BaseModel):
    """Explicit point or partition within a scenario or functional objective."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str = Field(default="", max_length=MAX_TITLE_LENGTH)
    dimension_assignments: dict[str, Any] = Field(default_factory=dict)
    transition_description: str | None = None
    required_hits: int = Field(default=1, ge=1)
    status: BinStatus = BinStatus.REQUIRED
    exclusion_id: str | None = None

    @classmethod
    def model_validate(cls, obj: Any, *args: Any, **kwargs: Any) -> CoverageBin:
        if isinstance(obj, dict):
            d = dict(obj)
            if "id" not in d and "bin_id" in d:
                d["id"] = d["bin_id"]
            if "title" not in d and "name" in d:
                d["title"] = d["name"]
            elif "title" not in d:
                d["title"] = d.get("id", "bin")
            return super().model_validate(d, *args, **kwargs)
        return super().model_validate(obj, *args, **kwargs)


class CoverageExclusion(BaseModel):
    """Exclusion record with technical justification."""

    model_config = ConfigDict(extra="ignore")

    id: str
    record_type: str = "exclusion"
    record_revision: int = 1
    objective_id: str
    bin_id: str | None = None
    reason_kind: ExclusionReason
    rationale: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    reviewer_label: str | None = None
    reviewed_at: str | None = None
    checkpoint_id: str | None = None
    archived: bool = False
    created_at: str
    updated_at: str


class CoverageAcceptance(BaseModel):
    """Typed family-specific acceptance criteria."""

    model_config = ConfigDict(extra="ignore")

    # Scenario / Functional
    required_hits_default: int = 1

    # Correctness
    minimum_evaluations: int = 1
    check_description: str | None = None

    # Property
    claim: PropertyClaimKind = PropertyClaimKind.UNBOUNDED
    bound: int | None = None
    assumption_set_id: str | None = None
    reachability_obligations: list[str] = Field(default_factory=list)
    vacuity_requirement: bool = True

    # Structural
    metric_kind: StructuralMetricKind | None = None
    target_elements: list[str] = Field(default_factory=list)
    threshold_bps: int = 10000  # 100.00%
    exclusions: list[str] = Field(default_factory=list)

    # Mutation
    mutant_set_version: str | None = None
    minimum_detection_ratio_bps: int = 10000


class CoverageObjective(BaseModel):
    """Coverage objective defining what evidence is needed for an intent."""

    model_config = ConfigDict(extra="ignore")

    id: str
    key: str
    record_type: str = "objective"
    record_revision: int = 1
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    description: str = Field(default="", max_length=MAX_TEXT_LENGTH)
    scope_id: str
    participant_scope_ids: list[str] = Field(default_factory=list)
    family: CoverageFamily
    semantic_definition: str = Field(default="", max_length=MAX_TEXT_LENGTH)
    dimension_ids: list[str] = Field(default_factory=list)
    bins: list[CoverageBin] = Field(default_factory=list)
    acceptance: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = Field(default=None, max_length=MAX_TEXT_LENGTH)
    authoring_state: AuthoringState = AuthoringState.DRAFT
    supplemental: bool = False
    copied_from: str | None = None
    archived: bool = False
    created_at: str
    updated_at: str

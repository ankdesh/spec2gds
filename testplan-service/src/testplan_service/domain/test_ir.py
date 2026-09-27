"""Typed Test Intermediate Representation (Test IR v1) domain models.

Defines the language-neutral, schema-versioned AST for scenario and property
recipes according to schema 'verification.test-ir.v1'.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from testplan_service.constants import (
    DEFAULT_EXTERNAL_RUNTIME_TIMEOUT_SECONDS,
    DEFAULT_MAX_EVALUATED_STEPS,
    DEFAULT_MAX_SIMULATED_EDGES,
    MAX_TEXT_LENGTH,
    MAX_TITLE_LENGTH,
    SCHEMA_VERSION_TEST_IR,
)


class IRType(str, Enum):
    """Core scalar and vector data types supported by Test IR v1."""

    BOOL = "bool"
    UINT = "uint"
    SINT = "sint"
    INTEGER = "integer"
    ENUM = "enum"
    LOGIC_VECTOR = "logic_vector"


class ArithmeticMode(str, Enum):
    """Arithmetic overflow handling modes."""

    CHECKED = "checked"
    WRAP = "wrap"


class ClockEdge(str, Enum):
    """Clock active transition edge."""

    RISING = "rising"
    FALLING = "falling"
    BOTH = "both"


class ResetPolarity(str, Enum):
    """Reset active polarity."""

    HIGH = "high"
    LOW = "low"


class ResetSyncType(str, Enum):
    """Reset synchronization behavior."""

    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"


class PortDirection(str, Enum):
    """Access direction for target bindings."""

    INPUT = "input"
    OUTPUT = "output"
    INOUT = "inout"


class StepPhase(str, Enum):
    """Deterministic simulation execution phase."""

    DRIVE_BEFORE_EDGE = "drive_before_edge"
    SAMPLE_BEFORE_EDGE = "sample_before_edge"
    ACTIVE_EDGE = "active_edge"
    SAMPLE_AFTER_SETTLE = "sample_after_settle"


class PropertyTemplate(str, Enum):
    """Standardized portable property templates."""

    INVARIANT = "invariant"
    IMPLICATION_FIXED_DELAY = "implication_fixed_delay"
    BOUNDED_RESPONSE = "bounded_response"
    STABILITY_WINDOW = "stability_window"
    REACHABILITY_COVER = "reachability_cover"


# --- Declarations ---

class ClockDecl(BaseModel):
    """Explicit clock domain declaration."""

    model_config = ConfigDict(extra="ignore")

    id: str
    edge: ClockEdge = ClockEdge.RISING
    period_fs: int = Field(default=10_000_000_000, ge=1)  # Default 10ns (100 MHz)
    phase_offset_fs: int = Field(default=0, ge=0)
    source_clock: str | None = None


class ResetDecl(BaseModel):
    """Explicit reset signal declaration."""

    model_config = ConfigDict(extra="ignore")

    id: str
    active_polarity: ResetPolarity = ResetPolarity.HIGH
    sync_type: ResetSyncType = ResetSyncType.SYNCHRONOUS
    domains: list[str] = Field(default_factory=list)


class PortDecl(BaseModel):
    """Semantic port reference and declared direction."""

    model_config = ConfigDict(extra="ignore")

    name: str
    direction: PortDirection
    width: int = Field(default=1, ge=1, le=4096)
    signed: bool = False
    binding_id: str | None = None


class VariableDecl(BaseModel):
    """Typed local state variable."""

    model_config = ConfigDict(extra="ignore")

    name: str
    type: IRType = IRType.UINT
    width: int = Field(default=32, ge=1, le=4096)
    initial_val: Any = 0


class ModelDecl(BaseModel):
    """Explicit portable reference model definition."""

    model_config = ConfigDict(extra="ignore")

    name: str
    kind: Literal["record", "fsm", "bounded_queue"] = "bounded_queue"
    capacity: int | None = Field(default=None, ge=1)
    element_type: str | None = "uint(8)"
    initial_state: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)


class IRLimits(BaseModel):
    """Enforceable bounds and execution quotas."""

    model_config = ConfigDict(extra="ignore")

    max_simulated_edges: int = Field(default=DEFAULT_MAX_SIMULATED_EDGES, ge=1)
    max_evaluated_steps: int = Field(default=DEFAULT_MAX_EVALUATED_STEPS, ge=1)
    external_runtime_timeout_seconds: int = Field(
        default=DEFAULT_EXTERNAL_RUNTIME_TIMEOUT_SECONDS, ge=1
    )


# --- Step Schemas ---

class IRStep(BaseModel):
    """Base class for structured sequence steps."""

    model_config = ConfigDict(extra="ignore")

    step_id: str
    step_type: str


class DriveStep(IRStep):
    """Drive values onto input bindings."""

    step_type: Literal["drive"] = "drive"
    domain: str = "clk"
    phase: StepPhase = StepPhase.DRIVE_BEFORE_EDGE
    assignments: list[dict[str, Any]] = Field(default_factory=list)  # [{"target": str, "expr": Any}]


class WaitEdgesStep(IRStep):
    """Advance simulation by a deterministic number of clock edges."""

    step_type: Literal["wait_edges"] = "wait_edges"
    domain: str = "clk"
    edge: ClockEdge = ClockEdge.RISING
    count: int = Field(default=1, ge=1)


class WaitUntilStep(IRStep):
    """Wait until condition holds or edge limit is reached."""

    step_type: Literal["wait_until"] = "wait_until"
    domain: str = "clk"
    phase: StepPhase = StepPhase.SAMPLE_AFTER_SETTLE
    condition: dict[str, Any]
    max_edges: int = Field(default=1000, ge=1)


class SampleStep(IRStep):
    """Sample target observations or expressions into named slots."""

    step_type: Literal["sample"] = "sample"
    domain: str = "clk"
    phase: StepPhase = StepPhase.SAMPLE_AFTER_SETTLE
    samples: list[dict[str, Any]] = Field(default_factory=list)  # [{"slot": str, "expr": Any}]


class AssignStep(IRStep):
    """Assign local variable without DUT interaction."""

    step_type: Literal["assign"] = "assign"
    variable: str
    expr: dict[str, Any]


class ModelUpdateStep(IRStep):
    """Update state of an authored reference model."""

    step_type: Literal["model_update"] = "model_update"
    model: str
    action: str  # e.g., "append", "pop", "peek", "clear"
    args: dict[str, Any] = Field(default_factory=dict)


class CheckStep(IRStep):
    """Evaluate an oracle condition against sampled values."""

    step_type: Literal["check"] = "check"
    check_id: str
    expr: dict[str, Any]
    abort_on_failure: bool = False
    rationale: str | None = None
    objective_id: str | None = None


class CoverStep(IRStep):
    """Mark a coverage event occurrence associated with a check."""

    step_type: Literal["cover"] = "cover"
    objective_id: str
    bin_id: str | None = None
    predicate: dict[str, Any] | None = None
    check_association: str | None = None


class IfStep(IRStep):
    """Conditional execution branch."""

    step_type: Literal["if"] = "if"
    condition: dict[str, Any]
    then_steps: list[dict[str, Any]] = Field(default_factory=list)
    else_steps: list[dict[str, Any]] = Field(default_factory=list)


class RepeatStep(IRStep):
    """Deterministic loop bounded by an explicit iteration count."""

    step_type: Literal["repeat"] = "repeat"
    count: int = Field(default=1, ge=0, le=10000)
    steps: list[dict[str, Any]] = Field(default_factory=list)


class ParallelStep(IRStep):
    """Parallel execution branches joined at completion."""

    step_type: Literal["parallel"] = "parallel"
    join: Literal["all"] = "all"
    branches: list[list[dict[str, Any]]] = Field(default_factory=list)


class CallExtensionStep(IRStep):
    """Call an explicit namespaced backend extension."""

    step_type: Literal["call_extension"] = "call_extension"
    op: str
    version: str = "1.0"
    args: dict[str, Any] = Field(default_factory=dict)


# --- Property Definitions ---

class PropertyDecl(BaseModel):
    """Temporal claim or assumption for formal verification."""

    model_config = ConfigDict(extra="ignore")

    property_id: str
    template: PropertyTemplate
    clock: str = "clk"
    reset: str | None = None
    predicate: dict[str, Any] | None = None
    antecedent: dict[str, Any] | None = None
    consequent: dict[str, Any] | None = None
    min_delay: int | None = None
    max_delay: int | None = None
    delay_edges: int | None = None
    guard: dict[str, Any] | None = None
    stable_edges: int | None = None
    objective_id: str | None = None
    description: str = Field(default="", max_length=MAX_TEXT_LENGTH)


# --- Test IR Envelope ---

class TestIR(BaseModel):
    """Canonical Test Intermediate Representation AST envelope."""

    model_config = ConfigDict(extra="ignore")

    schema_version: str = SCHEMA_VERSION_TEST_IR
    recipe_kind: Literal["scenario", "property"] = "scenario"
    parameters: dict[str, Any] = Field(default_factory=dict)
    ports: list[PortDecl] = Field(default_factory=list)
    clocks: list[ClockDecl] = Field(default_factory=list)
    resets: list[ResetDecl] = Field(default_factory=list)
    variables: list[VariableDecl] = Field(default_factory=list)
    models: list[ModelDecl] = Field(default_factory=list)
    setup: list[dict[str, Any]] = Field(default_factory=list)
    body: list[dict[str, Any]] = Field(default_factory=list)
    teardown: list[dict[str, Any]] = Field(default_factory=list)
    properties: list[PropertyDecl] = Field(default_factory=list)
    checks: list[dict[str, Any]] = Field(default_factory=list)
    coverage_events: list[dict[str, Any]] = Field(default_factory=list)
    limits: IRLimits = Field(default_factory=IRLimits)
    required_capabilities: list[str] = Field(default_factory=list)
    extensions: dict[str, Any] = Field(default_factory=dict)

"""Domain models for Target Bindings, Recipes, Backends, and Producer Manifests."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from testplan_service.constants import (
    MAX_TEXT_LENGTH,
    MAX_TITLE_LENGTH,
    SCHEMA_VERSION_PRODUCER,
)
from testplan_service.domain.enums import AuthoringState
from testplan_service.domain.test_ir import ClockDecl, ResetDecl, TestIR


class RecipeKind(str, Enum):
    """Execution paradigm of a test recipe."""

    SCENARIO = "scenario"
    PROPERTY = "property"
    EXTERNAL = "external"


class RecipeState(str, Enum):
    """Authoring and capability readiness state of a recipe."""

    DRAFT = "draft"
    READY = "ready"
    UNSUPPORTED = "unsupported"
    BLOCKED = "blocked"


class TargetKind(str, Enum):
    """Hardware interface classification for signal binding."""

    INPUT = "input"
    OUTPUT = "output"
    INTERNAL = "internal"
    TRANSACTION = "transaction"
    MODEL_VALUE = "model_value"


class TargetPermission(str, Enum):
    """Allowed interactions with target signal."""

    DRIVE = "drive"
    SAMPLE = "sample"


class TargetBinding(BaseModel):
    """Mapping of a semantic observation to a concrete DUT signal or locator."""

    model_config = ConfigDict(extra="ignore")

    id: str
    observation_name: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    source_ref: str | None = None
    target_kind: TargetKind = TargetKind.INPUT
    target_locator: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    data_type: str = "uint"
    width: int = Field(default=1, ge=1, le=4096)
    signed: bool = False
    clock_domain: str = "clk"
    sampling_phase: str = "sample_after_settle"
    permissions: list[TargetPermission] = Field(default_factory=lambda: [TargetPermission.SAMPLE])


class TargetBindingSet(BaseModel):
    """Collection of physical DUT signal bindings and clock/reset relationships."""

    model_config = ConfigDict(extra="ignore")

    id: str
    key: str
    title: str = ""
    record_type: str = "target_binding_set"
    record_revision: int = 1
    plan_id: str
    source_snapshot_id: str
    root_scope_id: str
    dut_language: str = "verilog"
    top_module: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    dut_manifest_digest: str | None = None
    resolved_parameters: dict[str, Any] = Field(default_factory=dict)
    clocks: list[ClockDecl] = Field(default_factory=list)
    resets: list[ResetDecl] = Field(default_factory=list)
    bindings: list[TargetBinding] = Field(default_factory=list)
    authoring_state: AuthoringState = AuthoringState.DRAFT
    archived: bool = False
    created_at: str
    updated_at: str


class OracleProvenance(BaseModel):
    """Audit trail explaining reference model origin and assumptions."""

    model_config = ConfigDict(extra="ignore")

    source_locators: list[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=MAX_TEXT_LENGTH)
    independently_authored: bool = True
    reviewed_assumptions: list[str] = Field(default_factory=list)


class EvidenceBinding(BaseModel):
    """Linkage between producer observation and Layer 2 coverage objective/bin."""

    model_config = ConfigDict(extra="ignore")

    observation_key: str
    objective_id: str
    bin_id: str | None = None
    definition_hash: str
    check_id: str | None = None


class Recipe(BaseModel):
    """Complete specification of how evidence is realized for one or more intents."""

    model_config = ConfigDict(extra="ignore")

    id: str
    key: str
    record_type: str = "recipe"
    record_revision: int = 1
    plan_id: str
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    description: str = Field(default="", max_length=MAX_TEXT_LENGTH)
    kind: RecipeKind = RecipeKind.SCENARIO
    coverage_checkpoint_id: str
    intent_ids: list[str] = Field(default_factory=list)
    objective_ids: list[str] = Field(default_factory=list)
    target_binding_set_id: str | None = None
    test_ir: TestIR | None = None
    backend_configuration_id: str | None = None
    evidence_bindings: list[EvidenceBinding] = Field(default_factory=list)
    oracle_provenance: OracleProvenance = Field(default_factory=OracleProvenance)
    authoring_state: RecipeState = RecipeState.DRAFT
    archived: bool = False
    created_at: str
    updated_at: str


class BackendConfiguration(BaseModel):
    """Pinned, immutable toolchain and backend plugin settings."""

    model_config = ConfigDict(extra="ignore")

    id: str
    key: str
    title: str = ""
    record_type: str = "backend_configuration"
    record_revision: int = 1
    plan_id: str
    plugin_id: str
    plugin_version: str
    package_digest: str
    toolchain_identifier: str = "reference"
    version_constraints: str = ">=1.0"
    config_json: dict[str, Any] = Field(default_factory=dict)
    capability_snapshot: dict[str, Any] = Field(default_factory=dict)
    configuration_digest: str
    created_at: str


class ProducerObservation(BaseModel):
    """Observation mapping Authority for test results."""

    model_config = ConfigDict(extra="ignore")

    observation_key: str
    objective_id: str
    objective_definition_hash: str
    bin_ids: list[str] = Field(default_factory=list)
    scope: str
    family: str
    check_id: str | None = None
    field_shape: str = "scalar"


class ProducerManifest(BaseModel):
    """Canonical verification.producer.v1 mapping authority manifest."""

    model_config = ConfigDict(extra="ignore")

    schema_version: str = SCHEMA_VERSION_PRODUCER
    producer_id: str
    manifest_digest: str
    implementation_checkpoint_id: str | None = None
    recipe_ids: list[str] = Field(default_factory=list)
    coverage_checkpoint_id: str
    source_hash: str
    coverage_hash: str
    target_hash: str
    backend_plugin_id: str
    backend_plugin_version: str
    tool_configuration: dict[str, Any] = Field(default_factory=dict)
    observations: dict[str, ProducerObservation] = Field(default_factory=dict)
    created_at: str


class ImplementationCheckpoint(BaseModel):
    """Immutable baseline capturing a reviewed implementation set (I1, I2, ...)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    key: str
    plan_id: str
    coverage_checkpoint_id: str
    recipe_ids: list[str] = Field(default_factory=list)
    target_binding_set_ids: list[str] = Field(default_factory=list)
    backend_configuration_ids: list[str] = Field(default_factory=list)
    evidence_bindings_digest: str
    unimplemented_objective_count: int = 0
    reviewer_label: str
    comment: str = ""
    content_hash: str
    created_at: str

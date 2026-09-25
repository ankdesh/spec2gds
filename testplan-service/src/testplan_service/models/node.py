"""Domain model representing a single node in the hierarchical testplan tree."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from testplan_service.constants import (
    MAX_DESCRIPTION_LENGTH,
    MAX_TAGS_COUNT,
    MAX_TITLE_LENGTH,
)
from testplan_service.models.enums import (
    CoverageCategory,
    NodeKind,
    NodePriority,
    NodeStatus,
    VerificationMethodology,
    VerificationStage,
)


class TestPlanNode(BaseModel):
    """One node in the hierarchical verification plan tree."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(
        ...,
        description="Unique identifier for the node within the testplan.",
        min_length=1,
        max_length=128,
    )
    parent_id: str | None = Field(
        default=None,
        description="Identifier of the parent node, or None if root-level.",
    )
    title: str = Field(
        ...,
        description="Short, human-readable title describing the test or feature.",
        min_length=1,
        max_length=MAX_TITLE_LENGTH,
    )
    kind: NodeKind = Field(
        default=NodeKind.TESTCASE,
        description="Structural role of this node in the hierarchy.",
    )
    category: CoverageCategory = Field(
        default=CoverageCategory.GENERAL,
        description="Hardware verification coverage category.",
    )
    description: str = Field(
        default="",
        description="Detailed markdown description of the test intent or requirement.",
        max_length=MAX_DESCRIPTION_LENGTH,
    )
    methodology: VerificationMethodology = Field(
        default=VerificationMethodology.DIRECTED,
        description="Verification approach (directed, constrained random, formal, etc.).",
    )
    stage: VerificationStage = Field(
        default=VerificationStage.V1,
        description="OpenTitan-aligned verification maturity stage.",
    )
    priority: NodePriority = Field(
        default=NodePriority.MEDIUM,
        description="Relative priority level of this item.",
    )
    status: NodeStatus = Field(
        default=NodeStatus.PLANNED,
        description="Current verification execution outcome or status.",
    )
    stimulus: str = Field(
        default="",
        description="Description or specification of driven inputs.",
        max_length=MAX_DESCRIPTION_LENGTH,
    )
    expected_outcome: str = Field(
        default="",
        description="Expected behavior, assertions, or pass/fail criteria.",
        max_length=MAX_DESCRIPTION_LENGTH,
    )
    coverage_bins: list[str] = Field(
        default_factory=list,
        description="List of targeted coverage bin identifiers (e.g. boundary:data_in:max).",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Categorical tags for filtering and organization.",
        max_length=MAX_TAGS_COUNT,
    )
    order: int = Field(
        default=0,
        description="Display order index among siblings.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible custom metadata dictionary.",
    )
    children: list[TestPlanNode] = Field(
        default_factory=list,
        description="Nested child nodes when representing a materialized tree.",
    )

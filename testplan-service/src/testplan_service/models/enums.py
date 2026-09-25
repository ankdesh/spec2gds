"""Enumeration types for hierarchical testplans and coverage taxonomy."""

from __future__ import annotations

from enum import Enum


class NodeKind(str, Enum):
    """Structural role of a node within the testplan hierarchy."""

    GROUP = "group"
    FEATURE = "feature"
    TESTPOINT = "testpoint"
    TESTCASE = "testcase"
    COVERGROUP = "covergroup"
    ASSERTION = "assertion"


class CoverageCategory(str, Enum):
    """Hardware verification coverage category taxonomy."""

    PORT_BOUNDARY = "port_boundary"
    RESET_BEHAVIOR = "reset_behavior"
    FUNCTIONAL_MODE = "functional_mode"
    PROTOCOL_COMPLIANCE = "protocol_compliance"
    ERROR_INJECTION = "error_injection"
    TIMING_SEQUENCING = "timing_sequencing"
    CROSS_PORT = "cross_port"
    STRUCTURAL_CONNECTIVITY = "structural_connectivity"
    SPECIAL_PATTERNS = "special_patterns"
    GENERAL = "general"


class VerificationMethodology(str, Enum):
    """Target verification approach for a test item."""

    DIRECTED = "directed"
    CONSTRAINED_RANDOM = "constrained_random"
    FORMAL = "formal"
    ASSERTION = "assertion"
    LINT = "lint"


class NodeStatus(str, Enum):
    """Current verification execution status."""

    DRAFT = "draft"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class NodePriority(str, Enum):
    """Priority level for test execution and tracking."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VerificationStage(str, Enum):
    """OpenTitan-aligned verification milestone stage."""

    V0 = "V0"
    V1 = "V1"
    V2 = "V2"
    V3 = "V3"

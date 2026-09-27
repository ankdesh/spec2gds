"""Domain enumerations for Verification Planner."""

from __future__ import annotations

from enum import Enum


class ScopeKind(str, Enum):
    """Supported verification scope kinds."""

    DESIGN = "design"
    COMPONENT = "component"
    INTERFACE = "interface"


class Priority(str, Enum):
    """Verification priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuthoringState(str, Enum):
    """Authoring readiness state for an Intent."""

    DRAFT = "draft"
    READY = "ready"
    BLOCKED = "blocked"


class RequirementDisposition(str, Enum):
    """Disposition of a captured source requirement."""

    UNASSESSED = "unassessed"
    VERIFY = "verify"
    INFORMATIONAL = "informational"
    OUT_OF_SCOPE = "out_of_scope"
    AMBIGUOUS = "ambiguous"


class SourceAuditDisposition(str, Enum):
    """Audit status of an in-scope source section."""

    UNREVIEWED = "unreviewed"
    REQUIREMENTS_CAPTURED = "requirements_captured"
    INFORMATIONAL = "informational"
    OUT_OF_SCOPE = "out_of_scope"


class IntentOrigin(str, Enum):
    """Origin of a verification intent."""

    DIRECT_REQUIREMENT = "direct_requirement"
    DERIVED_INTERPRETATION = "derived_interpretation"


class IssueKind(str, Enum):
    """Classification of an open question or ambiguity."""

    SOURCE_AMBIGUITY = "source_ambiguity"
    SOURCE_MISSING = "source_missing"
    CONTRADICTION = "contradiction"
    OBSERVATION_UNCLEAR = "observation_unclear"
    OTHER = "other"


class IssueSeverity(str, Enum):
    """Severity of a source or intent issue."""

    BLOCKING = "blocking"
    ADVISORY = "advisory"


class IssueState(str, Enum):
    """Lifecycle state of an issue."""

    OPEN = "open"
    RESOLVED = "resolved"

"""Domain-specific precise exceptions for Verification Planner."""

from __future__ import annotations

from typing import Any


class VerificationPlannerError(Exception):
    """Base exception for all Verification Planner service failures."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class PlanNotFoundError(VerificationPlannerError):
    """Raised when a requested plan does not exist."""

    def __init__(self, plan_id: str) -> None:
        super().__init__(f"Plan '{plan_id}' was not found.", {"plan_id": plan_id})
        self.plan_id = plan_id


class RecordNotFoundError(VerificationPlannerError):
    """Raised when a requested record is not found in the plan."""

    def __init__(self, plan_id: str, record_id: str) -> None:
        super().__init__(
            f"Record '{record_id}' was not found in plan '{plan_id}'.",
            {"plan_id": plan_id, "record_id": record_id},
        )
        self.plan_id = plan_id
        self.record_id = record_id


class RevisionConflictError(VerificationPlannerError):
    """Raised when base_edit_revision does not match the current plan revision."""

    def __init__(
        self,
        plan_id: str,
        base_revision: int,
        current_revision: int,
        diagnostics: list[dict[str, Any]] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            f"Revision conflict for plan '{plan_id}': expected revision {base_revision}, current is {current_revision}.",
            {
                "plan_id": plan_id,
                "base_revision": base_revision,
                "current_revision": current_revision,
                "diagnostics": diagnostics or [],
                "request_id": request_id,
            },
        )
        self.plan_id = plan_id
        self.base_revision = base_revision
        self.current_revision = current_revision
        self.diagnostics = diagnostics or []
        self.request_id = request_id


class PreconditionRequiredError(VerificationPlannerError):
    """Raised when an operation requires a base_edit_revision or If-Match precondition."""

    def __init__(self, message: str = "Command batch requires 'base_edit_revision' precondition.") -> None:
        super().__init__(message)


class IdempotencyMismatchError(VerificationPlannerError):
    """Raised when a request ID is reused with a different canonical payload."""

    def __init__(self, request_id: str) -> None:
        super().__init__(
            f"Request ID '{request_id}' was previously executed with a different payload.",
            {"request_id": request_id},
        )
        self.request_id = request_id


class DomainValidationError(VerificationPlannerError):
    """Raised when domain business invariants are violated."""

    def __init__(self, message: str, diagnostics: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message, {"diagnostics": diagnostics or []})
        self.diagnostics = diagnostics or []


class CycleDetectedError(DomainValidationError):
    """Raised when hierarchy or dependency cycle is detected."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, [{"code": "cycle_detected", "severity": "error", "message": message, "details": details or {}}])


class MaxDepthExceededError(DomainValidationError):
    """Raised when tree depth exceeds maximum allowed."""

    def __init__(self, depth: int, max_depth: int) -> None:
        super().__init__(
            f"Hierarchy depth {depth} exceeds limit of {max_depth}.",
            [{"code": "max_depth_exceeded", "severity": "error", "message": f"Depth {depth} exceeds {max_depth}"}],
        )


class CheckpointBlockerError(VerificationPlannerError):
    """Raised when creating a review checkpoint with unresolved blocking checklist items."""

    def __init__(self, message: str, checklist: dict[str, Any], blockers: list[str]) -> None:
        super().__init__(message, {"checklist": checklist, "blockers": blockers})
        self.checklist = checklist
        self.blockers = blockers


class StorageError(VerificationPlannerError):
    """Raised when persistence or SQLite storage operation fails."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message, {"cause": str(cause) if cause else None})
        self.cause = cause


class SnapshotError(VerificationPlannerError):
    """Raised when Activity Snapshot parsing or validation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class BundleError(VerificationPlannerError):
    """Raised when portable .vplan bundle validation or unpack fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidOperationError(VerificationPlannerError):
    """Raised when an operation is invalid or unknown."""

    def __init__(self, message: str, operation: str = "unknown") -> None:
        super().__init__(message, {"operation": operation})
        self.operation = operation


class CampaignNotFoundError(VerificationPlannerError):
    """Raised when an evidence campaign does not exist."""

    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"Evidence campaign '{campaign_id}' was not found.", {"campaign_id": campaign_id})
        self.campaign_id = campaign_id


class ProfileNotFoundError(VerificationPlannerError):
    """Raised when an evaluation profile does not exist."""

    def __init__(self, profile_id: str) -> None:
        super().__init__(f"Evaluation profile '{profile_id}' was not found.", {"profile_id": profile_id})
        self.profile_id = profile_id


class RunNotFoundError(VerificationPlannerError):
    """Raised when an evidence run does not exist."""

    def __init__(self, run_id: str) -> None:
        super().__init__(f"Evidence run '{run_id}' was not found.", {"run_id": run_id})
        self.run_id = run_id


class IncompatibleResultError(VerificationPlannerError):
    """Raised when an imported result is incompatible with baseline or profile."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details or {})


class CampaignRevisionConflictError(VerificationPlannerError):
    """Raised when base_campaign_revision does not match current campaign revision."""

    def __init__(
        self,
        campaign_id: str,
        base_revision: int,
        current_revision: int,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            f"Campaign conflict for '{campaign_id}': expected revision {base_revision}, current is {current_revision}.",
            {
                "campaign_id": campaign_id,
                "base_revision": base_revision,
                "current_revision": current_revision,
                "request_id": request_id,
            },
        )
        self.campaign_id = campaign_id
        self.base_revision = base_revision
        self.current_revision = current_revision
        self.request_id = request_id


class CampaignFrozenError(VerificationPlannerError):
    """Raised when attempting to mutate a frozen campaign."""

    def __init__(self, campaign_id: str) -> None:
        super().__init__(
            f"Campaign '{campaign_id}' is frozen and cannot be modified.",
            {"campaign_id": campaign_id},
        )
        self.campaign_id = campaign_id


class ImportValidationError(VerificationPlannerError):
    """Raised when result import payload validation fails."""

    def __init__(self, message: str, diagnostics: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message, {"diagnostics": diagnostics or []})
        self.diagnostics = diagnostics or []

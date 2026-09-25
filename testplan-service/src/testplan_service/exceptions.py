"""Domain-specific precise exceptions for Testplan Service."""

from __future__ import annotations

from typing import Any


class TestPlanError(Exception):
    """Base exception for all Testplan Service domain failures."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TestPlanNotFoundError(TestPlanError):
    """Raised when a requested testplan document does not exist."""

    def __init__(self, plan_id: str) -> None:
        super().__init__(f"Testplan '{plan_id}' was not found.", {"plan_id": plan_id})
        self.plan_id = plan_id


class TestPlanAlreadyExistsError(TestPlanError):
    """Raised when attempting to create a testplan with an existing identifier."""

    def __init__(self, plan_id: str) -> None:
        super().__init__(f"Testplan '{plan_id}' already exists.", {"plan_id": plan_id})
        self.plan_id = plan_id


class NodeNotFoundError(TestPlanError):
    """Raised when a requested node is not present in the testplan hierarchy."""

    def __init__(self, plan_id: str, node_id: str) -> None:
        super().__init__(
            f"Node '{node_id}' was not found in testplan '{plan_id}'.",
            {"plan_id": plan_id, "node_id": node_id},
        )
        self.plan_id = plan_id
        self.node_id = node_id


class DuplicateNodeError(TestPlanError):
    """Raised when attempting to add a node with an identifier that already exists in the plan."""

    def __init__(self, plan_id: str, node_id: str) -> None:
        super().__init__(
            f"Node '{node_id}' already exists in testplan '{plan_id}'.",
            {"plan_id": plan_id, "node_id": node_id},
        )
        self.plan_id = plan_id
        self.node_id = node_id


class CycleDetectedError(TestPlanError):
    """Raised when a tree modification would produce a cycle in the hierarchy."""

    def __init__(self, node_id: str, target_parent_id: str) -> None:
        super().__init__(
            f"Moving node '{node_id}' under '{target_parent_id}' would create a cycle.",
            {"node_id": node_id, "target_parent_id": target_parent_id},
        )
        self.node_id = node_id
        self.target_parent_id = target_parent_id


class MaxDepthExceededError(TestPlanError):
    """Raised when an operation would exceed the maximum permitted tree depth."""

    def __init__(self, node_id: str, depth: int, max_depth: int) -> None:
        super().__init__(
            f"Node '{node_id}' at depth {depth} exceeds maximum tree depth of {max_depth}.",
            {"node_id": node_id, "depth": depth, "max_depth": max_depth},
        )
        self.node_id = node_id
        self.depth = depth
        self.max_depth = max_depth


class InvalidOperationError(TestPlanError):
    """Raised when an invalid operation is attempted on a testplan or node."""

    def __init__(self, message: str, operation: str, details: dict[str, Any] | None = None) -> None:
        merged_details = {"operation": operation}
        if details:
            merged_details.update(details)
        super().__init__(message, merged_details)
        self.operation = operation


class ProposalValidationError(TestPlanError):
    """Raised when an AI Assistant proposal contains invalid or conflicting actions."""

    def __init__(self, message: str, errors: list[str]) -> None:
        super().__init__(message, {"errors": errors})
        self.errors = errors


class StorageError(TestPlanError):
    """Raised when a persistence or serialization error occurs."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message, {"cause": str(cause) if cause else None})
        self.cause = cause

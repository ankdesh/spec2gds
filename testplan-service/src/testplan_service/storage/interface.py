"""Interface specification for testplan document repositories."""

from __future__ import annotations

from abc import ABC, abstractmethod

from testplan_service.models.testplan import TestPlanDocument


class TestPlanRepository(ABC):
    """Abstract persistence interface for managing testplan documents."""

    @abstractmethod
    def get(self, plan_id: str) -> TestPlanDocument | None:
        """Retrieve a testplan document by ID, or None if not found."""
        ...

    @abstractmethod
    def list_all(self) -> list[TestPlanDocument]:
        """List all stored testplan documents."""
        ...

    @abstractmethod
    def save(self, document: TestPlanDocument) -> None:
        """Persist or update a testplan document."""
        ...

    @abstractmethod
    def delete(self, plan_id: str) -> bool:
        """Delete a testplan document by ID. Returns True if removed, False if not found."""
        ...

    @abstractmethod
    def exists(self, plan_id: str) -> bool:
        """Check whether a testplan with the given identifier exists."""
        ...

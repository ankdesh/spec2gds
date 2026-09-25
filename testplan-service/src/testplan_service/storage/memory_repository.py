"""In-memory thread-safe implementation of TestPlanRepository."""

from __future__ import annotations

import threading

from testplan_service.models.testplan import TestPlanDocument
from testplan_service.storage.interface import TestPlanRepository


class MemoryTestPlanRepository(TestPlanRepository):
    """Stores testplan documents in memory with thread-safe locking."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._store: dict[str, TestPlanDocument] = {}

    def get(self, plan_id: str) -> TestPlanDocument | None:
        with self._lock:
            doc = self._store.get(plan_id)
            return doc.model_copy(deep=True) if doc is not None else None

    def list_all(self) -> list[TestPlanDocument]:
        with self._lock:
            return [doc.model_copy(deep=True) for doc in self._store.values()]

    def save(self, document: TestPlanDocument) -> None:
        with self._lock:
            self._store[document.id] = document.model_copy(deep=True)

    def delete(self, plan_id: str) -> bool:
        with self._lock:
            return self._store.pop(plan_id, None) is not None

    def exists(self, plan_id: str) -> bool:
        with self._lock:
            return plan_id in self._store

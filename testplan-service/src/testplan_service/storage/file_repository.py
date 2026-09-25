"""File-backed persistent implementation of TestPlanRepository."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from testplan_service.exceptions import StorageError
from testplan_service.models.testplan import TestPlanDocument
from testplan_service.storage.interface import TestPlanRepository


class FileTestPlanRepository(TestPlanRepository):
    """Stores testplan documents as JSON files on disk with atomic replacement."""

    def __init__(self, root_dir: Path | str) -> None:
        self._dir = Path(root_dir).resolve()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _file_path(self, plan_id: str) -> Path:
        safe_name = f"{plan_id}.json"
        return self._dir / safe_name

    def get(self, plan_id: str) -> TestPlanDocument | None:
        with self._lock:
            path = self._file_path(plan_id)
            if not path.is_file():
                return None
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return TestPlanDocument.model_validate(data)
            except Exception as exc:
                raise StorageError(f"Failed to read testplan from {path}: {exc}", cause=exc) from exc

    def list_all(self) -> list[TestPlanDocument]:
        with self._lock:
            documents: list[TestPlanDocument] = []
            for path in self._dir.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    documents.append(TestPlanDocument.model_validate(data))
                except Exception as exc:
                    raise StorageError(f"Failed to parse testplan file {path}: {exc}", cause=exc) from exc
            return documents

    def save(self, document: TestPlanDocument) -> None:
        with self._lock:
            path = self._file_path(document.id)
            serialized = json.dumps(document.model_dump(), indent=2)
            try:
                with tempfile.NamedTemporaryFile(
                    "w",
                    dir=self._dir,
                    delete=False,
                    encoding="utf-8",
                ) as tmp:
                    tmp.write(serialized)
                    tmp_path = Path(tmp.name)
                os.replace(tmp_path, path)
            except Exception as exc:
                raise StorageError(f"Failed to save testplan to {path}: {exc}", cause=exc) from exc

    def delete(self, plan_id: str) -> bool:
        with self._lock:
            path = self._file_path(plan_id)
            if path.is_file():
                path.unlink()
                return True
            return False

    def exists(self, plan_id: str) -> bool:
        with self._lock:
            return self._file_path(plan_id).is_file()

"""Direct tests for storage repositories."""

from __future__ import annotations

from pathlib import Path

from testplan_service.models.testplan import TestPlanDocument
from testplan_service.storage.file_repository import FileTestPlanRepository
from testplan_service.storage.memory_repository import MemoryTestPlanRepository


def test_memory_repository() -> None:
    repo = MemoryTestPlanRepository()
    doc = TestPlanDocument(id="m1", name="Memory Plan")
    repo.save(doc)

    assert repo.exists("m1") is True
    assert repo.exists("m2") is False

    retrieved = repo.get("m1")
    assert retrieved is not None
    assert retrieved.name == "Memory Plan"

    all_docs = repo.list_all()
    assert len(all_docs) == 1

    deleted = repo.delete("m1")
    assert deleted is True
    assert repo.get("m1") is None


def test_file_repository(tmp_path: Path) -> None:
    repo = FileTestPlanRepository(tmp_path)
    doc = TestPlanDocument(id="f1", name="File Plan", target_design="top")
    repo.save(doc)

    assert repo.exists("f1") is True
    assert (tmp_path / "f1.json").is_file()

    loaded = repo.get("f1")
    assert loaded is not None
    assert loaded.name == "File Plan"
    assert loaded.target_design == "top"

    all_docs = repo.list_all()
    assert len(all_docs) == 1

    deleted = repo.delete("f1")
    assert deleted is True
    assert not (tmp_path / "f1.json").is_file()
    assert repo.get("f1") is None

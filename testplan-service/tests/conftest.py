"""Pytest fixtures for Verification Planner."""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from testplan_service.api.app import create_app
from testplan_service.fixtures.fifo_snapshot import get_fifo_snapshot_bytes
from testplan_service.fixtures.two_fifo_snapshot import get_two_fifo_snapshot_bytes


@pytest.fixture
def storage_dir(tmp_path: Path) -> Path:
    """Provide clean isolated storage directory for tests."""
    path = tmp_path / "verification_data"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def client(storage_dir: Path) -> TestClient:
    """Provide a TestClient connected to an isolated Verification Planner instance."""
    app = create_app(storage_dir=storage_dir)
    return TestClient(app)


@pytest.fixture
def fifo_bytes() -> bytes:
    """Provide deterministic bytes for Synchronous FIFO Activity Snapshot."""
    return get_fifo_snapshot_bytes()


@pytest.fixture
def two_fifo_bytes() -> bytes:
    """Provide deterministic bytes for Two-FIFO design Activity Snapshot."""
    return get_two_fifo_snapshot_bytes()

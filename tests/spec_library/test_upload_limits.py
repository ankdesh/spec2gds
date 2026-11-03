"""Unit tests for upload streaming bounds, zip safety, and zip bomb rejection."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
import pytest

from spec2gds.library_service.storage import (
    MAX_COMPRESSED_BYTES,
    MAX_MEMBER_BYTES,
    InvalidPackageError,
    LimitExceededError,
    LibraryStorage,
)


@pytest.fixture
def storage(tmp_path: Path) -> LibraryStorage:
    lib_root = tmp_path / "spec_library"
    lib_root.mkdir()
    return LibraryStorage(library_root=lib_root)


def test_compressed_size_limit(storage: LibraryStorage) -> None:
    oversized_bytes = b"0" * (MAX_COMPRESSED_BYTES + 10)
    with pytest.raises(LimitExceededError) as exc_info:
        storage.validate_archive_bytes(oversized_bytes)
    assert "Compressed archive size" in str(exc_info.value)


def test_member_uncompressed_limit(storage: LibraryStorage) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("huge.txt", b"A" * (MAX_MEMBER_BYTES + 100))
    raw = buf.getvalue()

    with pytest.raises(LimitExceededError) as exc_info:
        storage.validate_archive_bytes(raw)
    assert "uncompressed size" in str(exc_info.value)


def test_member_count_limit(storage: LibraryStorage) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        for i in range(1025):
            zf.writestr(f"file_{i}.txt", b"x")
    raw = buf.getvalue()

    with pytest.raises(LimitExceededError) as exc_info:
        storage.validate_archive_bytes(raw)
    assert "member count" in str(exc_info.value)


def test_zip_bomb_ratio_limit(storage: LibraryStorage) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1MB of zeros compresses to ~1000 bytes (ratio > 1000:1)
        zf.writestr("bomb.txt", b"\x00" * (1024 * 1024))
    raw = buf.getvalue()

    with pytest.raises(LimitExceededError) as exc_info:
        storage.validate_archive_bytes(raw)
    assert "compression ratio" in str(exc_info.value)


def test_path_traversal_rejected(storage: LibraryStorage) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../escaped.txt", b"bad")
    raw = buf.getvalue()

    with pytest.raises(InvalidPackageError) as exc_info:
        storage.validate_archive_bytes(raw)
    assert "Path traversal" in str(exc_info.value)


def test_backslash_path_rejected(storage: LibraryStorage) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("subdir\\file.txt", b"bad")
    raw = buf.getvalue()

    with pytest.raises(InvalidPackageError) as exc_info:
        storage.validate_archive_bytes(raw)
    assert "backslash" in str(exc_info.value)


def test_absolute_path_rejected(storage: LibraryStorage) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("/etc/passwd", b"bad")
    raw = buf.getvalue()

    with pytest.raises(InvalidPackageError) as exc_info:
        storage.validate_archive_bytes(raw)
    assert "Absolute" in str(exc_info.value)

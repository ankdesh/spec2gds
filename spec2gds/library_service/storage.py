"""Durable filesystem storage, streaming bounds enforcement, and path isolation."""

from __future__ import annotations

import io
import os
import shutil
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.models import EntityRef
from spec2gds.spec_library.schemas import (
    CatalogueAssetV1,
    EvidenceRecordV1,
    compute_sha256,
    get_package_asset,
)

# Upload streaming and security limits
MAX_COMPRESSED_BYTES: int = 8 * 1024 * 1024  # 8 MiB
MAX_UNCOMPRESSED_BYTES: int = 64 * 1024 * 1024  # 64 MiB
MAX_MEMBER_BYTES: int = 4 * 1024 * 1024  # 4 MiB
MAX_MEMBERS: int = 1024
MAX_COMPRESSION_RATIO: int = 100
MAX_EVIDENCE_BYTES: int = 1 * 1024 * 1024  # 1 MiB


class StorageError(Exception):
    """Base storage exception."""

    def __init__(self, code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class LimitExceededError(StorageError):
    """Payload or archive member exceeded defined streaming limits."""

    def __init__(self, message: str, details: Any = None) -> None:
        super().__init__("LIMIT_EXCEEDED", message, details)


class ImmutableConflictError(StorageError):
    """Attempted to overwrite an immutable released version with differing content."""

    def __init__(self, message: str, details: Any = None) -> None:
        super().__init__("IMMUTABLE_CONFLICT", message, details)


class StoragePathError(StorageError):
    """Path traversal, symlink traversal, or outside configured root."""

    def __init__(self, message: str, details: Any = None) -> None:
        super().__init__("PATH_ERROR", message, details)


class InvalidPackageError(StorageError):
    """Package archive or contents failed strict structural validation."""

    def __init__(self, message: str, details: Any = None) -> None:
        super().__init__("INVALID_PACKAGE", message, details)


class LibraryStorage:
    """Manages filesystem storage, upload boundaries, and package isolation."""

    def __init__(self, library_root: Path, staging_root: Path | None = None) -> None:
        self.library_root = library_root.resolve()
        self.staging_root = (staging_root or (self.library_root / "TEMP_uploads")).resolve()
        self.staging_root.mkdir(parents=True, exist_ok=True)

    def is_root_readable(self) -> bool:
        """Check if library root exists and is accessible."""
        return self.library_root.exists() and os.access(self.library_root, os.R_OK)

    def validate_archive_bytes(
        self, raw_bytes: bytes
    ) -> tuple[SpecPackage, CatalogueAssetV1, str, int]:
        """Strictly validate uploaded zip stream bounds, zip safety, and package integrity."""
        compressed_len = len(raw_bytes)
        if compressed_len > MAX_COMPRESSED_BYTES:
            raise LimitExceededError(
                f"Compressed archive size {compressed_len} exceeds limit of {MAX_COMPRESSED_BYTES} bytes."
            )

        try:
            zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
        except Exception as e:
            raise InvalidPackageError(f"Malformed ZIP archive: {e}")

        infolist = zf.infolist()
        if len(infolist) > MAX_MEMBERS:
            raise LimitExceededError(
                f"Archive member count {len(infolist)} exceeds limit of {MAX_MEMBERS} members."
            )

        seen_names: set[str] = set()
        total_uncompressed = 0

        for info in infolist:
            name = info.filename
            if name in seen_names:
                raise InvalidPackageError(f"Duplicate archive member name: {name!r}")
            seen_names.add(name)

            # Security checks: encrypted, symlinks, path safety
            if info.flag_bits & 0x1:
                raise InvalidPackageError(f"Encrypted ZIP entry not permitted: {name!r}")

            # Unix symlink check
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise InvalidPackageError(f"Symlinks not permitted in package: {name!r}")

            if name.startswith(("/", "\\")) or "\\" in name:
                raise InvalidPackageError(f"Absolute or backslash path not permitted: {name!r}")

            parts = Path(name).parts
            if ".." in parts:
                raise InvalidPackageError(f"Path traversal not permitted: {name!r}")

            # Member size & compression ratio checks
            if info.file_size > MAX_MEMBER_BYTES:
                raise LimitExceededError(
                    f"Member {name!r} uncompressed size {info.file_size} exceeds {MAX_MEMBER_BYTES} bytes."
                )

            total_uncompressed += info.file_size
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise LimitExceededError(
                    f"Total uncompressed archive size {total_uncompressed} exceeds {MAX_UNCOMPRESSED_BYTES} bytes."
                )

            if info.compress_size > 0 and info.file_size > 0:
                ratio = info.file_size / info.compress_size
                if ratio > MAX_COMPRESSION_RATIO:
                    raise LimitExceededError(
                        f"Member {name!r} compression ratio {ratio:.1f} exceeds {MAX_COMPRESSION_RATIO}:1 limit."
                    )

        # Load package strictly
        try:
            pkg = SpecPackage.from_bytes(raw_bytes)
        except Exception as e:
            raise InvalidPackageError(f"Spec package failed strict load: {e}")

        # Root entity check
        rev = SpecRevision.from_package(pkg)
        if len(rev.components) != 1:
            raise InvalidPackageError(f"Expected exactly 1 root hardware component, found {len(rev.components)}")

        root_comp = rev.components[0]
        if not root_comp.vlnv:
            raise InvalidPackageError(f"Root component {root_comp.ref} has no VLNV assigned")

        # Catalogue asset check
        cat_asset_bytes = get_package_asset(pkg, "library_catalogue_v1")
        if not cat_asset_bytes:
            raise InvalidPackageError("Missing required 'library_catalogue_v1' catalogue asset")

        try:
            cat_asset = CatalogueAssetV1.model_validate_json(cat_asset_bytes.decode("utf-8"))
        except Exception as e:
            raise InvalidPackageError(f"Catalogue asset metadata failed validation: {e}")

        # Check asset ID and version match VLNV
        expected_vlnv = f"spec2gds.local:{cat_asset.category}:{cat_asset.id}:{cat_asset.version}"
        if root_comp.vlnv != expected_vlnv:
            raise InvalidPackageError(
                f"VLNV mismatch: component has {root_comp.vlnv!r}, catalogue has {expected_vlnv!r}"
            )

        pkg_sha = compute_sha256(raw_bytes)
        return pkg, cat_asset, pkg_sha, compressed_len

    def _resolve_safe_path(self, *parts: str) -> Path:
        """Resolve destination path and ensure it stays inside library root without symlink escalation."""
        target = self.library_root.joinpath(*parts)
        try:
            resolved_target = target.resolve()
            resolved_root = self.library_root.resolve()
            resolved_target.relative_to(resolved_root)
        except (ValueError, RuntimeError):
            raise StoragePathError(f"Path escapes library root: {target}")

        # Ensure no ancestor in target path is a symlink
        curr = target
        while curr != self.library_root and curr != curr.parent:
            if curr.is_symlink():
                raise StoragePathError(f"Symlink ancestor not permitted: {curr}")
            curr = curr.parent

        return target

    def publish_package(
        self, raw_bytes: bytes, cat_asset: CatalogueAssetV1
    ) -> tuple[bool, Path, str]:
        """Atomically store package bytes under canonical path. Returns (is_created, target_path, pkg_sha)."""
        target_dir = self._resolve_safe_path(cat_asset.category, cat_asset.id, cat_asset.version)
        target_file = target_dir / f"{cat_asset.id}.spec"
        pkg_sha = compute_sha256(raw_bytes)

        if target_file.exists():
            existing_bytes = target_file.read_bytes()
            existing_sha = compute_sha256(existing_bytes)
            if existing_sha == pkg_sha:
                # 200 Identical retry
                return False, target_file, pkg_sha
            # 409 Conflict: different bytes for immutable version
            raise ImmutableConflictError(
                f"Version {cat_asset.version} of component {cat_asset.id} already exists with differing digest {existing_sha}."
            )

        # Stage and atomic fsync publish
        target_dir.mkdir(parents=True, exist_ok=True)
        stage_file = self.staging_root / f"upload_{uuid.uuid4().hex}.tmp"
        try:
            with open(stage_file, "wb") as f:
                f.write(raw_bytes)
                f.flush()
                os.fsync(f.fileno())

            # Atomic move into position
            shutil.move(stage_file, target_file)
        finally:
            if stage_file.exists():
                stage_file.unlink()

        return True, target_file, pkg_sha

    def store_evidence(
        self,
        category: str,
        comp_id: str,
        version: str,
        ev_bytes: bytes,
    ) -> tuple[bool, str, str]:
        """Store evidence JSON for a component version. Returns (is_created, ev_sha, received_at)."""
        if len(ev_bytes) > MAX_EVIDENCE_BYTES:
            raise LimitExceededError(f"Evidence size {len(ev_bytes)} exceeds limit of {MAX_EVIDENCE_BYTES} bytes.")

        try:
            ev_data = EvidenceRecordV1.model_validate_json(ev_bytes.decode("utf-8"))
        except Exception as e:
            raise InvalidPackageError(f"Evidence record validation failed: {e}")

        # Check target package exists and matches package_sha256
        target_spec = self._resolve_safe_path(category, comp_id, version, f"{comp_id}.spec")
        if not target_spec.is_file():
            raise StoragePathError(f"Target package does not exist for evidence: {target_spec}")

        spec_bytes = target_spec.read_bytes()
        actual_pkg_sha = compute_sha256(spec_bytes)
        if ev_data.package_sha256 != actual_pkg_sha:
            raise InvalidPackageError(
                f"Evidence package_sha256 {ev_data.package_sha256} does not match stored package {actual_pkg_sha}"
            )

        ev_sha = compute_sha256(ev_bytes)
        ev_hex = ev_sha.split(":")[1]

        ev_dir = self._resolve_safe_path(category, comp_id, version, "evidence")
        ev_dir.mkdir(parents=True, exist_ok=True)
        ev_file = ev_dir / f"{ev_hex}.json"

        now_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        if ev_file.exists():
            # Already exists: read original receipt timestamp or modification time
            mtime = os.path.getmtime(ev_file)
            existing_time = datetime.fromtimestamp(mtime, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            return False, ev_sha, existing_time

        stage_file = self.staging_root / f"ev_{uuid.uuid4().hex}.tmp"
        try:
            with open(stage_file, "wb") as f:
                f.write(ev_bytes)
                f.flush()
                os.fsync(f.fileno())
            shutil.move(stage_file, ev_file)
        finally:
            if stage_file.exists():
                stage_file.unlink()

        return True, ev_sha, now_str

    def get_package_bytes(self, category: str, comp_id: str, version: str) -> tuple[bytes, str] | None:
        """Read exact stored package bytes and digest."""
        target_file = self._resolve_safe_path(category, comp_id, version, f"{comp_id}.spec")
        if not target_file.is_file():
            return None
        data = target_file.read_bytes()
        sha = compute_sha256(data)
        return data, sha

"""Immutable content-addressed SHA-256 blob storage.

Reviewer path: hash bytes, stage locally and replace the content-addressed
file before recording references. Paths use one hash-prefix level; content
identity does not by itself authenticate an external producer or prove evidence.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import uuid


class BlobStore:
    """Content-addressed file store with atomic staging and verification."""

    def __init__(self, root_dir: Path | str) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.blobs_dir = self.root_dir / "blobs"
        self.staging_dir = self.root_dir / "staging"
        self.blobs_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def stage_bytes(self, data: bytes) -> str:
        """Stage raw bytes into staging directory and return staging handle ID."""
        staging_id = str(uuid.uuid4())
        staging_file = self.staging_dir / f"{staging_id}.tmp"
        staging_file.write_bytes(data)
        return staging_id

    def commit_staged(self, staging_id: str, expected_hash: str | None = None) -> str:
        """Verify digest, commit from staging to permanent content-addressed store."""
        staging_file = self.staging_dir / f"{staging_id}.tmp"
        if not staging_file.is_file():
            raise FileNotFoundError(f"Staged blob file '{staging_id}' not found.")

        data = staging_file.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        full_hash = f"sha256:{digest}" if not digest.startswith("sha256:") else digest

        if expected_hash and expected_hash != full_hash and expected_hash != digest:
            staging_file.unlink(missing_ok=True)
            raise ValueError(f"Staged blob hash '{full_hash}' does not match expected '{expected_hash}'.")

        dest_dir = self.blobs_dir / digest[:2]
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / digest
        if not dest_file.exists():
            dest_file.write_bytes(data)

        staging_file.unlink(missing_ok=True)
        return full_hash

    def put_bytes(self, data: bytes) -> str:
        """Atomically stage and commit bytes, returning sha256: hash."""
        staging_id = self.stage_bytes(data)
        return self.commit_staged(staging_id)

    def get_bytes(self, blob_hash: str) -> bytes:
        """Retrieve stored bytes for a given SHA-256 hash."""
        clean_hash = blob_hash.removeprefix("sha256:")
        dest_file = self.blobs_dir / clean_hash[:2] / clean_hash
        if not dest_file.is_file():
            raise FileNotFoundError(f"Blob with hash '{blob_hash}' not found.")
        return dest_file.read_bytes()

    def has_blob(self, blob_hash: str) -> bool:
        """Check if blob exists in store."""
        clean_hash = blob_hash.removeprefix("sha256:")
        dest_file = self.blobs_dir / clean_hash[:2] / clean_hash
        return dest_file.is_file()

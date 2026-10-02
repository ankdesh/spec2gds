"""Local sandbox for deterministic, managed Activity directory outputs.

Reviewer path: validate safe relative output and prior generator ownership
before staging a complete tree. Replacement/rollback protects other files;
workspace publication grants no mutation capability over the source package.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import typing
from pathlib import Path

from spec2gds.agent_spec.activities.contracts import PublishedDirectory, WorkspaceFile
from spec2gds.agent_spec.spec_format.models import sha256_digest, validate_safe_path

_OWNERSHIP_MANIFEST = "generation-manifest.json"


class LocalActivityWorkspace:
    """Publish complete generated trees beneath one caller-owned root."""

    def __init__(self, root: str | Path) -> None:
        candidate = Path(root)
        if candidate.exists() and candidate.is_symlink():
            raise ValueError("Activity workspace root must not be a symbolic link.")
        candidate.mkdir(parents=True, exist_ok=True)
        if not candidate.is_dir():
            raise NotADirectoryError(candidate)
        self._root = candidate.resolve()

    @property
    def root(self) -> Path:
        """Return the host-selected root for diagnostics and direct callers."""
        return self._root

    def replace_directory(
        self,
        *,
        relative_path: str,
        files: typing.Mapping[str, bytes],
        generator_id: str,
        document_id: str,
        design_id: str,
    ) -> PublishedDirectory:
        """Atomically replace an absent or generator-owned directory."""
        relative_path = validate_safe_path(relative_path)
        normalized = {
            validate_safe_path(path): bytes(content)
            for path, content in files.items()
        }
        if not normalized:
            raise ValueError("Generated workspace directory must contain at least one file.")
        self._validate_manifest(normalized, generator_id, document_id, design_id)

        target = self._root.joinpath(*relative_path.split("/"))
        self._assert_contained(target)
        self._assert_safe_existing_ancestors(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._validate_existing_target(target, generator_id, document_id, design_id)

        stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.stage-", dir=target.parent))
        backup: Path | None = None
        try:
            for path, content in sorted(normalized.items()):
                destination = stage.joinpath(*path.split("/"))
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
            if target.exists():
                backup = Path(tempfile.mkdtemp(prefix=f".{target.name}.backup-", dir=target.parent))
                backup.rmdir()
                os.replace(target, backup)
            try:
                os.replace(stage, target)
            except Exception:
                if backup is not None and backup.exists() and not target.exists():
                    os.replace(backup, target)
                    backup = None
                raise
            if backup is not None:
                shutil.rmtree(backup)
                backup = None
        finally:
            if stage.exists():
                shutil.rmtree(stage)
            if backup is not None and backup.exists():
                if not target.exists():
                    os.replace(backup, target)
                else:
                    shutil.rmtree(backup)

        records = tuple(
            WorkspaceFile(path=path, sha256=sha256_digest(content), size=len(content))
            for path, content in sorted(normalized.items())
        )
        tree_bytes = json.dumps(
            [item.model_dump(mode="json") for item in records],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return PublishedDirectory(
            relative_path=relative_path,
            tree_sha256=sha256_digest(tree_bytes),
            files=records,
        )

    def _assert_contained(self, target: Path) -> None:
        try:
            target.resolve(strict=False).relative_to(self._root)
        except ValueError as exc:
            raise ValueError("Generated directory escapes the Activity workspace root.") from exc

    def _assert_safe_existing_ancestors(self, target: Path) -> None:
        current = target
        while current != self._root:
            if current.exists() and current.is_symlink():
                raise ValueError("Generated directory path contains a symbolic link.")
            current = current.parent

    @staticmethod
    def _validate_manifest(
        files: dict[str, bytes],
        generator_id: str,
        document_id: str,
        design_id: str,
    ) -> None:
        data = files.get(_OWNERSHIP_MANIFEST)
        if data is None:
            raise ValueError(f"Generated directory requires {_OWNERSHIP_MANIFEST}.")
        try:
            manifest = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Generated ownership manifest is invalid JSON.") from exc
        if not isinstance(manifest, dict):
            raise ValueError("Generated ownership manifest must be a JSON object.")
        if manifest.get("schema_version") == "spec2gds.rtl-generation.v3":
            target_ref = manifest.get("target", {})
            if not isinstance(target_ref, dict) or target_ref.get("document_id") != document_id:
                raise ValueError("Generated manifest target does not match its document.")
            manifest = {**manifest, "design_id": target_ref.get("entity_id")}
        expected = {
            "generator_id": generator_id,
            "document_id": document_id,
            "design_id": design_id,
        }
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise ValueError("Generated ownership manifest does not match its destination.")

    @classmethod
    def _validate_existing_target(
        cls,
        target: Path,
        generator_id: str,
        document_id: str,
        design_id: str,
    ) -> None:
        if not target.exists():
            return
        if target.is_symlink() or not target.is_dir():
            raise ValueError("Refusing to replace a non-directory or symbolic-link target.")
        if any(item.is_symlink() for item in target.rglob("*")):
            raise ValueError("Refusing to replace a generated directory containing symbolic links.")
        manifest_path = target / _OWNERSHIP_MANIFEST
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise ValueError("Refusing to replace an unmanaged generated directory.")
        try:
            manifest = json.loads(manifest_path.read_bytes())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Refusing to replace a directory with an invalid ownership manifest.") from exc
        if not isinstance(manifest, dict):
            raise ValueError("Refusing to replace a directory with an invalid ownership manifest.")
        if manifest.get("schema_version") == "spec2gds.rtl-generation.v3":
            target_ref = manifest.get("target", {})
            if not isinstance(target_ref, dict) or target_ref.get("document_id") != document_id:
                raise ValueError("Generated manifest target does not match its document.")
            manifest = {**manifest, "design_id": target_ref.get("entity_id")}
        expected = {
            "generator_id": generator_id,
            "document_id": document_id,
            "design_id": design_id,
        }
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise ValueError("Refusing to replace a directory owned by another generation target.")

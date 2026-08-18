"""Deterministic, portable full-source snapshots for Activity execution."""

from __future__ import annotations

import io
import json
import typing
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pydantic

from spec2gds.agent_spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.models import (
    SHA256_PATTERN,
    EntityRef,
    StrictModel,
    sha256_digest,
)

ACTIVITY_SNAPSHOT_MIMETYPE = "application/vnd.spec2gds.activity-snapshot.v1+zip"
ACTIVITY_SNAPSHOT_SCHEMA = "spec2gds.activity-snapshot.v1"
_FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)
_SOURCE_PATH = "source/source.spec"
_SNAPSHOT_PATH = "snapshot.json"


class SnapshotSource(StrictModel):
    """Identity and integrity metadata for the embedded source package."""

    document_id: str
    source_revision_hash: str
    package_path: str = _SOURCE_PATH
    package_sha256: str

    @pydantic.field_validator("source_revision_hash", "package_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("Snapshot source hashes must use canonical SHA-256 syntax.")
        return value

    @pydantic.field_validator("package_path")
    @classmethod
    def _package_path(cls, value: str) -> str:
        if value != _SOURCE_PATH:
            raise ValueError(f"Activity snapshot source must be stored at {_SOURCE_PATH}.")
        return value


class SnapshotScope(StrictModel):
    """Document-wide or entity-targeted invocation scope."""

    kind: typing.Literal["document", "entity"]
    target: EntityRef | None = None

    def model_post_init(self, _: object) -> None:
        """Reject a target whose document identity differs from the snapshot."""
        if self.kind not in {"document", "entity"}:
            raise ValueError("Snapshot scope kind must be document or entity.")
        if (self.kind == "entity") != (self.target is not None):
            raise ValueError("Entity snapshot scope requires exactly one target.")


class ActivitySnapshotManifest(StrictModel):
    """Versioned manifest stored at the root of an Activity snapshot."""

    schema_version: str = ACTIVITY_SNAPSHOT_SCHEMA
    snapshot_id: str
    source: SnapshotSource
    scope: SnapshotScope
    dependency_closure: tuple[EntityRef, ...] = ()

    def model_post_init(self, _: object) -> None:
        """Cross-check manifest identity, scope, and source revision metadata."""
        if self.schema_version != ACTIVITY_SNAPSHOT_SCHEMA:
            raise ValueError("Unsupported Activity snapshot schema version.")
        if not SHA256_PATTERN.fullmatch(self.snapshot_id):
            raise ValueError("Activity snapshot_id must be a canonical SHA-256 digest.")


@dataclass(frozen=True)
class ActivitySnapshot:
    """Validated snapshot manifest, full source bytes, and immutable SpecRevision."""

    manifest: ActivitySnapshotManifest
    source_package: bytes
    revision: SpecRevision

    @classmethod
    def create(
        cls,
        revision: SpecRevision,
        target: EntityRef | None = None,
    ) -> "ActivitySnapshot":
        """Capture one complete source-only revision with optional entity scope."""
        if target is not None:
            revision.resolve(target)
        package = revision.to_package()
        package.files = {
            path: bytes(data)
            for path, data in package.files.items()
            if not path.startswith("activity/")
        }
        source_revision = SpecRevision.from_package(package)
        source_package = package.to_bytes()
        source = SnapshotSource(
            document_id=source_revision.document_id,
            source_revision_hash=source_revision.source_revision_hash,
            package_sha256=sha256_digest(source_package),
        )
        scope = SnapshotScope(kind="entity" if target else "document", target=target)
        closure = _closure(source_revision, target)
        identity = {
            "schema_version": ACTIVITY_SNAPSHOT_SCHEMA,
            "source": source.model_dump(mode="json"),
            "scope": scope.model_dump(mode="json"),
            "dependency_closure": [item.model_dump(mode="json") for item in closure],
        }
        manifest = ActivitySnapshotManifest(
            snapshot_id=sha256_digest(_canonical_json(identity)),
            source=source,
            scope=scope,
            dependency_closure=closure,
        )
        return cls(manifest=manifest, source_package=source_package, revision=source_revision)

    @classmethod
    def from_bytes(cls, data: bytes) -> "ActivitySnapshot":
        """Load and fully verify a serialized Activity snapshot."""
        try:
            with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
                names = archive.namelist()
                expected = ["mimetype", _SNAPSHOT_PATH, _SOURCE_PATH]
                if names != expected:
                    raise ValueError("Activity snapshot entries or ordering are invalid.")
                if archive.getinfo("mimetype").compress_type != zipfile.ZIP_STORED:
                    raise ValueError("Activity snapshot mimetype must be uncompressed.")
                if archive.read("mimetype") != ACTIVITY_SNAPSHOT_MIMETYPE.encode("ascii"):
                    raise ValueError("Unsupported Activity snapshot mimetype.")
                manifest = ActivitySnapshotManifest.model_validate_json(archive.read(_SNAPSHOT_PATH))
                source_package = archive.read(_SOURCE_PATH)
        except zipfile.BadZipFile as exc:
            raise ValueError(f"Invalid Activity snapshot ZIP: {exc}") from exc
        if sha256_digest(source_package) != manifest.source.package_sha256:
            raise ValueError("Activity snapshot source package hash does not match.")
        try:
            package = SpecPackage.from_bytes(source_package)
            revision = SpecRevision.from_package(package)
        except SpecValidationError as exc:
            raise ValueError(f"Activity snapshot contains invalid source: {exc}") from exc
        if any(path.startswith("activity/") for path in package.files):
            raise ValueError("Activity snapshot source package must not contain activity history.")
        if revision.document_id != manifest.source.document_id:
            raise ValueError("Activity snapshot document identity does not match source.")
        if revision.source_revision_hash != manifest.source.source_revision_hash:
            raise ValueError("Activity snapshot source revision hash does not match source.")
        target = manifest.scope.target
        if target is not None:
            revision.resolve(target)
        if _closure(revision, target) != manifest.dependency_closure:
            raise ValueError("Activity snapshot dependency closure does not match source.")
        expected_id = sha256_digest(
            _canonical_json(manifest.model_dump(mode="json", exclude={"snapshot_id"}))
        )
        if expected_id != manifest.snapshot_id:
            raise ValueError("Activity snapshot identity does not match its manifest.")
        return cls(manifest=manifest, source_package=source_package, revision=revision)

    @classmethod
    def read(cls, path: str | Path) -> "ActivitySnapshot":
        """Load a snapshot from one explicit filesystem path."""
        return cls.from_bytes(Path(path).read_bytes())

    @property
    def target(self) -> EntityRef | None:
        """Expose the optional entity target recorded by the snapshot scope."""
        return self.manifest.scope.target

    def to_bytes(self) -> bytes:
        """Serialize this validated snapshot with deterministic ZIP metadata."""
        entries = {
            "mimetype": ACTIVITY_SNAPSHOT_MIMETYPE.encode("ascii"),
            _SNAPSHOT_PATH: _pretty_json(self.manifest.model_dump(mode="json")),
            _SOURCE_PATH: self.source_package,
        }
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr(_zip_info("mimetype", zipfile.ZIP_STORED), entries["mimetype"])
            archive.writestr(_zip_info(_SNAPSHOT_PATH, zipfile.ZIP_DEFLATED), entries[_SNAPSHOT_PATH])
            archive.writestr(_zip_info(_SOURCE_PATH, zipfile.ZIP_DEFLATED), entries[_SOURCE_PATH])
        return output.getvalue()

    def write(self, path: str | Path) -> Path:
        """Write deterministic snapshot bytes to one explicit path."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.to_bytes())
        return destination


def _closure(revision: SpecRevision, target: EntityRef | None) -> tuple[EntityRef, ...]:
    if target is None:
        return ()
    if target.entity_kind in {"component", "design"}:
        return revision.dependency_closure(target)
    return (target,)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _pretty_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _zip_info(path: str, compression: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=_FIXED_ZIP_DATE)
    info.compress_type = compression
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info

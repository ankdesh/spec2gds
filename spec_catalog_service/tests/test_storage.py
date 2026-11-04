"""Unit tests for LibraryStorage filesystem management, conflict handling, and path isolation."""

from __future__ import annotations

from pathlib import Path

import pytest
from spec_catalog_service.catalog.authoring import build_component_spec
from spec_catalog_service.catalog.components.phase1 import MUX_DEF
from spec_catalog_service.catalog.schemas import (
    CheckRecord,
    EvidenceRecordV1,
    serialize_canonical_evidence_bytes,
)
from spec_catalog_service.http.storage import (
    ImmutableConflictError,
    InvalidPackageError,
    LibraryStorage,
)

from spec2gds.spec.spec_format.ir import SpecRevision


@pytest.fixture
def storage_env(tmp_path: Path) -> LibraryStorage:
    lib_root = tmp_path / "spec_library"
    lib_root.mkdir()
    return LibraryStorage(library_root=lib_root)


def test_publish_and_identical_retry(storage_env: LibraryStorage) -> None:
    pkg = build_component_spec(MUX_DEF)
    raw_bytes = pkg.to_bytes()

    parsed_pkg, cat_asset, pkg_sha, pkg_size = storage_env.validate_archive_bytes(raw_bytes)
    assert cat_asset.id == "mux"

    # First publication: created = True
    created, target_path, actual_sha = storage_env.publish_package(raw_bytes, cat_asset)
    assert created is True
    assert target_path.is_file()
    assert actual_sha == pkg_sha

    # Identical retry: created = False, same path and sha
    created_retry, target_retry, retry_sha = storage_env.publish_package(raw_bytes, cat_asset)
    assert created_retry is False
    assert target_retry == target_path
    assert retry_sha == actual_sha


def test_publish_immutable_conflict(storage_env: LibraryStorage) -> None:
    pkg = build_component_spec(MUX_DEF)
    raw_bytes = pkg.to_bytes()
    _, cat_asset, _, _ = storage_env.validate_archive_bytes(raw_bytes)

    # First publication
    storage_env.publish_package(raw_bytes, cat_asset)

    # Corrupt or modified bytes for same version
    modified_bytes = raw_bytes + b"\x00\x00"
    with pytest.raises(ImmutableConflictError):
        storage_env.publish_package(modified_bytes, cat_asset)


def test_evidence_storage_and_digest_validation(storage_env: LibraryStorage) -> None:
    pkg = build_component_spec(MUX_DEF)
    raw_bytes = pkg.to_bytes()
    _, cat_asset, pkg_sha, _ = storage_env.validate_archive_bytes(raw_bytes)
    storage_env.publish_package(raw_bytes, cat_asset)

    # Create evidence matching package_sha
    rev = SpecRevision.from_package(pkg)
    ev = EvidenceRecordV1(
        schema_version=1,
        package_sha256=pkg_sha,
        source_revision_hash=rev.source_revision_hash,
        root=rev.components[0].ref,
        runner_commit="0" * 40,
        tools={"python": "3.12.3"},
        presets=MUX_DEF.presets,
        checks=[CheckRecord(kind="package", preset=None, status="pass", seed=None, summary="ok")],
        limitations=[],
        created_at="2026-11-02T12:00:00Z",
    )
    ev_bytes = serialize_canonical_evidence_bytes(ev.model_dump(mode="json"))

    # Store evidence
    created, ev_sha, rec_time = storage_env.store_evidence(
        category=cat_asset.category,
        comp_id=cat_asset.id,
        version=cat_asset.version,
        ev_bytes=ev_bytes,
    )
    assert created is True
    assert ev_sha.startswith("sha256:")

    # Identical retry
    created2, ev_sha2, rec_time2 = storage_env.store_evidence(
        category=cat_asset.category,
        comp_id=cat_asset.id,
        version=cat_asset.version,
        ev_bytes=ev_bytes,
    )
    assert created2 is False
    assert ev_sha2 == ev_sha


def test_evidence_digest_mismatch_rejected(storage_env: LibraryStorage) -> None:
    pkg = build_component_spec(MUX_DEF)
    raw_bytes = pkg.to_bytes()
    _, cat_asset, _, _ = storage_env.validate_archive_bytes(raw_bytes)
    storage_env.publish_package(raw_bytes, cat_asset)

    # Evidence with mismatched package_sha
    rev = SpecRevision.from_package(pkg)
    ev = EvidenceRecordV1(
        schema_version=1,
        package_sha256="sha256:" + "f" * 64,
        source_revision_hash=rev.source_revision_hash,
        root=rev.components[0].ref,
        runner_commit="0" * 40,
        tools={"python": "3.12.3"},
        presets=MUX_DEF.presets,
        checks=[],
        limitations=[],
        created_at="2026-11-02T12:00:00Z",
    )
    ev_bytes = serialize_canonical_evidence_bytes(ev.model_dump(mode="json"))

    with pytest.raises(InvalidPackageError):
        storage_env.store_evidence(
            category=cat_asset.category,
            comp_id=cat_asset.id,
            version=cat_asset.version,
            ev_bytes=ev_bytes,
        )

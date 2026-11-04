"""Unit tests for SQLite catalogue indexing, queries, generation counter, and rebuilds."""

from __future__ import annotations

from pathlib import Path

import pytest
from spec_catalog_service.catalog.authoring import build_component_spec
from spec_catalog_service.catalog.components.phase1 import MUX_DEF
from spec_catalog_service.catalog.indexer import LibraryIndexer
from spec_catalog_service.catalog.schemas import (
    CatalogueAssetV1,
    CheckRecord,
    EvidenceRecordV1,
    compute_identity_key,
    get_package_asset,
    serialize_canonical_evidence_bytes,
)
from spec_catalog_service.http.index import CatalogueIndex

from spec2gds.spec.spec_format.ir import SpecRevision


@pytest.fixture
def index_env(tmp_path: Path) -> tuple[CatalogueIndex, Path]:
    lib_root = tmp_path / "spec_library"
    lib_root.mkdir()
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    idx = CatalogueIndex(db_path=state_dir / "catalogue.db", library_root=lib_root)
    return idx, lib_root


def test_generation_counter_and_recording(index_env: tuple[CatalogueIndex, Path]) -> None:
    idx, lib_root = index_env
    gen0 = idx.get_generation()
    assert gen0 == 0

    pkg = build_component_spec(MUX_DEF)
    cat_bytes = get_package_asset(pkg, "library_catalogue_v1")
    assert cat_bytes is not None
    cat_asset = CatalogueAssetV1.model_validate_json(cat_bytes.decode("utf-8"))
    rev = SpecRevision.from_package(pkg)

    # Write dummy spec file
    dest_file = lib_root / "logic/mux/1.0.0/mux.spec"
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    dest_file.write_bytes(pkg.to_bytes())

    idx.record_published_package(
        cat_asset=cat_asset,
        rel_path="logic/mux/1.0.0/mux.spec",
        pkg_sha="sha256:" + "0" * 64,
        source_rev_hash=rev.source_revision_hash,
    )

    gen1 = idx.get_generation()
    assert gen1 == 1

    key = compute_identity_key("spec2gds.local", "logic", "mux")
    comp = idx.get_component_by_key(key)
    assert comp is not None
    assert comp["id"] == "mux"
    assert len(comp["versions"]) == 1
    assert comp["versions"][0]["version"] == "1.0.0"


def test_functional_status_calculation(index_env: tuple[CatalogueIndex, Path]) -> None:
    idx, lib_root = index_env
    pkg = build_component_spec(MUX_DEF)
    cat_bytes = get_package_asset(pkg, "library_catalogue_v1")
    assert cat_bytes is not None
    cat_asset = CatalogueAssetV1.model_validate_json(cat_bytes.decode("utf-8"))
    rev = SpecRevision.from_package(pkg)

    # Case 1: No evidence -> unreported
    status, count = idx.compute_functional_status(cat_asset.model_dump(mode="json"), [])
    assert status == "unreported"
    assert count == 0

    # Case 2: Incomplete checks
    ev_partial = EvidenceRecordV1(
        schema_version=1,
        package_sha256="sha256:" + "a" * 64,
        source_revision_hash=rev.source_revision_hash,
        root=rev.components[0].ref,
        runner_commit="0" * 40,
        tools={"python": "3.12.3"},
        presets=MUX_DEF.presets,
        checks=[CheckRecord(kind="package", preset=None, status="pass", seed=None, summary="ok")],
        limitations=[],
        created_at="2026-11-02T12:00:00Z",
    )
    raw_ev = serialize_canonical_evidence_bytes(ev_partial.model_dump(mode="json")).decode("utf-8")
    status, count = idx.compute_functional_status(cat_asset.model_dump(mode="json"), [{"raw_json": raw_ev}])
    assert status == "reported_incomplete"
    assert count == 1

    # Case 3: Failing check
    ev_failing = EvidenceRecordV1(
        schema_version=1,
        package_sha256="sha256:" + "a" * 64,
        source_revision_hash=rev.source_revision_hash,
        root=rev.components[0].ref,
        runner_commit="0" * 40,
        tools={"python": "3.12.3"},
        presets=MUX_DEF.presets,
        checks=[
            CheckRecord(kind="package", preset=None, status="pass", seed=None, summary="ok"),
            CheckRecord(kind="simulation", preset="default", status="fail", seed=123, summary="assertion"),
        ],
        limitations=[],
        created_at="2026-11-02T12:00:00Z",
    )
    raw_fail = serialize_canonical_evidence_bytes(ev_failing.model_dump(mode="json")).decode("utf-8")
    status, count = idx.compute_functional_status(cat_asset.model_dump(mode="json"), [{"raw_json": raw_fail}])
    assert status == "reported_fail"


def test_indexer_rebuild(index_env: tuple[CatalogueIndex, Path]) -> None:
    idx, lib_root = index_env
    state_dir = idx.db_path.parent

    # Publish mux to disk
    pkg = build_component_spec(MUX_DEF)
    dest_dir = lib_root / "logic/mux/1.0.0"
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "mux.spec").write_bytes(pkg.to_bytes())
    (dest_dir / "usage.md").write_text("# Mux Usage\n")

    indexer = LibraryIndexer(library_root=lib_root, state_dir=state_dir)
    stats = indexer.rebuild()
    assert stats["components_indexed"] >= 1
    assert stats["releases_indexed"] >= 1

    # Query through CatalogueIndex
    key = compute_identity_key("spec2gds.local", "logic", "mux")
    comp = idx.get_component_by_key(key)
    assert comp is not None
    assert comp["id"] == "mux"

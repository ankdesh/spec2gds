"""Unit tests for Component Library schemas and serialization."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError
from spec_catalog_service.catalog.schemas import (
    CatalogueAssetV1,
    CheckRecord,
    EvidenceRecordV1,
    TimingInfo,
    compute_identity_key,
    compute_sha256,
    serialize_canonical_evidence_bytes,
)

from spec2gds.spec.spec_format.models import EntityRef


def test_catalogue_asset_valid() -> None:
    asset = CatalogueAssetV1(
        schema_version=1,
        root=EntityRef(document_id="doc1", entity_id="component_mux", entity_kind="component"),
        id="mux",
        category="logic",
        version="1.0.0",
        summary="Basic parameterized multiplexer",
        tags=["combinational", "logic", "mux"],
        licence="Apache-2.0",
        implementation="body_sv",
        contracts="docs/spec-catalog/contracts/phase-1.md#mux",
        presets={"default": {"W": "32", "N": "2"}},
        timing=TimingInfo(latency="0", throughput="1", reset="none"),
        dependencies=[],
        limitations=[],
    )
    assert asset.id == "mux"
    assert asset.category == "logic"
    assert asset.version == "1.0.0"


def test_catalogue_asset_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        CatalogueAssetV1(
            schema_version=1,
            root=EntityRef(document_id="doc1", entity_id="component_mux", entity_kind="component"),
            id="mux",
            category="logic",
            version="1.0.0",
            summary="Basic parameterized multiplexer",
            tags=["combinational", "logic", "mux"],
            licence="Apache-2.0",
            implementation="body_sv",
            contracts="docs/spec-catalog/contracts/phase-1.md#mux",
            presets={"default": {"W": "32", "N": "2"}},
            timing=TimingInfo(latency="0", throughput="1", reset="none"),
            dependencies=[],
            limitations=[],
            unknown_extra_field="disallowed",
        )


def test_catalogue_asset_invalid_id() -> None:
    with pytest.raises(ValidationError):
        CatalogueAssetV1(
            schema_version=1,
            root=EntityRef(document_id="doc1", entity_id="component_mux", entity_kind="component"),
            id="Mux-Invalid!",
            category="logic",
            version="1.0.0",
            summary="Bad id",
            tags=[],
            licence="Apache-2.0",
            implementation="body_sv",
            contracts="docs/spec-catalog/contracts/phase-1.md#mux",
            presets={"default": {}},
            timing=TimingInfo(latency="0", throughput="1", reset="none"),
            dependencies=[],
            limitations=[],
        )


def test_catalogue_asset_invalid_category() -> None:
    with pytest.raises(ValidationError):
        CatalogueAssetV1(
            schema_version=1,
            root=EntityRef(document_id="doc1", entity_id="component_mux", entity_kind="component"),
            id="mux",
            category="unknown_category",
            version="1.0.0",
            summary="Bad cat",
            tags=[],
            licence="Apache-2.0",
            implementation="body_sv",
            contracts="docs/spec-catalog/contracts/phase-1.md#mux",
            presets={"default": {}},
            timing=TimingInfo(latency="0", throughput="1", reset="none"),
            dependencies=[],
            limitations=[],
        )


def test_evidence_record_valid_and_canonical_bytes() -> None:
    ev = EvidenceRecordV1(
        schema_version=1,
        package_sha256="sha256:" + "a" * 64,
        source_revision_hash="b" * 64,
        root=EntityRef(document_id="doc1", entity_id="component_mux", entity_kind="component"),
        runner_commit="c" * 40,
        tools={"python": "3.12.3", "verilator": "5.020"},
        presets={"default": {"W": "32", "N": "2"}},
        checks=[
            CheckRecord(kind="package", preset=None, status="pass", seed=None, summary="ok"),
            CheckRecord(kind="simulation", preset="default", status="pass", seed=123, summary="pass"),
        ],
        limitations=[],
        created_at="2026-11-02T12:00:00Z",
    )
    raw_bytes = serialize_canonical_evidence_bytes(ev.model_dump(mode="json"))
    assert isinstance(raw_bytes, bytes)
    assert not raw_bytes.endswith(b"\n")
    # Verify deterministic digest
    sha = compute_sha256(raw_bytes)
    assert len(sha) == 71  # "sha256:" (7) + 64 hex = 71
    assert sha.startswith("sha256:")


def test_identity_key_computation() -> None:
    key1 = compute_identity_key("spec2gds", "library", "mux")
    key2 = compute_identity_key("spec2gds", "library", "mux")
    assert key1 == key2
    assert len(key1) == 64
    assert not key1.startswith("sha256:")


def test_inventory_contract_references_resolve() -> None:
    """Keep current catalog contract paths and Component anchors usable."""
    root = Path(__file__).resolve().parents[2]
    inventory = json.loads((root / "spec_catalog_service/catalog/inventory.json").read_text())
    for entry in inventory["entries"]:
        path, separator, anchor = entry["contract"].partition("#")
        assert separator and anchor, entry["id"]
        text = (root / path).read_text()
        assert re.search(r"^#{1,6}\s+" + re.escape(anchor) + r"\s*$", text, re.MULTILINE), entry["id"]

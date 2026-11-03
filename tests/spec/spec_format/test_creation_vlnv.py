"""Tests for explicit creation VLNV and atomic transactions in Spec source format."""

from __future__ import annotations

from pathlib import Path

import fastapi
import pytest

from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.transactions import (
    CreateHardware,
    SpecEditTransaction,
)
from spec2gds.spec.spec_format.v1_api import (
    CreateDocumentRequest,
    OpenDocumentRequest,
    TransactionRequest,
    create_app,
)


def test_create_hardware_omitted_vlnv_preserves_work_identity() -> None:
    package = SpecPackage.create("test_doc")
    rev = SpecRevision.from_package(package)
    res = SpecEditTransaction(
        rev.source_revision_hash,
        (CreateHardware(kind="component", name="alu_core"),),
    ).apply(rev)
    assert res.succeeded, res.diagnostics
    assert res.revision is not None
    comp = res.revision.components[0]
    assert comp.vlnv == "spec2gds.local:work:alu_core:1.0"


def test_create_hardware_explicit_vlnv_sets_exact_identity() -> None:
    package = SpecPackage.create("test_doc")
    rev = SpecRevision.from_package(package)
    res = SpecEditTransaction(
        rev.source_revision_hash,
        (
            CreateHardware(
                kind="component",
                name="mux",
                vlnv="spec2gds.local:logic:mux:1.0.0",
            ),
        ),
    ).apply(rev)
    assert res.succeeded, res.diagnostics
    assert res.revision is not None
    comp = res.revision.components[0]
    assert comp.vlnv == "spec2gds.local:logic:mux:1.0.0"


def test_create_hardware_rejects_mismatched_normalized_name() -> None:
    package = SpecPackage.create("test_doc")
    rev = SpecRevision.from_package(package)
    res = SpecEditTransaction(
        rev.source_revision_hash,
        (
            CreateHardware(
                kind="component",
                name="mux",
                vlnv="spec2gds.local:logic:demux:1.0.0",
            ),
        ),
    ).apply(rev)
    assert not res.succeeded
    assert any("does not match hardware name" in d for d in res.diagnostics)


def test_create_hardware_rejects_invalid_vlnv_format() -> None:
    package = SpecPackage.create("test_doc")
    rev = SpecRevision.from_package(package)
    res = SpecEditTransaction(
        rev.source_revision_hash,
        (
            CreateHardware(
                kind="component",
                name="mux",
                vlnv="invalid_vlnv_without_four_parts",
            ),
        ),
    ).apply(rev)
    assert not res.succeeded
    assert any("VLNV must be formatted as" in d for d in res.diagnostics)


def test_create_hardware_rejects_duplicate_vlnv_atomically() -> None:
    package = SpecPackage.create("test_doc")
    rev = SpecRevision.from_package(package)
    first_res = SpecEditTransaction(
        rev.source_revision_hash,
        (
            CreateHardware(
                kind="component",
                name="mux",
                vlnv="spec2gds.local:logic:mux:1.0.0",
            ),
        ),
    ).apply(rev)
    assert first_res.succeeded
    assert first_res.revision is not None

    dup_res = SpecEditTransaction(
        first_res.revision.source_revision_hash,
        (
            CreateHardware(
                kind="component",
                name="mux",
                vlnv="spec2gds.local:logic:mux:1.0.0",
            ),
        ),
    ).apply(first_res.revision)
    assert not dup_res.succeeded
    assert any("already exists" in d for d in dup_res.diagnostics)


def test_transaction_failure_leaves_source_unchanged() -> None:
    package = SpecPackage.create("test_doc")
    rev = SpecRevision.from_package(package)
    first_res = SpecEditTransaction(
        rev.source_revision_hash,
        (CreateHardware(kind="component", name="first_comp"),),
    ).apply(rev)
    assert first_res.succeeded
    assert first_res.revision is not None

    saved_bytes = package.to_bytes()

    failed_res = SpecEditTransaction(
        first_res.revision.source_revision_hash,
        (
            CreateHardware(kind="component", name="second_comp"),
            CreateHardware(
                kind="component",
                name="bad_comp",
                vlnv="spec2gds.local:logic:wrong_name:1.0.0",
            ),
        ),
    ).apply(first_res.revision)
    assert not failed_res.succeeded
    assert failed_res.revision is None
    # Original revision unchanged
    assert len(first_res.revision.components) == 1


def test_http_api_create_entity_with_explicit_vlnv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SPEC_EDITOR_STATE_ROOT", str(tmp_path / "state"))
    app = create_app()
    endpoints = {route.name: route.endpoint for route in app.routes if hasattr(route, "endpoint")}

    spec_path = tmp_path / "test_api.spec"
    package = SpecPackage.create("api_test")
    package.save(str(spec_path))

    open_res = endpoints["open_document"](OpenDocumentRequest(path=str(spec_path)))
    rev_hash = open_res["source_revision_hash"]

    result = endpoints["transaction"](TransactionRequest(
        expected_source_revision_hash=rev_hash,
        operations=[
            {
                "type": "create_entity",
                "kind": "component",
                "name": "mux",
                "vlnv": "spec2gds.local:logic:mux:1.0.0",
            }
        ],
    ))
    assert result["committed"] is True
    assert any(c["vlnv"] == "spec2gds.local:logic:mux:1.0.0" for c in result["snapshot"]["components"])

    # Duplicate submission fails with 422
    with pytest.raises(fastapi.HTTPException) as exc_info:
        endpoints["transaction"](TransactionRequest(
            expected_source_revision_hash=result["snapshot"]["source_revision_hash"],
            operations=[
                {
                    "type": "create_entity",
                    "kind": "component",
                    "name": "mux",
                    "vlnv": "spec2gds.local:logic:mux:1.0.0",
                }
            ],
        ))
    assert exc_info.value.status_code == 422
    assert "already exists" in str(exc_info.value.detail)

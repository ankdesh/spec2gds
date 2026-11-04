"""Integration tests for Library Service HTTP API endpoints."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from spec_catalog_service.catalog.authoring import build_component_spec
from spec_catalog_service.catalog.components.phase1 import MUX_DEF
from spec_catalog_service.catalog.schemas import (
    CheckRecord,
    EvidenceRecordV1,
    serialize_canonical_evidence_bytes,
)
from spec_catalog_service.http.service import create_app

from spec2gds.spec.spec_format.ir import SpecRevision


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    lib_root = tmp_path / "spec_library"
    lib_root.mkdir()
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    app = create_app(library_root=lib_root, state_dir=state_dir)
    return TestClient(app)


def test_health_and_capabilities(client: TestClient) -> None:
    res = client.get("/api/spec-catalog/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["root_readable"] is True
    assert data["schema_version"] == 1

    res_cap = client.get("/api/spec-catalog/v1/capabilities")
    assert res_cap.status_code == 200
    caps = res_cap.json()
    assert caps["profile"] == "trusted_local"
    assert "limits" in caps
    assert "logic" in caps["categories"]


def test_upload_list_details_download_lifecycle(client: TestClient) -> None:
    pkg = build_component_spec(MUX_DEF)
    raw_bytes = pkg.to_bytes()

    # 1. Upload valid component package
    files = {"file": ("mux.spec", io.BytesIO(raw_bytes), "application/zip")}
    res_up = client.post("/api/spec-catalog/v1/uploads", files=files)
    assert res_up.status_code == 201
    up_data = res_up.json()
    assert up_data["created"] is True
    vrow = up_data["version"]
    assert vrow["id"] == "mux"
    assert vrow["version"] == "1.0.0"
    key = vrow["key"]

    # 2. Identical retry returns 200 with created=False
    files_retry = {"file": ("mux.spec", io.BytesIO(raw_bytes), "application/zip")}
    res_retry = client.post("/api/spec-catalog/v1/uploads", files=files_retry)
    assert res_retry.status_code == 200
    assert res_retry.json()["created"] is False

    # 3. List components
    res_list = client.get("/api/spec-catalog/v1/components?category=logic")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total"] >= 1
    assert any(it["id"] == "mux" for it in list_data["items"])

    # 4. Component identity details
    res_comp = client.get(f"/api/spec-catalog/v1/components/{key}")
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert comp_data["id"] == "mux"
    assert len(comp_data["versions"]) == 1

    # 5. Version details
    res_ver = client.get(f"/api/spec-catalog/v1/components/{key}/versions/1.0.0")
    assert res_ver.status_code == 200
    ver_data = res_ver.json()
    assert "metadata" in ver_data
    assert ver_data["metadata"]["id"] == "mux"

    # 6. Download with ETag and 304
    res_dl = client.get(f"/api/spec-catalog/v1/components/{key}/versions/1.0.0/download")
    assert res_dl.status_code == 200
    assert res_dl.content == raw_bytes
    etag = res_dl.headers.get("ETag")
    assert etag is not None

    # Test If-None-Match
    res_304 = client.get(
        f"/api/spec-catalog/v1/components/{key}/versions/1.0.0/download",
        headers={"If-None-Match": etag},
    )
    assert res_304.status_code == 304

    # 7. Evidence submission and retrieval
    rev = SpecRevision.from_package(pkg)
    ev = EvidenceRecordV1(
        schema_version=1,
        package_sha256=vrow["package_sha256"],
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

    res_ev_post = client.post(
        f"/api/spec-catalog/v1/components/{key}/versions/1.0.0/evidence",
        content=ev_bytes,
        headers={"Content-Type": "application/json"},
    )
    assert res_ev_post.status_code == 201
    assert res_ev_post.json()["created"] is True

    # Get evidence
    res_ev_get = client.get(f"/api/spec-catalog/v1/components/{key}/versions/1.0.0/evidence")
    assert res_ev_get.status_code == 200
    ev_items = res_ev_get.json()["items"]
    assert len(ev_items) == 1
    assert ev_items[0]["evidence_sha256"] == res_ev_post.json()["evidence_sha256"]

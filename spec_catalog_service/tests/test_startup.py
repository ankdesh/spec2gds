"""A fresh service indexes releases and retains durable evidence after restart."""

from pathlib import Path

from fastapi.testclient import TestClient
from spec_catalog_service.catalog.authoring import build_component_spec
from spec_catalog_service.catalog.components.phase1 import MUX_DEF
from spec_catalog_service.catalog.schemas import compute_sha256
from spec_catalog_service.http.service import create_app


def test_fresh_service_indexes_all_published_releases_without_changing_bytes(tmp_path):
    root = Path(__file__).resolve().parents[1] / "catalog"
    before = {str(p): compute_sha256(p.read_bytes()) for p in root.rglob("*.spec")}
    with TestClient(create_app(root, tmp_path / "index")) as client:
        response = client.get("/api/spec-catalog/v1/components?limit=100")
        assert response.status_code == 200
        assert response.json()["total"] == len(before)
        assert (
            client.get("/api/spec-catalog/v1/components?implementation=body_sv&limit=100").json()[
                "total"
            ]
            == len(before)
        )
        assert (
            client.get("/api/spec-catalog/v1/components?implementation=composite").json()["total"]
            == 0
        )
        assert client.get("/api/spec-library/v1/health").status_code == 404
    assert before == {str(p): compute_sha256(p.read_bytes()) for p in root.rglob("*.spec")}


def test_startup_reconstructs_submitted_evidence_from_durable_files(tmp_path):
    root, state = tmp_path / "catalog", tmp_path / "index"
    root.mkdir()
    raw = build_component_spec(MUX_DEF).to_bytes()
    with TestClient(create_app(root, state)) as client:
        release = client.post(
            "/api/spec-catalog/v1/uploads", files={"file": ("mux.spec", raw, "application/zip")}
        ).json()["version"]
        evidence = {
            "schema_version": 1,
            "package_sha256": compute_sha256(raw),
            "source_revision_hash": release["source_revision_hash"],
            "root": {
                "document_id": "test",
                "entity_id": "component_mux",
                "entity_kind": "component",
            },
            "runner_commit": "0" * 40,
            "tools": {},
            "presets": {},
            "checks": [{"kind": "package", "status": "pass", "summary": "Checked"}],
            "limitations": [],
            "created_at": "2026-11-04T00:00:00Z",
        }
        route = f"/api/spec-catalog/v1/components/{release['key']}/versions/1.0.0/evidence"
        assert client.post(route, json=evidence).status_code == 201
    (state / "catalogue.db").unlink()
    with TestClient(create_app(root, state)) as client:
        restored = client.get(route)
        assert restored.status_code == 200
        assert len(restored.json()["items"]) == 1
        assert restored.json()["items"][0]["report"]["package_sha256"] == compute_sha256(raw)


def test_catalog_cli_uses_shared_paths_and_listener_overrides(tmp_path, monkeypatch):
    import json

    from spec_catalog_service.http import cli

    path = tmp_path / "services.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "public_host": "design.test",
                "spec_catalog": {"catalog_root": "published", "state_dir": "index"},
            }
        )
    )
    calls = {}
    monkeypatch.setattr(cli, "create_app", lambda **kwargs: calls.update(kwargs) or "catalog-app")
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, **kwargs: calls.update(app=app, **kwargs))
    assert cli.main(["--service-config", str(path), "--host", "127.0.0.1", "--port", "6447"]) == 0
    assert calls["library_root"] == tmp_path / "published"
    assert calls["state_dir"] == tmp_path / "index"
    assert calls["port"] == 6447 and calls["host"] == "127.0.0.1"

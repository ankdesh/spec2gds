from spec2gds.spec.spec_format.testing import bound_http_client
"""Check canonical API fields against existing V1 transport aliases."""

from fastapi.testclient import TestClient

from spec2gds.spec.spec_format.testing import build_test_package
from spec2gds.spec.spec_format.v1_api import create_app


def test_service_query_alias_keeps_the_bound_spec_and_explicit_target_routes(tmp_path):
    app = create_app()
    routes = {route.name: route.path for route in app.routes if hasattr(route, "endpoint")}
    path = tmp_path / "source.spec"
    build_test_package().save(str(path))
    with bound_http_client(app) as client:
        opened = client.post("/documents/open", json={"path": str(path)}).json()
        key = opened["service_document_key"]
        assert key == opened["owner_document_key"]
        component_id = opened["components"][0]["ref"]["entity_id"]
        design_id = opened["designs"][0]["ref"]["entity_id"]
        for kind, identifier in (("component", component_id), ("design", design_id)):
            for feature in ("activities", "actions"):
                canonical = client.get(f"/{kind}s/{identifier}/{feature}")
                legacy = client.get(f"/entities/{kind}/{identifier}/{feature}")
                assert canonical.status_code == legacy.status_code == 200
                assert canonical.json() == legacy.json()
        second = client.post(routes["create_document"], json={"path": str(tmp_path / "second.spec"), "document_id": "second"}).json()
        response = client.get(routes["document_snapshot"], params={
            "service_document_key": key, "owner_document_key": second["owner_document_key"],
        })
        assert response.status_code == 200
        assert response.json()["document_id"] == opened["document_id"]


def test_canonical_operation_aliases_keep_validation_and_reject_conflicting_parent():
    import pytest

    from spec2gds.spec.spec_format.assistant import normalize_operation_aliases

    assert normalize_operation_aliases({"type": "create_component", "name": "alu"}) == {
        "type": "create_entity", "kind": "component", "name": "alu"}
    assert normalize_operation_aliases({"type": "create_design", "name": "top"})["kind"] == "design"
    with pytest.raises(ValueError, match="hardware kind"):
        normalize_operation_aliases({"type": "create_component", "kind": "design"})
    reference = {"document_id": "spec", "entity_kind": "component", "entity_id": "alu"}
    normalized = normalize_operation_aliases({"type": "upsert_section", "parent": reference})
    assert normalized == {"type": "upsert_entity_section", "owner": reference}
    with pytest.raises(ValueError, match="parent aliases"):
        normalize_operation_aliases({"type": "delete_section", "parent": reference, "owner": {**reference, "entity_id": "other"}})

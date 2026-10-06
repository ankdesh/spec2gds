"""Spec service discovery does not require a Spec or Circuit service."""
import json
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient

from spec2gds.spec.spec_format.assistant_integration import ASSISTANT_ACTIONS
from spec2gds.spec.spec_format.v1_api import create_app


def test_metadata_without_open_spec_and_route_consistency():
    app = create_app()
    with TestClient(app) as client:
        response = client.get('/assistant/integration-metadata')
        assert response.status_code == 200
        metadata = response.json()
        assert metadata['service_kind'] == 'spec'
        assert metadata['format_version'] == 1
        digest = metadata.pop('digest')
        assert digest == 'sha256:' + sha256(json.dumps(metadata, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        routes = {(method, route.path) for route in app.routes for method in getattr(route, 'methods', [])}
        assert all((action['method'], action['path']) in routes for action in ASSISTANT_ACTIONS.values())
        assert client.get('/assistant/capabilities').status_code == 200
        assert client.get('/assistant/context/document?document_id=missing').status_code != 200
    fixture = Path(__file__).parents[3] / 'ai-assistant/tests/fixtures/spec-integration-metadata.json'
    expected = json.loads(fixture.read_text())
    expected.pop('digest')
    assert metadata == expected

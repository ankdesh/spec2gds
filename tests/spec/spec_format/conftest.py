"""Keep owner catalogs and approval policy isolated for every test."""
import json
import tempfile

import pytest

from spec2gds.service_registry import service_config_path, load_service_registry


@pytest.fixture(autouse=True)
def isolated_editor_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("SPEC_EDITOR_STATE_ROOT", str(tmp_path / "editor-state"))
    monkeypatch.setenv("SPEC2GDS_REQUIRE_HUMAN_APPROVAL", "0")
    configuration = json.loads(service_config_path().read_text())
    configuration["spec_editor"]["spec_root"] = tempfile.gettempdir()
    configuration["activities"]["scratch_root"] = str(tmp_path / "generated")
    configuration["logging"]["file"] = str(tmp_path / "events.jsonl")
    configuration["circuit_designer"]["preferences_file"] = str(tmp_path / "circuit-preferences.json")
    registry_path = tmp_path / "services.json"
    registry_path.write_text(json.dumps(configuration))
    import spec2gds.spec.spec_format.v1_api as api
    monkeypatch.setattr(api, "load_service_registry", lambda path=None: load_service_registry(path or registry_path))

"""Keep owner catalogs and approval policy isolated for every test."""
import pytest
import json

from spec2gds.service_registry import service_config_path


@pytest.fixture(autouse=True)
def isolated_editor_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("SPEC_EDITOR_STATE_ROOT", str(tmp_path / "editor-state"))
    monkeypatch.setenv("SPEC2GDS_REQUIRE_HUMAN_APPROVAL", "0")
    configuration = json.loads(service_config_path().read_text())
    configuration["activities"]["workspace_root"] = str(tmp_path / "generated")
    configuration["logging"]["file"] = str(tmp_path / "events.jsonl")
    configuration["circuit_designer"]["preferences_file"] = str(tmp_path / "circuit-preferences.json")
    registry_path = tmp_path / "services.json"
    registry_path.write_text(json.dumps(configuration))
    monkeypatch.setenv("SPEC2GDS_SERVICE_CONFIG", str(registry_path))

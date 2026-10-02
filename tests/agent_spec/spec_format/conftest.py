"""Keep owner catalogs and approval policy isolated for every test."""
import pytest
import json

from spec2gds.service_registry import service_config_path


@pytest.fixture(autouse=True)
def isolated_editor_owner(tmp_path_factory, monkeypatch):
    env_dir = tmp_path_factory.mktemp("isolated_env")
    monkeypatch.setenv("SPEC_EDITOR_STATE_ROOT", str(env_dir / "editor-state"))
    monkeypatch.setenv("SPEC2GDS_REQUIRE_HUMAN_APPROVAL", "0")
    configuration = json.loads(service_config_path().read_text())
    configuration["activities"]["workspace_root"] = str(env_dir / "generated")
    configuration["logging"]["file"] = str(env_dir / "events.jsonl")
    configuration["circuit_designer"]["preferences_file"] = str(env_dir / "circuit-preferences.json")
    registry_path = env_dir / "services.json"
    registry_path.write_text(json.dumps(configuration))
    monkeypatch.setenv("SPEC2GDS_SERVICE_CONFIG", str(registry_path))

"""Common resolver contracts and launch adapter regression protection."""

import importlib
import json
import os
import subprocess
from pathlib import Path

import pytest
from spec2gds_runtime.service_config import endpoint_url, listener_overrides, resolve_config

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests/fixtures/service-config.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_common_resolver_contract(case, tmp_path, monkeypatch):
    for key in ("SPEC2GDS_SERVICE_CONFIG", "SPEC2GDS_PUBLIC_HOST", "SPEC_SERVICE_PORT", "AGENT_SPEC_PORT", "CIRCUIT_DESIGNER_PORT", "ASSISTANT_PORT"):
        monkeypatch.setenv(key, "obsolete-invalid-value")
    path = tmp_path / "services.json"
    path.write_text(json.dumps({"public_host": "design.test", **case["config"]}))
    if case.get("error"):
        with pytest.raises(ValueError, match=case["error"]):
            resolve_config(path, overrides=case.get("overrides"))
    else:
        config = resolve_config(path, overrides=case.get("overrides"))
        assert endpoint_url(config["spec_editor"]["service"], config["public_host"]) == case["url"]
        assert endpoint_url(config["spec_editor"]["service"], config["public_host"], local=True) == case["local"]
        snapshot = tmp_path / "nested/services.json"
        snapshot.parent.mkdir()
        snapshot.write_text(json.dumps(config))
        assert resolve_config(snapshot) == config


def test_javascript_uses_the_same_fixtures(tmp_path):
    result = subprocess.run(["node", "--test", "runtime/service-config.test.mjs"], cwd=ROOT,
                            env={**os.environ, "TMPDIR": str(tmp_path)}, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_explicit_missing_file_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_config(tmp_path / "missing.json")


def test_auto_is_explicit_and_resolved_once(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("spec2gds_runtime.service_config.primary_ipv4", lambda: calls.append(1) or "192.0.2.10")
    monkeypatch.setenv("SPEC2GDS_PUBLIC_HOST", "obsolete.test")
    path = tmp_path / "services.json"
    path.write_text('{"public_host":"auto"}')
    config = resolve_config(path)
    path.write_text(json.dumps(config))
    assert resolve_config(path)["public_host"] == "192.0.2.10"
    assert calls == [1]


def test_reload_factory_preserves_configuration_and_approval(tmp_path, monkeypatch):
    from spec2gds.spec.api.__main__ import server_main
    monkeypatch.setenv("SPEC_EDITOR_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("SPEC_SERVICE_PORT", "9")
    monkeypatch.setenv("AI_ASSISTANT_URL", "http://obsolete.test:9")
    path = tmp_path / "services.json"
    path.write_text('{"public_host":"design.test"}')
    calls = []
    monkeypatch.setattr("uvicorn.run", lambda app, **kwargs: calls.append((app, kwargs)))
    server_main(["--service-config", str(path), "--port", "6420", "--reload", "--require-designer-approval"])
    module = importlib.import_module(calls[0][0].split(":")[0])
    app = module.create_app()
    endpoints = {route.name: route.endpoint for route in app.routes if hasattr(route, "endpoint")}
    directory = endpoints["services"]()["services"]
    assert directory["spec_editor"] == {"service_url": "http://design.test:6420", "ui_url": "http://design.test:6420/editor"}
    assert directory["ai_assistant"]["ui_url"] == "http://design.test:6013"
    assert endpoints["assistant_capabilities"]()["approval_policy"] == "review"
    app.state.activity_jobs.close()


def test_shared_listener_override_updates_both_surfaces():
    config = resolve_config(overrides=listener_overrides("verification_planner", host="::1", port=6430))
    assert config["verification_planner"]["service"] == config["verification_planner"]["ui"]

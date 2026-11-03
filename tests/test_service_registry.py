from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec2gds.service_registry import load_service_registry


def test_tracked_service_registry_exposes_all_public_urls(monkeypatch) -> None:
    monkeypatch.setenv("SPEC2GDS_PUBLIC_HOST", "design-host.test")
    registry = load_service_registry(overrides={"public_host": "design-host.test"})
    assert registry.spec_editor.service.host == "0.0.0.0"
    assert registry.public_host == "design-host.test"
    assert registry.spec_editor.ui.url == "http://design-host.test:6010/editor"
    assert registry.circuit_designer.service.url == (
        "http://design-host.test:6011/api/circuit-designer/v1"
    )
    assert registry.ai_assistant.ui.url == "http://design-host.test:6013"
    assert registry.logging.enabled is False
    assert registry.logging.level == "info"
    assert registry.logging.file.name == "spec2gds.jsonl"
    assert registry.activities.workspace_root.name == "generated"
    assert registry.activities.extension_modules == ()


def test_service_registry_rejects_invalid_ports(tmp_path: Path) -> None:
    source = Path(__file__).parents[1] / "config" / "services.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["ai_assistant"]["service"]["port"] = 70000
    invalid = tmp_path / "services.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="port must be between"):
        load_service_registry(invalid)

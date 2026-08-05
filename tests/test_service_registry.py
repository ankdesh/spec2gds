from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec2gds.service_registry import load_service_registry


def test_tracked_service_registry_exposes_all_public_urls() -> None:
    registry = load_service_registry()
    assert registry.spec_editor.ui.url == "http://127.0.0.1:8000/editor"
    assert registry.circuit_designer.service.url == (
        "http://127.0.0.1:4100/api/circuit-designer/v1"
    )
    assert registry.ai_assistant.ui.url == "http://127.0.0.1:4200"
    assert registry.logging.enabled is False
    assert registry.logging.level == "info"
    assert registry.logging.file.name == "spec2gds.jsonl"


def test_service_registry_rejects_invalid_ports(tmp_path: Path) -> None:
    source = Path(__file__).parents[1] / "config" / "services.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["ai_assistant"]["service"]["port"] = 70000
    invalid = tmp_path / "services.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="port must be between"):
        load_service_registry(invalid)

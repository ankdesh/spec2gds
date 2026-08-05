from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec2gds_runtime import LogSettings, StructuredLogger, load_log_settings, redact


def settings(
    path: Path,
    *,
    enabled: bool = True,
    level: str = "debug",
    max_bytes: int = 4096,
) -> LogSettings:
    return LogSettings(
        enabled, level, path, max_bytes, "127.0.0.1", 4300  # type: ignore[arg-type]
    )


def test_disabled_logger_does_not_create_a_file(tmp_path: Path) -> None:
    target = tmp_path / "system.jsonl"
    StructuredLogger("spec-editor", settings(target, enabled=False)).event(
        "api", "started", "Started"
    )
    assert not target.exists()


def test_debug_details_are_redacted_and_binary_is_summarized(tmp_path: Path) -> None:
    target = tmp_path / "system.jsonl"
    StructuredLogger("ai-assistant", settings(target)).event(
        "openai",
        "request",
        "Calling model",
        details={"prompt": "hello", "api_key": "secret", "image": b"png"},
    )
    value = json.loads(target.read_text(encoding="utf-8"))
    assert value["details"]["prompt"] == "hello"
    assert value["details"]["api_key"] == "[REDACTED]"
    assert value["details"]["image"]["bytes"] == 3


def test_info_mode_keeps_the_one_line_summary_without_debug_details(tmp_path: Path) -> None:
    target = tmp_path / "system.jsonl"
    StructuredLogger("spec-editor", settings(target, level="info")).event(
        "documents", "opened", "Opened specification", details={"path": "/private/demo.spec"}
    )
    value = json.loads(target.read_text(encoding="utf-8"))
    assert value["message"] == "Opened specification"
    assert "details" not in value


def test_single_file_compaction_retains_newest_complete_events(tmp_path: Path) -> None:
    target = tmp_path / "system.jsonl"
    logger = StructuredLogger("spec-editor", settings(target, max_bytes=1024))
    for number in range(30):
        logger.event("test", "item", f"event-{number}", details={"padding": "x" * 100})
    lines = target.read_text(encoding="utf-8").splitlines()
    assert target.stat().st_size <= 1024
    assert json.loads(lines[-1])["message"] == "event-29"
    assert all(json.loads(line) for line in lines)


def test_redaction_recurses_through_common_secret_keys() -> None:
    assert redact({"headers": {"Authorization": "Bearer value"}}) == {
        "headers": {"Authorization": "[REDACTED]"}
    }


def test_only_enabled_and_level_have_environment_overrides(
    tmp_path: Path, monkeypatch
) -> None:
    source = Path(__file__).parents[1] / "config" / "services.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["logging"]["file"] = "configured.jsonl"
    configured = tmp_path / "services.json"
    configured.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("SPEC2GDS_LOGGING", "ON")
    monkeypatch.setenv("SPEC2GDS_LOG_LEVEL", "debug")
    monkeypatch.setenv("SPEC2GDS_LOG_FILE", str(tmp_path / "ignored.jsonl"))
    resolved = load_log_settings(configured)
    assert resolved.enabled is True
    assert resolved.level == "debug"
    assert resolved.file == tmp_path / "configured.jsonl"


def test_logging_environment_rejects_values_other_than_on_or_off(
    monkeypatch,
) -> None:
    source = Path(__file__).parents[1] / "config" / "services.json"
    monkeypatch.setenv("SPEC2GDS_LOGGING", "yes")
    with pytest.raises(ValueError, match="ON or OFF"):
        load_log_settings(source)

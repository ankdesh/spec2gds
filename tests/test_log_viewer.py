from __future__ import annotations

import json
from pathlib import Path

from spec2gds.log_viewer import _matches, _read_records


def test_viewer_filters_combined_records(tmp_path: Path) -> None:
    log_file = tmp_path / "combined.jsonl"
    log_file.write_text(
        "\n".join(
            json.dumps(value)
            for value in (
                {"event_id": "1", "application": "spec-editor", "component": "http", "severity": "info", "message": "opened"},
                {"event_id": "2", "application": "ai-assistant", "component": "openai", "severity": "debug", "message": "response"},
            )
        ) + "\n",
        encoding="utf-8",
    )
    records, malformed = _read_records(log_file)
    filtered = [item for item in records if _matches(item, "ai-assistant", None, None, None, None)]
    assert malformed == 0
    assert [item["event_id"] for item in filtered] == ["2"]


def test_viewer_ignores_a_partial_or_malformed_record(tmp_path: Path) -> None:
    log_file = tmp_path / "combined.jsonl"
    log_file.write_text('{"event_id":"valid"}\n{"partial":', encoding="utf-8")
    records, malformed = _read_records(log_file)
    assert malformed == 1
    assert records == [{"event_id": "valid"}]

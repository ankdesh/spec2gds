"""Coverage measurement must not change functional selection or conceal gaps."""
from pathlib import Path

from scripts.test_capabilities import capability_results
from scripts.test_coverage import collect, instrument, percent


def test_python_instrumentation_preserves_every_pytest_argument(tmp_path):
    command = ["uv", "run", "--no-sync", "python", "-m", "pytest", "tests", "-m", "not extensive", "-q"]
    measured, kind = instrument(command.copy(), "python-fast", tmp_path, {}, Path.cwd())
    assert kind == "python"
    assert measured[-6:] == command[-6:]
    assert "--branch" in measured
    assert any(argument.startswith("--source=") for argument in measured)


def test_unsupported_measurement_keeps_the_command(tmp_path):
    command = ["npm", "run", "test:e2e"]
    measured, kind = instrument(command.copy(), "e2e-spec", tmp_path, {}, Path.cwd())
    assert measured == command and kind is None
    assert collect(kind, tmp_path, Path.cwd(), {}) == []


def test_native_node_coverage_keeps_the_same_assistant_test_pattern(tmp_path):
    (tmp_path / "ai-assistant/tests").mkdir(parents=True)
    (tmp_path / "ai-assistant/tests/one.test.ts").write_text("")
    (tmp_path / "ai-assistant/tests/native.integration.test.mjs").write_text("")
    destination = tmp_path / "out"
    destination.mkdir()
    command, kind = instrument(["npm", "test"], "assistant-units", destination, {}, tmp_path)
    assert kind == "node"
    assert "--experimental-test-coverage" in command
    assert command[-1].endswith("one.test.ts")
    assert not any(argument.endswith(".mjs") for argument in command)


def test_zero_statement_measurement_is_not_a_hundred_percent():
    assert percent(0, 0) is None
    assert percent(3, 4) == 75


def test_missing_measurement_provider_keeps_functional_command(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from scripts import test_coverage

    monkeypatch.setattr(test_coverage.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1))
    command = ["uv", "run", "python", "-m", "pytest", "tests", "-q"]
    result, kind = instrument(command.copy(), "python-fast", tmp_path, {}, tmp_path)
    assert result == command
    assert collect(kind, tmp_path, tmp_path, {})[0]["status"] == "unverified"


def test_capabilities_require_each_mapped_behaviour_not_just_a_green_suite():
    rows = capability_results([{"id": "e2e-spec", "status": "passed", "cases": []}])
    assert all(row["status"] == "unverified" for row in rows)
    rows = capability_results([{"id": "e2e-spec", "status": "passed", "cases": [
        {"name": "saves and reopens a wire port", "status": "passed"},
        {"name": "saves and reopens a transactional port", "status": "passed"},
        {"name": "saves and reopens a structured port", "status": "failed"},
    ]}])
    row = next(row for row in rows if row["name"] == "Wire, transactional and structured ports")
    assert row["status"] == "failed"

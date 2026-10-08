"""Exercise profile selection, dependency failures, evidence, and incomplete runs."""

import json
import os
import sys
from pathlib import Path

import pytest

from scripts import test_profiles as runner


@pytest.mark.parametrize("profile", ["fast", "regression"])
def test_profiles_have_exactly_three_short_live_checks_and_no_duplicate_suites(profile):
    suites = runner.select_suites(profile, runner.SCOPES)
    ids = [suite.id for suite in suites]
    assert len(ids) == len(set(ids))
    smoke = [suite for suite in suites if suite.id in {f"live-{case}" for case in runner.SMOKE_CASES}]
    assert len(smoke) == 3
    assert all(suite.timeout == 180 and "--live-model" in suite.command for suite in smoke)
    assert ("live-generalization" in ids) == (profile == "regression")
    for suite in suites:
        assert all(ids.index(dependency) < ids.index(suite.id) for dependency in suite.dependencies)


def test_spec_scope_includes_interface_consumers_but_not_live_evaluation():
    ids = {suite.id for suite in runner.select_suites("integration", {"spec"})}
    assert {"spec-api", "verification-api", "circuit-service-api", "harness", "spec-circuit-flow"} <= ids
    assert not any(id.startswith("live-") for id in ids)


def test_shared_changes_expand_to_all_integration_scopes():
    shared = {suite.id for suite in runner.select_suites("integration", {"shared"})}
    full = {suite.id for suite in runner.select_suites("integration", runner.SCOPES)}
    assert shared == full


def test_combined_scope_is_the_union_without_duplicate_builds():
    combined = runner.select_suites("integration", {"circuit", "verification"})
    expected = {suite.id for scope in ("circuit", "verification")
                for suite in runner.select_suites("integration", {scope})}
    assert {suite.id for suite in combined} == expected
    assert len(combined) == len(expected)


def test_dry_run_does_not_create_output_or_run_commands(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: pytest.fail("Executed a command"))
    output = tmp_path / "evidence"
    assert runner.main(["fast", "--dry-run", "--output", str(output)]) == 0
    assert not output.exists()
    assert "no checks executed" in capsys.readouterr().out


@pytest.mark.parametrize("arguments", [
    ["integration", "--scope", "unknown"], ["integration", "--scope", "all,spec"],
    ["regression", "--scope", "spec"],
])
def test_invalid_selection_is_rejected_before_execution(arguments):
    with pytest.raises(SystemExit) as error:
        runner.main(arguments)
    assert error.value.code == 2


def command_suite(id, code, **kwargs):
    return runner.Suite(id, (sys.executable, "-c", code), ("shared",), "runner", "isolated", **kwargs)


def test_failed_build_blocks_consumers_but_runs_independent_checks(tmp_path):
    build = command_suite("build", "raise SystemExit(17)")
    blocked = command_suite("consumer", "raise SystemExit(0)", dependencies=("build",))
    independent = command_suite("independent", "print('independent check ran')")
    report = {"profile": "integration"}
    assert runner.execute([build, blocked, independent], tmp_path, dict(os.environ), report) == 1
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert [suite["status"] for suite in summary["suites"]] == ["failed", "unverified", "passed"]
    assert summary["incomplete"] is True
    assert not (tmp_path / "consumer").exists()
    assert "independent check ran" in (tmp_path / "independent/command.log").read_text()


def test_missing_live_key_continues_other_checks_and_returns_incomplete(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    unavailable = command_suite("live", "raise SystemExit(0)", requirements=("live",))
    independent = command_suite("independent", "raise SystemExit(0)")
    report = {"profile": "fast"}
    assert runner.execute([unavailable, independent], tmp_path, dict(os.environ), report) == 1
    assert report["status"] == "incomplete"
    assert report["counts"] == {"passed": 1, "failed": 0, "unverified": 1}
    assert "no live inference" in report["suites"][0]["reason"]


def test_failed_command_retains_first_outcome_and_redacts_secrets(tmp_path):
    suite = command_suite("failure", "import os; print(os.environ['OPENAI_API_KEY']); raise SystemExit(5)")
    environment = {**os.environ, "OPENAI_API_KEY": "private-test-key"}
    result = runner.run_suite(suite, tmp_path, environment)
    assert result["status"] == "failed" and result["exit_code"] == 5
    assert "private-test-key" not in (tmp_path / "command.log").read_text()
    assert "[REDACTED]" in (tmp_path / "command.log").read_text()
    assert not (tmp_path / ".command.raw").exists()


def test_browser_registry_does_not_leak_into_isolated_contract_checks(tmp_path):
    suite = command_suite("registry", "import os; print(os.environ.get('SPEC2GDS_SERVICE_CONFIG', 'default'))")
    environment = {**os.environ, "SPEC2GDS_SERVICE_CONFIG": "/private/browser-services.json"}
    result = runner.run_suite(suite, tmp_path, environment)
    assert result["status"] == "passed"
    assert (tmp_path / "command.log").read_text().strip() == "default"


def test_timeout_terminates_the_command_and_reports_failure(tmp_path):
    suite = command_suite("timeout", "import time; time.sleep(30)", timeout=1)
    result = runner.run_suite(suite, tmp_path, dict(os.environ))
    assert result["status"] == "failed"
    assert "execution limit" in result["reason"]
    assert result["duration_seconds"] < 5


def test_junit_skips_are_visible_and_are_not_claimed_as_coverage(tmp_path):
    suite = command_suite("optional", "pass")
    (tmp_path / "pytest.xml").write_text('<testsuite><testcase><skipped message="Missing optional tool" /></testcase></testsuite>')
    result = runner.run_suite(suite, tmp_path, dict(os.environ))
    assert result["skipped"] == [{"message": "Missing optional tool"}]
    assert "outside the executed coverage" in result["coverage_note"]


def test_malformed_junit_is_a_failure_not_a_pass(tmp_path):
    (tmp_path / "pytest.xml").write_text("<testsuite>")
    result = runner.run_suite(command_suite("partial", "pass"), tmp_path, dict(os.environ))
    assert result["status"] == "failed"
    assert "incomplete or malformed" in result["reason"]


def test_generated_authentication_tokens_are_removed_from_nested_text_artifacts(tmp_path):
    child = tmp_path / "nested"
    child.mkdir()
    (child / "assistant.log").write_text("http://127.0.0.1:1234/?token=private-launch-token\n")
    result = runner.run_suite(command_suite("private", "pass"), tmp_path, dict(os.environ))
    assert result["status"] == "passed"
    assert "private-launch-token" not in (child / "assistant.log").read_text()
    assert "token=[REDACTED]" in (child / "assistant.log").read_text()


def test_hardware_prerequisites_do_not_block_independent_cli_checks():
    catalogue = runner.suite_catalogue()
    assert "hardware" not in catalogue["python-extensive"].requirements
    assert "hardware" in catalogue["hardware-extensive"].requirements


def test_report_directory_is_not_overwritten(tmp_path):
    (tmp_path / "summary.json").write_text("original evidence")
    with pytest.raises(SystemExit) as error:
        runner.main(["fast", "--output", str(tmp_path)])
    assert error.value.code == 2
    assert (tmp_path / "summary.json").read_text() == "original evidence"


def test_isolated_environment_uses_distinct_ports_and_private_storage(tmp_path, monkeypatch):
    class Listener:
        port = 10_000

        def __init__(self):
            Listener.port += 1
            self.port = Listener.port

        def bind(self, address):
            assert address == ("127.0.0.1", 0)

        def getsockname(self):
            return "127.0.0.1", self.port

        def close(self):
            pass

    monkeypatch.setattr(runner.socket, "socket", Listener)
    environment = runner.isolated_environment(tmp_path)
    config = json.loads(Path(environment["SPEC2GDS_SERVICE_CONFIG"]).read_text())
    ports = [config[service][surface]["port"] for service in ("spec_editor", "circuit_designer", "ai_assistant")
             for surface in ("service", "ui")]
    assert len(set(ports)) == 6
    assert environment["SPEC2GDS_TEST_ISOLATED"] == "1"
    assert environment["SPEC_EDITOR_STATE_ROOT"].startswith(str(tmp_path))
    assert environment["CIRCUIT_DESIGNER_PREFERENCES_FILE"].startswith(str(tmp_path))
    assert environment["CIRCUIT_DESIGNER_SERVICE_ORIGIN"] == (
        f"http://127.0.0.1:{config['circuit_designer']['service']['port']}")
    assert config["activities"]["scratch_root"].startswith(str(tmp_path))
    assert environment["CIRCUIT_DESIGNER_E2E_API_URL"] == (
        f"http://127.0.0.1:{config['circuit_designer']['service']['port']}/api/circuit-designer/v1")


def test_unavailable_ports_are_reported_without_stopping_non_browser_checks(tmp_path, monkeypatch):
    def unavailable():
        raise PermissionError("Loopback denied")

    monkeypatch.setattr(runner.socket, "socket", unavailable)
    environment = runner.isolated_environment(tmp_path)
    assert "Loopback denied" in environment["SPEC2GDS_TEST_PORT_ERROR"]
    assert Path(environment["SPEC2GDS_SERVICE_CONFIG"]).exists()
    assert runner.prerequisite_errors(("live",), {"OPENAI_API_KEY": "configured"}) == []


def test_suite_inventory_commands_and_paths_are_valid():
    for suite in runner.suite_catalogue().values():
        assert (runner.ROOT / suite.cwd).is_dir()
        if suite.command[0] == "bash":
            assert (runner.ROOT / suite.command[1]).is_file()
        assert set(suite.scopes) <= runner.SCOPES
        assert suite.timeout > 0
        assert suite.risks

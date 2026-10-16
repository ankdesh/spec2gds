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


def test_new_browser_projects_and_fast_smoke_are_selected_without_duplicate_execution():
    fast = {suite.id for suite in runner.select_suites("fast", runner.SCOPES)}
    regression = {suite.id for suite in runner.select_suites("regression", runner.SCOPES)}
    assert "spec-smoke" in fast and "e2e-spec" not in fast
    assert "circuit-smoke" in fast and "e2e-circuit" not in fast
    assert "spec-smoke" not in regression
    assert "circuit-smoke" not in regression
    assert {"e2e-spec", "e2e-circuit", "e2e-assistant", "e2e-verification"} <= regression
    ordered = [suite.id for suite in runner.select_suites("regression", runner.SCOPES)]
    assert all(ordered.index(f"e2e-{project}") < ordered.index("live-generalization")
               for project in ("spec", "circuit", "assistant", "verification"))
    verification = {suite.id for suite in runner.select_suites("integration", {"verification"})}
    assert "e2e-verification" in verification and "e2e-assistant" not in verification
    smoke = runner.suite_catalogue()["spec-smoke"]
    assert smoke.command[-2:] == ("--grep", "@smoke")
    circuit_smoke = runner.suite_catalogue()["circuit-smoke"]
    assert circuit_smoke.command[-2:] == ("--grep", "@smoke")


def test_coverage_dry_run_preserves_selection_and_does_not_write(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: pytest.fail("Executed a command"))
    output = tmp_path / "coverage"
    assert runner.main(["fast", "--coverage", "--dry-run", "--output", str(output)]) == 0
    assert not output.exists()
    assert "spec-smoke" in capsys.readouterr().out


def test_junit_failed_case_cannot_be_hidden_by_a_successful_process(tmp_path):
    (tmp_path / "pytest.xml").write_text('<testsuite><testcase name="atomic rollback" time="0.1"><failure /></testcase></testsuite>')
    result = runner.run_suite(command_suite("evidence", "pass"), tmp_path, dict(os.environ))
    assert result["status"] == "failed"
    assert result["cases"][0]["status"] == "failed"


def test_browser_skipped_cases_are_unverified_and_recorded_per_case(tmp_path):
    evidence = tmp_path / "playwright"
    evidence.mkdir()
    (evidence / "results.json").write_text(json.dumps({"suites": [{"specs": [
        {"title": "saved source", "tests": [{"results": [{"status": "passed", "duration": 100}]}]},
        {"title": "missing tool", "tests": [{"annotations": [{"type": "skip", "description": "Docling unavailable"}],
                                               "results": [{"status": "skipped", "duration": 0}]}]},
    ]}]}))
    result = runner.run_suite(command_suite("e2e-spec", "pass"), tmp_path, dict(os.environ))
    assert [case["status"] for case in result["cases"]] == ["passed", "unverified"]
    assert "Docling is unavailable" in result["cases"][1]["explanation"]
    page = runner.render_report({"profile": "integration", "suites": [result]}, tmp_path)
    assert "Docling is unavailable" in page
    assert "Explanation" in page


def test_browser_success_requires_nonempty_evidence(tmp_path):
    result = runner.run_suite(command_suite("e2e-spec", "pass"), tmp_path, dict(os.environ))
    assert result["status"] == "failed"
    assert "evidence report" in result["reason"]


def test_missing_requested_measurement_keeps_functional_pass_but_profile_incomplete(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "run_suite", lambda *a: {"id": "unit", "status": "passed", "code_coverage": [
        {"name": "Unit coverage", "status": "unverified", "note": "Measurement unavailable."},
    ]})
    report = {"profile": "fast"}
    assert runner.execute([command_suite("unit", "pass")], tmp_path, dict(os.environ), report) == 1
    assert report["status"] == "incomplete"
    assert report["suites"][0]["status"] == "passed"
    assert "This run is incomplete" in (tmp_path / "summary.html").read_text()


def test_interrupt_preserves_completed_results_and_marks_remaining_checks_unverified(tmp_path, monkeypatch):
    original = runner.run_suite

    def run(suite, *args):
        if suite.id == "interrupted":
            raise KeyboardInterrupt
        return original(suite, *args)

    monkeypatch.setattr(runner, "run_suite", run)
    report = {"profile": "regression"}
    suites = [command_suite("completed", "pass"), command_suite("interrupted", "pass"), command_suite("remaining", "pass")]
    assert runner.execute(suites, tmp_path, dict(os.environ), report) == 130
    assert [suite["status"] for suite in report["suites"]] == ["passed", "unverified", "unverified"]
    assert report["status"] == "incomplete"
    assert not (tmp_path / "remaining").exists()


def test_cli_sigterm_handler_records_interruption_and_restores_previous_handler(tmp_path, monkeypatch):
    import signal

    before = signal.getsignal(signal.SIGTERM)
    monkeypatch.setattr(runner, "select_suites", lambda *args: [command_suite("interrupted", "pass")])
    monkeypatch.setattr(runner, "tool_version", lambda *args: "test version")

    def terminate(*args):
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)

    monkeypatch.setattr(runner, "run_suite", terminate)
    output = tmp_path / "signal-report"
    assert runner.main(["regression", "--output", str(output)]) == 130
    assert json.loads((output / "summary.json").read_text())["status"] == "incomplete"
    assert signal.getsignal(signal.SIGTERM) is before


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
    html = (tmp_path / "summary.html").read_text()
    assert "A required earlier check did not pass." in html
    assert "This run is incomplete." in html


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


def test_adder_regression_selection_retains_other_suites_and_original_repeats(capsys):
    assert runner.main(["regression", "--rtl-cases", "adder_4,adder_8,adder_13", "--dry-run"]) == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert [row["id"] for row in rows] == [suite.id for suite in runner.select_suites("regression", runner.SCOPES)]
    rtl = next(row for row in rows if row["id"] == "live-generalization")
    assert rtl["command"][-2:] == ["--case", "adder_4,adder_8,adder_13"]
    assert "--repeats" not in rtl["command"]
    assert sum(row["id"].startswith("live-") for row in rows) == 4


@pytest.mark.parametrize("arguments", [["fast", "--rtl-cases", "adder_8"], ["regression", "--rtl-cases", "adder_8,unknown"], ["regression", "--rtl-cases", "adder_8,adder_8"]])
def test_invalid_live_case_selection_is_rejected_before_execution(arguments):
    with pytest.raises(SystemExit) as error:
        runner.main([*arguments, "--dry-run"])
    assert error.value.code == 2

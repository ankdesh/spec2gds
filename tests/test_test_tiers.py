"""The tier runner must expose failures and avoid running stale build consumers."""

import json
import os
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_RUNNER = _ROOT / "scripts/test-all.sh"


def _run(tmp_path, tier, *options, failure=""):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.jsonl"
    command = """#!/usr/bin/python3
import json, os, sys
from pathlib import Path
call = [Path(sys.argv[0]).name, *sys.argv[1:]]
with open(os.environ['TIER_TEST_LOG'], 'a') as log:
    log.write(json.dumps(call) + '\\n')
failure = os.environ['TIER_TEST_FAILURE']
if failure == 'python' and call[0] == 'uv':
    sys.exit(17)
if failure == 'frontend' and call == ['npm', '--prefix', 'circuit-designer', 'run', 'build']:
    sys.exit(18)
"""
    for name in ("uv", "npm"):
        executable = bin_dir / name
        executable.write_text(command)
        executable.chmod(0o755)
    result = subprocess.run(
        ["bash", str(_RUNNER), tier, *options],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "TIER_TEST_LOG": str(log),
            "TIER_TEST_FAILURE": failure,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return result, calls


def test_dry_run_previews_both_tiers_without_invoking_dependencies(tmp_path):
    result, calls = _run(tmp_path, "all", "--dry-run")
    assert result.returncode == 0
    assert not calls
    assert "Python fundamentals" in result.stdout
    assert "Python extensive" in result.stdout
    assert "Assistant browser" in result.stdout
    assert "no checks executed" in result.stdout


def test_failed_python_check_still_runs_independent_units_and_fails_the_runner(tmp_path):
    result, calls = _run(tmp_path, "fundamental", failure="python")
    assert result.returncode == 1
    assert "Python fundamentals (exit 17)" in result.stdout
    assert ["npm", "--prefix", "circuit-designer", "test"] in calls
    assert ["npm", "--prefix", "ai-assistant", "test"] in calls
    assert all("build" not in call and "test:ui" not in call for call in calls)
    assert calls[0][-2:] == ["-m", "not extensive"]
    assert "--ignore=tests/test_tutorials.py" in calls[0]


def test_failed_frontend_build_prevents_browser_checks_but_keeps_backend_checks(tmp_path):
    result, calls = _run(tmp_path, "extensive", failure="frontend")
    assert result.returncode == 1
    assert "Build Circuit Designer and editor (exit 18)" in result.stdout
    python_call = next(call for call in calls if call[0] == "uv")
    assert python_call[-2:] == ["-m", "extensive"]
    assert "--ignore=tests/test_tutorials.py" in python_call
    assert ["npm", "--prefix", "ai-assistant", "run", "test:harness"] in calls
    assert not any(any(argument.startswith("test:e2e") for argument in call) for call in calls)
    assert not any("test:ui" in call for call in calls)

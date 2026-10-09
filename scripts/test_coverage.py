"""Optional measurement for selected checks. Never select additional functional tests."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def instrument(command: list[str], suite_id: str, destination: Path, env: dict, root: Path):
    directory = destination / "coverage"
    directory.mkdir(exist_ok=True)
    if "pytest" in command and "python" in command:
        try:
            available = subprocess.run([str(root / ".venv/bin/python"), "-c", "import coverage"],
                                       capture_output=True, timeout=10).returncode == 0
        except OSError:
            available = False
        if not available:
            return command, "unavailable-python"
        index = command.index("python") + 1
        sources = ",".join(str(root / path) for path in ("spec2gds", "runtime", "testplan-service/src", "scripts"))
        command[index:index] = ["-m", "coverage", "run", "--branch", f"--source={sources}",
                                f"--data-file={directory / '.coverage'}"]
        return command, "python"
    if suite_id == "circuit-units":
        if not (root / "circuit-designer/node_modules/@vitest/coverage-v8").exists():
            return command, "unavailable-vitest"
        env["SPEC2GDS_TEST_COVERAGE_DIR"] = str(directory)
        return command, "vitest"
    if suite_id in {"circuit-service-api", "circuit-client-http-api"}:
        if not (root / "circuit-designer/node_modules/@vitest/coverage-v8").exists():
            return command, "unavailable-vitest"
        command += ["--", "--coverage", "--coverage.include=src/**",
                    "--coverage.reporter=json-summary", "--coverage.reporter=html",
                    f"--coverage.reportsDirectory={directory}"]
        return command, "vitest"
    if suite_id == "assistant-units":
        # Keep the same test file pattern and tsx loader as npm test.
        files = sorted(str(path) for path in (root / "ai-assistant/tests").glob("*.test.ts"))
        return ["node", "--experimental-test-coverage", "--import", "tsx", "--test",
                "--test-coverage-include=**/ai-assistant/src/**",
                "--test-coverage-exclude=**/tests/**",
                "--test-reporter=spec", "--test-reporter-destination=stdout",
                "--test-reporter=lcov", f"--test-reporter-destination={directory / 'node.lcov'}", *files], "node"
    return command, None


def collect(kind: str | None, destination: Path, root: Path, env: dict) -> list[dict]:
    directory = destination / "coverage"
    rows = []
    if kind and kind.startswith("unavailable-"):
        return [{"name": "Code coverage", "status": "unverified",
                 "note": "The measurement tool is unavailable. Functional checks still ran without measurement."}]
    if kind == "python":
        result = subprocess.run([str(root / ".venv/bin/python"), "-m", "coverage", "json",
                                 f"--data-file={directory / '.coverage'}", "-o", str(directory / "python.json")],
                                cwd=root, env=env, capture_output=True, text=True, timeout=30)
        if result.returncode:
            return [{"name": "Python measurement", "status": "unverified", "note": "Measurement is unavailable for this check."}]
        data = json.loads((directory / "python.json").read_text())
        groups = {}
        for filename, file in data["files"].items():
            name = ("Verification Planner" if "testplan-service/" in filename else
                    "Shared runtime" if filename.startswith("runtime/") else
                    "Test and command support" if filename.startswith("scripts/") else "Spec service")
            totals = groups.setdefault(name, [0, 0, 0, 0])
            summary = file["summary"]
            for index, key in enumerate(("covered_lines", "num_statements", "covered_branches", "num_branches")):
                totals[index] += summary.get(key, 0)
        for name, (lines, total, branches, branch_total) in groups.items():
            rows.append({"name": name, "lines": percent(lines, total), "branches": percent(branches, branch_total),
                         "note": "Includes untested source. This measurement covers this check only."})
    if kind == "vitest":
        for path in sorted(directory.rglob("coverage-summary.json")):
            total = json.loads(path.read_text())["total"]
            name = path.parent.name if path.parent != directory else "Circuit service package"
            names = {"spec2gds-spec-editor": "Spec Editor", "spec2gds-document-a2ui-react": "Shared Spec rendering",
                     "spec2gds-document-core": "Shared document client", "spec2gds-circuit-core": "Circuit data rules",
                     "spec2gds-circuit-service": "Circuit service", "spec2gds-circuit-client-http": "Circuit service client",
                     "spec2gds-circuit-app-react": "Circuit Designer", "spec2gds-circuit-designer-standalone": "Circuit Designer",
                     "spec2gds-circuit-layout": "Circuit layout", "spec2gds-circuit-react": "Circuit canvas",
                     "spec2gds-observability": "Service logging"}
            rows.append({"name": names.get(name, name.replace("spec2gds-", "").replace("-", " ").capitalize()),
                         "lines": total["lines"]["pct"], "branches": total["branches"]["pct"],
                         "note": "Includes untested package source. This measurement covers this check only."})
        if not rows:
            rows.append({"name": "Vitest measurement", "status": "unverified", "note": "Measurement is unavailable for this check."})
    if kind == "node":
        path = directory / "node.lcov"
        totals = {key: 0 for key in ("LF", "LH", "BRF", "BRH")}
        if path.exists():
            for line in path.read_text().splitlines():
                key, _, value = line.partition(":")
                if key in totals:
                    totals[key] += int(value)
            rows.append({"name": "AI Assistant", "lines": percent(totals["LH"], totals["LF"]),
                         "branches": percent(totals["BRH"], totals["BRF"]),
                         "note": "Observed loaded files only; experimental Node measurement. No environment-wide percentage is claimed."})
        else:
            rows.append({"name": "AI Assistant", "status": "unverified", "note": "Measurement is unavailable for this check."})
    return rows


def percent(covered: int, total: int) -> float | None:
    return round(100 * covered / total, 1) if total else None

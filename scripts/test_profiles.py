"""Select local regression suites and report their evidence without hiding gaps.

The legacy shell tiers remain separate. This runner builds a dependency graph
from existing commands, uses isolated browser configuration, and writes one
report for each invocation. Model credentials are never part of the report.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

if __package__:
    from .test_coverage import collect, instrument
    from .test_report import render_report
else:
    from test_coverage import collect, instrument
    from test_report import render_report

ROOT = Path(__file__).resolve().parents[1]
SCOPES = {"spec", "circuit", "assistant", "verification", "activities", "shared"}
PROFILES = ("fast", "browser-smoke", "live-smoke", "integration", "regression")
SMOKE_CASES = ("description", "wire-range", "restricted-description")
SCENARIOS = ("automatic", "restricted", "live", "binding", "repeated", "architecture")


@dataclass(frozen=True)
class Suite:
    """A command's selection, dependencies, prerequisites, and evidence type."""

    id: str
    command: tuple[str, ...]
    scopes: tuple[str, ...]
    layer: str
    evidence: str
    cwd: str = "."
    dependencies: tuple[str, ...] = ()
    requirements: tuple[str, ...] = ()
    timeout: int = 900
    risks: tuple[str, ...] = ()


def suite_catalogue() -> dict[str, Suite]:
    """Keep selection metadata together with the command that supplies evidence."""
    suites: dict[str, Suite] = {}

    def add(id, command, scopes, layer, evidence, **kwargs):
        risk_map = {"spec": ("source integrity", "revision control"),
                    "circuit": ("source boundary", "topology"),
                    "assistant": ("approval", "binding", "model outcome"),
                    "verification": ("snapshot identity", "review checkpoints"),
                    "activities": ("determinism", "source boundary"),
                    "shared": ("configuration", "process isolation")}
        kwargs["risks"] = tuple(dict.fromkeys(risk for scope in scopes for risk in risk_map[scope]))
        suites[id] = Suite(id, tuple(command), tuple(scopes), layer, evidence, **kwargs)

    def python(id, paths, scopes, marker="not extensive", dependencies=(), tools=()):
        add(id, ["uv", "run", "--no-sync", "python", "-m", "pytest", "-q",
                 "--strict-markers", *paths, "-m", marker, "-ra",
                 "--junitxml={output}/pytest.xml"], scopes, "service/API", "isolated",
            dependencies=dependencies, requirements=("python", *tools))

    python("python-baseline", [
        "tests/spec/spec_format/test_http_contracts.py",
        "spec_catalog_service/tests/test_source_contracts.py",
        "tests/spec/activities/test_activity_sdk.py",
        "testplan-service/tests/test_layer1_acceptance.py",
        "tests/test_service_config.py",
    ], sorted(SCOPES))
    python("python-fast", ["tests", "testplan-service/tests", "spec_catalog_service/tests",
                           "--ignore=tests/test_tutorials.py"], sorted(SCOPES))
    add("circuit-units", ["npm", "test"], ["spec", "circuit", "shared"],
        "unit/component/API", "isolated", cwd="circuit-designer", requirements=("circuit",))
    add("assistant-units", ["npm", "test"], ["assistant"], "unit/contract", "isolated",
        cwd="ai-assistant", requirements=("assistant",))
    add("scenario-units", ["npm", "run", "test:fixture"], ["spec", "assistant"],
        "test infrastructure", "isolated", cwd="tests/ui-scenarios", requirements=("scenarios",))
    add("build-assistant", ["npm", "run", "build"], ["assistant"], "build", "build",
        cwd="ai-assistant", requirements=("assistant",))
    add("build-circuit", ["npm", "run", "build"], ["spec", "circuit"], "build", "build",
        cwd="circuit-designer", requirements=("circuit",))
    add("schema-check", ["npm", "run", "generate:check"], ["spec", "circuit", "shared"],
        "contract", "generated-contract", cwd="circuit-designer", requirements=("circuit",))
    python("python-extensive", ["tests/spec/spec_format"], ["spec", "assistant"],
           marker="extensive", dependencies=("build-assistant",))
    python("hardware-extensive", ["tests/spec/activities"], ["spec", "activities"],
           marker="extensive", tools=("hardware",))
    python("spec-api", ["tests/spec/spec_format", "tests/spec/importers", "spec_catalog_service/tests"],
           ["spec", "circuit", "assistant", "activities"])
    python("verification-api", ["testplan-service/tests"], ["spec", "verification", "activities"])
    python("activity-api", ["tests/spec/activities"], ["spec", "activities"])
    python("shared-api", ["tests/test_service_registry.py", "tests/test_service_config.py", "tests/test_serve_all.py", "tests/test_observability.py",
                           "tests/test_log_viewer.py", "tests/test_terminology_compatibility.py",
                           "tests/test_test_tiers.py", "tests/test_test_profiles.py",
                           "tests/test_test_report.py", "tests/test_test_coverage.py"], ["shared"])
    for package in ("service", "client-http"):
        add(f"circuit-{package}-api", ["npm", "run", "test", "--workspace",
                                      f"@spec2gds/circuit-{package}"], ["spec", "circuit"],
            "service/client integration", "isolated", cwd="circuit-designer",
            requirements=("circuit",))
    add("harness", ["npm", "run", "test:harness"], ["spec", "circuit", "assistant"],
        "integration", "real-Harness/fixture-services-model", cwd="ai-assistant",
        dependencies=("build-assistant",), requirements=("harness",))
    for id, command, scopes, cwd, deps in (
        ("spec-browser", ["npm", "run", "test:e2e:editor"], ["spec"], "circuit-designer",
         ("build-circuit",)),
        ("circuit-browser", ["npm", "run", "test:e2e"], ["circuit"], "circuit-designer",
         ("build-circuit",)),
        ("assistant-browser", ["npm", "run", "test:ui"], ["assistant"], "ai-assistant",
         ("build-assistant",)),
    ):
        add(id, command, scopes, "browser", "fixture-browser", cwd=cwd,
            dependencies=deps, requirements=("browser",))
    for scenario in SCENARIOS:
        add(f"scenario-{scenario}", ["bash", "tests/ui-scenarios/run-test.sh", "--scenario",
                                    scenario, "--output", "{output}"],
            ["spec", "assistant", "activities"], "end-to-end", "real-services/fixture-model",
            dependencies=("build-assistant", "build-circuit"),
            requirements=("python", "browser", "harness", "scenarios"), timeout=600)
    for project, scopes, deps in (
        ("spec", ["spec"], ("build-circuit",)),
        ("circuit", ["spec", "circuit"], ("build-circuit",)),
        ("assistant", ["spec", "assistant"], ("build-assistant", "build-circuit")),
        ("verification", ["spec", "verification", "activities"], ()),
    ):
        add(f"e2e-{project}", ["npm", "run", "test:e2e", "--", "--project", project],
            scopes, "end-to-end", "real-services/fixture-model" if project == "assistant" else "real-services",
            cwd="tests/ui-scenarios", dependencies=deps,
            requirements=("python", "browser", "scenarios", *(("harness",) if project == "assistant" else ())), timeout=1200)
    add("spec-smoke", ["npm", "run", "test:e2e", "--", "--project", "spec", "--grep", "@smoke"],
        ["spec"], "end-to-end", "real-services", cwd="tests/ui-scenarios",
        dependencies=("build-circuit",), requirements=("python", "browser", "scenarios"), timeout=300)
    add("circuit-smoke", ["npm", "run", "test:e2e", "--", "--project", "circuit", "--grep", "@smoke"],
        ["spec", "circuit"], "end-to-end", "real-services", cwd="tests/ui-scenarios",
        dependencies=("build-circuit",), requirements=("python", "browser", "scenarios"), timeout=300)
    # The presentation flow also starts Circuit service/UI and saves back to Spec.
    add("spec-circuit-flow", ["bash", "tests/ui-scenarios/run-test.sh", "--scenario", "automatic",
                              "--presentation", "--output", "{output}"], ["spec", "circuit"],
        "end-to-end", "real-services/fixture-model", dependencies=("build-assistant", "build-circuit"),
        requirements=("python", "browser", "harness", "scenarios"), timeout=600)
    for case in SMOKE_CASES:
        add(f"live-{case}", ["bash", "tests/ui-scenarios/run-test.sh", "--scenario", "smoke",
                             "--smoke-case", case, "--live-model", "--output", "{output}"],
            ["spec", "assistant"], "end-to-end", "live-model/real-services",
            dependencies=("build-assistant", "build-circuit"),
            requirements=("python", "browser", "harness", "scenarios", "live"), timeout=180)
    add("live-generalization", ["node", "--import", "tsx", "runner/run_generalization.ts",
                                 "--output", "{output}"], ["spec", "assistant", "activities"],
        "quality evaluation", "live-model/hardware-simulation", cwd="tests/ui-scenarios",
        dependencies=("build-assistant", "build-circuit"),
        requirements=("python", "browser", "harness", "scenarios", "live", "hardware"),
        timeout=21_600)
    add("evaluation-catalogue", ["npm", "run", "eval", "--", "--output", "{output}"],
        ["assistant"], "catalogue validation", "catalogued-only", cwd="ai-assistant",
        dependencies=("build-assistant",), requirements=("assistant",))
    return suites


def select_suites(profile: str, scopes: set[str]) -> list[Suite]:
    """Expand prerequisites once; integration includes consumers of Spec contracts."""
    catalogue = suite_catalogue()
    fundamentals = ["circuit-units", "assistant-units", "scenario-units", "schema-check"]
    live = [f"live-{case}" for case in SMOKE_CASES]
    if profile == "fast":
        selected = ["python-baseline", *fundamentals]
    elif profile == "browser-smoke":
        selected = ["spec-smoke", "circuit-smoke"]
    elif profile == "live-smoke":
        selected = live
    elif profile == "regression":
        selected = ["python-fast", *fundamentals, "python-extensive", "hardware-extensive", "harness", "spec-browser", "circuit-browser",
                    "assistant-browser", "evaluation-catalogue", "spec-circuit-flow"]
        selected += [f"scenario-{scenario}" for scenario in SCENARIOS]
        selected += [f"e2e-{project}" for project in ("spec", "circuit", "assistant", "verification")]
        selected += live + ["live-generalization"]
    else:
        if "shared" in scopes:
            scopes = SCOPES.copy()
        candidates = ["spec-api", "verification-api", "activity-api", "shared-api",
                      "circuit-service-api", "circuit-client-http-api", "schema-check", "harness",
                      "spec-browser", "circuit-browser", "assistant-browser", "spec-circuit-flow"]
        candidates += [f"scenario-{scenario}" for scenario in SCENARIOS]
        candidates += [f"e2e-{project}" for project in ("spec", "circuit", "assistant", "verification")]
        if "activities" in scopes:
            candidates.append("hardware-extensive")
        if scopes.intersection({"spec", "assistant"}):
            candidates.append("python-extensive")
        selected = [id for id in candidates if scopes.intersection(catalogue[id].scopes)]
    ordered: dict[str, Suite] = {}

    def include(id):
        for dependency in catalogue[id].dependencies:
            include(dependency)
        ordered[id] = catalogue[id]

    for id in selected:
        include(id)
    return list(ordered.values())


def tool_version(command: list[str], env: dict[str, str]) -> str:
    try:
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else "unavailable"
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"


def prerequisite_errors(requirements: tuple[str, ...], env: dict[str, str]) -> list[str]:
    """Inspect availability, without installing packages or contacting a provider."""
    errors = []
    paths = {"python": ".venv/bin/python", "circuit": "circuit-designer/node_modules",
             "assistant": "ai-assistant/node_modules", "scenarios": "tests/ui-scenarios/node_modules"}
    for requirement in requirements:
        if requirement in paths and not (ROOT / paths[requirement]).exists():
            errors.append(f"Missing {paths[requirement]}; run scripts/setup-all.sh.")
        if requirement == "python" and not shutil.which("uv", path=env.get("PATH")):
            errors.append("uv is unavailable.")
        if requirement in {"circuit", "assistant", "scenarios", "harness", "browser"}:
            version = tool_version(["node", "--version"], env)
            parsed = re.match(r"^v(\d+)\.(\d+)\.", version)
            if not parsed or (int(parsed[1]), int(parsed[2])) < (24, 2):
                errors.append("Profiles require Node.js 24.2 or newer on PATH.")
            if not shutil.which("npm", path=env.get("PATH")):
                errors.append("npm is unavailable.")
        if requirement == "harness":
            runtime = ROOT / "ai-assistant/node_modules/@ankdesh/dsh/lib/bin.js"
            if not runtime.exists():
                errors.append("Harness packages are unavailable; run npm run install:packages in ai-assistant.")
        if requirement == "browser":
            if env.get("SPEC2GDS_TEST_PORT_ERROR"):
                errors.append(env["SPEC2GDS_TEST_PORT_ERROR"])
            directory = Path(env["PLAYWRIGHT_BROWSERS_PATH"])
            if not directory.exists() or not list(directory.glob("chromium*")):
                errors.append("Playwright Chromium is unavailable; run scripts/setup-all.sh.")
        if requirement == "live" and not env.get("OPENAI_API_KEY", "").strip():
            errors.append("OPENAI_API_KEY is unavailable; no live inference was performed.")
        if requirement == "hardware":
            for tool in ("verilator", "make", "c++"):
                if not shutil.which(tool, path=env.get("PATH")):
                    errors.append(f"Required hardware tool {tool} is unavailable.")
            if shutil.which("verilator", path=env.get("PATH")):
                if not tool_version(["verilator", "--version"], env).startswith("Verilator 5."):
                    errors.append("Verilator 5.x is required.")
    return list(dict.fromkeys(errors))


def isolated_environment(output: Path, *, allocate_ports: bool = True) -> dict[str, str]:
    """Separate local browser checks from any running designer environment."""
    env = dict(os.environ)
    env.setdefault("UV_CACHE_DIR", str(output / "uv-cache"))
    env.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / "circuit-designer/.playwright-browsers"))
    env["AI_ASSISTANT_UI_TEST_DEPS"] = env.get("AI_ASSISTANT_UI_TEST_DEPS", str(ROOT / "circuit-designer"))
    env["SPEC2GDS_TEST_ISOLATED"] = "1"
    config = json.loads((ROOT / "config/services.json").read_text())
    config["public_host"] = "127.0.0.1"
    config["spec_editor"]["spec_root"] = str(output)
    sockets = []
    try:
        for name in ("spec_editor", "circuit_designer", "ai_assistant", "verification_planner", "spec_catalog"):
            surfaces = ("service", "ui", "dev_ui") if name == "spec_editor" else ("service", "ui")
            for surface in surfaces:
                endpoint = config[name][surface]
                endpoint["host"] = "127.0.0.1"
                if surface == "ui" and name != "circuit_designer":
                    endpoint["port"] = config[name]["service"]["port"]
                elif allocate_ports:
                    listener = socket.socket()
                    sockets.append(listener)
                    listener.bind(("127.0.0.1", 0))
                    endpoint["port"] = listener.getsockname()[1]
    except OSError as error:
        env["SPEC2GDS_TEST_PORT_ERROR"] = f"Isolated browser ports are unavailable: {error}"
    finally:
        for listener in sockets:
            listener.close()
    config["spec_catalog"]["catalog_root"] = str(ROOT / "spec_catalog_service/catalog")
    config["spec_catalog"]["state_dir"] = str(output / "catalog-state")
    config["logging"]["enabled"] = False
    config["logging"]["file"] = str(output / "events.jsonl")
    config["activities"]["scratch_root"] = str(output / "generated")
    config["circuit_designer"]["preferences_file"] = str(output / "preferences.json")
    config_path = output / "services.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    temporary = output / "TEMP_process"
    temporary.mkdir(exist_ok=True)
    env.update(SPEC2GDS_TEST_SERVICE_CONFIG=str(config_path),
               TMPDIR=str(temporary), TMP=str(temporary), TEMP=str(temporary),
               SPEC_EDITOR_STATE_ROOT=str(output / "spec-state"),
               ASSISTANT_STATE=str(output / "assistant-state"),
               SPEC_DOCUMENT_ROOT=str(output / "spec-documents"),
               SPEC2GDS_SCRATCH_ROOT=str(output / "scratch"))
    return env


def redact(text: str, env: dict[str, str]) -> str:
    """Prevent configured secret values from reaching runner logs or reports."""
    for name, value in env.items():
        if value and len(value) >= 4 and any(part in name.upper() for part in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            text = text.replace(value, "[REDACTED]")
    text = re.sub(r"([?&](?:token|access_token|api_key|key|auth)=)[^&\s\"'<>]+",
                  r"\1[REDACTED]", text, flags=re.IGNORECASE)
    return text


def stop_process(process: subprocess.Popen) -> None:
    """Give the scenario harness time to stop its own isolated service groups."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    finally:
        # npm/uv wrappers can exit before descendants finish. The group belongs
        # to this command; remove surviving members without touching other servers.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_suite(suite: Suite, destination: Path, env: dict[str, str]) -> dict:
    """Bound execution and retain the original outcome; do not retry failures."""
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    command = [argument.replace("{output}", str(destination)) for argument in suite.command]
    result = {**asdict(suite), "command": command, "output": str(destination),
              "status": "failed", "duration_seconds": 0.0}
    started = time.monotonic()
    raw_log = destination / ".command.raw"
    command_env = dict(env)
    command_env["SPEC2GDS_TEST_OUTPUT_DIR"] = str(destination / "playwright")
    coverage_kind = None
    if env.get("SPEC2GDS_TEST_COVERAGE") == "1":
        command, coverage_kind = instrument(command, suite.id, destination, command_env, ROOT)
        result["command"] = command
    if suite.evidence in {"isolated", "generated-contract", "catalogued-only"}:
        # Unit/API fixtures control their own registry. Browser configuration
        # must not change the tracked-default contract that those suites verify.
        command_env.pop("SPEC2GDS_TEST_SERVICE_CONFIG", None)
        command_env.pop("SPEC2GDS_PUBLIC_HOST", None)
    try:
        with raw_log.open("w") as stream:
            process = subprocess.Popen(command, cwd=ROOT / suite.cwd, env=command_env, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                result["exit_code"] = process.wait(timeout=suite.timeout)
                result["status"] = "passed" if result["exit_code"] == 0 else "failed"
            except subprocess.TimeoutExpired:
                stop_process(process)
                result["reason"] = f"Exceeded the {suite.timeout}-second execution limit."
            except KeyboardInterrupt:
                stop_process(process)
                raise
    except OSError as error:
        result.update(status="unverified", reason=str(error))
    finally:
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        log = redact(raw_log.read_text(errors="replace") if raw_log.exists() else "", env)
        (destination / "command.log").write_text(log)
        raw_log.unlink(missing_ok=True)
        for path in destination.rglob("*"):
            if path.is_file() and path.suffix in {".log", ".json", ".jsonl", ".xml"}:
                text = path.read_text(errors="replace")
                cleaned = redact(text, env)
                if cleaned != text:
                    path.write_text(cleaned)
    junit = destination / "pytest.xml"
    if junit.exists():
        try:
            skipped = [item.attrib for item in ET.parse(junit).iter("skipped")]
            result["cases"] = [{"name": item.get("name", "Additional check"),
                                "status": "failed" if item.find("failure") is not None or item.find("error") is not None else
                                "unverified" if item.find("skipped") is not None else "passed",
                                "duration_seconds": float(item.get("time", 0))}
                               for item in ET.parse(junit).iter("testcase")]
            result["skipped"] = skipped
            if skipped:
                result["coverage_note"] = "Skipped checks are outside the executed coverage; see pytest.xml."
        except (ET.ParseError, ValueError):
            result.update(status="failed", reason="The Python evidence report is incomplete or malformed.")
    playwright = destination / "playwright/results.json"
    if playwright.exists():
        try:
            def browser_cases(node):
                for spec in node.get("specs", []):
                    for test in spec.get("tests", []):
                        runs = test.get("results", [])
                        status = runs[-1].get("status") if runs else "skipped"
                        yield {"name": spec["title"], "status": "passed" if status == "passed" else
                               "unverified" if status in {"skipped", "interrupted"} else "failed",
                               "explanation": "Docling is unavailable; real document import remains unverified."
                               if status == "skipped" and any("Docling" in item.get("description", "")
                                   for item in test.get("annotations", [])) else "",
                               "duration_seconds": sum(run.get("duration", 0) for run in runs) / 1000}
                for child in node.get("suites", []):
                    yield from browser_cases(child)
            result["cases"] = list(browser_cases(json.loads(playwright.read_text())))
            result["skipped"] = [{"message": case["name"]} for case in result["cases"] if case["status"] == "unverified"]
        except (ValueError, KeyError, TypeError):
            result.update(status="failed", reason="The browser evidence report is incomplete or malformed.")
    if suite.id.startswith("e2e-") or suite.id in {"spec-smoke", "circuit-smoke"}:
        if not result.get("cases") and result["status"] == "passed":
            result.update(status="failed", reason="The browser evidence report is incomplete or malformed.")
    if result["status"] == "passed" and any(case["status"] == "failed" for case in result.get("cases", [])):
        result.update(status="failed", reason="The evidence contains a failed check.")
    result["code_coverage"] = collect(coverage_kind, destination, ROOT, command_env)
    return result


def execute(suites: list[Suite], output: Path, env: dict[str, str], report: dict) -> int:
    """Continue independent checks and report blocked consumers as unverified."""
    outcomes: dict[str, dict] = {}
    interrupted = False
    for suite in suites:
        print(f">>> {suite.id} [{suite.evidence}]", flush=True)
        blocked = [id for id in suite.dependencies if outcomes[id]["status"] != "passed"]
        errors = prerequisite_errors(suite.requirements, env)
        if interrupted or blocked or errors:
            reasons = (["Run interrupted."] if interrupted else [])
            reasons += [f"Prerequisite check {id} did not pass." for id in blocked] + errors
            outcome = {**asdict(suite), "status": "unverified", "reason": " ".join(reasons),
                       "duration_seconds": 0.0}
        else:
            try:
                outcome = run_suite(suite, output / suite.id, env)
            except KeyboardInterrupt:
                interrupted = True
                outcome = {**asdict(suite), "status": "unverified", "reason": "Run interrupted."}
        outcomes[suite.id] = outcome
        print(f"    {outcome['status']}: {outcome.get('reason', '')}", flush=True)
        if outcome["status"] == "failed":
            print(f"    Log: {output / suite.id / 'command.log'}", flush=True)
        report["suites"] = list(outcomes.values())
        report["status"] = "running"
        write_reports(report, output, env)
    states = {outcome["status"] for outcome in outcomes.values()}
    measurement_missing = any(row.get("status") == "unverified" for outcome in outcomes.values() for row in outcome.get("code_coverage", []))
    report["status"] = "failed" if "failed" in states else "incomplete" if "unverified" in states or measurement_missing else "passed"
    report["incomplete"] = "unverified" in states or measurement_missing
    report["counts"] = {state: sum(item["status"] == state for item in outcomes.values())
                        for state in ("passed", "failed", "unverified")}
    write_reports(report, output, env)
    print(f"{report['profile']}: {report['status']}. Report: {output / 'summary.html'}", flush=True)
    return 130 if interrupted else 1 if states != {"passed"} or measurement_missing else 0


def write_reports(report: dict, output: Path, env: dict[str, str]) -> None:
    """Keep structured diagnostics and make the human report the primary result."""
    safe_json = redact(json.dumps(report, indent=2), env)
    (output / "summary.json").write_text(safe_json + "\n", encoding="utf-8")
    safe_report = json.loads(safe_json)
    (output / "summary.html").write_text(redact(render_report(safe_report, output), env), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=PROFILES)
    parser.add_argument("--scope", default="all", help="Comma-separated integration scopes; default: all.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rtl-cases", help="Limit regression live RTL evaluation to a comma-separated list; retain all other suites.")
    parser.add_argument("--coverage", action="store_true", help="Measure selected unit/service checks; do not select extra checks.")
    parser.add_argument("--output", type=Path, help="New, empty report directory; default: an ignored repository temp/TEMP_* directory.")
    args = parser.parse_args(argv)
    scopes = set(args.scope.split(","))
    if scopes != {"all"} and (not scopes or not scopes <= SCOPES):
        parser.error("Use all or comma-separated scopes: " + ", ".join(sorted(SCOPES)))
    if args.profile != "integration" and args.scope != "all":
        parser.error("--scope is only supported by integration.")
    scopes = SCOPES.copy() if scopes == {"all"} else scopes
    if args.profile == "browser-smoke":
        scopes = {"spec", "circuit"}
    elif args.profile == "live-smoke":
        scopes = {"spec", "assistant"}
    suites = select_suites(args.profile, scopes)
    rtl_cases = None
    if args.rtl_cases is not None:
        if args.profile != "regression":
            parser.error("--rtl-cases is only supported by regression.")
        rtl_cases = args.rtl_cases.split(",")
        catalogue = json.loads((ROOT / "tests/evaluation/rtl/cases.json").read_text())
        known_cases = {case["id"] for case in catalogue["cases"]}
        if len(set(rtl_cases)) != len(rtl_cases) or not rtl_cases or any(case not in known_cases for case in rtl_cases):
            parser.error("--rtl-cases requires distinct known RTL case IDs.")
        suites = [replace(suite, command=(*suite.command, "--case", args.rtl_cases))
                  if suite.id == "live-generalization" else suite for suite in suites]
    if args.dry_run:
        for suite in suites:
            print(json.dumps(asdict(suite)))
        print("Dry run complete; no checks executed, reports written, or provider calls made.")
        return 0
    temp_dir = ROOT / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix="TEMP_tests-", dir=temp_dir))
    if output.exists() and any(output.iterdir()):
        parser.error("--output must be a new or empty directory; existing evidence is not replaced.")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.chmod(0o700)
    env = isolated_environment(output, allocate_ports=any(
        suite.id in {"spec-browser", "circuit-browser"} for suite in suites))
    if args.coverage:
        env["SPEC2GDS_TEST_COVERAGE"] = "1"
    env.setdefault("OPENAI_MODEL", "gpt-4o-mini")
    env.setdefault("OPENAI_BASE_URL", "https://api.openai.com/v1")
    endpoint = urlsplit(env.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    host = endpoint.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    if endpoint.port:
        host += f":{endpoint.port}"
    safe_endpoint = urlunsplit((endpoint.scheme, host, endpoint.path, "", ""))
    report = {"schema_version": "spec2gds.test-run.v1", "profile": args.profile,
              "scopes": sorted(scopes), "started_at": datetime.now(UTC).isoformat(),
              "source_revision": tool_version(["git", "rev-parse", "HEAD"], env),
              "source_dirty": bool(tool_version(["git", "status", "--porcelain"], env)),
              "versions": {name: tool_version([name, "--version"], env)
                           for name in ("python3", "node", "npm", "uv", "verilator")},
              "model": {"name": env.get("OPENAI_MODEL", "gpt-4o-mini"), "endpoint": safe_endpoint,
                        "smoke_step_limit": 6, "smoke_output_token_limit": 4096},
              "optional_toolchains": {name: "configured" if env.get(name) else "not configured; not claimed"
                                      for name in ("SYSTEMC_PREFIX", "CIRCT_PREFIX")},
              "capability_matrix": True,
              "known_failures": [
                  "Previously observed live wire-range saving timeout; retain the current live result without retries.",
                  "Previously observed Circuit Designer keyboard focus and SVG export failures; retain the current browser result.",
                  "Previously observed Spec Editor selected-path mismatch; retain the current existing-destination rejection result.",
                  "Previously observed Spec Editor running-job visibility and cancellation failure; retain the current browser result.",
                  "Previously observed Verification Planner sample snapshot import failure; retain the current browser result.",
                  "Previously observed Verification Planner export HTTP method mismatch; retain the current browser result.",
              ],
              "coverage_gaps": ["automated visual baselines",
                                "system-wide performance and accessibility thresholds"], "suites": []}
    if args.profile == "fast":
        report["coverage_gaps"].append(
            "Fast samples unit and contract checks. Browser, wider service, hardware, and live model checks are separate."
        )
    if rtl_cases is not None:
        report["profile"] = "regression (selected live RTL cases)"
        report["rtl_cases"] = rtl_cases
        report["coverage_gaps"].append("Live RTL evaluation is limited to " + ", ".join(rtl_cases) + "; other RTL cases were not rerun.")
    previous_handler = signal.getsignal(signal.SIGTERM)

    def terminate_run(_number, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate_run)
    try:
        return execute(suites, output, env, report)
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


if __name__ == "__main__":
    raise SystemExit(main())

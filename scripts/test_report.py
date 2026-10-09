"""Render test outcomes as a standalone report for people, without raw metadata."""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

if __package__:
    from .test_capabilities import capability_results
else:
    from test_capabilities import capability_results

CHECK_NAMES = {
    "python-fast": "Spec service and Verification Planner checks",
    "circuit-units": "Circuit Designer package checks",
    "assistant-units": "AI Assistant package checks",
    "scenario-units": "Test runner checks",
    "schema-check": "Interface consistency",
    "build-assistant": "Build AI Assistant",
    "build-circuit": "Build Spec Editor and Circuit Designer",
    "python-extensive": "Spec service and Assistant command-line checks",
    "hardware-extensive": "Hardware compilation and simulation",
    "spec-api": "Spec service interfaces",
    "verification-api": "Verification Planner interfaces",
    "activity-api": "Activity interfaces",
    "shared-api": "Shared infrastructure checks",
    "circuit-service-api": "Circuit service interfaces",
    "circuit-client-http-api": "Circuit service client checks",
    "harness": "DeepSeek Harness integration",
    "spec-browser": "Spec Editor browser checks",
    "circuit-browser": "Circuit Designer browser checks",
    "assistant-browser": "AI Assistant browser checks",
    "spec-circuit-flow": "Circuit editing and Save to Spec",
    "scenario-automatic": "Automatic saving flow",
    "scenario-restricted": "Restricted approval flow",
    "scenario-live": "Saved updates and private drafts",
    "scenario-binding": "Spec binding and service restart",
    "scenario-repeated": "Repeated editing flow",
    "scenario-architecture": "Architecture review flow",
    "live-description": "Live model: save a Component description",
    "live-wire-range": "Live model: change a wire range",
    "live-restricted-description": "Live model: save after restricted approval",
    "live-generalization": "Live model: hardware behaviour evaluation",
    "evaluation-catalogue": "Evaluation catalogue consistency",
    "spec-smoke": "Spec Editor: two deterministic smoke flows",
    "e2e-spec": "Spec Editor with the real Spec service",
    "e2e-circuit": "Circuit Designer with real Spec and Circuit services",
    "e2e-assistant": "AI Assistant: large native proposals",
    "e2e-verification": "Verification Planner with real storage",
}

SCOPE_NAMES = {
    "spec": "Spec Editor and Spec service", "circuit": "Circuit Designer and Circuit service",
    "assistant": "AI Assistant", "verification": "Verification Planner",
    "activities": "Activities", "shared": "Shared infrastructure",
}
STATUS_NAMES = {"passed": "Passed", "failed": "Failed", "unverified": "Not run",
                "incomplete": "Incomplete", "running": "In progress"}


def duration_text(seconds: float | int | None) -> str:
    """Use elapsed time rather than a numeric implementation field."""
    if seconds is None:
        return "—"
    if 0 < seconds < 1:
        return "Under 1 sec"
    seconds = max(0, round(seconds))
    if seconds < 60:
        return f"{seconds} sec"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {seconds} sec"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} hr {minutes} min {seconds} sec"


def outcome_details(suite: dict, output: Path) -> str:
    """Explain known results; never embed commands, exceptions, or stack traces."""
    status = suite.get("status")
    if status == "passed":
        if suite.get("skipped"):
            count = len(suite["skipped"])
            subject = "check did" if count == 1 else "checks did"
            return f"Completed. {count} optional {subject} not run. Unrun checks are outside this result."
        if suite.get("id") == "evaluation-catalogue":
            return "Catalogue checked. Evaluation requests were not executed by this check."
        return "Completed successfully."
    reason = suite.get("reason", "")
    if status == "unverified":
        explanations = []
        if "OPENAI_API_KEY" in reason:
            explanations.append("Live model access is not configured.")
        if "verilator" in reason.lower() or "Verilator 5.x" in reason:
            explanations.append("Verilator 5.x is required for these hardware checks.")
        if "Required hardware tool make" in reason or "Required hardware tool c++" in reason:
            explanations.append("The required hardware build tools are unavailable.")
        if "Node.js" in reason:
            explanations.append("The required Node.js version is unavailable.")
        if "Missing " in reason or "npm is unavailable" in reason or "uv is unavailable" in reason:
            explanations.append("Required test dependencies are unavailable.")
        if "Chromium" in reason:
            explanations.append("The test browser is not installed.")
        if "Harness source" in reason:
            explanations.append("DeepSeek Harness is unavailable.")
        if "browser ports" in reason:
            explanations.append("The environment does not permit isolated browser services.")
        if "Prerequisite check" in reason:
            explanations.append("A required earlier check did not pass.")
        if "interrupted" in reason.lower():
            explanations.append("The run was interrupted.")
        return " ".join(explanations) or "This check could not run; its result is not verified."
    if "execution limit" in reason:
        return "The check reached its time limit before it completed."
    if "evidence report" in reason:
        return "The check did not produce a complete results report."
    if "interrupted" in reason.lower():
        return "The run was interrupted. Completed failures remain recorded; remaining checks are unverified."
    id = suite.get("id", "")
    log = ""
    if re.fullmatch(r"[a-z0-9-]+", id):
        path = output / id / "command.log"
        if path.is_file():
            log = path.read_text(errors="replace")
    timeout = re.search(r"Timeout (\d+)ms exceeded", log)
    if timeout:
        time = duration_text(int(timeout[1]) / 1000)
        if id in {"live-description", "live-wire-range", "live-restricted-description"}:
            return f"Timed out after {time} while waiting for the requested change to be saved."
        return f"Timed out after {time} while waiting for the expected result."
    if "must not start creation of a new Spec" in log or "instead of refining the bound Spec" in log:
        return "The model attempted to create a new Spec instead of changing the bound Spec."
    if "at most two architecture decisions" in log:
        return "The model requested more architecture approvals than this short check permits."
    return "One or more checks failed. The expected result was not confirmed."


def render_report(report: dict, output: Path) -> str:
    """Build escaped, accessible tables with no scripts or external resources."""
    suites = report.get("suites", [])
    profile = {"fast": "Fast", "integration": "Integration", "regression": "Full regression"}.get(
        report.get("profile"), "Test")
    status = report.get("status", "running")
    status_name = STATUS_NAMES.get(status, "Unknown")
    counts = {state: sum(suite.get("status") == state for suite in suites)
              for state in ("passed", "failed", "unverified")}
    elapsed = sum(suite.get("duration_seconds", 0) for suite in suites)
    scopes = report.get("scopes", [])
    coverage = "Full environment" if set(scopes) == set(SCOPE_NAMES) else ", ".join(
        SCOPE_NAMES.get(scope, scope.replace("-", " ").capitalize()) for scope in scopes)
    summary = [("Overall result", status_name), ("Check groups listed", str(len(suites))),
               ("Passed groups", str(counts["passed"])), ("Failed groups", str(counts["failed"])),
               ("Groups not run", str(counts["unverified"])), ("Total check time", duration_text(elapsed))]
    cases = [case for suite in suites for case in suite.get("cases", [])]
    if cases:
        summary.extend([("Individual checks recorded", str(len(cases))),
                        ("Passed individual checks", str(sum(case["status"] == "passed" for case in cases))),
                        ("Failed individual checks", str(sum(case["status"] == "failed" for case in cases))),
                        ("Individual checks not run", str(sum(case["status"] == "unverified" for case in cases)))])
    if coverage:
        summary.append(("Coverage selected", coverage))
    summary_rows = "".join(f"<tr><th scope=\"row\">{escape(name)}</th><td>{escape(value)}</td></tr>"
                           for name, value in summary)
    rows = []
    for suite in suites:
        result = suite.get("status", "unverified")
        name = CHECK_NAMES.get(suite.get("id"), suite.get("id", "Additional check").replace("-", " ").capitalize())
        css = result if result in STATUS_NAMES else "unverified"
        duration = duration_text(suite.get("duration_seconds")) if result != "unverified" else "—"
        rows.append(f'<tr><th scope="row">{escape(name)}</th>'
                    f'<td><span class="status {css}">{escape(STATUS_NAMES.get(result, "Unknown"))}</span></td>'
                    f'<td class="time">{escape(duration)}</td>'
                    f'<td>{escape(outcome_details(suite, output))}</td></tr>')
    if not rows:
        rows.append('<tr><td colspan="4">The run has started. Results will appear as checks finish.</td></tr>')
    note = ""
    if counts["unverified"] or report.get("incomplete"):
        note = "<p class=\"notice\">Some required checks or requested measurements remain unverified. This run is incomplete.</p>"
    gaps = report.get("coverage_gaps", [])
    limits = ""
    if gaps:
        items = "".join(f"<li>{escape(gap[:1].upper() + gap[1:])}</li>" for gap in gaps)
        limits = f'<section><h2>Coverage still to add</h2><ul>{items}</ul></section>'
    details = render_details(report, suites)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(profile)} test results · spec2gds</title>
<style>
:root {{ color-scheme: light; font-family: system-ui, sans-serif; color: #182636; background: #f3f6f9; }}
body {{ margin: 0; padding: 28px 16px; }}
main {{ max-width: 1120px; margin: auto; background: white; padding: 32px; border: 1px solid #dce3ea; border-radius: 12px; }}
.brand {{ margin: 0 0 8px; color: #486277; font-weight: 600; }}
h1 {{ margin: 0 0 12px; font-size: 28px; }} h2 {{ font-size: 19px; margin: 28px 0 12px; }}
p, li {{ line-height: 1.6; }} table {{ width: 100%; border-collapse: collapse; text-align: left; }}
th, td {{ padding: 12px 14px; border-bottom: 1px solid #e3e8ee; vertical-align: top; }}
thead th {{ background: #edf2f7; color: #354b60; }} tbody th {{ font-weight: 550; }}
.summary {{ max-width: 760px; }} .summary th {{ width: 42%; }}
.table-scroll {{ overflow-x: auto; }} .checks {{ min-width: 700px; }} .checks th:first-child {{ width: 32%; }}
.status {{ display: inline-block; padding: 3px 10px; border-radius: 20px; font-weight: 650; white-space: nowrap; }}
.passed {{ color: #175d36; background: #e6f5ec; }} .failed {{ color: #912432; background: #fdecee; }}
.unverified, .incomplete {{ color: #77510c; background: #fff2d7; }} .running {{ color: #245581; background: #eaf1fb; }}
.time {{ white-space: nowrap; color: #42566b; }} .notice {{ padding: 12px 16px; background: #fff7e4; border-left: 4px solid #aa771c; }}
footer {{ margin-top: 28px; color: #53677b; font-size: 14px; }}
@media(max-width: 600px) {{ body {{ padding: 12px 8px; }} main {{ padding: 20px 12px; }} h1 {{ font-size: 24px; }} }}
@media print {{ body {{ background: white; padding: 0; }} main {{ border: 0; padding: 0; }} .table-scroll {{ overflow: visible; }} }}
</style></head><body><main>
<p class="brand">spec2gds</p><h1>{escape(profile)} test results</h1>
<p><span class="status {status if status in STATUS_NAMES else "unverified"}">{escape(status_name)}</span></p>
<section aria-labelledby="summary-heading"><h2 id="summary-heading">Run summary</h2>
<table class="summary" aria-label="Run summary"><tbody>{summary_rows}</tbody></table>{note}</section>
<section aria-labelledby="checks-heading"><h2 id="checks-heading">Check results</h2><div class="table-scroll">
<table class="checks" aria-label="Check results"><thead><tr><th scope="col">Check</th><th scope="col">Result</th>
<th scope="col">Time</th><th scope="col">Details</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>
{details}{limits}<footer>Results apply only to the checks listed above. Checks that did not run are not counted as passed.</footer>
</main></body></html>'''


def detail_table(title: str, headings: list[str], rows: list[list[str]]) -> str:
    header = "".join(f'<th scope="col">{escape(value)}</th>' for value in headings)
    body = "".join('<tr>' + "".join(f'<td>{escape(value)}</td>' for value in row) + '</tr>' for row in rows)
    return (f'<section><h2>{escape(title)}</h2><div class="table-scroll"><table>'
            f'<thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div></section>')


def render_details(report: dict, suites: list[dict]) -> str:
    sections = []
    if report.get("capability_matrix"):
        rows = [[row["name"], STATUS_NAMES[row["status"]], row["note"]]
                for row in capability_results(suites)]
        sections.append('<p>Only executed checks verify capabilities. Unselected and skipped behaviours remain unverified.</p>')
        sections.append(detail_table("Capability coverage", ["Capability and tested behaviour", "Result", "Explanation"], rows))
    cases, measurements = [], []
    for suite in suites:
        for case in suite.get("cases", []):
            name = re.sub(r"\[.*\]$", "", re.sub(r"^test_", "", case["name"]))
            name = name.replace("_", " ").removeprefix("@smoke ")
            evidence = ("Real services; scripted model" if "fixture-model" in suite.get("evidence", "") else
                        "Live model and real services" if "live-model" in suite.get("evidence", "") else
                        "Real services" if suite.get("evidence") == "real-services" else "Isolated service or local check")
            explanation = case.get("explanation") or {
                "passed": "Expected result confirmed.",
                "failed": "Expected result not confirmed.",
                "unverified": "This check did not complete; no successful result is claimed.",
            }.get(case["status"], "No confirmed result.")
            cases.append([name, evidence, STATUS_NAMES.get(case["status"], "Unknown"), duration_text(case.get("duration_seconds")), explanation])
        for row in suite.get("code_coverage", []):
            values = ["Not measured" if row.get(key) is None else f'{row[key]}%' for key in ("lines", "branches")]
            measurements.append([row["name"], CHECK_NAMES.get(suite["id"], "Selected checks"), *values, row["note"]])
    if cases:
        sections.append(detail_table("Individual checks", ["Behaviour", "Evidence", "Result", "Time", "Explanation"], cases))
    if measurements:
        sections.append('<p>Each coverage row measures one set of checks. No complete functional or environment-wide percentage is claimed.</p>')
        sections.append(detail_table("Code coverage diagnostics", ["Subsystem", "Measured checks", "Lines", "Branches", "Limits"], measurements))
    if report.get("known_failures"):
        sections.append(detail_table("Known failures tracked separately", ["Issue", "Result policy"],
                                     [[issue, "Keep the executed result. Do not retry or weaken assertions."] for issue in report["known_failures"]]))
    return "".join(sections)

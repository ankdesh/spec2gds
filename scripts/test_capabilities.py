"""Map capabilities to executed cases, rather than infer coverage from suite totals."""
import re

CAPABILITIES = [
    ("Spec authoring and persistence", ("spec-smoke", "e2e-spec"), ("@smoke creates a Component",)),
    ("Invalid drafts, cancel and corrected saving", ("spec-smoke", "e2e-spec"), ("@smoke preserves an invalid draft",)),
    ("Wire, transactional and structured ports", ("e2e-spec",), tuple(f"saves and reopens a {family} port" for family in ("wire", "transactional", "structured"))),
    ("Failed opens and existing destinations", ("e2e-spec",), ("failed opens and an existing destination",)),
    ("Stable names and keyboard access", ("e2e-spec",), ("names retain identity",)),
    ("Design and Component instance authoring", ("e2e-spec",), ("creates an entry Design",)),
    ("SystemVerilog add, edit, delete and reopen", ("e2e-spec",), ("SystemVerilog add, edit, delete",)),
    ("Hidden source preservation", ("e2e-spec",), ("editing visible text preserves hidden",)),
    ("Competing writers and reviewed retry", ("e2e-spec",), ("two writers preserve",)),
    ("Delayed response protection", ("e2e-spec",), ("a delayed response cannot replace",)),
    ("Source event recovery", ("e2e-spec",), ("source events reconnect",)),
    ("SVG preview without Circuit service", ("e2e-spec",), ("renders and downloads a source-derived SVG",)),
    ("Activity success, failure and cancellation", ("e2e-spec",), tuple(f"Activity {title} reaches" for title in ("Source proof", "Controlled failure", "Controlled barrier"))),
    ("Activity immutable source after restart", ("e2e-spec",), ("an Activity retains its enqueued source",)),
    ("HTTP request validation and serialized errors", ("python-baseline", "python-fast", "spec-api"), ("test_http_request_validation",)),
    ("HTTP document selection", ("python-baseline", "python-fast", "spec-api"), ("test_http_document_selection",)),
    ("Atomic HTTP changes and stale writer rejection", ("python-baseline", "python-fast", "spec-api"), ("test_http_invalid_batch", "test_http_stale_writer")),
    ("Proposal preview and exact-once replay", ("python-baseline", "python-fast", "spec-api"), ("test_http_proposal_preview_replay",)),
    ("Circuit saving into real Spec source", ("e2e-circuit",), ("saves Circuit topology",)),
    ("Circuit cancel, stale save and read-only previews", ("e2e-circuit",), ("cancel discards", "a stale Circuit save", "leaf Component Circuit previews")),
    ("Portable circuit files and invalid input", ("e2e-circuit",), ("standalone circuit roundtrip",)),
    ("Large native Assistant proposals", ("e2e-assistant",), ("native automatic saving", "native restricted saving")),
    ("Planner creation from sample source", ("e2e-verification",), ("creates a Test Plan from the sample",)),
    ("Planner drafts and readiness validation", ("e2e-verification",), ("authors a Section and draft intent", "rejects ready intent authoring")),
    ("Immutable plan checkpoint", ("e2e-verification",), ("reviews a ready plan and freezes P1",)),
    ("Planner bundle export and import", ("e2e-verification",), ("exports a bundle", "imports a real exported bundle")),
    ("Immutable coverage checkpoint", ("e2e-verification",), ("reviews ready evidence coverage",)),
    ("Evidence preview, invalid input, commit and restart", ("e2e-verification",), ("stages synthetic evidence", "invalid result text")),
    ("Reference preflight, artifacts and restart", ("e2e-verification",), ("preflights reference recipes",)),
    ("Immutable SDK snapshot handoff", ("python-baseline", "python-fast", "spec-api"), ("test_http_sdk_snapshot_handoff",)),
    ("Real PDF, DOCX and ODT imports", ("e2e-spec",), tuple(f"real {format} document import" for format in ("PDF", "DOCX", "ODT"))),
]


def capability_results(suites):
    rows = []
    for name, ids, patterns in CAPABILITIES:
        selected = [suite for suite in suites if suite.get("id") in ids]
        cases = [case for suite in selected for case in suite.get("cases", [])]
        matches = [[case for case in cases if re.search(pattern, case["name"])] for pattern in patterns]
        states = {case["status"] for group in matches for case in group}
        missing = any(not group for group in matches)
        status = "failed" if "failed" in states else "unverified" if missing or "unverified" in states else "passed"
        note = ("A mapped behaviour failed." if status == "failed" else
                "All mapped behaviours executed successfully." if status == "passed" else
                "Some mapped behaviours did not run or have no confirmed result.")
        rows.append({"name": name, "status": status, "note": note})
    return rows

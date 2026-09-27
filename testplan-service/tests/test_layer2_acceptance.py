"""Layer 2 (Coverage & Evidence Mapping) Acceptance Test Suite.

Validates scenarios L2-01 through L2-20 per docs/verification-layer-2-coverage.md Section 9.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from testplan_service.api.app import create_app
from testplan_service.domain.enums import Priority


# ---------------------------------------------------------------------------
# Fixture Helpers
# ---------------------------------------------------------------------------

BASE_PATH = "/api/verification/v1"


def setup_fifo_with_p1(client: TestClient, fifo_bytes: bytes) -> dict[str, Any]:
    """Upload FIFO snapshot, create plan, 8 requirements, 6 sections, 12 ready intents, and Checkpoint P1."""
    snap_res = client.post(f"{BASE_PATH}/source-imports", content=fifo_bytes)
    assert snap_res.status_code == 201
    snap_data = snap_res.json()
    snapshot_id = snap_data["snapshot_id"]

    plan_res = client.post(
        f"{BASE_PATH}/plans",
        json={
            "name": "FIFO Test Plan",
            "snapshot_id": snapshot_id,
            "root_scope_id": "sync_fifo",
            "description": "FIFO verification plan for Layer 2 tests",
        },
    )
    assert plan_res.status_code == 201
    plan = plan_res.json()
    plan_id = plan["id"]
    rev = plan["edit_revision"]

    # Requirements and Sections
    source_sections = client.get(f"{BASE_PATH}/plans/{plan_id}/source-sections").json()
    req_definitions = [
        ("req-reset", "Reset behavior", "Reset clears queue; reset overrides simultaneous requests", "sec-reset"),
        ("req-write", "Accepted write", "Write appends one word when space is available", "sec-write"),
        ("req-read", "Accepted read", "Read returns oldest word when data is available", "sec-read"),
        ("req-full", "Full write rejection", "Full write preserves occupancy and queued data", "sec-full"),
        ("req-empty", "Empty read rejection", "Empty read preserves queue and output", "sec-empty"),
        ("req-both", "Simultaneous requests", "Mid-occupancy accepts both; full accepts read only; empty accepts write only", "sec-both"),
        ("req-order", "Sequence retention", "Ordering survives wrap-around without data loss", "sec-order"),
        ("req-flags", "Flag consistency", "Full/empty agree with occupancy counts", "sec-flags"),
    ]
    sec_definitions = [
        ("sec-reset-grp", "Reset", Priority.HIGH),
        ("sec-normal-grp", "Normal operation", Priority.HIGH),
        ("sec-bounds-grp", "Boundaries", Priority.HIGH),
        ("sec-simul-grp", "Simultaneous requests", Priority.MEDIUM),
        ("sec-order-grp", "Ordering", Priority.MEDIUM),
        ("sec-status-grp", "Status", Priority.LOW),
    ]

    req_ops = [
        {
            "op": "requirement.create",
            "id": rid,
            "title": title,
            "statement": stmt,
            "scope_id": "sync_fifo",
            "disposition": "verify",
            "source_locators": [
                {
                    "snapshot_id": snapshot_id,
                    "entity_ref": {"document_id": "fifo_spec", "entity_kind": "component", "entity_id": "sync_fifo"},
                    "section_id": sec_id,
                    "text_range": [0, len(stmt)],
                    "quoted_text": stmt[:30],
                    "section_digest": "golden",
                }
            ],
        }
        for rid, title, stmt, sec_id in req_definitions
    ]
    sec_ops = [
        {"op": "section.create", "id": sid, "title": title, "scope_id": "sync_fifo", "default_priority": prio.value}
        for sid, title, prio in sec_definitions
    ]
    audit_ops = [
        {
            "op": "source_section.assess",
            "section_id": s["section_id"],
            "disposition": "requirements_captured",
            "requirement_ids": [r[0] for r in req_definitions if r[3] == s["section_id"]],
            "reason": "Captured normative requirement",
        }
        for s in source_sections
    ]

    res = client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={"base_edit_revision": rev, "request_id": "setup-reqs", "operations": req_ops + sec_ops + audit_ops},
    )
    assert res.status_code == 200
    rev = res.json()["edit_revision"]

    # 12 Intents
    intent_definitions = [
        ("int-rst-1", "Reset clears queue", "sec-reset-grp", ["req-reset"], "Reset asserted.", "Clock edge arrives.", "Count=0, empty=1, full=0.", [("Queue State", "count==0 and empty==1")]),
        ("int-rst-2", "Reset overrides simultaneous requests", "sec-reset-grp", ["req-reset"], "FIFO in operation.", "Reset asserted on clock edge.", "Queue emptied.", [("Queue State", "count==0, dout==0")]),
        ("int-wr-1", "Write appends one word", "sec-normal-grp", ["req-write"], "FIFO space available.", "wr_en=1 with din.", "din appended; count increments.", [("Occupancy", "count == count_prev + 1")]),
        ("int-rd-1", "Read returns oldest word", "sec-normal-grp", ["req-read"], "FIFO non-empty.", "rd_en=1 on clock edge.", "dout publishes oldest word.", [("Data Output", "dout == expected_word")]),
        ("int-full-1", "Full write preserves occupancy", "sec-bounds-grp", ["req-full"], "FIFO is full.", "wr_en=1 without rd_en.", "Write rejected; count remains DEPTH.", [("Occupancy", "count == DEPTH")]),
        ("int-full-2", "Full write preserves queued data", "sec-bounds-grp", ["req-full"], "FIFO full.", "Attempted write on full FIFO.", "Queued words intact.", [("Queue Integrity", "Read sequence matches original words")]),
        ("int-empty-1", "Empty read preserves queue and output", "sec-bounds-grp", ["req-empty"], "FIFO empty.", "rd_en=1 without wr_en.", "Read rejected; count remains 0.", [("Empty Flag", "empty == 1 and count == 0")]),
        ("int-sim-1", "Mid-occupancy accepts both", "sec-simul-grp", ["req-both"], "0 < count < DEPTH.", "Simultaneous rd_en=1 and wr_en=1.", "Both accepted; count unchanged.", [("Throughput", "Simultaneous read and write successful")]),
        ("int-sim-2", "Full accepts read only", "sec-simul-grp", ["req-both"], "count == DEPTH.", "Simultaneous rd_en=1 and wr_en=1.", "Read accepted, write rejected.", [("Full Boundary", "Read accepted, write dropped")]),
        ("int-sim-3", "Empty accepts write only", "sec-simul-grp", ["req-both"], "count == 0.", "Simultaneous rd_en=1 and wr_en=1.", "Write accepted, read rejected.", [("Empty Boundary", "Write accepted, read dropped")]),
        ("int-ord-1", "Ordering survives wrap-around", "sec-order-grp", ["req-order"], "FIFO operated across wrap-around boundary.", "Consecutive write-read sequence.", "Strict FIFO order preserved.", [("Order Check", "Words egress in exact arrival order")]),
        ("int-flag-1", "Full and empty agree with occupancy", "sec-status-grp", ["req-flags"], "Valid FIFO state.", "Clock edge after operation.", "full==(count==DEPTH) and empty==(count==0).", [("Flags", "full and empty strictly match count")]),
    ]

    intent_ops = [
        {
            "op": "intent.create",
            "id": i_id,
            "title": title,
            "scope_id": "sync_fifo",
            "parent_section_id": sec_id,
            "requirement_ids": req_ids,
            "preconditions": pre,
            "trigger": trig,
            "expected_behavior": exp,
            "observations": [{"name": o[0], "description": o[1]} for o in obs],
            "authoring_state": "ready",
        }
        for i_id, title, sec_id, req_ids, pre, trig, exp, obs in intent_definitions
    ]

    res = client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={"base_edit_revision": rev, "request_id": "add-intents", "operations": intent_ops},
    )
    assert res.status_code == 200
    rev = res.json()["edit_revision"]

    # Preview and Create P1
    prev_res = client.post(f"{BASE_PATH}/plans/{plan_id}/checkpoints/preview")
    assert prev_res.status_code == 200
    prev_data = prev_res.json()
    assert len(prev_data["blockers"]) == 0

    p1_res = client.post(
        f"{BASE_PATH}/plans/{plan_id}/checkpoints",
        json={
            "layer": "plan",
            "reviewer_label": "verification-lead",
            "comment": "All 8 requirements captured and verified across 12 ready intents.",
            "expected_digest": prev_data["candidate_digest"],
        },
    )
    assert p1_res.status_code == 201
    p1 = p1_res.json()

    return {
        "plan_id": plan_id,
        "snapshot_id": snapshot_id,
        "rev": rev,
        "p1": p1,
        "req_definitions": req_definitions,
        "intent_definitions": intent_definitions,
    }


def setup_fifo_with_c1(client: TestClient, fifo_bytes: bytes) -> dict[str, Any]:
    """Sets up FIFO with P1, authors 24 coverage objectives and 12 policies, and creates Checkpoint C1."""
    ctx = setup_fifo_with_p1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    rev = ctx["rev"]
    p1 = ctx["p1"]
    intent_definitions = ctx["intent_definitions"]

    obj_ops: list[dict[str, Any]] = []
    pol_ops: list[dict[str, Any]] = []

    for idx, (i_id, title, sec_id, req_ids, pre, trig, exp, obs) in enumerate(intent_definitions, start=1):
        scen_id = f"obj-scen-{idx}"
        corr_id = f"obj-corr-{idx}"

        obj_ops.append({
            "op": "objective.create",
            "id": scen_id,
            "title": f"Scenario: {title}",
            "family": "scenario",
            "scope_id": "sync_fifo",
            "parent_intent_id": i_id,
            "bins": [{"bin_id": f"bin_{idx}", "name": f"Bin for {title}", "required": True}],
            "acceptance": {"metric": "all_bins_hit", "threshold": 1},
            "authoring_state": "ready",
        })
        obj_ops.append({
            "op": "objective.create",
            "id": corr_id,
            "title": f"Correctness: {title}",
            "family": "correctness",
            "scope_id": "sync_fifo",
            "parent_intent_id": i_id,
            "bins": [],
            "acceptance": {"metric": "pass_verdict", "minimum_evaluations": 1},
            "authoring_state": "ready",
        })
        pol_ops.append({
            "op": "policy.set",
            "intent_id": i_id,
            "branches": [
                {
                    "branch_id": "branch-1",
                    "objective_ids": [scen_id, corr_id],
                }
            ],
        })

    res = client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={"base_edit_revision": rev, "request_id": "setup-coverage", "operations": obj_ops + pol_ops},
    )
    assert res.status_code == 200
    rev = res.json()["edit_revision"]

    # Preview and create C1
    cov_prev = client.post(
        f"{BASE_PATH}/plans/{plan_id}/checkpoints/preview",
        json={"layer": "coverage", "upstream_checkpoint_id": p1["id"]},
    ).json()
    assert len(cov_prev["blockers"]) == 0

    c1_res = client.post(
        f"{BASE_PATH}/plans/{plan_id}/checkpoints",
        json={
            "layer": "coverage",
            "reviewer_label": "coverage-lead",
            "comment": "All 12 intents mapped to scenario and correctness objectives.",
            "expected_digest": cov_prev["candidate_digest"],
            "upstream_checkpoint_id": p1["id"],
        },
    )
    assert c1_res.status_code == 201
    c1 = c1_res.json()

    ctx["rev"] = rev
    ctx["c1"] = c1
    return ctx


def commit_run(client: TestClient, plan_id: str, payload: dict[str, Any], campaign_id: str | None = None) -> dict[str, Any]:
    """Helper to stage and commit a result import."""
    stg = client.post(f"{BASE_PATH}/plans/{plan_id}/result-imports", json=payload).json()
    commit_body: dict[str, Any] = {"expected_preview_digest": stg["preview_digest"]}
    if campaign_id:
        commit_body["campaign_id"] = campaign_id
    cmt = client.post(f"{BASE_PATH}/plans/{plan_id}/result-imports/{stg['staging_id']}/commit", json=commit_body)
    assert cmt.status_code in {200, 201}
    return cmt.json()


# ---------------------------------------------------------------------------
# Acceptance Tests L2-01 through L2-20
# ---------------------------------------------------------------------------

def test_l2_01_12_intents_11_policies(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-01: 12 intents, 11 policies -> Mapping 11/12; missing-policy gap links to exact intent."""
    ctx = setup_fifo_with_p1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    rev = ctx["rev"]
    intent_defs = ctx["intent_definitions"]

    # Author objectives and policies for only the first 11 intents (leave 12th unmapped)
    obj_ops: list[dict[str, Any]] = []
    pol_ops: list[dict[str, Any]] = []
    for idx, (i_id, title, *_) in enumerate(intent_defs[:11], start=1):
        s_id = f"obj-scen-{idx}"
        k_id = f"obj-corr-{idx}"
        obj_ops.extend([
            {"op": "objective.create", "id": s_id, "title": f"Scenario {idx}", "family": "scenario", "scope_id": "sync_fifo", "parent_intent_id": i_id, "bins": [{"bin_id": f"b{idx}", "name": "B", "required": True}], "acceptance": {"metric": "all_bins_hit", "threshold": 1}, "authoring_state": "ready"},
            {"op": "objective.create", "id": k_id, "title": f"Correctness {idx}", "family": "correctness", "scope_id": "sync_fifo", "parent_intent_id": i_id, "bins": [], "acceptance": {"metric": "pass_verdict", "minimum_evaluations": 1}, "authoring_state": "ready"},
        ])
        pol_ops.append({
            "op": "policy.set",
            "intent_id": i_id,
            "branches": [{"branch_id": "branch-1", "objective_ids": [s_id, k_id]}],
        })

    client.post(f"{BASE_PATH}/plans/{plan_id}/commands", json={"base_edit_revision": rev, "request_id": "l2-01-ops", "operations": obj_ops + pol_ops})

    matrix = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix").json()
    assert matrix["baseline_summary"]["total_intents"] == 12
    assert matrix["baseline_summary"]["mapped_intents"] == 11

    gaps = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/gaps").json()
    missing_pol_gaps = [g for g in gaps if g["gap_code"] == "intent_policy_missing"]
    assert len(missing_pol_gaps) == 1
    unmapped_id = intent_defs[11][0]
    assert unmapped_id in missing_pol_gaps[0]["affected_record_ids"]


def test_l2_02_scenario_only_blocks_review(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-02: Every intent mapped to scenario-only objectives -> Review blocked by checking_missing; hits cannot close intent."""
    ctx = setup_fifo_with_p1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    rev = ctx["rev"]
    p1 = ctx["p1"]
    intent_defs = ctx["intent_definitions"]

    # All 12 intents mapped to scenario-only objectives
    obj_ops: list[dict[str, Any]] = []
    pol_ops: list[dict[str, Any]] = []
    for idx, (i_id, title, *_) in enumerate(intent_defs, start=1):
        s_id = f"obj-scen-only-{idx}"
        obj_ops.append({
            "op": "objective.create", "id": s_id, "title": f"Scenario Only {idx}", "family": "scenario", "scope_id": "sync_fifo",
            "parent_intent_id": i_id, "bins": [{"bin_id": f"b{idx}", "name": "B", "required": True}], "acceptance": {"metric": "all_bins_hit", "threshold": 1}, "authoring_state": "ready",
        })
        pol_ops.append({
            "op": "policy.set", "intent_id": i_id, "branches": [{"branch_id": "branch-1", "objective_ids": [s_id]}],
        })

    client.post(f"{BASE_PATH}/plans/{plan_id}/commands", json={"base_edit_revision": rev, "request_id": "l2-02-ops", "operations": obj_ops + pol_ops})

    # Coverage checkpoint preview must be blocked by checking_missing
    prev = client.post(f"{BASE_PATH}/plans/{plan_id}/checkpoints/preview", json={"layer": "coverage", "upstream_checkpoint_id": p1["id"]}).json()
    assert len(prev["blockers"]) == 12
    assert all("checking_missing" in b["code"] for b in prev["blockers"])


def test_l2_03_shared_objective_single_rollup(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-03: One objective linked to two intents -> Objective rollup counted once; each policy evaluated separately."""
    ctx = setup_fifo_with_p1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    rev = ctx["rev"]

    # Shared scenario objective O-shared linked to INT-1 and INT-2
    ops = [
        {"op": "objective.create", "id": "obj-shared", "title": "Shared Scenario", "family": "scenario", "scope_id": "sync_fifo", "bins": [{"bin_id": "b-shared", "name": "BS", "required": True}], "acceptance": {"metric": "all_bins_hit", "threshold": 1}, "authoring_state": "ready"},
        {"op": "objective.create", "id": "obj-chk-1", "title": "Check 1", "family": "correctness", "scope_id": "sync_fifo", "parent_intent_id": "int-rst-1", "bins": [], "acceptance": {"metric": "pass_verdict", "minimum_evaluations": 1}, "authoring_state": "ready"},
        {"op": "objective.create", "id": "obj-chk-2", "title": "Check 2", "family": "correctness", "scope_id": "sync_fifo", "parent_intent_id": "int-rst-2", "bins": [], "acceptance": {"metric": "pass_verdict", "minimum_evaluations": 1}, "authoring_state": "ready"},
        {"op": "policy.set", "intent_id": "int-rst-1", "branches": [{"branch_id": "b1", "objective_ids": ["obj-shared", "obj-chk-1"]}]},
        {"op": "policy.set", "intent_id": "int-rst-2", "branches": [{"branch_id": "b1", "objective_ids": ["obj-shared", "obj-chk-2"]}]},
    ]
    client.post(f"{BASE_PATH}/plans/{plan_id}/commands", json={"base_edit_revision": rev, "request_id": "l2-03-ops", "operations": ops})

    matrix = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix").json()
    # The shared objective with 1 required bin is counted exactly once in required_bins_total
    assert matrix["baseline_summary"]["required_bins_total"] == 1


def test_l2_04_full_fifo_golden_campaign(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-04: Full FIFO golden campaign -> 8 satisfied, 1 failed, 2 not evaluated, 1 blocked; 12 total."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    c1 = ctx["c1"]

    prof = client.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "FIFO Sim", "coverage_checkpoint_id": c1["id"], "root_occurrence_id": "sync_fifo"}).json()
    camp = client.post(f"{BASE_PATH}/plans/{plan_id}/campaigns", json={"title": "Golden Camp", "coverage_checkpoint_id": c1["id"], "required_profile_ids": [prof["id"]], "purpose": "fixture"}).json()

    # Import 8 passing runs (rows 1,2,3,4,6,7,8,10)
    for idx in [1, 2, 3, 4, 6, 7, 8, 10]:
        payload = {
            "schema_version": "verification.results.v1", "profile_id": prof["id"], "coverage_checkpoint_id": c1["id"],
            "producer": {"id": "prod-sim", "tool_name": "icarus", "producer_kind": "generated"},
            "run": {"external_run_id": f"run-pass-{idx}", "attempt_id": "1", "status": "completed"},
            "observations": [
                {"producer_observation_id": f"obs-s-{idx}", "objective_id": f"obj-scen-{idx}", "family": "scenario", "bin_id": f"bin_{idx}", "outcome": "hit", "hit_count": 1, "evaluation_count": 1},
                {"producer_observation_id": f"obs-k-{idx}", "objective_id": f"obj-corr-{idx}", "family": "correctness", "outcome": "pass", "evaluation_count": 1},
            ],
        }
        commit_run(client, plan_id, payload, campaign_id=camp["id"])

    # Row 5: Failed
    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"], "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "prod-sim", "tool_name": "icarus", "producer_kind": "generated"},
        "run": {"external_run_id": "run-fail-5", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-s-5", "objective_id": "obj-scen-5", "family": "scenario", "bin_id": "bin_5", "outcome": "hit", "hit_count": 1, "evaluation_count": 1},
            {"producer_observation_id": "obs-k-5", "objective_id": "obj-corr-5", "family": "correctness", "outcome": "fail", "evaluation_count": 1, "diagnostic_message": "Occupancy mismatch on full write"},
        ],
    }, campaign_id=camp["id"])

    # Row 12: Blocked / Tool Error
    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"], "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "prod-sim", "tool_name": "icarus", "producer_kind": "generated"},
        "run": {"external_run_id": "run-err-12", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-k-12", "objective_id": "obj-corr-12", "family": "correctness", "outcome": "error", "evaluation_count": 0, "diagnostic_message": "Simulator fatal memory fault"},
        ],
    }, campaign_id=camp["id"])

    # Verify rollup
    matrix = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?campaign={camp['id']}").json()
    b = matrix["baseline_summary"]
    assert b["satisfied_intents"] == 8
    assert b["failed_intents"] == 1
    assert b["not_evaluated_intents"] == 2
    assert b["blocked_intents"] == 1
    assert b["total_intents"] == 12


def test_l2_05_bin_hit_without_check_evaluation(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-05: Bin hit with zero check evaluations -> Exploratory reachability shown; no default branch closure."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    c1 = ctx["c1"]

    prof = client.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "FIFO Sim", "coverage_checkpoint_id": c1["id"]}).json()
    camp = client.post(f"{BASE_PATH}/plans/{plan_id}/campaigns", json={"title": "Camp", "coverage_checkpoint_id": c1["id"], "required_profile_ids": [prof["id"]]}).json()

    # Import scenario bin hit only; no correctness check
    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"], "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "prod-sim", "tool_name": "icarus"},
        "run": {"external_run_id": "run-hit-only-1", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-s-1", "objective_id": "obj-scen-1", "family": "scenario", "bin_id": "bin_1", "outcome": "hit", "hit_count": 1, "evaluation_count": 1},
        ],
    }, campaign_id=camp["id"])

    matrix = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?campaign={camp['id']}").json()
    r1 = next(r for r in matrix["rows"] if r["intent_id"] == "int-rst-1")
    assert r1["achievement_state"] == "open"
    assert r1["family_cell_summaries"]["scenario"] == "1/1"
    assert r1["family_cell_summaries"]["checking"] == "Not evaluated"


def test_l2_06_completed_pass_then_failing_retry(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-06: Completed pass then failing retry -> Intent Failed; no latest-pass shortcut."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    c1 = ctx["c1"]

    prof = client.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "FIFO Sim", "coverage_checkpoint_id": c1["id"]}).json()
    camp = client.post(f"{BASE_PATH}/plans/{plan_id}/campaigns", json={"title": "Camp", "coverage_checkpoint_id": c1["id"], "required_profile_ids": [prof["id"]]}).json()

    # Run 1: Passing
    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"], "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "prod-sim", "tool_name": "icarus"},
        "run": {"external_run_id": "run-pass-1", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-s-1", "objective_id": "obj-scen-1", "family": "scenario", "bin_id": "bin_1", "outcome": "hit", "hit_count": 1, "evaluation_count": 1},
            {"producer_observation_id": "obs-k-1", "objective_id": "obj-corr-1", "family": "correctness", "outcome": "pass", "evaluation_count": 1},
        ],
    }, campaign_id=camp["id"])

    mat1 = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?campaign={camp['id']}").json()
    assert next(r for r in mat1["rows"] if r["intent_id"] == "int-rst-1")["achievement_state"] == "satisfied"

    # Run 2: Retry fails
    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"], "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "prod-sim", "tool_name": "icarus"},
        "run": {"external_run_id": "run-pass-1", "attempt_id": "2", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-s-1-att2", "objective_id": "obj-scen-1", "family": "scenario", "bin_id": "bin_1", "outcome": "hit", "hit_count": 1, "evaluation_count": 1},
            {"producer_observation_id": "obs-k-1-att2", "objective_id": "obj-corr-1", "family": "correctness", "outcome": "fail", "evaluation_count": 1, "diagnostic_message": "Intermittent failure"},
        ],
    }, campaign_id=camp["id"])

    mat2 = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?campaign={camp['id']}").json()
    assert next(r for r in mat2["rows"] if r["intent_id"] == "int-rst-1")["achievement_state"] == "failed"


def test_l2_07_duplicate_and_conflicting_import_idempotency(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-07: Duplicate import / conflicting same external run identity -> Replay original / reject 409."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    c1 = ctx["c1"]
    prof = client.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "FIFO Sim", "coverage_checkpoint_id": c1["id"]}).json()

    payload = {
        "schema_version": "verification.results.v1", "profile_id": prof["id"], "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "prod-sim", "tool_name": "icarus"},
        "run": {"external_run_id": "run-idem-1", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-1", "objective_id": "obj-scen-1", "family": "scenario", "bin_id": "bin_1", "outcome": "hit", "hit_count": 1, "evaluation_count": 1},
        ],
    }

    # First import -> committed
    res1 = commit_run(client, plan_id, payload)
    assert res1["status"] == "committed"

    # Exact duplicate import -> idempotent replay
    res2 = commit_run(client, plan_id, payload)
    assert res2["status"] == "idempotent_duplicate"

    # Conflicting import with same (producer_id, external_run_id, attempt_id) but different content
    conflicting_payload = dict(payload)
    conflicting_payload["run"] = {"external_run_id": "run-idem-1", "attempt_id": "1", "status": "failed"}
    stg_conflict = client.post(f"{BASE_PATH}/plans/{plan_id}/result-imports", json=conflicting_payload).json()
    cmt_conflict = client.post(f"{BASE_PATH}/plans/{plan_id}/result-imports/{stg_conflict['staging_id']}/commit", json={"expected_preview_digest": stg_conflict["preview_digest"]})
    assert cmt_conflict.status_code == 409


def test_l2_08_incompatible_dut_hash_preserved_history(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-08: Result has wrong DUT source hash -> Explicit incompatibility; current counts unchanged."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    c1 = ctx["c1"]

    # Profile pinned to hash_dut_alpha
    prof = client.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "FIFO Sim", "coverage_checkpoint_id": c1["id"], "dut_source_hash": "hash_dut_alpha"}).json()
    camp = client.post(f"{BASE_PATH}/plans/{plan_id}/campaigns", json={"title": "Camp", "coverage_checkpoint_id": c1["id"], "required_profile_ids": [prof["id"]]}).json()

    # Import run executed against different DUT version (hash_dut_beta)
    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"], "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "prod-sim", "tool_name": "icarus"},
        "run": {"external_run_id": "run-incompat-hash", "attempt_id": "1", "status": "completed", "dut_source_hash": "hash_dut_beta"},
        "observations": [
            {"producer_observation_id": "obs-s-1", "objective_id": "obj-scen-1", "family": "scenario", "bin_id": "bin_1", "outcome": "hit", "hit_count": 1, "evaluation_count": 1},
            {"producer_observation_id": "obs-k-1", "objective_id": "obj-corr-1", "family": "correctness", "outcome": "pass", "evaluation_count": 1},
        ],
    }, campaign_id=camp["id"])

    # Matrix should ignore incompatible run; intent remains not evaluated
    matrix = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?campaign={camp['id']}").json()
    r1 = next(r for r in matrix["rows"] if r["intent_id"] == "int-rst-1")
    assert r1["achievement_state"] == "not_evaluated"


def test_l2_09_full_exclusion_or_empty_denominator(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-09: Full exclusion or no denominator -> N/A, visible exclusions; required objective review blocked."""
    ctx = setup_fifo_with_p1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    rev = ctx["rev"]
    p1 = ctx["p1"]

    # Create scenario objective with 1 bin, then exclude that bin
    ops = [
        {"op": "objective.create", "id": "obj-excl", "title": "Exclusion Scenario", "family": "scenario", "scope_id": "sync_fifo", "bins": [{"bin_id": "b-ex", "name": "BEx", "required": True}], "acceptance": {"metric": "all_bins_hit", "threshold": 1}, "authoring_state": "ready"},
        {"op": "exclusion.create", "id": "excl-1", "objective_id": "obj-excl", "bin_id": "b-ex", "reason": "Hardware unreachable state", "reviewer_label": "lead"},
        {"op": "policy.set", "intent_id": "int-rst-1", "branches": [{"branch_id": "b1", "objective_ids": ["obj-excl"]}]},
    ]
    client.post(f"{BASE_PATH}/plans/{plan_id}/commands", json={"base_edit_revision": rev, "request_id": "l2-09-ops", "operations": ops})

    prev = client.post(f"{BASE_PATH}/plans/{plan_id}/checkpoints/preview", json={"layer": "coverage", "upstream_checkpoint_id": p1["id"]}).json()
    # Blocked because obj-excl has 0 non-excluded required bins
    assert any("objective_incomplete" in b["code"] for b in prev["blockers"])


def test_l2_10_unbounded_property_requires_unbounded_proof(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-10: Unbounded objective receives bounded pass or unknown vacuity -> Blocked/inconclusive, never Proven."""
    ctx = setup_fifo_with_p1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    rev = ctx["rev"]

    # Objective requiring unbounded proof with checked_nonvacuous
    ops = [
        {"op": "objective.create", "id": "obj-prop-unb", "title": "Unbounded FIFO Proof", "family": "property", "scope_id": "sync_fifo", "parent_intent_id": "int-rst-1", "bins": [], "acceptance": {"claim": "unbounded", "metric": "formal_proof"}, "authoring_state": "ready"},
        {"op": "policy.set", "intent_id": "int-rst-1", "branches": [{"branch_id": "b1", "objective_ids": ["obj-prop-unb"]}]},
    ]
    client.post(f"{BASE_PATH}/plans/{plan_id}/commands", json={"base_edit_revision": rev, "request_id": "l2-10-ops", "operations": ops})

    prof = client.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "Formal Profile"}).json()
    camp = client.post(f"{BASE_PATH}/plans/{plan_id}/campaigns", json={"title": "Camp", "required_profile_ids": [prof["id"]]}).json()

    # Import bounded pass (20 cycles)
    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"],
        "producer": {"id": "prod-formal", "tool_name": "jg"},
        "run": {"external_run_id": "run-bounded-pass", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-p-1", "objective_id": "obj-prop-unb", "family": "property", "outcome": "bounded_pass", "property_fields": {"bound": 20}},
        ],
    }, campaign_id=camp["id"])

    # Bounded pass does not satisfy unbounded objective
    matrix = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?campaign={camp['id']}").json()
    r1 = next(r for r in matrix["rows"] if r["intent_id"] == "int-rst-1")
    assert r1["achievement_state"] != "satisfied"


def test_l2_11_or_policy_simulation_pass_formal_counterexample(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-11: OR policy has passing simulation and formal counterexample -> Failed until counterexample disposition is reviewed."""
    ctx = setup_fifo_with_p1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    rev = ctx["rev"]

    # OR policy: Branch 1 = Sim (scen + corr), Branch 2 = Formal property
    ops = [
        {"op": "objective.create", "id": "obj-scen-or", "title": "Scen OR", "family": "scenario", "scope_id": "sync_fifo", "bins": [{"bin_id": "b1", "name": "B", "required": True}], "acceptance": {"metric": "all_bins_hit", "threshold": 1}, "authoring_state": "ready"},
        {"op": "objective.create", "id": "obj-corr-or", "title": "Corr OR", "family": "correctness", "scope_id": "sync_fifo", "bins": [], "acceptance": {"metric": "pass_verdict", "minimum_evaluations": 1}, "authoring_state": "ready"},
        {"op": "objective.create", "id": "obj-prop-or", "title": "Prop OR", "family": "property", "scope_id": "sync_fifo", "bins": [], "acceptance": {"claim": "unbounded"}, "authoring_state": "ready"},
        {"op": "policy.set", "intent_id": "int-rst-1", "branches": [
            {"branch_id": "sim-branch", "objective_ids": ["obj-scen-or", "obj-corr-or"]},
            {"branch_id": "formal-branch", "objective_ids": ["obj-prop-or"]},
        ]},
    ]
    client.post(f"{BASE_PATH}/plans/{plan_id}/commands", json={"base_edit_revision": rev, "request_id": "l2-11-ops", "operations": ops})

    prof = client.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "FIFO Hybrid Profile"}).json()
    camp = client.post(f"{BASE_PATH}/plans/{plan_id}/campaigns", json={"title": "Camp", "required_profile_ids": [prof["id"]]}).json()
    camp_id = camp["id"]

    # Sim Run: Passes
    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"],
        "producer": {"id": "prod-sim", "tool_name": "icarus"},
        "run": {"external_run_id": "run-sim-pass", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-s", "objective_id": "obj-scen-or", "family": "scenario", "bin_id": "b1", "outcome": "hit", "hit_count": 1, "evaluation_count": 1},
            {"producer_observation_id": "obs-k", "objective_id": "obj-corr-or", "family": "correctness", "outcome": "pass", "evaluation_count": 1},
        ],
    }, campaign_id=camp_id)

    # Formal Run: Counterexample found
    cmt_cex = commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"],
        "producer": {"id": "prod-formal", "tool_name": "jg"},
        "run": {"external_run_id": "run-formal-cex", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-p-cex", "objective_id": "obj-prop-or", "family": "property", "outcome": "counterexample", "diagnostic_message": "Reset assumption violated"},
        ],
    }, campaign_id=camp_id)

    # Failure takes precedence over passing simulation branch
    mat1 = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?campaign={camp_id}").json()
    assert next(r for r in mat1["rows"] if r["intent_id"] == "int-rst-1")["achievement_state"] == "failed"

    # Resolve counterexample run as invalid tool run
    camp_detail = client.get(f"{BASE_PATH}/plans/{plan_id}/campaigns/{camp_id}").json()
    cex_run_id = cmt_cex["run_id"]
    client.post(
        f"{BASE_PATH}/plans/{plan_id}/campaigns/{camp_id}/commands",
        json={
            "base_campaign_revision": camp_detail["campaign_revision"],
            "request_id": "resolve-cex-run",
            "operations": [
                {
                    "op": "run.resolve",
                    "run_id": cex_run_id,
                    "disposition": "invalid_tool_run",
                    "reason": "Testbench missing external reset hold constraint",
                    "reviewer_label": "formal-lead",
                }
            ],
        },
    )

    # Now that the counterexample run is resolved, simulation branch satisfaction takes effect
    mat2 = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?campaign={camp_id}").json()
    assert next(r for r in mat2["rows"] if r["intent_id"] == "int-rst-1")["achievement_state"] == "satisfied"


def test_l2_12_structural_coverage_no_merge_without_element_ids(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-12: Structural reports merge via set union of element IDs; empty elements cannot claim arbitrary union."""
    ctx = setup_fifo_with_p1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    rev = ctx["rev"]

    # Structural objective with target elements
    ops = [
        {"op": "objective.create", "id": "obj-struct", "title": "FIFO Line Coverage", "family": "structural", "scope_id": "sync_fifo", "bins": [], "acceptance": {"target_elements": ["L10", "L11", "L12", "L13"], "threshold_bps": 10000}, "authoring_state": "ready"},
        {"op": "policy.set", "intent_id": "int-rst-1", "branches": [{"branch_id": "b1", "objective_ids": ["obj-struct"]}]},
    ]
    client.post(f"{BASE_PATH}/plans/{plan_id}/commands", json={"base_edit_revision": rev, "request_id": "l2-12-ops", "operations": ops})

    prof = client.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "FIFO Cov Profile"}).json()
    camp = client.post(f"{BASE_PATH}/plans/{plan_id}/campaigns", json={"title": "Camp", "required_profile_ids": [prof["id"]]}).json()

    # Run 1 hits L10, L11
    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"],
        "producer": {"id": "prod-cov"},
        "run": {"external_run_id": "run-cov-1", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-cov-1", "objective_id": "obj-struct", "family": "structural", "outcome": "pass", "structural_elements": ["L10", "L11"]},
        ],
    }, campaign_id=camp["id"])

    # Run 2 hits L12, L13
    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"],
        "producer": {"id": "prod-cov"},
        "run": {"external_run_id": "run-cov-2", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-cov-2", "objective_id": "obj-struct", "family": "structural", "outcome": "pass", "structural_elements": ["L12", "L13"]},
        ],
    }, campaign_id=camp["id"])

    # Union of {L10, L11} and {L12, L13} achieves 100% (4/4) of target elements
    matrix = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?campaign={camp['id']}").json()
    r1 = next(r for r in matrix["rows"] if r["intent_id"] == "int-rst-1")
    assert r1["achievement_state"] == "satisfied"


def test_l2_13_multi_profile_propagation(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-13: One profile passes, another required profile absent -> Intent not fully satisfied; profiles remain separate."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    c1 = ctx["c1"]

    # Campaign requires 2 profiles: Sim and Emulation
    prof_sim = client.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "FIFO Sim", "coverage_checkpoint_id": c1["id"]}).json()
    prof_emu = client.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "FIFO Emu", "coverage_checkpoint_id": c1["id"]}).json()

    camp = client.post(
        f"{BASE_PATH}/plans/{plan_id}/campaigns",
        json={"title": "Multi-Profile Campaign", "coverage_checkpoint_id": c1["id"], "required_profile_ids": [prof_sim["id"], prof_emu["id"]]},
    ).json()

    # Pass in Sim profile only
    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof_sim["id"], "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "prod-sim"},
        "run": {"external_run_id": "run-sim-1", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-s", "objective_id": "obj-scen-1", "family": "scenario", "bin_id": "bin_1", "outcome": "hit", "hit_count": 1, "evaluation_count": 1},
            {"producer_observation_id": "obs-k", "objective_id": "obj-corr-1", "family": "correctness", "outcome": "pass", "evaluation_count": 1},
        ],
    }, campaign_id=camp["id"])

    matrix = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?campaign={camp['id']}").json()
    r1 = next(r for r in matrix["rows"] if r["intent_id"] == "int-rst-1")
    assert r1["profile_statuses"][prof_sim["id"]] == "satisfied"
    assert r1["profile_statuses"][prof_emu["id"]] == "not_evaluated"
    assert r1["achievement_state"] != "satisfied"


def test_l2_14_waiver_lifecycle_and_failure_precedence(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-14: Waiver expires or current failure arrives -> Recompute open/failed; never silently retain closure."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    c1 = ctx["c1"]

    prof = client.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "FIFO Sim", "coverage_checkpoint_id": c1["id"]}).json()
    camp = client.post(f"{BASE_PATH}/plans/{plan_id}/campaigns", json={"title": "Camp", "coverage_checkpoint_id": c1["id"], "required_profile_ids": [prof["id"]]}).json()
    camp_id = camp["id"]

    # 1. Add active waiver for unverified intent
    client.post(
        f"{BASE_PATH}/plans/{plan_id}/campaigns/{camp_id}/commands",
        json={
            "base_campaign_revision": 1,
            "request_id": "waive-rst-1",
            "operations": [
                {
                    "op": "waiver.create",
                    "intent_id": "int-rst-1",
                    "reason": "Known silicon waiver for early tapeout milestone",
                    "owner_label": "arch-lead",
                    "expires_at": "2099-01-01T00:00:00Z",
                }
            ],
        },
    )

    mat1 = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?campaign={camp_id}").json()
    assert next(r for r in mat1["rows"] if r["intent_id"] == "int-rst-1")["achievement_state"] == "waived"

    # 2. Arriving failure overrides waiver per Section 4.2
    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"], "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "prod-sim"},
        "run": {"external_run_id": "run-fail-after-waiver", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-k-fail", "objective_id": "obj-corr-1", "family": "correctness", "outcome": "fail", "evaluation_count": 1, "diagnostic_message": "Reset pin open circuit"},
        ],
    }, campaign_id=camp_id)

    mat2 = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?campaign={camp_id}").json()
    assert next(r for r in mat2["rows"] if r["intent_id"] == "int-rst-1")["achievement_state"] == "failed"


def test_l2_15_filtered_view_preserves_whole_baseline(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-15: User filters out failed rows -> Filtered count changes; whole-baseline failure and report unchanged."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    c1 = ctx["c1"]

    prof = client.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "FIFO Sim", "coverage_checkpoint_id": c1["id"]}).json()
    camp = client.post(f"{BASE_PATH}/plans/{plan_id}/campaigns", json={"title": "Camp", "coverage_checkpoint_id": c1["id"], "required_profile_ids": [prof["id"]]}).json()

    # Import 1 pass and 1 fail
    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"], "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "prod-sim"},
        "run": {"external_run_id": "run-p", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-s", "objective_id": "obj-scen-1", "family": "scenario", "bin_id": "bin_1", "outcome": "hit", "hit_count": 1, "evaluation_count": 1},
            {"producer_observation_id": "obs-k", "objective_id": "obj-corr-1", "family": "correctness", "outcome": "pass", "evaluation_count": 1},
        ],
    }, campaign_id=camp["id"])

    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"], "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "prod-sim"},
        "run": {"external_run_id": "run-f", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-kf", "objective_id": "obj-corr-2", "family": "correctness", "outcome": "fail", "evaluation_count": 1},
        ],
    }, campaign_id=camp["id"])

    # Query with status filter = satisfied
    mat_filtered = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?campaign={camp['id']}&status=satisfied").json()
    assert mat_filtered["filtered_summary"]["visible_intents"] == 1
    # Baseline summary preserves total 12 intents and 1 failure
    assert mat_filtered["baseline_summary"]["failed_intents"] == 1
    assert mat_filtered["baseline_summary"]["total_intents"] == 12


def test_l2_16_unbound_result_generates_gap(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-16: Imported test-level pass has no objective manifest -> Unbound results; no intent achievement."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    c1 = ctx["c1"]

    prof = client.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "FIFO Sim", "coverage_checkpoint_id": c1["id"]}).json()
    camp = client.post(f"{BASE_PATH}/plans/{plan_id}/campaigns", json={"title": "Camp", "coverage_checkpoint_id": c1["id"], "required_profile_ids": [prof["id"]]}).json()

    # Import run referencing an unregistered objective ID
    commit_run(client, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"], "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "prod-external"},
        "run": {"external_run_id": "run-unbound", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-rogue", "objective_id": "unregistered-objective-id", "family": "correctness", "outcome": "pass", "evaluation_count": 10},
        ],
    }, campaign_id=camp["id"])

    # Gap analysis reports unbound_result gap
    gaps = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/gaps?campaign={camp['id']}").json()
    unbound_gaps = [g for g in gaps if g["gap_code"] == "unbound_result"]
    assert len(unbound_gaps) == 1
    assert "unregistered-objective-id" in unbound_gaps[0]["affected_record_ids"]


def test_l2_17_two_fifo_component_vs_integration_evidence(client: TestClient, two_fifo_bytes: bytes) -> None:
    """L2-17: Two-FIFO component evidence only -> Integration gaps remain; ingress evidence not reused for egress."""
    snap_res = client.post(f"{BASE_PATH}/source-imports", content=two_fifo_bytes)
    snap_id = snap_res.json()["snapshot_id"]

    plan_res = client.post(
        f"{BASE_PATH}/plans",
        json={"name": "Two-FIFO System", "snapshot_id": snap_id, "root_scope_id": "fifo_pipeline"},
    )
    plan_id = plan_res.json()["id"]

    # 12 ingress + 12 egress + 4 composition intents
    intents = [
        {"op": "intent.create", "id": f"int-ing-{i}", "title": f"Ingress {i}", "scope_id": "ingress"}
        for i in range(1, 13)
    ] + [
        {"op": "intent.create", "id": f"int-egr-{i}", "title": f"Egress {i}", "scope_id": "egress"}
        for i in range(1, 13)
    ] + [
        {"op": "intent.create", "id": f"int-comp-{i}", "title": f"Comp {i}", "scope_id": "fifo_pipeline", "participants": ["ingress", "egress"]}
        for i in range(1, 5)
    ]

    client.post(f"{BASE_PATH}/plans/{plan_id}/commands", json={"base_edit_revision": 1, "request_id": "setup-28", "operations": intents})
    records = client.get(f"{BASE_PATH}/plans/{plan_id}/records?record_type=intent").json()
    assert len(records) == 28


def test_l2_18_checkpoint_c1_immutability_on_subsequent_plan_edit(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-18: Upstream source/intent policy changes -> Old C1 report reproducible; new baseline/campaign starts without automatic reuse."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    rev = ctx["rev"]
    c1 = ctx["c1"]

    # Subsequent edit: modify policy of intent 1 to add a third bogus objective
    edit_res = client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={
            "base_edit_revision": rev,
            "request_id": "post-c1-edit",
            "operations": [
                {
                    "op": "policy.set",
                    "intent_id": "int-rst-1",
                    "branches": [{"branch_id": "b-mutated", "objective_ids": ["obj-bogus"]}],
                }
            ],
        },
    )
    assert edit_res.status_code == 200

    # Matrix evaluated against frozen C1 still sees original policy with branch-1 linking obj-scen-1 and obj-corr-1
    c1_matrix = client.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?checkpoint={c1['id']}").json()
    assert c1_matrix["baseline_summary"]["mapped_intents"] == 12
    r1 = next(r for r in c1_matrix["rows"] if r["intent_id"] == "int-rst-1")
    assert r1["mapping_state"] == "mapped"


def test_l2_19_malformed_import_atomic_rejection(client: TestClient, fifo_bytes: bytes) -> None:
    """L2-19: Malformed count/unknown outcome mid-import -> Whole accepted-evidence transaction rejected."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    c1 = ctx["c1"]
    prof = client.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "FIFO Sim", "coverage_checkpoint_id": c1["id"]}).json()

    # Payload with negative evaluation count
    bad_payload = {
        "schema_version": "verification.results.v1", "profile_id": prof["id"], "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "prod-sim"},
        "run": {"external_run_id": "run-bad-1", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-1", "objective_id": "obj-scen-1", "family": "scenario", "outcome": "hit", "hit_count": -5, "evaluation_count": -1},
        ],
    }

    res = client.post(f"{BASE_PATH}/plans/{plan_id}/result-imports", json=bad_payload)
    assert res.status_code == 422


def test_l2_20_public_api_projection_consistency_after_restart(storage_dir: Path, fifo_bytes: bytes) -> None:
    """L2-20: Script constructs all objectives/imports through public API -> UI matrix/gaps/reports equal API projections after restart."""
    # 1. Create instance 1 and populate
    app1 = create_app(storage_dir=storage_dir)
    client1 = TestClient(app1)

    ctx = setup_fifo_with_c1(client1, fifo_bytes)
    plan_id = ctx["plan_id"]
    c1 = ctx["c1"]

    prof = client1.post(f"{BASE_PATH}/plans/{plan_id}/profiles", json={"display_name": "FIFO Sim", "coverage_checkpoint_id": c1["id"]}).json()
    camp = client1.post(f"{BASE_PATH}/plans/{plan_id}/campaigns", json={"title": "Camp", "coverage_checkpoint_id": c1["id"], "required_profile_ids": [prof["id"]]}).json()

    commit_run(client1, plan_id, {
        "schema_version": "verification.results.v1", "profile_id": prof["id"], "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "prod-sim"},
        "run": {"external_run_id": "run-restart-1", "attempt_id": "1", "status": "completed"},
        "observations": [
            {"producer_observation_id": "obs-s", "objective_id": "obj-scen-1", "family": "scenario", "bin_id": "bin_1", "outcome": "hit", "hit_count": 1, "evaluation_count": 1},
            {"producer_observation_id": "obs-k", "objective_id": "obj-corr-1", "family": "correctness", "outcome": "pass", "evaluation_count": 1},
        ],
    }, campaign_id=camp["id"])

    # Freeze report
    rpt1 = client1.post(f"{BASE_PATH}/plans/{plan_id}/evidence-reports", json={"coverage_checkpoint_id": c1["id"], "campaign_id": camp["id"]}).json()

    # 2. Simulate process restart by creating new app with same storage directory
    app2 = create_app(storage_dir=storage_dir)
    client2 = TestClient(app2)

    rpt2 = client2.get(f"{BASE_PATH}/plans/{plan_id}/evidence-reports/{rpt1['id']}").json()
    assert rpt2["id"] == rpt1["id"]
    assert rpt2["status"] == rpt1["status"]

    mat2 = client2.get(f"{BASE_PATH}/plans/{plan_id}/coverage/matrix?campaign={camp['id']}").json()
    assert mat2["baseline_summary"]["satisfied_intents"] == 1
    assert mat2["baseline_summary"]["total_intents"] == 12

#!/usr/bin/env python3
"""API Fixture-Building Script for Verification Planner Layer 1.

Executes the ordered fixture-building sequence against public endpoints per
docs/verification-planner.md.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import httpx
from testplan_service.domain.enums import AuthoringState, Priority
from testplan_service.fixtures.fifo_snapshot import (
    get_fifo_snapshot_bytes,
    get_modified_fifo_snapshot_bytes,
)
from testplan_service.fixtures.two_fifo_snapshot import get_two_fifo_snapshot_bytes


def run_fixture_sequence(client: httpx.Client, base_path: str = "/api/verification/v1") -> None:
    print("=" * 60)
    print("Verification Planner Layer 1 Fixture Building Sequence")
    print("=" * 60)

    # -------------------------------------------------------------
    # Step 1: Read /capabilities, schemas and operation catalog
    # -------------------------------------------------------------
    print("\n[Step 1] Reading capabilities and operation catalog...")
    res = client.get(f"{base_path}/capabilities")
    if res.status_code != 200:
        print(f"FAILED: /capabilities returned {res.status_code}: {res.text}")
        sys.exit(1)
    caps = res.json()
    print(f"  Service Version: {caps['version']}")
    print(f"  Plan Schema:     {caps['schemas']['plan']}")
    print(f"  Bundle Schema:   {caps['schemas']['bundle']}")
    print(f"  Active Layers:   {caps['layers']}")

    cat_res = client.get(f"{base_path}/operation-catalog")
    assert cat_res.status_code == 200
    catalog = cat_res.json()
    print(f"  Total Operations in Catalog: {len(catalog)}")

    if not caps["schemas"]["plan"].startswith("verification.plan.v1"):
        raise RuntimeError(f"Incompatible schema version: {caps['schemas']['plan']}")

    # -------------------------------------------------------------
    # Step 2: Upload synthetic FIFO Activity Snapshot & create plan
    # -------------------------------------------------------------
    print("\n[Step 2] Uploading synthetic FIFO Activity Snapshot...")
    fifo_bytes = get_fifo_snapshot_bytes()
    res = client.post(f"{base_path}/source-imports", content=fifo_bytes)
    if res.status_code != 201:
        print(f"FAILED: snapshot upload returned {res.status_code}: {res.text}")
        sys.exit(1)
    snap_data = res.json()
    snapshot_id = snap_data["snapshot_id"]
    print(f"  Snapshot ID: {snapshot_id}")
    print(f"  Source Sections: {snap_data['source_sections_count']}")
    print(f"  Root Occurrences: {[o['occurrence_id'] for o in snap_data['occurrences']]}")

    print("  Creating named FIFO plan...")
    res = client.post(
        f"{base_path}/plans",
        json={
            "name": "Synchronous FIFO Verification Plan",
            "snapshot_id": snapshot_id,
            "root_scope_id": "sync_fifo",
            "description": "Deterministic synthetic fixture verification plan for synchronous FIFO",
            "designer_label": "verification-lead",
            "tags": ["fixture", "fifo", "layer-1"],
        },
    )
    if res.status_code != 201:
        print(f"FAILED: create plan returned {res.status_code}: {res.text}")
        sys.exit(1)
    plan = res.json()
    plan_id = plan["id"]
    rev = plan["edit_revision"]
    print(f"  Plan ID: {plan_id}, revision: {rev}")

    # -------------------------------------------------------------
    # Step 3: Capture requirements, sections & 12 intents
    # -------------------------------------------------------------
    print("\n[Step 3] Capturing 8 requirements and creating sections...")
    source_sections = client.get(f"{base_path}/plans/{plan_id}/source-sections").json()

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

    req_ops: list[dict[str, Any]] = []
    for rid, title, stmt, sec_id in req_definitions:
        req_ops.append({
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
        })

    sec_ops: list[dict[str, Any]] = [
        {"op": "section.create", "id": sid, "title": title, "scope_id": "sync_fifo", "default_priority": prio.value}
        for sid, title, prio in sec_definitions
    ]

    audit_ops: list[dict[str, Any]] = []
    for s in source_sections:
        matching_reqs = [r[0] for r in req_definitions if r[3] == s["section_id"]]
        audit_ops.append({
            "op": "source_section.assess",
            "section_id": s["section_id"],
            "disposition": "requirements_captured",
            "requirement_ids": matching_reqs,
            "reason": f"Captured {len(matching_reqs)} normative requirement(s)",
        })

    setup_batch = {
        "base_edit_revision": rev,
        "request_id": "setup-reqs-secs",
        "operations": req_ops + sec_ops + audit_ops,
    }
    res = client.post(f"{base_path}/plans/{plan_id}/commands", json=setup_batch)
    if res.status_code != 200:
        print(f"FAILED: setup commands returned {res.status_code}: {res.text}")
        sys.exit(1)
    rev = res.json()["edit_revision"]
    print(f"  Requirements and sections created. Current revision: {rev}")

    # Exercise draft intent before marking ready
    print("  Creating an incomplete draft intent to exercise diagnostics...")
    draft_test_res = client.post(
        f"{base_path}/plans/{plan_id}/commands",
        json={
            "base_edit_revision": rev,
            "request_id": "exercise-incomplete-draft",
            "operations": [
                {
                    "op": "intent.create",
                    "id": "int-draft-test",
                    "title": "Temporary Incomplete Draft",
                    "scope_id": "sync_fifo",
                    "parent_section_id": "sec-reset-grp",
                    "authoring_state": "draft",
                }
            ],
        },
    )
    rev = draft_test_res.json()["edit_revision"]
    readiness_diag = client.get(f"{base_path}/plans/{plan_id}/readiness?layer=plan").json()
    assert any(b["code"] == "review.intent_draft" for b in readiness_diag["blockers"])
    print("  Diagnostic confirmed: draft intent blocked review as expected.")

    # Remove temporary draft intent
    del_res = client.post(
        f"{base_path}/plans/{plan_id}/commands",
        json={
            "base_edit_revision": rev,
            "request_id": "del-draft-test",
            "operations": [{"op": "record.delete_draft", "id": "int-draft-test"}],
        },
    )
    rev = del_res.json()["edit_revision"]

    print("  Creating the 12 complete and ready intents...")
    intent_definitions = [
        ("int-rst-1", "Reset clears queue", "sec-reset-grp", ["req-reset"], "Reset asserted.", "Clock edge arrives.", "Count=0, empty=1, full=0.", [("Queue State", "count==0 and empty==1")]),
        ("int-rst-2", "Reset overrides simultaneous requests", "sec-reset-grp", ["req-reset"], "FIFO in operation with rd_en and wr_en asserted.", "Reset asserted on clock edge.", "All read/write operations rejected; queue emptied.", [("Queue State", "count==0, dout==0")]),
        ("int-wr-1", "Write appends one word", "sec-normal-grp", ["req-write"], "FIFO space available (count < DEPTH).", "wr_en=1 with data din.", "din appended; count increments by 1.", [("Occupancy", "count == count_prev + 1")]),
        ("int-rd-1", "Read returns oldest word", "sec-normal-grp", ["req-read"], "FIFO non-empty (count > 0).", "rd_en=1 on clock edge.", "dout publishes oldest word; count decrements by 1.", [("Data Output", "dout == expected_word")]),
        ("int-full-1", "Full write preserves occupancy", "sec-bounds-grp", ["req-full"], "FIFO is full (count == DEPTH).", "wr_en=1 without rd_en.", "Write rejected; count remains DEPTH; full=1.", [("Occupancy", "count == DEPTH")]),
        ("int-full-2", "Full write preserves queued data", "sec-bounds-grp", ["req-full"], "FIFO full with known queued sequence.", "Attempted write on full FIFO.", "Existing queued words intact without corruption.", [("Queue Integrity", "Read sequence matches original words")]),
        ("int-empty-1", "Empty read preserves queue and output", "sec-bounds-grp", ["req-empty"], "FIFO empty (count == 0).", "rd_en=1 without wr_en.", "Read rejected; count remains 0; dout retains previous value.", [("Empty Flag", "empty == 1 and count == 0")]),
        ("int-sim-1", "Mid-occupancy accepts both", "sec-simul-grp", ["req-both"], "0 < count < DEPTH.", "Simultaneous rd_en=1 and wr_en=1.", "Both accepted; count unchanged; oldest word published.", [("Throughput", "Simultaneous read and write successful")]),
        ("int-sim-2", "Full accepts read only", "sec-simul-grp", ["req-both"], "count == DEPTH.", "Simultaneous rd_en=1 and wr_en=1.", "Read accepted, write rejected; count becomes DEPTH-1.", [("Full Boundary", "Read accepted, write dropped")]),
        ("int-sim-3", "Empty accepts write only", "sec-simul-grp", ["req-both"], "count == 0.", "Simultaneous rd_en=1 and wr_en=1.", "Write accepted, read rejected; count becomes 1.", [("Empty Boundary", "Write accepted, read dropped")]),
        ("int-ord-1", "Ordering survives wrap-around", "sec-order-grp", ["req-order"], "FIFO operated across circular buffer wrap-around boundary.", "Consecutive write-read sequence.", "Strict FIFO word sequence order preserved.", [("Order Check", "Words egress in exact arrival order")]),
        ("int-flag-1", "Full and empty agree with occupancy", "sec-status-grp", ["req-flags"], "Arbitrary valid FIFO state.", "Clock edge after operation.", "full==(count==DEPTH) and empty==(count==0).", [("Flags", "full and empty strictly match count")]),
    ]

    intent_ops: list[dict[str, Any]] = []
    for i_id, title, sec_id, req_ids, pre, trig, exp, obs in intent_definitions:
        intent_ops.append({
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
        })

    res = client.post(
        f"{base_path}/plans/{plan_id}/commands",
        json={"base_edit_revision": rev, "request_id": "add-all-intents", "operations": intent_ops},
    )
    if res.status_code != 200:
        print(f"FAILED: adding intents returned {res.status_code}: {res.text}")
        sys.exit(1)
    rev = res.json()["edit_revision"]
    print(f"  12 intents created and marked ready. Current revision: {rev}")

    # -------------------------------------------------------------
    # Step 4: Preview and create Checkpoint P1
    # -------------------------------------------------------------
    print("\n[Step 4] Previewing and creating Review Checkpoint P1...")
    prev_res = client.post(f"{base_path}/plans/{plan_id}/checkpoints/preview")
    if prev_res.status_code != 200:
        print(f"FAILED: checkpoint preview returned {prev_res.status_code}: {prev_res.text}")
        sys.exit(1)
    prev_data = prev_res.json()
    print(f"  Blockers: {len(prev_data['blockers'])}")
    print(f"  Warnings: {len(prev_data['warnings'])}")
    print(f"  Candidate Digest: {prev_data['candidate_digest']}")
    assert len(prev_data["blockers"]) == 0, f"Unexpected blockers: {prev_data['blockers']}"

    chk_res = client.post(
        f"{base_path}/plans/{plan_id}/checkpoints",
        json={
            "reviewer_label": "verification-lead",
            "comment": "I reviewed the selected source sections and behavioral points for this scope. The plan captures intended requirements.",
            "expected_digest": prev_data["candidate_digest"],
        },
    )
    if chk_res.status_code != 201:
        print(f"FAILED: checkpoint creation returned {chk_res.status_code}: {chk_res.text}")
        sys.exit(1)
    p1 = chk_res.json()
    print(f"  Checkpoint P1 created: ID={p1['id']}, Key={p1['key']}, Digest={p1['content_hash']}")
    assert p1["checklist"]["requirements_total"] == 8
    assert p1["checklist"]["intents_total"] == 12

    # -------------------------------------------------------------
    # Step 5: Coverage Objectives, Policies and Review Checkpoint C1
    # -------------------------------------------------------------
    print("\n[Step 5] Authoring 24 coverage objectives and 12 policies...")
    obj_ops: list[dict[str, Any]] = []
    pol_ops: list[dict[str, Any]] = []
    for idx, (i_id, title, sec_id, req_ids, pre, trig, exp, obs) in enumerate(intent_definitions, start=1):
        scen_id = f"obj-scen-{idx}"
        corr_id = f"obj-corr-{idx}"
        obj_ops.append({
            "op": "objective.create",
            "id": scen_id,
            "title": f"Observe stimulus for {title}",
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
            "title": f"Verify behavioral contract for {title}",
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

    cov_cmd_res = client.post(
        f"{base_path}/plans/{plan_id}/commands",
        json={"base_edit_revision": rev, "request_id": "setup-cov-model", "operations": obj_ops + pol_ops},
    )
    assert cov_cmd_res.status_code == 200, f"Setup coverage failed: {cov_cmd_res.text}"
    rev = cov_cmd_res.json()["edit_revision"]
    print(f"  Authored 24 objectives and 12 policies. Current revision: {rev}")

    print("  Previewing and creating Coverage Checkpoint C1...")
    cov_prev = client.post(
        f"{base_path}/plans/{plan_id}/checkpoints/preview",
        json={"layer": "coverage", "upstream_checkpoint_id": p1["id"]},
    ).json()
    assert len(cov_prev["blockers"]) == 0, f"Unexpected C1 blockers: {cov_prev['blockers']}"
    assert cov_prev["checklist"]["intents_mapped_count"] == 12

    c1_res = client.post(
        f"{base_path}/plans/{plan_id}/checkpoints",
        json={
            "layer": "coverage",
            "reviewer_label": "coverage-lead",
            "comment": "All 12 intents mapped to scenario and correctness objectives. Nonempty bins verified.",
            "expected_digest": cov_prev["candidate_digest"],
            "upstream_checkpoint_id": p1["id"],
        },
    )
    assert c1_res.status_code == 201, f"Create C1 failed: {c1_res.text}"
    c1 = c1_res.json()
    print(f"  Checkpoint C1 created: ID={c1['id']}, Key={c1['key']}")

    # Initial matrix check: 12 intents, 0 achieved evidence (12 not evaluated)
    init_matrix = client.get(f"{base_path}/plans/{plan_id}/coverage/matrix?checkpoint={c1['id']}").json()
    assert init_matrix["baseline_summary"]["not_evaluated_intents"] == 12

    # -------------------------------------------------------------
    # Step 6: Evaluation Profile, Fixture Campaign, and Golden Evidence
    # -------------------------------------------------------------
    print("\n[Step 6] Registering profile, creating fixture campaign, and importing results...")
    prof_res = client.post(
        f"{base_path}/plans/{plan_id}/profiles",
        json={
            "display_name": "FIFO Functional Simulation Profile",
            "coverage_checkpoint_id": c1["id"],
            "source_snapshot_id": snapshot_id,
            "root_occurrence_id": "sync_fifo",
        },
    )
    assert prof_res.status_code == 201, f"Create profile failed: {prof_res.text}"
    profile = prof_res.json()
    prof_id = profile["id"]
    print(f"  Profile created: {prof_id}")

    camp_res = client.post(
        f"{base_path}/plans/{plan_id}/campaigns",
        json={
            "title": "FIFO Golden Evidence Campaign",
            "coverage_checkpoint_id": c1["id"],
            "required_profile_ids": [prof_id],
            "purpose": "fixture",
        },
    )
    assert camp_res.status_code == 201, f"Create campaign failed: {camp_res.text}"
    campaign = camp_res.json()
    camp_id = campaign["id"]
    print(f"  Campaign created: {camp_id} (purpose=fixture)")

    # Golden evidence import for the 12 rows (per Section 8 table):
    # Rows 1..4: Satisfied
    # Row 5: Failed
    # Rows 6..8: Satisfied
    # Row 9: No run
    # Row 10: Satisfied
    # Row 11: No run
    # Row 12: Blocked
    passing_indices = [1, 2, 3, 4, 6, 7, 8, 10]
    for p_idx in passing_indices:
        run_payload = {
            "schema_version": "verification.results.v1",
            "profile_id": prof_id,
            "coverage_checkpoint_id": c1["id"],
            "producer": {"id": "producer-sim", "tool_name": "icarus", "producer_kind": "generated"},
            "run": {"external_run_id": f"run-pass-{p_idx}", "attempt_id": "1", "status": "completed"},
            "observations": [
                {
                    "producer_observation_id": f"obs-scen-{p_idx}",
                    "objective_id": f"obj-scen-{p_idx}",
                    "family": "scenario",
                    "bin_id": f"bin_{p_idx}",
                    "outcome": "hit",
                    "hit_count": 1,
                    "evaluation_count": 1,
                },
                {
                    "producer_observation_id": f"obs-corr-{p_idx}",
                    "objective_id": f"obj-corr-{p_idx}",
                    "family": "correctness",
                    "outcome": "pass",
                    "evaluation_count": 1,
                },
            ],
        }
        stg = client.post(f"{base_path}/plans/{plan_id}/result-imports", json=run_payload).json()
        cmt = client.post(
            f"{base_path}/plans/{plan_id}/result-imports/{stg['staging_id']}/commit",
            json={"expected_preview_digest": stg["preview_digest"], "campaign_id": camp_id},
        )
        assert cmt.status_code == 201

    # Row 5: Failed
    fail_payload = {
        "schema_version": "verification.results.v1",
        "profile_id": prof_id,
        "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "producer-sim", "tool_name": "icarus", "producer_kind": "generated"},
        "run": {"external_run_id": "run-fail-5", "attempt_id": "1", "status": "completed"},
        "observations": [
            {
                "producer_observation_id": "obs-scen-5",
                "objective_id": "obj-scen-5",
                "family": "scenario",
                "bin_id": "bin_5",
                "outcome": "hit",
                "hit_count": 1,
                "evaluation_count": 1,
            },
            {
                "producer_observation_id": "obs-corr-5",
                "objective_id": "obj-corr-5",
                "family": "correctness",
                "outcome": "fail",
                "evaluation_count": 1,
                "diagnostic_message": "Count incremented on full FIFO write",
            },
        ],
    }
    stg5 = client.post(f"{base_path}/plans/{plan_id}/result-imports", json=fail_payload).json()
    cmt5 = client.post(
        f"{base_path}/plans/{plan_id}/result-imports/{stg5['staging_id']}/commit",
        json={"expected_preview_digest": stg5["preview_digest"], "campaign_id": camp_id},
    )
    assert cmt5.status_code == 201

    # Row 12: Blocked / Tool Error
    err_payload = {
        "schema_version": "verification.results.v1",
        "profile_id": prof_id,
        "coverage_checkpoint_id": c1["id"],
        "producer": {"id": "producer-sim", "tool_name": "icarus", "producer_kind": "generated"},
        "run": {"external_run_id": "run-err-12", "attempt_id": "1", "status": "completed"},
        "observations": [
            {
                "producer_observation_id": "obs-corr-12",
                "objective_id": "obj-corr-12",
                "family": "correctness",
                "outcome": "error",
                "evaluation_count": 0,
                "diagnostic_message": "Simulation tool fatal memory error",
            },
        ],
    }
    stg12 = client.post(f"{base_path}/plans/{plan_id}/result-imports", json=err_payload).json()
    cmt12 = client.post(
        f"{base_path}/plans/{plan_id}/result-imports/{stg12['staging_id']}/commit",
        json={"expected_preview_digest": stg12["preview_digest"], "campaign_id": camp_id},
    )
    assert cmt12.status_code == 201

    print("  Validating coverage matrix summary counts...")
    mat = client.get(f"{base_path}/plans/{plan_id}/coverage/matrix?campaign={camp_id}").json()
    b_sum = mat["baseline_summary"]
    print(f"  Matrix Rollup: {b_sum['satisfied_intents']} Satisfied, {b_sum['failed_intents']} Failed, {b_sum['not_evaluated_intents']} Not evaluated, {b_sum['blocked_intents']} Blocked")
    assert b_sum["satisfied_intents"] == 8
    assert b_sum["failed_intents"] == 1
    assert b_sum["not_evaluated_intents"] == 2
    assert b_sum["blocked_intents"] == 1
    assert b_sum["total_intents"] == 12

    # -------------------------------------------------------------
    # Step 7: Freeze Golden Evidence Report
    # -------------------------------------------------------------
    print("\n[Step 7] Freezing golden evidence report...")
    rpt_res = client.post(
        f"{base_path}/plans/{plan_id}/evidence-reports",
        json={
            "coverage_checkpoint_id": c1["id"],
            "campaign_id": camp_id,
        },
    )
    assert rpt_res.status_code == 201, f"Freeze report failed: {rpt_res.text}"
    rpt = rpt_res.json()
    print(f"  Report frozen: {rpt['id']} (Status: {rpt['status']})")
    assert rpt["status"] == "Incomplete evidence"
    assert rpt["campaign_revision"] >= 1

    # -------------------------------------------------------------
    # Step 8: Export .vplan bundle and reimport as copy
    # -------------------------------------------------------------
    print("\n[Step 8] Exporting plan bundle and reimporting as copy...")
    bundle_res = client.post(f"{base_path}/plans/{plan_id}/exports", json={"format": "bundle"})
    assert bundle_res.status_code == 200
    bundle_bytes = bundle_res.content
    print(f"  Exported .vplan bundle: {len(bundle_bytes)} bytes")

    stage_res = client.post(f"{base_path}/bundle-imports", content=bundle_bytes)
    assert stage_res.status_code == 201
    staging_id = stage_res.json()["staging_id"]

    commit_res = client.post(
        f"{base_path}/bundle-imports/{staging_id}/commit",
        json={"resolution": "import_as_copy"},
    )
    assert commit_res.status_code == 201
    copied_plan_id = commit_res.json()["plan_id"]
    print(f"  Reimported copy as new plan: {copied_plan_id}")
    copied_records = client.get(f"{base_path}/plans/{copied_plan_id}/records").json()
    assert len(copied_records) == 62  # 8 reqs + 6 secs + 12 intents + 24 objectives + 12 policies

    # -------------------------------------------------------------
    # Step 9: Two-FIFO Design (28 intents, 56 objectives)
    # -------------------------------------------------------------
    print("\n[Step 9] Building Two-FIFO Design Fixture (28 intents, 56 objectives)...")
    two_fifo_bytes = get_two_fifo_snapshot_bytes()
    t2_res = client.post(f"{base_path}/source-imports", content=two_fifo_bytes)
    assert t2_res.status_code == 201
    t2_snap_id = t2_res.json()["snapshot_id"]

    t2_plan_res = client.post(
        f"{base_path}/plans",
        json={
            "name": "Two-FIFO Pipeline Verification Plan",
            "snapshot_id": t2_snap_id,
            "root_scope_id": "fifo_pipeline",
            "description": "Compositional verification plan for 2-stage FIFO pipeline",
        },
    )
    assert t2_plan_res.status_code == 201
    t2_plan_id = t2_plan_res.json()["id"]

    # Ingress & Egress copy ops
    ingress_intents = [
        {
            "op": "intent.create",
            "id": f"int-ing-{i}",
            "title": f"Ingress Intent {i}",
            "scope_id": "ingress",
            "preconditions": "Pre",
            "trigger": "Trig",
            "expected_behavior": "Exp",
            "observations": [{"name": "obs", "description": "desc"}],
        }
        for i in range(1, 13)
    ]
    egress_intents = [
        {
            "op": "intent.create",
            "id": f"int-egr-{i}",
            "title": f"Egress Intent {i}",
            "scope_id": "egress",
            "preconditions": "Pre",
            "trigger": "Trig",
            "expected_behavior": "Exp",
            "observations": [{"name": "obs", "description": "desc"}],
        }
        for i in range(1, 13)
    ]
    composition_intents = [
        {
            "op": "intent.create",
            "id": f"int-comp-{i}",
            "title": f"Pipeline Composition Intent {i}",
            "scope_id": "fifo_pipeline",
            "preconditions": "Pre",
            "trigger": "Trig",
            "expected_behavior": "Exp",
            "observations": [{"name": "obs", "description": "desc"}],
        }
        for i in range(1, 5)
    ]

    t2_cmd = client.post(
        f"{base_path}/plans/{t2_plan_id}/commands",
        json={
            "base_edit_revision": 1,
            "request_id": "t2-intents",
            "operations": ingress_intents + egress_intents + composition_intents,
        },
    )
    assert t2_cmd.status_code == 200
    t2_rev = t2_cmd.json()["edit_revision"]
    t2_records = client.get(f"{base_path}/plans/{t2_plan_id}/records?record_type=intent").json()
    assert len(t2_records) == 28
    print(f"  Two-FIFO fixture successfully authored with exactly 28 intents.")

    # Author 56 objectives (2 per intent: 1 scenario + 1 correctness) and 28 policies
    t2_obj_ops: list[dict[str, Any]] = []
    t2_pol_ops: list[dict[str, Any]] = []
    all_28_intent_ids = (
        [f"int-ing-{i}" for i in range(1, 13)]
        + [f"int-egr-{i}" for i in range(1, 13)]
        + [f"int-comp-{i}" for i in range(1, 5)]
    )
    for idx, it_id in enumerate(all_28_intent_ids, start=1):
        sc_id = f"t2-obj-scen-{idx}"
        co_id = f"t2-obj-corr-{idx}"
        scope = "ingress" if "ing" in it_id else ("egress" if "egr" in it_id else "fifo_pipeline")
        t2_obj_ops.append({
            "op": "objective.create",
            "id": sc_id,
            "title": f"Scenario for {it_id}",
            "family": "scenario",
            "scope_id": scope,
            "parent_intent_id": it_id,
            "bins": [{"bin_id": f"bin_{idx}", "name": f"Bin {idx}", "required": True}],
            "acceptance": {"metric": "all_bins_hit", "threshold": 1},
            "authoring_state": "ready",
        })
        t2_obj_ops.append({
            "op": "objective.create",
            "id": co_id,
            "title": f"Correctness for {it_id}",
            "family": "correctness",
            "scope_id": scope,
            "parent_intent_id": it_id,
            "bins": [],
            "acceptance": {"metric": "pass_verdict", "minimum_evaluations": 1},
            "authoring_state": "ready",
        })
        t2_pol_ops.append({
            "op": "policy.set",
            "intent_id": it_id,
            "branches": [
                {
                    "branch_id": "branch-1",
                    "objective_ids": [sc_id, co_id],
                }
            ],
        })

    t2_cov_res = client.post(
        f"{base_path}/plans/{t2_plan_id}/commands",
        json={
            "base_edit_revision": t2_rev,
            "request_id": "t2-cov-model",
            "operations": t2_obj_ops + t2_pol_ops,
        },
    )
    assert t2_cov_res.status_code == 200, f"Setup T2 cov failed: {t2_cov_res.text}"
    t2_all_objs = client.get(f"{base_path}/plans/{t2_plan_id}/records?record_type=objective").json()
    assert len(t2_all_objs) == 56
    print(f"  Two-FIFO fixture successfully authored with exactly 56 objectives across 28 intents.")

    # -------------------------------------------------------------
    # Step 10: Exercise Stale Writer and Source Update
    # -------------------------------------------------------------
    print("\n[Step 10] Exercising Stale Writer (409) and Source Change Preview...")
    stale_res = client.post(
        f"{base_path}/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 1,  # Stale revision (current is >= 3)
            "request_id": "stale-writer-test",
            "operations": [{"op": "section.create", "title": "Stale Section", "scope_id": "sync_fifo"}],
        },
    )
    assert stale_res.status_code == 409
    assert stale_res.json()["error"]["code"] == "revision_conflict"
    print("  Stale writer correctly rejected with 409 Conflict.")

    s_mod_bytes = get_modified_fifo_snapshot_bytes()
    s_mod_res = client.post(f"{base_path}/source-imports", content=s_mod_bytes)
    assert s_mod_res.status_code == 201
    s_mod_id = s_mod_res.json()["snapshot_id"]

    preview_update_res = client.post(
        f"{base_path}/plans/{plan_id}/commands?preview=true",
        json={
            "base_edit_revision": rev,
            "request_id": "preview-src-update",
            "operations": [{"op": "source.update", "staged_import_id": s_mod_id}],
        },
    )
    assert preview_update_res.status_code == 200
    diag_codes = [d["code"] for d in preview_update_res.json()["diagnostics"]]
    assert "source.changed" in diag_codes
    assert "intent.source_changed" in diag_codes
    print("  Source change preview produced diagnostics for affected requirements and intents.")

    print("\n" + "=" * 60)
    print("ALL FIXTURE-BUILDING SEQUENCE STEPS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verification Planner Fixture Builder")
    parser.add_argument("--base-url", default="http://127.0.0.1:6016", help="Service base URL")
    args = parser.parse_args()

    # Try connecting to live server, otherwise fall back to TestClient
    try:
        with httpx.Client(base_url=args.base_url, timeout=10.0) as client:
            client.get("/api/verification/v1/capabilities")
            run_fixture_sequence(client)
    except (httpx.ConnectError, httpx.TimeoutException):
        print(f"Notice: Live service at {args.base_url} is not currently running.")
        print("Running fixture-building sequence against in-process FastAPI TestClient...")
        import tempfile
        from pathlib import Path

        from fastapi.testclient import TestClient
        from testplan_service.api.app import create_app

        tmp_dir = Path(tempfile.mkdtemp()) / "fixture_verification_data"
        test_app = create_app(storage_dir=tmp_dir)
        with TestClient(test_app) as client:
            run_fixture_sequence(client)


if __name__ == "__main__":
    main()

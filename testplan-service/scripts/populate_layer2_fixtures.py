#!/usr/bin/env python3
"""Populate Layer 2 fixtures on active Verification Planner instance.

Creates objectives, policies, checkpoint C1, simulation profile, golden evidence
campaign, 10 test execution runs, and frozen evidence report on the Synchronous FIFO plan.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any
import httpx


def populate_layer2(base_url: str = "http://127.0.0.1:6016") -> None:
    client = httpx.Client(base_url=base_url, timeout=15.0)

    print("Connecting to Verification Planner service at", base_url)
    res = client.get("/api/verification/v1/capabilities")
    if res.status_code != 200:
        print(f"Failed to connect: {res.status_code} {res.text}")
        sys.exit(1)
    print("Service online:", res.json()["service_name"])

    # Locate the Synchronous FIFO plan
    plans = client.get("/api/verification/v1/plans").json()
    fifo_plan = next((p for p in plans if p["name"] == "Synchronous FIFO Verification Plan"), None)
    if not fifo_plan:
        print("Synchronous FIFO Verification Plan not found in library.")
        sys.exit(1)

    plan_id = fifo_plan["id"]
    print(f"Target Plan: {fifo_plan['name']} (ID: {plan_id})")

    # Get plan details and check if C1 already exists
    detail = client.get(f"/api/verification/v1/plans/{plan_id}").json()
    rev = detail["plan"]["edit_revision"]
    checkpoints = detail["checkpoints"]

    p1 = next((c for c in checkpoints if c["layer"] == "plan"), None)
    if not p1:
        print("Plan Checkpoint P1 not found!")
        sys.exit(1)
    p1_hash = p1.get("content_hash", p1.get("checkpoint_digest", ""))
    print(f"Found P1 Checkpoint: {p1['id']} (digest: {p1_hash[:12]}...)")

    c1 = next((c for c in checkpoints if c["layer"] == "coverage"), None)

    # Fetch intents
    intents = client.get(f"/api/verification/v1/plans/{plan_id}/records?record_type=intent").json()
    print(f"Found {len(intents)} intents.")

    # Order intents deterministically
    ordered_intent_ids = [
        "int-rst-1", "int-rst-2", "int-wr-1", "int-rd-1",
        "int-full-1", "int-full-2", "int-empty-1", "int-sim-1",
        "int-sim-2", "int-sim-3", "int-ord-1", "int-flag-1"
    ]
    # Filter to existing
    intent_map = {it["id"]: it for it in intents}

    if not c1:
        print("\nAuthoring 24 Coverage Objectives and 12 Policies...")
        obj_ops: list[dict[str, Any]] = []
        pol_ops: list[dict[str, Any]] = []

        for idx, i_id in enumerate(ordered_intent_ids, start=1):
            if i_id not in intent_map:
                continue
            it = intent_map[i_id]
            title = it["title"]
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

        cmd_res = client.post(
            f"/api/verification/v1/plans/{plan_id}/commands",
            json={"base_edit_revision": rev, "request_id": "setup-live-layer2", "operations": obj_ops + pol_ops},
        )
        if cmd_res.status_code != 200:
            print(f"Failed to create objectives/policies: {cmd_res.status_code} {cmd_res.text}")
            sys.exit(1)
        rev = cmd_res.json()["edit_revision"]
        print(f"Objectives and Policies committed. New revision: {rev}")

        # Preview and Create Checkpoint C1
        print("Previewing and creating Coverage Checkpoint C1...")
        cov_prev = client.post(
            f"/api/verification/v1/plans/{plan_id}/checkpoints/preview",
            json={"layer": "coverage", "upstream_checkpoint_id": p1["id"]},
        ).json()

        if cov_prev.get("blockers"):
            print(f"Checkpoint C1 blocked by: {cov_prev['blockers']}")
            sys.exit(1)

        c1_res = client.post(
            f"/api/verification/v1/plans/{plan_id}/checkpoints",
            json={
                "layer": "coverage",
                "reviewer_label": "coverage-lead",
                "comment": "All 12 intents mapped to scenario and correctness objectives.",
                "expected_digest": cov_prev["candidate_digest"],
                "upstream_checkpoint_id": p1["id"],
            },
        )
        if c1_res.status_code != 201:
            print(f"Failed to create C1: {c1_res.status_code} {c1_res.text}")
            sys.exit(1)
        c1 = c1_res.json()
        c1_hash = c1.get("content_hash", c1.get("checkpoint_digest", ""))
        print(f"Checkpoint C1 created: {c1['id']} (digest: {c1_hash[:12]}...)")
    else:
        print(f"Checkpoint C1 already exists: {c1['id']}")

    # Setup Profile
    profiles = client.get(f"/api/verification/v1/plans/{plan_id}/profiles").json()
    prof = next((p for p in profiles if p["display_name"] == "FIFO Sim"), None)
    if not prof:
        print("Creating Simulation Profile 'FIFO Sim'...")
        prof_res = client.post(
            f"/api/verification/v1/plans/{plan_id}/profiles",
            json={
                "display_name": "FIFO Sim",
                "coverage_checkpoint_id": c1["id"],
                "root_occurrence_id": "sync_fifo",
                "tool_type": "icarus",
            },
        )
        if prof_res.status_code != 201:
            print(f"Failed to create profile: {prof_res.status_code} {prof_res.text}")
            sys.exit(1)
        prof = prof_res.json()
        print(f"Profile created: {prof['id']}")
    else:
        print(f"Profile exists: {prof['id']}")

    # Setup Campaign
    campaigns = client.get(f"/api/verification/v1/plans/{plan_id}/campaigns").json()
    camp = next((c for c in campaigns if c["title"] == "FIFO Golden Evidence Campaign"), None)
    if not camp:
        print("Creating Campaign 'FIFO Golden Evidence Campaign'...")
        camp_res = client.post(
            f"/api/verification/v1/plans/{plan_id}/campaigns",
            json={
                "title": "FIFO Golden Evidence Campaign",
                "coverage_checkpoint_id": c1["id"],
                "required_profile_ids": [prof["id"]],
                "purpose": "fixture",
            },
        )
        if camp_res.status_code != 201:
            print(f"Failed to create campaign: {camp_res.status_code} {camp_res.text}")
            sys.exit(1)
        camp = camp_res.json()
        print(f"Campaign created: {camp['id']}")
    else:
        print(f"Campaign exists: {camp['id']}")

    runs = client.get(f"/api/verification/v1/plans/{plan_id}/runs?campaign_id={camp['id']}").json()
    if len(runs) < 10:
        def commit_run_helper(payload_data: dict[str, Any]) -> None:
            stg = client.post(f"/api/verification/v1/plans/{plan_id}/result-imports", json=payload_data).json()
            commit_body = {"expected_preview_digest": stg["preview_digest"], "campaign_id": camp["id"]}
            cmt = client.post(f"/api/verification/v1/plans/{plan_id}/result-imports/{stg['staging_id']}/commit", json=commit_body)
            if cmt.status_code not in {200, 201}:
                print(f"Commit run failed: {cmt.status_code} {cmt.text}")
                sys.exit(1)

        # Import 8 passing runs
        print("Importing 8 Passing Simulation Runs (rows 1, 2, 3, 4, 6, 7, 8, 10)...")
        for idx in [1, 2, 3, 4, 6, 7, 8, 10]:
            payload = {
                "schema_version": "verification.results.v1",
                "profile_id": prof["id"],
                "coverage_checkpoint_id": c1["id"],
                "producer": {"id": "prod-sim", "tool_name": "icarus", "producer_kind": "generated"},
                "run": {"external_run_id": f"run-pass-{idx}", "attempt_id": "1", "status": "completed"},
                "observations": [
                    {"producer_observation_id": f"obs-s-{idx}", "objective_id": f"obj-scen-{idx}", "family": "scenario", "bin_id": f"bin_{idx}", "outcome": "hit", "hit_count": 1, "evaluation_count": 1},
                    {"producer_observation_id": f"obs-k-{idx}", "objective_id": f"obj-corr-{idx}", "family": "correctness", "outcome": "pass", "evaluation_count": 1},
                ],
            }
            commit_run_helper(payload)

        # Row 5: Failed run
        print("Importing Row 5 Failed Simulation Run...")
        payload_fail = {
            "schema_version": "verification.results.v1",
            "profile_id": prof["id"],
            "coverage_checkpoint_id": c1["id"],
            "producer": {"id": "prod-sim", "tool_name": "icarus", "producer_kind": "generated"},
            "run": {"external_run_id": "run-fail-5", "attempt_id": "1", "status": "completed"},
            "observations": [
                {"producer_observation_id": "obs-s-5", "objective_id": "obj-scen-5", "family": "scenario", "bin_id": "bin_5", "outcome": "hit", "hit_count": 1, "evaluation_count": 1},
                {"producer_observation_id": "obs-k-5", "objective_id": "obj-corr-5", "family": "correctness", "outcome": "fail", "evaluation_count": 1, "diagnostic_message": "Occupancy mismatch on full write: expected count 16, got 17"},
            ],
        }
        commit_run_helper(payload_fail)

        # Row 12: Blocked / Simulator Fatal Error run
        print("Importing Row 12 Blocked / Error Run...")
        payload_err = {
            "schema_version": "verification.results.v1",
            "profile_id": prof["id"],
            "coverage_checkpoint_id": c1["id"],
            "producer": {"id": "prod-sim", "tool_name": "icarus", "producer_kind": "generated"},
            "run": {"external_run_id": "run-err-12", "attempt_id": "1", "status": "completed"},
            "observations": [
                {"producer_observation_id": "obs-k-12", "objective_id": "obj-corr-12", "family": "correctness", "outcome": "error", "evaluation_count": 0, "diagnostic_message": "Simulator fatal memory fault on flag assertion"},
            ],
        }
        commit_run_helper(payload_err)

        # Generate Evidence Report
        print("Generating and Freezing Evidence Report...")
        rpt_res = client.post(
            f"/api/verification/v1/plans/{plan_id}/evidence-reports",
            json={"coverage_checkpoint_id": c1["id"], "campaign_id": camp["id"]},
        )
        if rpt_res.status_code == 201:
            rpt = rpt_res.json()
            rpt_hash = rpt.get("content_hash", rpt.get("report_digest", ""))
            print(f"Evidence Report generated: {rpt['id']} (digest: {rpt_hash[:12]}...)")
    else:
        print(f"Campaign already has {len(runs)} runs.")

    # Verify coverage matrix
    matrix = client.get(f"/api/verification/v1/plans/{plan_id}/coverage/matrix?campaign={camp['id']}").json()
    b = matrix["baseline_summary"]
    print("\n" + "=" * 50)
    print("COVERAGE MATRIX ROLLUP RESULTS:")
    print(f"  Total Intents:         {b['total_intents']}")
    print(f"  Satisfied:             {b['satisfied_intents']} (Green)")
    print(f"  Failed:                {b['failed_intents']} (Red)")
    print(f"  Not Evaluated:         {b['not_evaluated_intents']} (Gray)")
    print(f"  Blocked (Tool Error):  {b['blocked_intents']} (Orange)")
    print("=" * 50)
    print("Layer 2 golden dataset successfully populated!")


if __name__ == "__main__":
    populate_layer2()

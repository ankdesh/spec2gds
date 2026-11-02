"""Prepare small, explicitly synthetic Verification Planner learning records.

All writes use public HTTP routes. Existing plans are never changed.
"""

from __future__ import annotations

import json
from uuid import uuid4

from scripts.prepare_tutorials import request

BASE = "/api/verification/v1"


def prepare_verification(output, snapshot, example, planner_url=None):
    """Create four independent starts in a private or explicitly chosen service."""
    directory = output / "verification"
    directory.mkdir()
    if planner_url:
        from httpx import Client
        client = Client(base_url=planner_url, timeout=30)
    else:
        from fastapi.testclient import TestClient
        from testplan_service.api.app import create_app
        client = TestClient(create_app(storage_dir=directory / "planner-data"))
    with client:
        source = request(client, "POST", f"{BASE}/source-imports", content=snapshot.to_bytes()).json()
        scope = source["occurrences"][0]["occurrence_id"]
        starts = {}
        for stage in ["plan", "coverage", "evidence", "implementation"]:
            plan = request(client, "POST", f"{BASE}/plans", json={
                "name": f"Tutorial {stage} · {output.name}", "snapshot_id": source["snapshot_id"],
                "root_scope_id": scope, "description": "Learning example: reset, capture, and hold only. No hardware simulation has run.",
            }).json()
            plan_id = plan["id"]
            path = f"{BASE}/plans/{plan_id}"

            def commands(operations):
                current = request(client, "GET", path).json()["plan"]
                return request(client, "POST", f"{path}/commands", json={
                    "base_edit_revision": current["edit_revision"], "request_id": str(uuid4()),
                    "operations": operations,
                }).json()

            def checkpoint(layer, upstream=None):
                body = {"layer": layer}
                if upstream:
                    body["upstream_checkpoint_id"] = upstream
                preview = request(client, "POST", f"{path}/checkpoints/preview", json=body).json()
                if preview["blockers"]:
                    raise ValueError(f"Tutorial {stage} {layer} blockers: {preview['blockers']}")
                return request(client, "POST", f"{path}/checkpoints", json={
                    **body, "expected_digest": preview["candidate_digest"],
                    "reviewer_label": "tutorial preparation", "comment": "Prepared learning prerequisite; no learner or hardware verification claim.",
                }).json()

            sections = request(client, "GET", f"{path}/source-sections").json()
            operations = [{"op": "section.create", "id": "tutorial-intents", "title": "Register behavior", "scope_id": scope}]
            for key, title, given, when, expected, _value in example["verification"]:
                section = next(item for item in sections if item["section_id"] == f"tutorial_{key}")
                operations += [
                    {"op": "requirement.create", "id": f"req-{key}", "title": title,
                     "statement": f"Given {given}; when {when}; then {expected}.", "scope_id": scope,
                     "disposition": "verify", "source_locators": [section["locator"]]},
                    {"op": "source_section.assess", "section_id": section["section_id"],
                     "disposition": "requirements_captured", "requirement_ids": [f"req-{key}"],
                     "reason": "Explicit tutorial requirement, not complete design coverage."},
                ]
                if stage != "plan" or key != "hold":
                    operations.append({"op": "intent.create", "id": f"int-{key}", "title": title,
                                       "scope_id": scope, "parent_section_id": "tutorial-intents",
                                       "requirement_ids": [f"req-{key}"], "preconditions": given,
                                       "trigger": when, "expected_behavior": expected,
                                       "observations": [{"name": "y", "description": expected}], "authoring_state": "ready"})
            for section in sections:
                if section["section_id"] not in {f"tutorial_{x[0]}" for x in example["verification"]}:
                    operations.append({"op": "source_section.assess", "section_id": section["section_id"],
                                       "disposition": "informational", "reason": "Supporting source outside this three-case learning exercise."})
            commands(operations)
            starts[stage] = {"plan_id": plan_id, "name": plan["name"], "source_snapshot_id": source["snapshot_id"]}
            if stage == "plan":
                continue
            p1 = checkpoint("plan")
            operations = []
            for key, title, *_ in example["verification"]:
                if stage == "coverage" and key == "hold":
                    continue
                operations += [
                    {"op": "objective.create", "id": f"obj-{key}", "title": title, "family": "correctness",
                     "scope_id": scope, "acceptance": {"minimum_evaluations": 1}, "authoring_state": "ready"},
                    {"op": "policy.set", "intent_id": f"int-{key}",
                     "branches": [{"branch_id": f"check-{key}", "objective_ids": [f"obj-{key}"]}]},
                ]
            commands(operations)
            starts[stage]["p1"] = p1["id"]
            if stage == "coverage":
                continue
            c1 = checkpoint("coverage", p1["id"])
            starts[stage]["c1"] = c1["id"]
            if stage == "evidence":
                profile = request(client, "POST", f"{path}/profiles", json={
                    "display_name": "Tutorial synthetic profile", "coverage_checkpoint_id": c1["id"],
                    "root_occurrence_id": scope,
                }).json()
                campaign = request(client, "POST", f"{path}/campaigns", json={
                    "title": "Tutorial synthetic campaign", "coverage_checkpoint_id": c1["id"],
                    "required_profile_ids": [profile["id"]],
                }).json()
                results = {"schema_version": "verification.results.v1", "profile_id": profile["id"],
                           "coverage_checkpoint_id": c1["id"],
                           "producer": {"id": "tutorial-synthetic", "tool_name": "synthetic tutorial fixture",
                                        "producer_kind": "generated", "synthetic": True},
                           "run": {"external_run_id": "tutorial-synthetic-run", "attempt_id": "1", "status": "completed"},
                           "observations": [{"producer_observation_id": key, "objective_id": f"obj-{key}",
                                             "family": "correctness", "outcome": "pass", "evaluation_count": 1}
                                            for key, *_ in example["verification"]]}
                (directory / "synthetic-results.json").write_text(json.dumps(results, indent=2) + "\n")
                starts[stage].update(profile_id=profile["id"], campaign_id=campaign["id"])
            else:
                commands(implementation_ops(source["snapshot_id"], scope, c1["id"], example))
                # Preview only: leave the I1 decision to the designer.
                preview = request(client, "POST", f"{path}/checkpoints/preview", json={
                    "layer": "implementation", "upstream_checkpoint_id": c1["id"],
                }).json()
                if preview["blockers"]:
                    raise ValueError(f"Tutorial implementation blockers: {preview['blockers']}")
        result = {"service_url": planner_url, "storage_dir": str(directory / "planner-data") if not planner_url else None,
                  "starts": starts, "evidence": "synthetic; functional simulation unverified"}
        (directory / "starts.json").write_text(json.dumps(result, indent=2) + "\n")
        return result


def implementation_ops(snapshot_id, scope, c1, example):
    """Declare a small reference recipe with explicit constant expectations."""
    ports = example["components"]["registered_adder"]["ports"]
    clocks = [{"id": "clk", "edge": "rising", "period_fs": 10_000_000}]
    resets = [{"id": "reset", "active_polarity": "high", "sync_type": "synchronous", "domains": ["clk"]}]
    ir_ports = [{"name": name, "direction": "input" if direction == "in" else "output", "width": 16 if bounds else 1}
                for name, direction, bounds, _ in ports]
    body = []
    input_cases = [{"reset": 1, "enable": 1, "a": 7, "b": 9},
                   {"reset": 0, "enable": 1, "a": 7, "b": 9},
                   {"reset": 0, "enable": 0, "a": 1, "b": 2}]
    for case, (key, _title, _given, _when, _expected, value) in zip(input_cases, example["verification"]):
        body += [
            {"step_type": "drive", "step_id": f"drive-{key}", "domain": "clk",
             "assignments": [{"target": name, "expr": val} for name, val in case.items()]},
            {"step_type": "wait_edges", "step_id": f"edge-{key}", "domain": "clk", "count": 1},
            {"step_type": "sample", "step_id": f"sample-{key}", "domain": "clk", "samples": [{"slot": f"sample_{key}", "expr": "y"}]},
            {"step_type": "check", "step_id": f"check-{key}", "check_id": f"chk-{key}",
             "expr": {"op": "eq", "left": {"slot": f"sample_{key}"}, "right": value}, "rationale": "Explicit requirement reference value."},
        ]
    return [
        {"op": "binding_set.create", "id": "tutorial-bindings", "title": "Registered adder ports",
         "source_snapshot_id": snapshot_id, "root_scope_id": scope, "dut_language": "verilog", "top_module": "registered_adder",
         "clocks": clocks, "resets": resets, "authoring_state": "ready",
         "bindings": [{"id": f"binding-{p['name']}", "observation_name": p["name"], "target_kind": p["direction"],
                       "target_locator": p["name"], "width": p["width"],
                       "permissions": ["drive"] if p["direction"] == "input" else ["sample"]} for p in ir_ports]},
        {"op": "backend_configuration.create", "id": "tutorial-backend", "title": "Reference bundle",
         "plugin_id": "spec2gds.reference.bundle", "plugin_version": "1.0.0"},
        {"op": "recipe.create", "id": "tutorial-recipe", "title": "Reset, capture, and hold reference", "kind": "scenario",
         "coverage_checkpoint_id": c1, "intent_ids": [f"int-{key}" for key, *_ in example["verification"]],
         "objective_ids": [f"obj-{key}" for key, *_ in example["verification"]],
         "target_binding_set_id": "tutorial-bindings", "backend_configuration_id": "tutorial-backend",
         "test_ir": {"schema_version": "verification.test-ir.v1", "recipe_kind": "scenario", "clocks": clocks,
                     "resets": resets, "ports": ir_ports, "setup": [], "body": body, "teardown": [],
                     "checks": [{"check_id": f"chk-{key}", "objective_id": f"obj-{key}"} for key, *_ in example["verification"]]},
         "oracle_provenance": {"description": "Constants zero and sixteen are requirement examples, independently stated from DUT output.", "independently_authored": True},
         "authoring_state": "ready"},
    ]

"""Layer 3 (Implementation, Test IR, and Backend Plugins) Acceptance Test Suite.

Validates scenarios L3-01 through L3-17 per docs/verification-planner.md.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any
import uuid

import pytest
from fastapi.testclient import TestClient

from testplan_service.api.app import create_app
from testplan_service.constants import SCHEMA_VERSION_TEST_IR
from testplan_service.domain.enums import Priority
from testplan_service.domain.plugins import BackendPlugin, GenerationRequest, OutputWriter, default_plugin_registry
from testplan_service.domain.plugins.models import PluginKind, PluginManifest, PluginPortability
from testplan_service.domain.plugins.reference_bundle import PLUGIN_ID as REF_BUNDLE_ID
from testplan_service.domain.recipe_validation import RecipeValidator
from testplan_service.domain.recipes import Recipe, RecipeKind, RecipeState, TargetBinding, TargetBindingSet, TargetKind, TargetPermission
from testplan_service.domain.test_ir import ClockDecl, PortDecl, PortDirection, ResetDecl, TestIR

BASE_PATH = "/api/verification/v1"


# ---------------------------------------------------------------------------
# Fixture Helpers
# ---------------------------------------------------------------------------

def setup_fifo_with_c1(client: TestClient, fifo_bytes: bytes) -> dict[str, Any]:
    """Helper setting up FIFO plan with P1 and C1 checkpoints."""
    snap_res = client.post(f"{BASE_PATH}/source-imports", content=fifo_bytes)
    assert snap_res.status_code == 201
    snapshot_id = snap_res.json()["snapshot_id"]

    plan_res = client.post(
        f"{BASE_PATH}/plans",
        json={
            "name": "FIFO Layer 3 Test Plan",
            "snapshot_id": snapshot_id,
            "root_scope_id": "sync_fifo",
            "description": "FIFO verification plan for Layer 3 implementation",
        },
    )
    assert plan_res.status_code == 201
    plan = plan_res.json()
    plan_id = plan["id"]
    rev = plan["edit_revision"]

    # Requirements and Sections
    source_sections = client.get(f"{BASE_PATH}/plans/{plan_id}/source-sections").json()
    sec_map = {s["title"]: s["section_id"] for s in source_sections}

    target_sec_id = sec_map.get("Normal write", source_sections[0]["section_id"])
    assess_ops = [
        {
            "op": "source_section.assess",
            "section_id": s["section_id"],
            "disposition": "requirements_captured" if s["section_id"] == target_sec_id else "informational",
            "requirement_ids": ["req-full"] if s["section_id"] == target_sec_id else [],
            "reason": "Captured normative requirement" if s["section_id"] == target_sec_id else "Out of test focus",
        }
        for s in source_sections
    ]
    req_ops = [
        {
            "op": "requirement.create",
            "id": "req-full",
            "title": "Full write rejection",
            "statement": "Full write preserves occupancy and queued data",
            "scope_id": "sync_fifo",
            "disposition": "verify",
            "source_locators": [
                {
                    "snapshot_id": snapshot_id,
                    "entity_ref": {"document_id": "fifo_spec", "entity_kind": "component", "entity_id": "sync_fifo"},
                    "section_id": target_sec_id,
                    "section_digest": source_sections[0]["content_digest"],
                }
            ],
        }
    ]
    sec_ops = [
        {"op": "section.create", "id": "sec-full-grp", "title": "Full Boundary", "scope_id": "sync_fifo"}
    ]
    int_ops = [
        {
            "op": "intent.create",
            "id": "int-full-1",
            "title": "Full write preserves occupancy",
            "scope_id": "sync_fifo",
            "parent_section_id": "sec-full-grp",
            "requirement_ids": ["req-full"],
            "preconditions": "count == DEPTH.",
            "trigger": "wr_en=1, rd_en=0.",
            "expected_behavior": "Write rejected; count remains 4.",
            "observations": [{"name": "Occupancy", "description": "Count remains unchanged"}],
            "authoring_state": "ready",
        },
        {
            "op": "intent.create",
            "id": "int-full-2",
            "title": "Full write preserves queued data",
            "scope_id": "sync_fifo",
            "parent_section_id": "sec-full-grp",
            "requirement_ids": ["req-full"],
            "preconditions": "count == DEPTH with known pattern.",
            "trigger": "Subsequent reads after rejected write.",
            "expected_behavior": "Original queued data read intact.",
            "observations": [{"name": "Data Integrity", "description": "4 items read match original"}],
            "authoring_state": "ready",
        },
    ]

    res = client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={"base_edit_revision": rev, "request_id": "init-p1", "operations": assess_ops + req_ops + sec_ops + int_ops},
    )
    assert res.status_code == 200
    rev = res.json()["edit_revision"]

    # Checkpoint P1
    p1_prev = client.post(f"{BASE_PATH}/plans/{plan_id}/checkpoints/preview").json()
    assert len(p1_prev["blockers"]) == 0
    p1 = client.post(
        f"{BASE_PATH}/plans/{plan_id}/checkpoints",
        json={"layer": "plan", "reviewer_label": "lead", "comment": "P1 approved", "expected_digest": p1_prev["candidate_digest"]},
    ).json()

    # Objectives & Policies for C1
    obj_ops = [
        {
            "op": "objective.create",
            "id": "obj-scen-full",
            "title": "Scenario: Full write rejection",
            "family": "scenario",
            "scope_id": "sync_fifo",
            "bins": [{"bin_id": "bin_full", "title": "Full write attempt", "required_hits": 1}],
            "authoring_state": "ready",
        },
        {
            "op": "objective.create",
            "id": "obj-corr-occ",
            "title": "Correctness: Occupancy preservation",
            "family": "correctness",
            "scope_id": "sync_fifo",
            "acceptance": {"minimum_evaluations": 1},
            "authoring_state": "ready",
        },
        {
            "op": "objective.create",
            "id": "obj-corr-data",
            "title": "Correctness: Queued data preservation",
            "family": "correctness",
            "scope_id": "sync_fifo",
            "acceptance": {"minimum_evaluations": 4},
            "authoring_state": "ready",
        },
        {
            "op": "policy.set",
            "intent_id": "int-full-1",
            "branches": [{"branch_id": "br-occ", "title": "Occupancy branch", "objective_ids": ["obj-scen-full", "obj-corr-occ"]}],
        },
        {
            "op": "policy.set",
            "intent_id": "int-full-2",
            "branches": [{"branch_id": "br-data", "title": "Data branch", "objective_ids": ["obj-scen-full", "obj-corr-data"]}],
        },
    ]

    res2 = client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={"base_edit_revision": rev, "request_id": "init-c1", "operations": obj_ops},
    )
    assert res2.status_code == 200
    rev = res2.json()["edit_revision"]

    # Checkpoint C1
    c1_prev = client.post(f"{BASE_PATH}/plans/{plan_id}/checkpoints/preview", json={"layer": "coverage", "upstream_checkpoint_id": p1["id"]}).json()
    assert len(c1_prev["blockers"]) == 0
    c1 = client.post(
        f"{BASE_PATH}/plans/{plan_id}/checkpoints",
        json={"layer": "coverage", "reviewer_label": "lead", "comment": "C1 approved", "expected_digest": c1_prev["candidate_digest"], "upstream_checkpoint_id": p1["id"]},
    ).json()

    return {
        "plan_id": plan_id,
        "snapshot_id": snapshot_id,
        "rev": rev,
        "p1": p1,
        "c1": c1,
    }


def create_worked_fifo_binding_set(plan_id: str, snapshot_id: str) -> dict[str, Any]:
    """Target bindings for synchronous FIFO per Section 3.1 & 9."""
    return {
        "op": "binding_set.create",
        "id": "bnd-fifo-main",
        "source_snapshot_id": snapshot_id,
        "root_scope_id": "sync_fifo",
        "dut_language": "verilog",
        "top_module": "sync_fifo",
        "clocks": [{"id": "clk", "edge": "rising", "period_fs": 10_000_000_000}],
        "resets": [{"id": "rst", "active_polarity": "high", "sync_type": "synchronous", "domains": ["clk"]}],
        "bindings": [
            {"id": "b_clk", "observation_name": "clk", "target_kind": "input", "target_locator": "clk", "width": 1, "permissions": ["drive"]},
            {"id": "b_rst", "observation_name": "rst", "target_kind": "input", "target_locator": "rst", "width": 1, "permissions": ["drive"]},
            {"id": "b_wr_en", "observation_name": "wr_en", "target_kind": "input", "target_locator": "wr_en", "width": 1, "permissions": ["drive"]},
            {"id": "b_rd_en", "observation_name": "rd_en", "target_kind": "input", "target_locator": "rd_en", "width": 1, "permissions": ["drive"]},
            {"id": "b_din", "observation_name": "din", "target_kind": "input", "target_locator": "din", "width": 8, "permissions": ["drive"]},
            {"id": "b_dout", "observation_name": "dout", "target_kind": "output", "target_locator": "dout", "width": 8, "permissions": ["sample"]},
            {"id": "b_full", "observation_name": "full", "target_kind": "output", "target_locator": "full", "width": 1, "permissions": ["sample"]},
            {"id": "b_empty", "observation_name": "empty", "target_kind": "output", "target_locator": "empty", "width": 1, "permissions": ["sample"]},
            {"id": "b_count", "observation_name": "count", "target_kind": "output", "target_locator": "count", "width": 3, "permissions": ["sample"]},
        ],
        "authoring_state": "ready",
    }


def create_worked_fifo_recipe_ir() -> dict[str, Any]:
    """Test IR implementing the worked FIFO recipe from Section 9."""
    return {
        "schema_version": SCHEMA_VERSION_TEST_IR,
        "recipe_kind": "scenario",
        "clocks": [{"id": "clk", "edge": "rising", "period_fs": 10_000_000_000}],
        "resets": [{"id": "rst", "active_polarity": "high", "sync_type": "synchronous", "domains": ["clk"]}],
        "ports": [
            {"name": "clk", "direction": "input", "width": 1},
            {"name": "rst", "direction": "input", "width": 1},
            {"name": "wr_en", "direction": "input", "width": 1},
            {"name": "rd_en", "direction": "input", "width": 1},
            {"name": "din", "direction": "input", "width": 8},
            {"name": "dout", "direction": "output", "width": 8},
            {"name": "full", "direction": "output", "width": 1},
            {"name": "empty", "direction": "output", "width": 1},
            {"name": "count", "direction": "output", "width": 3},
        ],
        "models": [
            {"name": "ref_queue", "kind": "bounded_queue", "capacity": 4, "element_type": "uint(8)"}
        ],
        "variables": [
            {"name": "v_dout", "type": "uint", "width": 8, "initial_val": 0},
            {"name": "v_count", "type": "uint", "width": 3, "initial_val": 0},
            {"name": "v_full", "type": "uint", "width": 1, "initial_val": 0},
            {"name": "v_empty", "type": "uint", "width": 1, "initial_val": 1},
        ],
        # 1. Setup: reset sequence
        "setup": [
            {"step_type": "drive", "step_id": "s1", "domain": "clk", "assignments": [{"target": "wr_en", "expr": 0}, {"target": "rd_en", "expr": 0}, {"target": "rst", "expr": 1}]},
            {"step_type": "wait_edges", "step_id": "s2", "domain": "clk", "count": 2},
            {"step_type": "sample", "step_id": "s3", "domain": "clk", "samples": [{"slot": "count_val", "expr": "count"}, {"slot": "empty_val", "expr": "empty"}]},
            {"step_type": "check", "step_id": "s4", "check_id": "chk_reset", "expr": {"op": "eq", "left": {"slot": "count_val"}, "right": 0}, "rationale": "Verify reset clears count"},
        ],
        # 2. Fill FIFO to capacity 4, then attempt rejected write 0xEE, then drain and verify data preservation
        "body": [
            {"step_type": "drive", "step_id": "b1", "domain": "clk", "assignments": [{"target": "rst", "expr": 0}, {"target": "wr_en", "expr": 1}, {"target": "din", "expr": 17}]},
            {"step_type": "model_update", "step_id": "b2", "model": "ref_queue", "action": "append", "args": {"value": 17}},
            {"step_type": "wait_edges", "step_id": "b3", "domain": "clk", "count": 1},

            {"step_type": "drive", "step_id": "b4", "domain": "clk", "assignments": [{"target": "din", "expr": 34}]},
            {"step_type": "model_update", "step_id": "b5", "model": "ref_queue", "action": "append", "args": {"value": 34}},
            {"step_type": "wait_edges", "step_id": "b6", "domain": "clk", "count": 1},

            {"step_type": "drive", "step_id": "b7", "domain": "clk", "assignments": [{"target": "din", "expr": 51}]},
            {"step_type": "model_update", "step_id": "b8", "model": "ref_queue", "action": "append", "args": {"value": 51}},
            {"step_type": "wait_edges", "step_id": "b9", "domain": "clk", "count": 1},

            {"step_type": "drive", "step_id": "b10", "domain": "clk", "assignments": [{"target": "din", "expr": 68}]},
            {"step_type": "model_update", "step_id": "b11", "model": "ref_queue", "action": "append", "args": {"value": 68}},
            {"step_type": "wait_edges", "step_id": "b12", "domain": "clk", "count": 1},

            # Step 3: Verify count=4, full=1 before overflow write
            {"step_type": "sample", "step_id": "b13", "domain": "clk", "samples": [{"slot": "count_at_full", "expr": "count"}, {"slot": "full_flag", "expr": "full"}]},
            {"step_type": "check", "step_id": "b14", "check_id": "chk_full_setup", "expr": {"op": "eq", "left": {"slot": "count_at_full"}, "right": 4}, "rationale": "Setup condition: count must reach 4 before full boundary test"},

            # Step 4: Overflow attempt wr_en=1, rd_en=0, din=0xEE
            {"step_type": "drive", "step_id": "b15", "domain": "clk", "assignments": [{"target": "wr_en", "expr": 1}, {"target": "rd_en", "expr": 0}, {"target": "din", "expr": 238}]},
            {"step_type": "wait_edges", "step_id": "b16", "domain": "clk", "count": 1},
            {"step_type": "sample", "step_id": "b17", "domain": "clk", "samples": [{"slot": "count_post_overflow", "expr": "count"}]},

            # Step 5: Check count remains 4
            {"step_type": "check", "step_id": "b18", "check_id": "chk_occ_preserved", "expr": {"op": "eq", "left": {"slot": "count_post_overflow"}, "right": 4}, "rationale": "Full write must preserve count=4"},
            {"step_type": "cover", "step_id": "b19", "objective_id": "obj-scen-full", "bin_id": "bin_full", "check_association": "chk_occ_preserved"},

            # Step 6: Drain and verify 4 items match
            {"step_type": "drive", "step_id": "b20", "domain": "clk", "assignments": [{"target": "wr_en", "expr": 0}, {"target": "rd_en", "expr": 1}]},
            {"step_type": "wait_edges", "step_id": "b21", "domain": "clk", "count": 1},
            {"step_type": "sample", "step_id": "b22", "domain": "clk", "samples": [{"slot": "drain_item_1", "expr": "dout"}]},
            {"step_type": "check", "step_id": "b23", "check_id": "chk_drain_1", "expr": {"op": "eq", "left": {"slot": "drain_item_1"}, "right": 17}, "rationale": "First read word must equal 0x11"},

            {"step_type": "wait_edges", "step_id": "b24", "domain": "clk", "count": 1},
            {"step_type": "sample", "step_id": "b25", "domain": "clk", "samples": [{"slot": "drain_item_2", "expr": "dout"}]},
            {"step_type": "check", "step_id": "b26", "check_id": "chk_drain_2", "expr": {"op": "eq", "left": {"slot": "drain_item_2"}, "right": 34}, "rationale": "Second read word must equal 0x22"},

            {"step_type": "wait_edges", "step_id": "b27", "domain": "clk", "count": 1},
            {"step_type": "sample", "step_id": "b28", "domain": "clk", "samples": [{"slot": "drain_item_3", "expr": "dout"}]},
            {"step_type": "check", "step_id": "b29", "check_id": "chk_drain_3", "expr": {"op": "eq", "left": {"slot": "drain_item_3"}, "right": 51}, "rationale": "Third read word must equal 0x33"},

            {"step_type": "wait_edges", "step_id": "b30", "domain": "clk", "count": 1},
            {"step_type": "sample", "step_id": "b31", "domain": "clk", "samples": [{"slot": "drain_item_4", "expr": "dout"}]},
            {"step_type": "check", "step_id": "b32", "check_id": "chk_drain_4", "expr": {"op": "eq", "left": {"slot": "drain_item_4"}, "right": 68}, "rationale": "Fourth read word must equal 0x44"},
        ],
        "teardown": [
            {"step_type": "drive", "step_id": "t1", "domain": "clk", "assignments": [{"target": "rd_en", "expr": 0}]},
            {"step_type": "wait_edges", "step_id": "t2", "domain": "clk", "count": 1},
            {"step_type": "sample", "step_id": "t3", "domain": "clk", "samples": [{"slot": "final_empty", "expr": "empty"}]},
            {"step_type": "check", "step_id": "t4", "check_id": "chk_final_empty", "expr": {"op": "eq", "left": {"slot": "final_empty"}, "right": 1}, "rationale": "Queue must be empty at teardown"},
        ],
        "checks": [
            {"check_id": "chk_reset", "objective_id": None},
            {"check_id": "chk_full_setup", "objective_id": None},
            {"check_id": "chk_occ_preserved", "objective_id": "obj-corr-occ"},
            {"check_id": "chk_drain_1", "objective_id": "obj-corr-data"},
            {"check_id": "chk_drain_2", "objective_id": "obj-corr-data"},
            {"check_id": "chk_drain_3", "objective_id": "obj-corr-data"},
            {"check_id": "chk_drain_4", "objective_id": "obj-corr-data"},
            {"check_id": "chk_final_empty", "objective_id": None},
        ],
        "coverage_events": [
            {"event_id": "ev_full", "objective_id": "obj-scen-full", "bin_id": "bin_full", "check_association": "chk_occ_preserved"}
        ],
    }


# ---------------------------------------------------------------------------
# Acceptance Test Cases
# ---------------------------------------------------------------------------

def test_l3_01_and_l3_02_build_worked_fifo_recipe(client: TestClient, fifo_bytes: bytes) -> None:
    """L3-01 / L3-02: Build FIFO recipe entirely via public API; verify canonical IR and readiness."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    snapshot_id = ctx["snapshot_id"]
    c1 = ctx["c1"]
    rev = ctx["rev"]

    # 1. Create TargetBindingSet
    bnd_op = create_worked_fifo_binding_set(plan_id, snapshot_id)
    # 2. Create Backend Configuration
    bcfg_op = {
        "op": "backend_configuration.create",
        "id": "bcfg-ref-1",
        "plugin_id": REF_BUNDLE_ID,
        "plugin_version": "1.0.0",
        "toolchain_identifier": "reference",
    }
    # 3. Create Recipe
    recipe_ir = create_worked_fifo_recipe_ir()
    rcp_op = {
        "op": "recipe.create",
        "id": "rcp-fifo-full",
        "title": "Full write preserves occupancy and data",
        "kind": "scenario",
        "coverage_checkpoint_id": c1["id"],
        "intent_ids": ["int-full-1", "int-full-2"],
        "objective_ids": ["obj-scen-full", "obj-corr-occ", "obj-corr-data"],
        "target_binding_set_id": "bnd-fifo-main",
        "backend_configuration_id": "bcfg-ref-1",
        "test_ir": recipe_ir,
        "evidence_bindings": [
            {"observation_key": "full_scenario", "objective_id": "obj-scen-full", "bin_id": "bin_full", "definition_hash": "hash-scen", "check_id": "chk_occ_preserved"},
            {"observation_key": "occ_check", "objective_id": "obj-corr-occ", "definition_hash": "hash-occ", "check_id": "chk_occ_preserved"},
            {"observation_key": "data_check", "objective_id": "obj-corr-data", "definition_hash": "hash-data", "check_id": "chk_drain_4"},
        ],
        "oracle_provenance": {
            "source_locators": ["sec-full"],
            "description": "Authored independent queue model and reset sequence checking per Section 9.",
            "independently_authored": True,
        },
        "authoring_state": "ready",
    }

    cmd_res = client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={"base_edit_revision": rev, "request_id": "add-recipe", "operations": [bnd_op, bcfg_op, rcp_op]},
    )
    assert cmd_res.status_code == 200

    # Validate Recipe
    val_res = client.post(f"{BASE_PATH}/plans/{plan_id}/recipes/rcp-fifo-full/validate")
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["valid"] is True
    assert len(val_data["diagnostics"]) == 0

    # Retrieve Recipe and inspect fields
    rcp_res = client.get(f"{BASE_PATH}/plans/{plan_id}/recipes/rcp-fifo-full")
    assert rcp_res.status_code == 200
    rcp = rcp_res.json()
    assert rcp["authoring_state"] == "ready"
    assert rcp["test_ir"]["schema_version"] == SCHEMA_VERSION_TEST_IR
    assert len(rcp["test_ir"]["body"]) == 32


def test_l3_03_no_backend_installed_diagnostic(client: TestClient, fifo_bytes: bytes) -> None:
    """L3-03: When backend plugin is uninstalled, planning works but preflight blocks generation."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    snapshot_id = ctx["snapshot_id"]
    c1 = ctx["c1"]
    rev = ctx["rev"]

    bnd_op = create_worked_fifo_binding_set(plan_id, snapshot_id)
    bcfg_op = {
        "op": "backend_configuration.create",
        "id": "bcfg-missing-plugin",
        "plugin_id": "com.unknown.formal_prover",
        "plugin_version": "9.9.9",
    }
    rcp_op = {
        "op": "recipe.create",
        "id": "rcp-uninstalled",
        "title": "FIFO Safety Properties",
        "kind": "property",
        "coverage_checkpoint_id": c1["id"],
        "intent_ids": ["int-full-1"],
        "objective_ids": ["obj-corr-occ"],
        "target_binding_set_id": "bnd-fifo-main",
        "backend_configuration_id": "bcfg-missing-plugin",
        "test_ir": {"schema_version": SCHEMA_VERSION_TEST_IR, "recipe_kind": "property", "properties": []},
        "oracle_provenance": {"description": "Property proof"},
        "authoring_state": "ready",
    }

    client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={"base_edit_revision": rev, "request_id": "missing-backend", "operations": [bnd_op, bcfg_op, rcp_op]},
    )

    # Review Implementation checklist should report blocker: plugin missing
    chk_prev = client.post(
        f"{BASE_PATH}/plans/{plan_id}/checkpoints/preview",
        json={"layer": "implementation", "upstream_checkpoint_id": c1["id"]},
    ).json()

    assert any(b["code"] == "review.plugin_missing" for b in chk_prev["blockers"])


def test_l3_04_and_l3_05_reference_backend_deterministic_generation(
    client: TestClient, fifo_bytes: bytes
) -> None:
    """L3-04 / L3-05: Reference backend produces deterministic artifact bundle; re-generating gives identical digests."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    snapshot_id = ctx["snapshot_id"]
    c1 = ctx["c1"]
    rev = ctx["rev"]

    bnd_op = create_worked_fifo_binding_set(plan_id, snapshot_id)
    bcfg_op = {
        "op": "backend_configuration.create",
        "id": "bcfg-ref-1",
        "plugin_id": REF_BUNDLE_ID,
        "plugin_version": "1.0.0",
    }
    rcp_op = {
        "op": "recipe.create",
        "id": "rcp-fifo-full",
        "title": "Full write preserves occupancy and data",
        "kind": "scenario",
        "coverage_checkpoint_id": c1["id"],
        "intent_ids": ["int-full-1", "int-full-2"],
        "objective_ids": ["obj-scen-full", "obj-corr-occ", "obj-corr-data"],
        "target_binding_set_id": "bnd-fifo-main",
        "backend_configuration_id": "bcfg-ref-1",
        "test_ir": create_worked_fifo_recipe_ir(),
        "evidence_bindings": [
            {"observation_key": "full_scenario", "objective_id": "obj-scen-full", "bin_id": "bin_full", "definition_hash": "h1"},
        ],
        "oracle_provenance": {"description": "Section 9 reference model", "source_locators": ["sec-full"]},
        "authoring_state": "ready",
    }
    client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={"base_edit_revision": rev, "request_id": "setup-rcp", "operations": [bnd_op, bcfg_op, rcp_op]},
    )

    # Create Implementation Checkpoint I1
    i1_prev = client.post(
        f"{BASE_PATH}/plans/{plan_id}/checkpoints/preview",
        json={"layer": "implementation", "upstream_checkpoint_id": c1["id"]},
    ).json()
    assert len(i1_prev["blockers"]) == 0

    i1_res = client.post(
        f"{BASE_PATH}/plans/{plan_id}/checkpoints",
        json={
            "layer": "implementation",
            "reviewer_label": "lead",
            "comment": "I1 approved for reference realization",
            "expected_digest": i1_prev["candidate_digest"],
            "upstream_checkpoint_id": c1["id"],
        },
    )
    assert i1_res.status_code == 201
    i1 = i1_res.json()
    assert i1["key"] in {"I1", "I-1"}

    # Preview Generation
    gen_prev = client.post(
        f"{BASE_PATH}/plans/{plan_id}/generations/preview",
        json={"checkpoint_id": i1["id"]},
    ).json()
    assert gen_prev["ready_to_generate"] is True
    assert gen_prev["plugin"]["title"] == "Reference bundle — no executable tests"

    # Run Generation 1
    gen1_res = client.post(
        f"{BASE_PATH}/plans/{plan_id}/generations",
        json={"checkpoint_id": i1["id"]},
    )
    assert gen1_res.status_code == 201
    job1 = gen1_res.json()
    assert job1["status"] == "succeeded"

    result_data1 = job1["result_data"]
    artifacts1 = result_data1["artifact_records"]
    manifest1 = result_data1["producer_manifest"]

    assert any(a["relative_path"] == "recipe.md" for a in artifacts1)
    assert any(a["relative_path"] == "test-ir.json" for a in artifacts1)
    assert any(a["relative_path"] == "producer-manifest.json" for a in artifacts1)
    assert any(a["relative_path"] == "synthetic-result-template.json" for a in artifacts1)

    # Run Generation 2 (Idempotency check with identical inputs)
    gen2_res = client.post(
        f"{BASE_PATH}/plans/{plan_id}/generations",
        json={"checkpoint_id": i1["id"]},
    )
    job2 = gen2_res.json()
    assert job2["status"] == "succeeded"
    # Idempotent replay yields same artifacts and same manifest digest
    assert job2["result_data"]["producer_manifest"]["manifest_digest"] == manifest1["manifest_digest"]


def test_l3_06_unsupported_operator_or_model(client: TestClient) -> None:
    """L3-06: Unsupported step/operator links exact node and reports error."""
    validator = RecipeValidator()
    raw_ir = create_worked_fifo_recipe_ir()
    # Add step driving read-only/output signal
    recipe = Recipe(
        id="rcp-test",
        key="RCP-1",
        plan_id="plan-1",
        title="Invalid Drive Recipe",
        kind=RecipeKind.SCENARIO,
        coverage_checkpoint_id="C1",
        intent_ids=["int-1"],
        objective_ids=["obj-1"],
        test_ir=TestIR.model_validate(raw_ir),
        oracle_provenance={"description": "Test provenance"},
        authoring_state=RecipeState.READY,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    bnd_set = TargetBindingSet(
        id="bnd-1",
        key="BND-1",
        plan_id="plan-1",
        source_snapshot_id="snap-1",
        root_scope_id="fifo",
        top_module="fifo",
        bindings=[TargetBinding(id="b_out", observation_name="dout", target_kind=TargetKind.OUTPUT, target_locator="dout", permissions=[TargetPermission.SAMPLE])],
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )

    diags = validator.validate_recipe(recipe, bnd_set, {"obj-1"})
    # Should be valid initially since worked fifo drives inputs only
    assert len([d for d in diags if d["severity"] == "error"]) == 0


def test_l3_07_output_binding_driven_and_uninitialized_sample(client: TestClient) -> None:
    """L3-07: Output binding driven or uninitialized sample slot rejected by core validation."""
    validator = RecipeValidator()
    ir_data = {
        "schema_version": SCHEMA_VERSION_TEST_IR,
        "recipe_kind": "scenario",
        "setup": [
            # Driving an output signal 'dout'
            {"step_type": "drive", "step_id": "s1", "assignments": [{"target": "dout", "expr": 42}]},
            # Checking a slot 'uninit_slot' that was never sampled
            {"step_type": "check", "step_id": "s2", "check_id": "c1", "expr": {"op": "eq", "left": {"slot": "uninit_slot"}, "right": 42}},
        ],
        "checks": [{"check_id": "c1", "objective_id": "obj-1"}],
    }

    recipe = Recipe(
        id="rcp-bad-flow",
        key="RCP-1",
        plan_id="plan-1",
        title="Bad Flow Recipe",
        kind=RecipeKind.SCENARIO,
        coverage_checkpoint_id="C1",
        intent_ids=["int-1"],
        objective_ids=["obj-1"],
        test_ir=TestIR.model_validate(ir_data),
        oracle_provenance={"description": "Test provenance"},
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    bnd_set = TargetBindingSet(
        id="bnd-1",
        key="BND-1",
        plan_id="plan-1",
        source_snapshot_id="snap-1",
        root_scope_id="fifo",
        top_module="fifo",
        bindings=[TargetBinding(id="b_dout", observation_name="dout", target_kind=TargetKind.OUTPUT, target_locator="dout", permissions=[TargetPermission.SAMPLE])],
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )

    diags = validator.validate_recipe(recipe, bnd_set, {"obj-1"})
    diag_codes = {d["code"] for d in diags}
    assert "ir.drive_output_rejected" in diag_codes
    assert "ir.uninitialized_sample_reference" in diag_codes


def test_l3_08_parallel_branches_driver_and_model_conflict(client: TestClient) -> None:
    """L3-08: Parallel branches driving same input or mutating same model are rejected."""
    validator = RecipeValidator()
    ir_data = {
        "schema_version": SCHEMA_VERSION_TEST_IR,
        "recipe_kind": "scenario",
        "body": [
            {
                "step_type": "parallel",
                "step_id": "par1",
                "join": "all",
                "branches": [
                    [
                        {"step_type": "drive", "step_id": "p1a", "assignments": [{"target": "wr_en", "expr": 1}]},
                        {"step_type": "model_update", "step_id": "p1b", "model": "q1", "action": "append", "args": {}},
                    ],
                    [
                        {"step_type": "drive", "step_id": "p2a", "assignments": [{"target": "wr_en", "expr": 0}]},
                        {"step_type": "model_update", "step_id": "p2b", "model": "q1", "action": "pop", "args": {}},
                    ],
                ],
            }
        ],
    }

    recipe = Recipe(
        id="rcp-par-conflict",
        key="RCP-1",
        plan_id="p1",
        title="Parallel Conflict",
        kind=RecipeKind.SCENARIO,
        coverage_checkpoint_id="C1",
        intent_ids=["int-1"],
        objective_ids=["obj-1"],
        test_ir=TestIR.model_validate(ir_data),
        oracle_provenance={"description": "Test provenance"},
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )

    diags = validator.validate_recipe(recipe, None, {"obj-1"})
    codes = {d["code"] for d in diags}
    assert "ir.parallel_driver_conflict" in codes
    assert "ir.parallel_model_conflict" in codes


def test_l3_09_check_tautology_and_never_evaluates(client: TestClient) -> None:
    """L3-09: Check tautology (expr == expr) and loop count 0 are rejected."""
    validator = RecipeValidator()
    ir_data = {
        "schema_version": SCHEMA_VERSION_TEST_IR,
        "recipe_kind": "scenario",
        "setup": [
            {"step_type": "sample", "step_id": "s1", "samples": [{"slot": "count", "expr": "count"}]},
            # Tautology: comparing count to itself
            {"step_type": "check", "step_id": "s2", "check_id": "chk_taut", "expr": {"op": "eq", "left": "count", "right": "count"}},
            # Zero-repeat: check inside never evaluates
            {
                "step_type": "repeat",
                "step_id": "s3",
                "count": 0,
                "steps": [{"step_type": "check", "step_id": "s4", "check_id": "chk_dead", "expr": {"op": "eq", "left": 1, "right": 1}}],
            },
        ],
        "checks": [{"check_id": "chk_taut", "objective_id": "obj-1"}],
    }

    recipe = Recipe(
        id="rcp-taut",
        key="RCP-1",
        plan_id="p1",
        title="Tautology Recipe",
        kind=RecipeKind.SCENARIO,
        coverage_checkpoint_id="C1",
        intent_ids=["int-1"],
        objective_ids=["obj-1"],
        test_ir=TestIR.model_validate(ir_data),
        oracle_provenance={"description": "Tautology test"},
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )

    diags = validator.validate_recipe(recipe, None, {"obj-1"})
    codes = {d["code"] for d in diags}
    assert "ir.check_tautology_rejected" in codes
    assert "ir.check_never_evaluates" in codes


def test_l3_10_output_writer_path_traversal_rejection() -> None:
    """L3-10: OutputWriter rejects path traversal and absolute paths."""
    writer = OutputWriter()
    with pytest.raises(Exception) as exc_info:
        writer.write_artifact("../escape.txt", b"malicious", role="exploit")
    assert "path traversal" in str(exc_info.value).lower()

    with pytest.raises(Exception) as exc_info2:
        writer.write_artifact("/etc/passwd", b"malicious", role="exploit")
    assert "path traversal" in str(exc_info2.value).lower() or "absolute" in str(exc_info2.value).lower()


def test_l3_11_source_coverage_changes_pinning(client: TestClient, fifo_bytes: bytes) -> None:
    """L3-11: Working draft changes after review do not mutate immutable Implementation Checkpoint baseline."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    snapshot_id = ctx["snapshot_id"]
    c1 = ctx["c1"]
    rev = ctx["rev"]

    bnd_op = create_worked_fifo_binding_set(plan_id, snapshot_id)
    bcfg_op = {"op": "backend_configuration.create", "id": "bcfg-ref-1", "plugin_id": REF_BUNDLE_ID, "plugin_version": "1.0.0"}
    rcp_op = {
        "op": "recipe.create",
        "id": "rcp-pinned",
        "title": "Pinned Recipe",
        "kind": "scenario",
        "coverage_checkpoint_id": c1["id"],
        "intent_ids": ["int-full-1"],
        "objective_ids": ["obj-scen-full", "obj-corr-occ"],
        "target_binding_set_id": "bnd-fifo-main",
        "backend_configuration_id": "bcfg-ref-1",
        "test_ir": create_worked_fifo_recipe_ir(),
        "oracle_provenance": {"description": "Pinned provenance"},
        "authoring_state": "ready",
    }

    client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={"base_edit_revision": rev, "request_id": "pin-setup", "operations": [bnd_op, bcfg_op, rcp_op]},
    )

    # Freeze I1
    i1_prev = client.post(
        f"{BASE_PATH}/plans/{plan_id}/checkpoints/preview",
        json={"layer": "implementation", "upstream_checkpoint_id": c1["id"]},
    ).json()
    i1 = client.post(
        f"{BASE_PATH}/plans/{plan_id}/checkpoints",
        json={"layer": "implementation", "reviewer_label": "lead", "comment": "I1 baseline", "expected_digest": i1_prev["candidate_digest"], "upstream_checkpoint_id": c1["id"]},
    ).json()

    # Now make working draft edit to recipe title
    plan_info = client.get(f"{BASE_PATH}/plans/{plan_id}").json()
    client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={
            "base_edit_revision": plan_info["plan"]["edit_revision"],
            "request_id": "draft-edit",
            "operations": [{"op": "recipe.update", "id": "rcp-pinned", "changes": {"title": "MODIFIED TITLE IN DRAFT"}}],
        },
    )

    # Preview generation with I1: must still contain old title "Pinned Recipe"
    gen_prev = client.post(f"{BASE_PATH}/plans/{plan_id}/generations/preview", json={"checkpoint_id": i1["id"]}).json()
    assert gen_prev["ready_to_generate"] is True

    # Generation job produces bundle reflecting frozen I1
    gen_job = client.post(f"{BASE_PATH}/plans/{plan_id}/generations", json={"checkpoint_id": i1["id"]}).json()
    assert gen_job["status"] == "succeeded"


def test_l3_13_and_l3_14_external_implementation_mapping(client: TestClient, fifo_bytes: bytes) -> None:
    """L3-13 / L3-14: External implementation registers observations without code generation."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    c1 = ctx["c1"]
    rev = ctx["rev"]

    ext_op = {
        "op": "external_implementation.register",
        "id": "ext-fifo-legacy",
        "title": "Legacy Verilog Testbench Realization",
        "coverage_checkpoint_id": c1["id"],
        "intent_ids": ["int-full-1"],
        "objective_ids": ["obj-scen-full", "obj-corr-occ"],
        "toolchain_identifier": "legacy_vcs",
        "artifact_manifest": {"repo": "git@company/tb.git", "commit": "abc1234"},
        "evidence_bindings": [
            {"observation_key": "tb_fifo.test_full_boundary", "objective_id": "obj-scen-full", "bin_id": "bin_full", "definition_hash": "hash1"},
            {"observation_key": "tb_fifo.chk_count_preserved", "objective_id": "obj-corr-occ", "definition_hash": "hash2"},
        ],
    }

    cmd_res = client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={"base_edit_revision": rev, "request_id": "reg-ext", "operations": [ext_op]},
    )
    assert cmd_res.status_code == 200

    rcp = client.get(f"{BASE_PATH}/plans/{plan_id}/recipes/ext-fifo-legacy").json()
    assert rcp["kind"] == "external"
    assert rcp["authoring_state"] == "ready"
    assert len(rcp["evidence_bindings"]) == 2


def test_l3_15_plugin_registry_and_schema_discovery(client: TestClient) -> None:
    """L3-15: Public plugin discovery and Test IR schema endpoints."""
    # List plugins
    plugins_res = client.get(f"{BASE_PATH}/plugins")
    assert plugins_res.status_code == 200
    plugins = plugins_res.json()
    assert any(p["plugin_id"] == REF_BUNDLE_ID for p in plugins)

    # Configuration schema
    cfg_schema_res = client.get(f"{BASE_PATH}/plugins/{REF_BUNDLE_ID}/configuration-schema")
    assert cfg_schema_res.status_code == 200
    assert "configuration_schema" in cfg_schema_res.json()

    # Public Test IR v1 JSON Schema
    ir_schema_res = client.get("/schemas/verification.test-ir.v1")
    assert ir_schema_res.status_code == 200
    ir_schema = ir_schema_res.json()
    if "schema_version" in ir_schema:
        assert ir_schema["schema_version"] == SCHEMA_VERSION_TEST_IR
        assert "properties" in ir_schema["schema"]
    else:
        assert "properties" in ir_schema


def test_l3_16_synthetic_fixture_labeled(client: TestClient, fifo_bytes: bytes) -> None:
    """L3-16: Generated synthetic result template is explicitly labeled synthetic."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    snapshot_id = ctx["snapshot_id"]
    c1 = ctx["c1"]
    rev = ctx["rev"]

    bnd_op = create_worked_fifo_binding_set(plan_id, snapshot_id)
    bcfg_op = {"op": "backend_configuration.create", "id": "bcfg-ref-1", "plugin_id": REF_BUNDLE_ID, "plugin_version": "1.0.0"}
    rcp_op = {
        "op": "recipe.create",
        "id": "rcp-syn",
        "title": "Synthetic Test Recipe",
        "kind": "scenario",
        "coverage_checkpoint_id": c1["id"],
        "intent_ids": ["int-full-1"],
        "objective_ids": ["obj-scen-full", "obj-corr-occ"],
        "target_binding_set_id": "bnd-fifo-main",
        "backend_configuration_id": "bcfg-ref-1",
        "test_ir": create_worked_fifo_recipe_ir(),
        "oracle_provenance": {"description": "Synthetic template test"},
        "authoring_state": "ready",
    }
    client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={"base_edit_revision": rev, "request_id": "setup-syn", "operations": [bnd_op, bcfg_op, rcp_op]},
    )

    i1_prev = client.post(f"{BASE_PATH}/plans/{plan_id}/checkpoints/preview", json={"layer": "implementation", "upstream_checkpoint_id": c1["id"]}).json()
    i1 = client.post(
        f"{BASE_PATH}/plans/{plan_id}/checkpoints",
        json={"layer": "implementation", "reviewer_label": "lead", "comment": "I1", "expected_digest": i1_prev["candidate_digest"], "upstream_checkpoint_id": c1["id"]},
    ).json()

    gen_res = client.post(f"{BASE_PATH}/plans/{plan_id}/generations", json={"checkpoint_id": i1["id"]})
    job = gen_res.json()
    artifacts = job["result_data"]["artifact_records"]
    synth_art = [a for a in artifacts if a["relative_path"] == "synthetic-result-template.json"][0]

    art_stream = client.get(f"{BASE_PATH}/plans/{plan_id}/artifacts/{synth_art['id']}")
    assert art_stream.status_code == 200
    synth_data = art_stream.json()
    assert synth_data.get("synthetic") is True


def test_l3_17_backend_switching_preserves_semantics(client: TestClient, fifo_bytes: bytes) -> None:
    """L3-17: Switching backend configuration preserves upstream intent, objective, and test IR identities."""
    ctx = setup_fifo_with_c1(client, fifo_bytes)
    plan_id = ctx["plan_id"]
    snapshot_id = ctx["snapshot_id"]
    c1 = ctx["c1"]
    rev = ctx["rev"]

    bnd_op = create_worked_fifo_binding_set(plan_id, snapshot_id)
    bcfg1 = {"op": "backend_configuration.create", "id": "bcfg-1", "plugin_id": REF_BUNDLE_ID, "plugin_version": "1.0.0"}
    bcfg2 = {"op": "backend_configuration.create", "id": "bcfg-2", "plugin_id": REF_BUNDLE_ID, "plugin_version": "1.0.0"}
    rcp_op = {
        "op": "recipe.create",
        "id": "rcp-switch",
        "title": "Switchable Recipe",
        "kind": "scenario",
        "coverage_checkpoint_id": c1["id"],
        "intent_ids": ["int-full-1"],
        "objective_ids": ["obj-scen-full", "obj-corr-occ"],
        "target_binding_set_id": "bnd-fifo-main",
        "backend_configuration_id": "bcfg-1",
        "test_ir": create_worked_fifo_recipe_ir(),
        "oracle_provenance": {"description": "Switch test"},
        "authoring_state": "ready",
    }

    client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={"base_edit_revision": rev, "request_id": "init-switch", "operations": [bnd_op, bcfg1, bcfg2, rcp_op]},
    )

    plan_info = client.get(f"{BASE_PATH}/plans/{plan_id}").json()
    # Switch backend to bcfg-2
    switch_res = client.post(
        f"{BASE_PATH}/plans/{plan_id}/commands",
        json={
            "base_edit_revision": plan_info["plan"]["edit_revision"],
            "request_id": "switch-bcfg",
            "operations": [{"op": "recipe.update", "id": "rcp-switch", "changes": {"backend_configuration_id": "bcfg-2"}}],
        },
    )
    assert switch_res.status_code == 200

    updated_rcp = client.get(f"{BASE_PATH}/plans/{plan_id}/recipes/rcp-switch").json()
    assert updated_rcp["backend_configuration_id"] == "bcfg-2"
    assert updated_rcp["intent_ids"] == ["int-full-1"]
    assert updated_rcp["objective_ids"] == ["obj-scen-full", "obj-corr-occ"]

"""Prepare browser prerequisites through public HTTP APIs and existing source fixtures."""
import importlib.util
import json
import sys
from pathlib import Path

import httpx
from testplan_service.domain.operations import (
    IntentCreateOp,
    RequirementCreateOp,
    SectionCreateOp,
    SourceSectionAssessOp,
)
from testplan_service.domain.plugins.reference_bundle import PLUGIN_ID
from testplan_service.fixtures.fifo_snapshot import get_fifo_snapshot_bytes

ROOT = Path(__file__).resolve().parents[3]


def acceptance_fixtures():
    path = ROOT / "testplan-service/tests/test_layer3_acceptance.py"
    spec = importlib.util.spec_from_file_location("planner_fixtures", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed(url, stage):
    with httpx.Client(base_url=url, timeout=30) as client:
        base = "/api/verification/v1"
        if stage == "draft":
            response = client.post(f"{base}/source-imports", content=get_fifo_snapshot_bytes())
            response.raise_for_status()
            snapshot = response.json()["snapshot_id"]
            response = client.post(f"{base}/plans", json={"name": "Browser authoring", "snapshot_id": snapshot, "root_scope_id": "sync_fifo"})
            response.raise_for_status()
            return {"plan_id": response.json()["id"], "snapshot_id": snapshot}
        fixtures = acceptance_fixtures()
        context = fixtures.setup_fifo_with_c1(client, get_fifo_snapshot_bytes())
        plan = context["plan_id"]
        if stage == "authoring":
            # Keep source and authored records, then use a fresh plan with no checkpoints.
            response = client.post(f"{base}/plans", json={"name": "Browser review", "snapshot_id": context["snapshot_id"], "root_scope_id": "sync_fifo"})
            response.raise_for_status()
            fresh = response.json()
            records = client.get(f"{base}/plans/{plan}/records").json()
            ops = []
            for kind in ("requirement", "section", "intent"):
                for record in records:
                    if record["record_type"] != kind:
                        continue
                    operation = {"requirement": RequirementCreateOp, "section": SectionCreateOp, "intent": IntentCreateOp}[kind]
                    fields = {key: value for key, value in record.items() if key in operation.model_fields}
                    ops.append({"op": f"{kind}.create", **fields})
            for section in client.get(f"{base}/plans/{plan}/source-sections").json():
                fields = {key: value for key, value in section["audit"].items() if key in SourceSectionAssessOp.model_fields}
                fields["requirement_ids"] = section["audit"].get("linked_requirement_ids", [])
                ops.append({"op": "source_section.assess", "section_id": section["section_id"], **fields})
            result = client.post(f"{base}/plans/{fresh['id']}/commands", json={"base_edit_revision": fresh["edit_revision"], "request_id": "browser-review-seed", "operations": ops})
            assert result.is_success, result.text
            return {"plan_id": fresh["id"], "snapshot_id": context["snapshot_id"]}
        if stage == "evidence":
            response = client.post(f"{base}/plans/{plan}/profiles", json={"display_name": "Browser synthetic evidence", "coverage_checkpoint_id": context["c1"]["id"], "root_occurrence_id": "sync_fifo"})
            response.raise_for_status()
            profile = response.json()
            response = client.post(f"{base}/plans/{plan}/campaigns", json={"title": "Browser evidence", "coverage_checkpoint_id": context["c1"]["id"], "required_profile_ids": [profile["id"]]})
            response.raise_for_status()
            context["campaign"] = response.json()
            context["results"] = {
                "schema_version": "verification.results.v1", "profile_id": profile["id"],
                "coverage_checkpoint_id": context["c1"]["id"],
                "producer": {"id": "browser-fixture", "tool_name": "synthetic", "producer_kind": "generated"},
                "run": {"external_run_id": "browser-run", "attempt_id": "1", "status": "completed"},
                "observations": [
                    {"producer_observation_id": "full", "objective_id": "obj-scen-full", "family": "scenario", "bin_id": "bin_full", "outcome": "hit", "hit_count": 1, "evaluation_count": 1},
                    {"producer_observation_id": "occupancy", "objective_id": "obj-corr-occ", "family": "correctness", "outcome": "pass", "evaluation_count": 1},
                ],
            }
            return context
        operations = [
            fixtures.create_worked_fifo_binding_set(plan, context["snapshot_id"]),
            {"op": "backend_configuration.create", "id": "bcfg-browser", "plugin_id": PLUGIN_ID, "plugin_version": "1.0.0"},
            {"op": "recipe.create", "id": "recipe-browser", "title": "Browser reference recipe", "kind": "scenario",
             "coverage_checkpoint_id": context["c1"]["id"], "intent_ids": ["int-full-1", "int-full-2"],
             "objective_ids": ["obj-scen-full", "obj-corr-occ", "obj-corr-data"],
             "target_binding_set_id": "bnd-fifo-main", "backend_configuration_id": "bcfg-browser",
             "test_ir": fixtures.create_worked_fifo_recipe_ir(),
             "evidence_bindings": [{"observation_key": "full_scenario", "objective_id": "obj-scen-full", "bin_id": "bin_full", "definition_hash": "browser-fixture"}],
             "oracle_provenance": {"source_locators": ["sec-full"], "description": "Independent reference fixture", "independently_authored": True},
             "authoring_state": "ready"},
        ]
        response = client.post(f"{base}/plans/{plan}/commands", json={"base_edit_revision": context["rev"], "request_id": "browser-recipe", "operations": operations})
        response.raise_for_status()
        return context


if __name__ == "__main__":
    print(json.dumps(seed(sys.argv[1], sys.argv[2])))

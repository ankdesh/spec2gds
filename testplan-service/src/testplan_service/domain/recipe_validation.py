"""Preflight validation for Test IR and Recipe records."""

from __future__ import annotations

from typing import Any
from testplan_service.domain.recipes import Recipe, RecipeKind, TargetBindingSet, TargetKind, TargetPermission
from testplan_service.domain.test_ir import StepPhase, TestIR


class RecipeValidator:
    """Performs deep structural, semantic, and capability preflight validation on recipes."""

    def validate_recipe(
        self,
        recipe: Recipe,
        binding_set: TargetBindingSet | None = None,
        upstream_objective_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Validate a recipe against Core Validation Order rules."""
        diagnostics: list[dict[str, Any]] = []

        # 1. Basic linkage validation
        if not recipe.intent_ids:
            diagnostics.append({
                "code": "recipe.intents_empty",
                "severity": "error",
                "record_id": recipe.id,
                "ir_path": "intent_ids",
                "message": f"Recipe '{recipe.title}' must be linked to at least one Intent.",
            })

        if not recipe.objective_ids:
            diagnostics.append({
                "code": "recipe.objectives_empty",
                "severity": "error",
                "record_id": recipe.id,
                "ir_path": "objective_ids",
                "message": f"Recipe '{recipe.title}' must be linked to at least one Coverage Objective.",
            })

        if upstream_objective_ids is not None:
            for oid in recipe.objective_ids:
                if oid not in upstream_objective_ids:
                    diagnostics.append({
                        "code": "recipe.objective_not_in_checkpoint",
                        "severity": "error",
                        "record_id": recipe.id,
                        "ir_path": f"objective_ids.{oid}",
                        "message": f"Linked objective '{oid}' does not exist in Coverage Checkpoint '{recipe.coverage_checkpoint_id}'.",
                    })

        # 2. Oracle provenance checks
        if not recipe.oracle_provenance.description and not recipe.oracle_provenance.source_locators:
            diagnostics.append({
                "code": "recipe.oracle_missing_rationale",
                "severity": "error",
                "record_id": recipe.id,
                "ir_path": "oracle_provenance",
                "message": f"Recipe '{recipe.title}' lacks required oracle rationale or source locators.",
            })

        # 3. Test IR validation for scenario and property recipes
        if recipe.kind in {RecipeKind.SCENARIO, RecipeKind.PROPERTY}:
            if not recipe.test_ir:
                diagnostics.append({
                    "code": "recipe.test_ir_missing",
                    "severity": "error",
                    "record_id": recipe.id,
                    "ir_path": "test_ir",
                    "message": f"Recipe '{recipe.title}' of kind '{recipe.kind.value}' requires a valid Test IR.",
                })
            else:
                diagnostics.extend(
                    self.validate_test_ir(recipe.id, recipe.test_ir, binding_set)
                )

        return diagnostics

    def validate_test_ir(
        self,
        recipe_id: str,
        test_ir: TestIR,
        binding_set: TargetBindingSet | None = None,
    ) -> list[dict[str, Any]]:
        """Validate Test IR AST invariants."""
        diagnostics: list[dict[str, Any]] = []

        # Signal map from binding set
        binding_map = {b.id: b for b in binding_set.bindings} if binding_set else {}
        port_name_map = {b.observation_name: b for b in binding_set.bindings} if binding_set else {}

        # Track declared sample slots and initialized variables
        sampled_slots: set[str] = set()
        declared_vars: set[str] = {v.name for v in test_ir.variables}
        evaluated_checks: set[str] = set()

        # This is selected preflight validation, not a recursive typed interpreter.
        # Nested dictionaries and unhandled step kinds are not comprehensively checked;
        # executable backends must not infer support merely from an empty diagnostic list.
        # Step lists
        all_step_containers = [
            ("setup", test_ir.setup),
            ("body", test_ir.body),
            ("teardown", test_ir.teardown),
        ]

        for container_name, step_list in all_step_containers:
            for idx, raw_step in enumerate(step_list):
                step_path = f"{container_name}[{idx}]"
                step_type = raw_step.get("step_type")

                if step_type == "drive":
                    assignments = raw_step.get("assignments", [])
                    for a_idx, assignment in enumerate(assignments):
                        target = assignment.get("target")
                        # Target direction check (cannot drive output)
                        bnd = port_name_map.get(target) or binding_map.get(target)
                        if bnd:
                            if bnd.target_kind == TargetKind.OUTPUT or TargetPermission.DRIVE not in bnd.permissions:
                                diagnostics.append({
                                    "code": "ir.drive_output_rejected",
                                    "severity": "error",
                                    "record_id": recipe_id,
                                    "ir_path": f"{step_path}.assignments[{a_idx}].target",
                                    "message": f"Cannot drive output or read-only signal '{target}'.",
                                })

                elif step_type == "sample":
                    samples = raw_step.get("samples", [])
                    for s_idx, sample in enumerate(samples):
                        slot = sample.get("slot")
                        if slot:
                            sampled_slots.add(slot)

                elif step_type == "check":
                    check_id = raw_step.get("check_id")
                    if check_id:
                        evaluated_checks.add(check_id)
                    expr = raw_step.get("expr", {})
                    # A syntactic guard only: different expressions may still encode
                    # the same DUT-derived oracle. Human provenance review remains needed.
                    # Tautology guard: expression compares identical items
                    if expr.get("op") in {"eq", "==", "ne", "!="}:
                        left = expr.get("left")
                        right = expr.get("right")
                        if left and right and left == right:
                            diagnostics.append({
                                "code": "ir.check_tautology_rejected",
                                "severity": "error",
                                "record_id": recipe_id,
                                "ir_path": f"{step_path}.expr",
                                "message": f"Check '{check_id}' is tautological (compares identical expression '{left}').",
                            })
                    # Sampled-before-use check in expressions
                    self._check_expression_sampled_slots(
                        expr, sampled_slots, recipe_id, f"{step_path}.expr", diagnostics
                    )

                elif step_type == "parallel":
                    branches = raw_step.get("branches", [])
                    driven_in_branches: list[set[str]] = []
                    mutated_models_in_branches: list[set[str]] = []

                    for b_idx, branch in enumerate(branches):
                        branch_driven: set[str] = set()
                        branch_models: set[str] = set()
                        for b_step in branch:
                            if b_step.get("step_type") == "drive":
                                for asgn in b_step.get("assignments", []):
                                    branch_driven.add(asgn.get("target", ""))
                            elif b_step.get("step_type") == "model_update":
                                branch_models.add(b_step.get("model", ""))
                        driven_in_branches.append(branch_driven)
                        mutated_models_in_branches.append(branch_models)

                    # Check disjoint driven bindings
                    for i in range(len(driven_in_branches)):
                        for j in range(i + 1, len(driven_in_branches)):
                            conflict_targets = driven_in_branches[i].intersection(driven_in_branches[j])
                            if conflict_targets:
                                diagnostics.append({
                                    "code": "ir.parallel_driver_conflict",
                                    "severity": "error",
                                    "record_id": recipe_id,
                                    "ir_path": f"{step_path}.branches",
                                    "message": f"Parallel branches conflict: multiple branches drive same signal(s) {sorted(conflict_targets)}.",
                                })
                            conflict_models = mutated_models_in_branches[i].intersection(mutated_models_in_branches[j])
                            if conflict_models:
                                diagnostics.append({
                                    "code": "ir.parallel_model_conflict",
                                    "severity": "error",
                                    "record_id": recipe_id,
                                    "ir_path": f"{step_path}.branches",
                                    "message": f"Parallel branches conflict: multiple branches mutate same model(s) {sorted(conflict_models)}.",
                                })

                elif step_type == "repeat":
                    count = raw_step.get("count", 1)
                    if count == 0:
                        # Checks inside zero-repeat loop will never evaluate
                        inner_steps = raw_step.get("steps", [])
                        for in_step in inner_steps:
                            if in_step.get("step_type") == "check":
                                diagnostics.append({
                                    "code": "ir.check_never_evaluates",
                                    "severity": "error",
                                    "record_id": recipe_id,
                                    "ir_path": f"{step_path}.steps",
                                    "message": f"Check '{in_step.get('check_id')}' inside repeat block with count=0 will never evaluate.",
                                })

        # Verify declared checks are evaluated
        declared_check_ids = {c.get("check_id") for c in test_ir.checks if c.get("check_id")}
        for cid in declared_check_ids:
            if cid not in evaluated_checks:
                diagnostics.append({
                    "code": "ir.check_not_evaluated",
                    "severity": "error",
                    "record_id": recipe_id,
                    "ir_path": f"checks.{cid}",
                    "message": f"Check '{cid}' is declared but never evaluated in setup, body, or teardown steps.",
                })

        return diagnostics

    def _check_expression_sampled_slots(
        self,
        expr: dict[str, Any],
        sampled_slots: set[str],
        recipe_id: str,
        path: str,
        diagnostics: list[dict[str, Any]],
    ) -> None:
        """Recursively ensure sampled slot references have been sampled prior to evaluation."""
        if not isinstance(expr, dict):
            return

        node_type = expr.get("type")
        if node_type == "sample_ref" or "slot" in expr:
            slot = expr.get("slot") or expr.get("name")
            if slot and slot not in sampled_slots:
                diagnostics.append({
                    "code": "ir.uninitialized_sample_reference",
                    "severity": "error",
                    "record_id": recipe_id,
                    "ir_path": path,
                    "message": f"Reference to sample slot '{slot}' used before any sample step populates it.",
                })

        for key, val in expr.items():
            if isinstance(val, dict):
                self._check_expression_sampled_slots(
                    val, sampled_slots, recipe_id, f"{path}.{key}", diagnostics
                )
            elif isinstance(val, list):
                for idx, item in enumerate(val):
                    if isinstance(item, dict):
                        self._check_expression_sampled_slots(
                            item, sampled_slots, recipe_id, f"{path}.{key}[{idx}]", diagnostics
                        )

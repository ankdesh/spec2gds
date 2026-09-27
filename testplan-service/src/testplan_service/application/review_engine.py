"""Review checkpoint evaluation and creation engine for Layer 1 and Layer 2."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from testplan_service.constants import (
    KEY_PREFIX_CHK,
    KEY_PREFIX_CHK_COVERAGE,
    KEY_PREFIX_CHK_IMPLEMENTATION,
    KEY_PREFIX_CHK_PLAN,
)
from testplan_service.domain.enums import (
    AuthoringState,
    IntentOrigin,
    IssueSeverity,
    IssueState,
    RequirementDisposition,
    SourceAuditDisposition,
)
from testplan_service.domain.hash import canonical_json, sha256_digest
from testplan_service.domain.models import (
    Intent,
    Issue,
    PlanCheckpoint,
    PlanHeader,
    Requirement,
    Section,
    SourceAuditEntry,
)
from testplan_service.domain.objectives import (
    BinStatus,
    CoverageBin,
    CoverageDimension,
    CoverageExclusion,
    CoverageFamily,
    CoverageObjective,
)
from testplan_service.domain.policies import IntentEvidencePolicy, PolicyBranch
from testplan_service.domain.plugins import default_plugin_registry
from testplan_service.domain.recipe_validation import RecipeValidator
from testplan_service.domain.recipes import (
    BackendConfiguration,
    Recipe,
    RecipeKind,
    RecipeState,
    TargetBindingSet,
)
from testplan_service.exceptions import CheckpointBlockerError, PlanNotFoundError
from testplan_service.storage.sqlite_repo import SqlitePlanRepository


class ReviewEngine:
    """Evaluates readiness checklist and creates immutable review checkpoints."""

    def __init__(self, repo: SqlitePlanRepository) -> None:
        self.repo = repo

    def evaluate_checklist(
        self,
        plan_id: str,
        layer: str = "plan",
        upstream_checkpoint_id: str | None = None,
    ) -> dict[str, Any]:
        """Compute review checklist for Layer 1 (plan) or Layer 2 (coverage)."""
        if layer == "coverage":
            return self.evaluate_coverage_checklist(plan_id, upstream_checkpoint_id)
        elif layer == "implementation":
            return self.evaluate_implementation_checklist(plan_id, upstream_checkpoint_id)
        return self._evaluate_plan_checklist(plan_id)

    def _evaluate_plan_checklist(self, plan_id: str) -> dict[str, Any]:
        """Compute complete Layer 1 review checklist, reporting blockers and warnings."""
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        snapshot = self.repo.get_snapshot(plan.snapshot_id)
        raw_records = self.repo.get_records(plan_id, include_archived=False)

        requirements: dict[str, Requirement] = {
            r["id"]: Requirement.model_validate(r) for r in raw_records if r.get("record_type") == "requirement"
        }
        sections: dict[str, Section] = {
            r["id"]: Section.model_validate(r) for r in raw_records if r.get("record_type") == "section"
        }
        intents: dict[str, Intent] = {
            r["id"]: Intent.model_validate(r) for r in raw_records if r.get("record_type") == "intent"
        }
        issues: dict[str, Issue] = {
            r["id"]: Issue.model_validate(r) for r in raw_records if r.get("record_type") == "issue"
        }

        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        # 1. Snapshot and root occurrence check
        if not snapshot:
            blockers.append({
                "code": "review.snapshot_missing",
                "message": f"Pinned snapshot '{plan.snapshot_id}' cannot be found in repository.",
                "record_id": plan.snapshot_id,
            })
        else:
            occ_ids = {o.occurrence_id for o in snapshot.occurrences}
            if plan.root_scope_id not in occ_ids:
                blockers.append({
                    "code": "review.root_scope_invalid",
                    "message": f"Root scope '{plan.root_scope_id}' does not exist in snapshot occurrences.",
                    "record_id": plan.root_scope_id,
                })

            # 2. Source section audit completeness
            for s_sec in snapshot.source_sections:
                audit = plan.source_audit.get(s_sec.section_id)
                if not audit or audit.disposition == SourceAuditDisposition.UNREVIEWED:
                    blockers.append({
                        "code": "review.source_section_unreviewed",
                        "message": f"Source section '{s_sec.title}' ({s_sec.section_id}) has not been audited.",
                        "record_id": s_sec.section_id,
                    })

        # 3. Requirement disposition completeness
        for req_id, req in requirements.items():
            if req.disposition == RequirementDisposition.UNASSESSED:
                blockers.append({
                    "code": "review.requirement_unassessed",
                    "message": f"Requirement '{req.title}' ({req.key}) is unassessed.",
                    "record_id": req_id,
                })
            elif req.disposition == RequirementDisposition.AMBIGUOUS:
                # Check if resolved by an issue
                resolved = any(
                    issues[i_id].state == IssueState.RESOLVED
                    for i_id in req.issue_ids
                    if i_id in issues
                )
                if not resolved:
                    blockers.append({
                        "code": "review.requirement_ambiguous",
                        "message": f"Requirement '{req.title}' ({req.key}) is ambiguous without resolution.",
                        "record_id": req_id,
                    })

        # 4. Verifiable requirements mapped to active intents
        for req_id, req in requirements.items():
            if req.disposition == RequirementDisposition.VERIFY:
                linked = any(req_id in intent.requirement_ids for intent in intents.values())
                if not linked:
                    blockers.append({
                        "code": "review.requirement_unmapped",
                        "message": f"Verifiable requirement '{req.title}' ({req.key}) has no active linked intent.",
                        "record_id": req_id,
                    })

        # 5. Active intent completeness & readiness
        for intent_id, intent in intents.items():
            if intent.authoring_state == AuthoringState.DRAFT:
                blockers.append({
                    "code": "review.intent_draft",
                    "message": f"Active intent '{intent.title}' ({intent.key}) is still in draft state.",
                    "record_id": intent_id,
                })
            elif intent.authoring_state == AuthoringState.BLOCKED:
                blockers.append({
                    "code": "review.intent_blocked",
                    "message": f"Active intent '{intent.title}' ({intent.key}) is blocked.",
                    "record_id": intent_id,
                })
            if not intent.preconditions.strip() or not intent.trigger.strip() or not intent.expected_behavior.strip():
                blockers.append({
                    "code": "review.intent_incomplete_behavior",
                    "message": f"Intent '{intent.title}' ({intent.key}) lacks complete Given/When/Then behavior.",
                    "record_id": intent_id,
                })
            if not intent.observations:
                blockers.append({
                    "code": "review.intent_no_observations",
                    "message": f"Intent '{intent.title}' ({intent.key}) has no observations.",
                    "record_id": intent_id,
                })
            if intent.origin == IntentOrigin.DERIVED_INTERPRETATION and (not intent.rationale or not intent.rationale.strip()):
                blockers.append({
                    "code": "review.intent_missing_rationale",
                    "message": f"Derived intent '{intent.title}' ({intent.key}) lacks rationale citing source.",
                    "record_id": intent_id,
                })

        # 6. Warnings: empty sections, duplicate titles, advisory issues
        for sec_id, sec in sections.items():
            child_intents = [cid for cid in sec.child_ids if cid in intents]
            child_sections = [cid for cid in sec.child_ids if cid in sections]
            if not child_intents and not child_sections:
                warnings.append({
                    "code": "review.empty_section",
                    "message": f"Section '{sec.title}' ({sec.key}) contains no child intents or subsections.",
                    "record_id": sec_id,
                })

        # Duplicate title check
        titles_seen: dict[str, str] = {}
        for intent_id, intent in intents.items():
            norm_title = intent.title.strip().lower()
            if norm_title in titles_seen:
                warnings.append({
                    "code": "review.duplicate_intent_title",
                    "message": f"Intent '{intent.title}' ({intent.key}) shares title with {titles_seen[norm_title]}.",
                    "record_id": intent_id,
                })
            else:
                titles_seen[norm_title] = intent.key

        # Open advisory issues
        for iss_id, iss in issues.items():
            if iss.state == IssueState.OPEN and iss.severity == IssueSeverity.ADVISORY:
                warnings.append({
                    "code": "review.advisory_issue_open",
                    "message": f"Advisory issue '{iss.title}' ({iss.key}) remains open.",
                    "record_id": iss_id,
                })

        # Compute candidate digest over active records
        summary_payload = {
            "plan_id": plan_id,
            "snapshot_id": plan.snapshot_id,
            "root_scope_id": plan.root_scope_id,
            "requirements": [r.model_dump() for r in sorted(requirements.values(), key=lambda x: x.id)],
            "sections": [s.model_dump() for s in sorted(sections.values(), key=lambda x: x.id)],
            "intents": [i.model_dump() for i in sorted(intents.values(), key=lambda x: x.id)],
            "issues": [iss.model_dump() for iss in sorted(issues.values(), key=lambda x: x.id)],
            "source_audit": {k: v.model_dump() for k, v in sorted(plan.source_audit.items())},
        }
        candidate_digest = sha256_digest(canonical_json(summary_payload))

        return {
            "plan_id": plan_id,
            "edit_revision": plan.edit_revision,
            "candidate_digest": candidate_digest,
            "blockers": blockers,
            "warnings": warnings,
            "checklist": {
                "snapshot_valid": snapshot is not None,
                "sections_reviewed_count": sum(1 for a in plan.source_audit.values() if a.disposition != SourceAuditDisposition.UNREVIEWED),
                "sections_total": len(snapshot.source_sections) if snapshot else 0,
                "requirements_total": len(requirements),
                "verifiable_requirements": sum(1 for r in requirements.values() if r.disposition == RequirementDisposition.VERIFY),
                "intents_total": len(intents),
                "intents_ready": sum(1 for i in intents.values() if i.authoring_state == AuthoringState.READY),
                "blockers_count": len(blockers),
                "warnings_count": len(warnings),
            },
            "payload": summary_payload,
        }

    def evaluate_coverage_checklist(
        self, plan_id: str, upstream_checkpoint_id: str | None = None
    ) -> dict[str, Any]:
        """Compute complete Layer 2 review checklist, verifying mapping to upstream P1 baseline."""
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        # 1. Reconcile against upstream Plan checkpoint (P1)
        upstream_cp: PlanCheckpoint | None = None
        if upstream_checkpoint_id:
            upstream_cp = self.repo.get_checkpoint(plan_id, upstream_checkpoint_id)
        else:
            all_cps = self.repo.list_checkpoints(plan_id)
            plan_cps = [c for c in all_cps if c.layer == "plan"]
            if plan_cps:
                upstream_cp = plan_cps[-1]

        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        if not upstream_cp or upstream_cp.layer != "plan":
            blockers.append({
                "code": "review.upstream_checkpoint_missing",
                "message": "Coverage review requires an approved upstream Plan checkpoint (P1).",
            })
            upstream_intents: list[Intent] = []
        else:
            raw_intents = upstream_cp.payload.get("intents", [])
            upstream_intents = [Intent.model_validate(i) for i in raw_intents if not i.get("archived")]

        # 2. Load Layer 2 records
        raw_records = self.repo.get_records(plan_id, include_archived=False)
        objectives: dict[str, CoverageObjective] = {
            r["id"]: CoverageObjective.model_validate(r)
            for r in raw_records
            if r.get("record_type") == "objective"
        }
        dimensions: dict[str, CoverageDimension] = {
            r["id"]: CoverageDimension.model_validate(r)
            for r in raw_records
            if r.get("record_type") == "dimension"
        }
        policies: dict[str, IntentEvidencePolicy] = {
            r["intent_id"]: IntentEvidencePolicy.model_validate(r)
            for r in raw_records
            if r.get("record_type") == "policy"
        }
        exclusions: dict[str, CoverageExclusion] = {
            r["id"]: CoverageExclusion.model_validate(r)
            for r in raw_records
            if r.get("record_type") == "exclusion"
        }

        # 3. Policy mapping completeness & checking requirement
        for intent in upstream_intents:
            if intent.id not in policies:
                blockers.append({
                    "code": "review.intent_policy_missing",
                    "message": f"Active intent '{intent.title}' ({intent.key}) has no evidence policy.",
                    "record_id": intent.id,
                })
            else:
                pol = policies[intent.id]
                if not pol.branches:
                    blockers.append({
                        "code": "review.intent_policy_empty",
                        "message": f"Policy for intent '{intent.title}' ({intent.key}) has no branches.",
                        "record_id": intent.id,
                    })
                for b_idx, branch in enumerate(pol.branches):
                    if not branch.objective_ids:
                        blockers.append({
                            "code": "review.branch_empty",
                            "message": f"Branch '{branch.title}' for intent '{intent.title}' has no objectives.",
                            "record_id": intent.id,
                        })
                        continue

                    has_checking = False
                    for oid in branch.objective_ids:
                        if oid not in objectives:
                            blockers.append({
                                "code": "review.dangling_mapping",
                                "message": f"Branch '{branch.title}' references non-existent objective '{oid}'.",
                                "record_id": oid,
                            })
                            continue
                        obj = objectives[oid]
                        if obj.family in {CoverageFamily.CORRECTNESS, CoverageFamily.PROPERTY}:
                            has_checking = True

                        # Scope check: objective must cover intent's occurrence scope
                        if (
                            obj.scope_id != intent.scope_id
                            and obj.scope_id not in intent.participants
                            and intent.scope_id not in obj.participant_scope_ids
                        ):
                            blockers.append({
                                "code": "review.objective_scope_mismatch",
                                "message": f"Objective '{obj.title}' scope '{obj.scope_id}' does not cover intent scope '{intent.scope_id}'.",
                                "record_id": obj.id,
                            })

                    if not has_checking:
                        blockers.append({
                            "code": "review.checking_missing",
                            "message": f"Branch '{branch.title}' for intent '{intent.title}' contains only coverage and lacks correctness or property verification.",
                            "record_id": intent.id,
                        })

        # 4. Objective completeness & readiness
        for obj in objectives.values():
            if obj.authoring_state != AuthoringState.READY:
                blockers.append({
                    "code": "review.objective_draft",
                    "message": f"Objective '{obj.title}' ({obj.key}) is still in draft state.",
                    "record_id": obj.id,
                })

            if obj.family in {CoverageFamily.SCENARIO, CoverageFamily.FUNCTIONAL}:
                excluded_bin_ids = {e.bin_id for e in exclusions.values() if e.objective_id == obj.id and not e.archived}
                req_bins = [b for b in obj.bins if b.status == BinStatus.REQUIRED and b.id not in excluded_bin_ids]
                if not req_bins:
                    blockers.append({
                        "code": "review.objective_incomplete",
                        "message": f"Scenario/functional objective '{obj.title}' ({obj.key}) has zero required non-excluded bins.",
                        "record_id": obj.id,
                    })
            elif obj.family == CoverageFamily.CORRECTNESS:
                min_evals = obj.acceptance.get("minimum_evaluations", 1)
                if min_evals < 1:
                    blockers.append({
                        "code": "review.objective_invalid_evaluations",
                        "message": f"Correctness objective '{obj.title}' must require at least 1 evaluation.",
                        "record_id": obj.id,
                    })

        # 5. Calculate candidate digest
        summary_payload = {
            "plan_id": plan_id,
            "layer": "coverage",
            "upstream_checkpoint_id": upstream_cp.id if upstream_cp else None,
            "upstream_content_hash": upstream_cp.content_hash if upstream_cp else None,
            "dimensions": [d.model_dump() for d in sorted(dimensions.values(), key=lambda x: x.id)],
            "objectives": [o.model_dump() for o in sorted(objectives.values(), key=lambda x: x.id)],
            "policies": [p.model_dump() for p in sorted(policies.values(), key=lambda x: x.id)],
            "exclusions": [e.model_dump() for e in sorted(exclusions.values(), key=lambda x: x.id)],
        }
        candidate_digest = sha256_digest(canonical_json(summary_payload))

        return {
            "plan_id": plan_id,
            "layer": "coverage",
            "edit_revision": plan.edit_revision,
            "upstream_checkpoint_id": upstream_cp.id if upstream_cp else None,
            "candidate_digest": candidate_digest,
            "blockers": blockers,
            "warnings": warnings,
            "checklist": {
                "upstream_checkpoint_valid": upstream_cp is not None,
                "intents_total": len(upstream_intents),
                "intents_mapped": sum(1 for i in upstream_intents if i.id in policies and policies[i.id].branches),
                "intents_mapped_count": sum(1 for i in upstream_intents if i.id in policies and policies[i.id].branches),
                "objectives_total": len(objectives),
                "objectives_ready": sum(1 for o in objectives.values() if o.authoring_state == AuthoringState.READY),
                "blockers_count": len(blockers),
                "warnings_count": len(warnings),
            },
            "payload": summary_payload,
        }

    def evaluate_implementation_checklist(
        self,
        plan_id: str,
        upstream_checkpoint_id: str | None = None,
        selected_recipe_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Compute review checklist for Layer 3 (implementation), reporting blockers and warnings."""
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        # 1. Resolve upstream Coverage Checkpoint (C1)
        all_checkpoints = self.repo.list_checkpoints(plan_id)
        coverage_checkpoints = [c for c in all_checkpoints if c.layer == "coverage"]
        upstream_cp = None
        if upstream_checkpoint_id:
            for c in coverage_checkpoints:
                if c.id == upstream_checkpoint_id or c.key == upstream_checkpoint_id:
                    upstream_cp = c
                    break
        elif coverage_checkpoints:
            upstream_cp = coverage_checkpoints[-1]

        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        if not upstream_cp:
            blockers.append({
                "code": "review.upstream_coverage_missing",
                "message": "An approved Coverage Checkpoint (C1) is required before reviewing implementation.",
                "record_id": plan_id,
            })

        # Load Layer 3 and upstream records
        binding_sets = {b.id: b for b in self.repo.get_binding_sets(plan_id, include_archived=False)}
        all_recipes = {r.id: r for r in self.repo.get_recipes(plan_id, include_archived=False)}
        backend_configs = {c.id: c for c in self.repo.get_backend_configurations(plan_id)}

        # Filter selected recipes
        if selected_recipe_ids is not None:
            recipes_to_eval = [all_recipes[rid] for rid in selected_recipe_ids if rid in all_recipes]
        elif upstream_cp:
            recipes_to_eval = [r for r in all_recipes.values() if r.coverage_checkpoint_id == upstream_cp.id]
            if not recipes_to_eval:
                recipes_to_eval = list(all_recipes.values())
        else:
            recipes_to_eval = list(all_recipes.values())

        if not recipes_to_eval:
            blockers.append({
                "code": "review.no_recipes_selected",
                "message": "At least one ready recipe must be selected for implementation review.",
                "record_id": plan_id,
            })

        # Upstream objectives set
        upstream_obj_ids = set()
        if upstream_cp:
            upstream_obj_ids = {o["id"] for o in upstream_cp.payload.get("objectives", [])}

        validator = RecipeValidator()
        bound_objective_ids = set()

        for recipe in recipes_to_eval:
            if recipe.authoring_state != RecipeState.READY:
                blockers.append({
                    "code": "review.recipe_not_ready",
                    "message": f"Recipe '{recipe.title}' ({recipe.key}) is in '{recipe.authoring_state.value}' state; only ready recipes can be reviewed.",
                    "record_id": recipe.id,
                })

            bnd_set = binding_sets.get(recipe.target_binding_set_id) if recipe.target_binding_set_id else None
            if recipe.kind in {RecipeKind.SCENARIO, RecipeKind.PROPERTY}:
                if not bnd_set:
                    blockers.append({
                        "code": "review.target_binding_missing",
                        "message": f"Recipe '{recipe.title}' ({recipe.key}) lacks target bindings.",
                        "record_id": recipe.id,
                    })
                elif bnd_set.authoring_state != AuthoringState.READY:
                    blockers.append({
                        "code": "review.target_binding_not_ready",
                        "message": f"Target binding set for '{recipe.title}' is still in draft state.",
                        "record_id": bnd_set.id,
                    })

            if recipe.backend_configuration_id:
                bcfg = backend_configs.get(recipe.backend_configuration_id)
                if not bcfg:
                    blockers.append({
                        "code": "review.backend_config_missing",
                        "message": f"Recipe '{recipe.title}' references non-existent backend configuration '{recipe.backend_configuration_id}'.",
                        "record_id": recipe.id,
                    })
                else:
                    plugin = default_plugin_registry.get_backend(bcfg.plugin_id, bcfg.plugin_version)
                    if not plugin:
                        blockers.append({
                            "code": "review.plugin_missing",
                            "message": f"Required backend plugin '{bcfg.plugin_id}' version '{bcfg.plugin_version}' is not installed.",
                            "record_id": recipe.id,
                        })

            # Deep validation
            diags = validator.validate_recipe(recipe, bnd_set, upstream_obj_ids)
            for d in diags:
                if d.get("severity") == "error":
                    blockers.append({
                        "code": d.get("code", "recipe.validation_error"),
                        "message": d["message"],
                        "record_id": recipe.id,
                    })

            for oid in recipe.objective_ids:
                bound_objective_ids.add(oid)

        # Unimplemented objectives
        unimplemented_count = len(upstream_obj_ids - bound_objective_ids) if upstream_obj_ids else 0
        if unimplemented_count > 0:
            warnings.append({
                "code": "review.partial_implementation",
                "message": f"{unimplemented_count} coverage objective(s) from {upstream_cp.key if upstream_cp else 'baseline'} are not implemented in this selection.",
                "count": unimplemented_count,
            })

        summary_payload = {
            "plan_id": plan_id,
            "layer": "implementation",
            "upstream_checkpoint_id": upstream_cp.id if upstream_cp else None,
            "upstream_content_hash": upstream_cp.content_hash if upstream_cp else None,
            "recipes": [r.model_dump() for r in sorted(recipes_to_eval, key=lambda x: x.id)],
            "target_binding_sets": [b.model_dump() for b in sorted(binding_sets.values(), key=lambda x: x.id)],
            "backend_configurations": [c.model_dump() for c in sorted(backend_configs.values(), key=lambda x: x.id)],
            "unimplemented_objective_count": unimplemented_count,
        }
        candidate_digest = sha256_digest(canonical_json(summary_payload))

        return {
            "plan_id": plan_id,
            "layer": "implementation",
            "edit_revision": plan.edit_revision,
            "upstream_checkpoint_id": upstream_cp.id if upstream_cp else None,
            "candidate_digest": candidate_digest,
            "blockers": blockers,
            "warnings": warnings,
            "checklist": {
                "upstream_coverage_checkpoint_valid": upstream_cp is not None,
                "recipes_total": len(recipes_to_eval),
                "recipes_ready": sum(1 for r in recipes_to_eval if r.authoring_state == RecipeState.READY),
                "target_bindings_ready": sum(1 for b in binding_sets.values() if b.authoring_state == AuthoringState.READY),
                "backends_ready": len(backend_configs),
                "unimplemented_objective_count": unimplemented_count,
                "blockers_count": len(blockers),
                "warnings_count": len(warnings),
            },
            "payload": summary_payload,
        }

    def create_checkpoint(
        self,
        plan_id: str,
        reviewer_label: str,
        comment: str,
        expected_digest: str | None = None,
        acknowledged_warnings: list[str] | None = None,
        layer: str = "plan",
        upstream_checkpoint_id: str | None = None,
    ) -> PlanCheckpoint:
        """Create an immutable Plan Checkpoint (P1), Coverage Checkpoint (C1), or Implementation Checkpoint (I1)."""
        evaluation = self.evaluate_checklist(
            plan_id=plan_id,
            layer=layer,
            upstream_checkpoint_id=upstream_checkpoint_id,
        )
        blockers = evaluation["blockers"]
        if blockers:
            raise CheckpointBlockerError(
                f"Cannot create checkpoint: {len(blockers)} unresolved blockers exist.",
                evaluation["checklist"],
                [b["message"] for b in blockers],
            )

        candidate_digest = evaluation["candidate_digest"]
        if expected_digest and expected_digest != candidate_digest:
            raise CheckpointBlockerError(
                f"Checkpoint candidate digest mismatch: expected '{expected_digest}', got '{candidate_digest}'.",
                evaluation["checklist"],
                ["Digest mismatch indicates concurrent edits since preview."],
            )

        ack_set = set(acknowledged_warnings or [])
        if layer == "implementation":
            prefix = KEY_PREFIX_CHK_IMPLEMENTATION
        elif layer == "coverage":
            prefix = KEY_PREFIX_CHK_COVERAGE
        else:
            prefix = KEY_PREFIX_CHK_PLAN

        key = self.repo.allocate_key(plan_id, prefix)
        now_iso = datetime.now(timezone.utc).isoformat()
        checkpoint_id = str(uuid.uuid4())

        plan = self.repo.get_plan(plan_id)
        assert plan is not None

        checkpoint = PlanCheckpoint(
            id=checkpoint_id,
            key=key,
            layer=layer,
            plan_id=plan_id,
            created_at=now_iso,
            reviewer_label=reviewer_label,
            comment=comment,
            upstream_checkpoint_id=evaluation.get("upstream_checkpoint_id"),
            snapshot_id=plan.snapshot_id,
            root_scope_id=plan.root_scope_id,
            checklist=evaluation["checklist"],
            acknowledged_warnings=list(ack_set),
            content_hash=candidate_digest,
            payload=evaluation["payload"],
        )

        self.repo.save_checkpoint(checkpoint)
        return checkpoint

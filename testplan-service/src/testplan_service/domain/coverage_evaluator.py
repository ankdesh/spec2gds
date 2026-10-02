"""Coverage status computation, deterministic evaluation order, and gap analysis engine.

Reviewer path: choose eligible campaign/profile observations before computing
family/branch status. Failures outrank waivers and later passes; no-campaign or
missing evidence stays unevaluated rather than becoming a fabricated success.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from testplan_service.domain.enums import AuthoringState, RequirementDisposition
from testplan_service.domain.evidence import (
    CampaignPurpose,
    CampaignState,
    EvaluationProfile,
    EvidenceCampaign,
    EvidenceObservation,
    EvidenceRun,
    ObservationOutcome,
    RunDispositionKind,
    RunStatus,
)
from testplan_service.domain.gaps import CoverageGap, GapCode, GapSeverity
from testplan_service.domain.models import Intent, Requirement
from testplan_service.domain.objectives import (
    BinStatus,
    CoverageFamily,
    CoverageObjective,
    PropertyClaimKind,
)
from testplan_service.domain.policies import IntentEvidencePolicy, IntentWaiver


class CoverageEvaluator:
    """Evaluates Layer 2 coverage status, aggregation metrics, and deterministic gaps."""

    def evaluate_intent_status(
        self,
        intent: Intent,
        policy: IntentEvidencePolicy | None,
        objectives: dict[str, CoverageObjective],
        campaign: EvidenceCampaign | None,
        profiles: dict[str, EvaluationProfile],
        runs: dict[str, EvidenceRun],
        observations_by_run: dict[str, list[EvidenceObservation]],
        now_iso: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate status of one intent against the selected campaign and required profiles."""
        if now_iso is None:
            now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Authoring and Mapping State
        if not policy or not policy.branches:
            return {
                "intent_id": intent.id,
                "authoring_state": intent.authoring_state.value,
                "mapping_state": "no_policy",
                "achievement_state": "not_evaluated",
                "profile_statuses": {},
                "branch_evaluations": [],
                "unresolved_failures": [],
                "family_cell_summaries": {
                    "scenario": "None planned",
                    "functional": "None planned",
                    "checking": "Missing",
                    "property": "—",
                },
                "explanation": "No evidence policy defined for this intent.",
            }

        # Check mapping completeness
        missing_objectives: list[str] = []
        for branch in policy.branches:
            for obj_id in branch.objective_ids:
                if obj_id not in objectives or objectives[obj_id].archived:
                    missing_objectives.append(obj_id)

        mapping_state = "invalid" if missing_objectives else "mapped"

        # Determine target profiles
        target_profile_ids = campaign.required_profile_ids if campaign else list(profiles.keys())
        if not target_profile_ids and profiles:
            target_profile_ids = list(profiles.keys())

        if not campaign or not target_profile_ids:
            # Without a campaign or profiles
            cell_summaries = self._compute_family_cells(policy, objectives, [])
            return {
                "intent_id": intent.id,
                "authoring_state": intent.authoring_state.value,
                "mapping_state": mapping_state,
                "achievement_state": "not_evaluated",
                "profile_statuses": {},
                "branch_evaluations": [],
                "unresolved_failures": [],
                "family_cell_summaries": cell_summaries,
                "explanation": "No campaign selected.",
            }

        profile_statuses: dict[str, str] = {}
        all_eligible_obs: list[EvidenceObservation] = []
        unresolved_failures_all: list[str] = []

        for prof_id in target_profile_ids:
            prof = profiles.get(prof_id)
            if not prof:
                continue

            status, prof_obs, prof_failures = self._evaluate_intent_for_profile(
                intent=intent,
                policy=policy,
                objectives=objectives,
                campaign=campaign,
                profile=prof,
                runs=runs,
                observations_by_run=observations_by_run,
                now_iso=now_iso,
            )
            profile_statuses[prof_id] = status
            all_eligible_obs.extend(prof_obs)
            unresolved_failures_all.extend(prof_failures)

        # Propagate across profiles per Section 4.2
        overall_status = self._propagate_profile_statuses(profile_statuses)
        cell_summaries = self._compute_family_cells(policy, objectives, all_eligible_obs)

        return {
            "intent_id": intent.id,
            "authoring_state": intent.authoring_state.value,
            "mapping_state": mapping_state,
            "achievement_state": overall_status,
            "profile_statuses": profile_statuses,
            "unresolved_failures": list(set(unresolved_failures_all)),
            "family_cell_summaries": cell_summaries,
            "explanation": f"Evaluation across {len(profile_statuses)} profile(s): {overall_status}.",
        }

    def _evaluate_intent_for_profile(
        self,
        intent: Intent,
        policy: IntentEvidencePolicy,
        objectives: dict[str, CoverageObjective],
        campaign: EvidenceCampaign,
        profile: EvaluationProfile,
        runs: dict[str, EvidenceRun],
        observations_by_run: dict[str, list[EvidenceObservation]],
        now_iso: str,
    ) -> tuple[str, list[EvidenceObservation], list[str]]:
        """Evaluate intent status for a single evaluation profile."""
        # 1. Select campaign runs included for this profile
        eligible_runs: list[EvidenceRun] = []
        for run_id in campaign.included_run_ids:
            run = runs.get(run_id)
            if not run or run.profile_id != profile.id:
                continue

            # Check disposition
            if run_id in campaign.run_dispositions:
                disp = campaign.run_dispositions[run_id]
                if disp.disposition in {RunDispositionKind.INVALID_TOOL_RUN, RunDispositionKind.SUPERSEDED_AFTER_FIX}:
                    continue

            eligible_runs.append(run)

        # 2. Collect eligible observations with provenance matching
        eligible_observations: list[EvidenceObservation] = []
        tool_errors_encountered: list[str] = []
        incompatible_runs: list[str] = []

        all_linked_obj_ids = set()
        for branch in policy.branches:
            all_linked_obj_ids.update(branch.objective_ids)
        all_linked_obj_ids.update(policy.supplemental_objective_ids)

        for run in eligible_runs:
            # Check compatibility against profile
            if run.dut_source_hash != profile.dut_source_hash:
                incompatible_runs.append(run.id)
                continue

            if run.status == RunStatus.ERROR:
                tool_errors_encountered.append(f"Tool error in run {run.id}")

            run_obs = observations_by_run.get(run.id, [])
            for obs in run_obs:
                if obs.objective_id in all_linked_obj_ids:
                    # Scope check: scope of observation must match scope of intent or participants (if specified)
                    if obs.scope_id and obs.scope_id != intent.scope_id and obs.scope_id not in intent.participants:
                        continue
                    eligible_observations.append(obs)

        # 3. Check for unresolved behavioral check failures
        unresolved_failures: list[str] = []
        for obs in eligible_observations:
            if obs.outcome in {ObservationOutcome.FAIL, ObservationOutcome.COUNTEREXAMPLE}:
                unresolved_failures.append(f"Failed check on objective {obs.objective_id}: {obs.diagnostic_message or 'behavioral failure'}")

        if unresolved_failures:
            return "failed", eligible_observations, unresolved_failures

        # 4. Check for blocking tool errors / inconclusive proof
        if tool_errors_encountered and not eligible_observations:
            return "blocked", eligible_observations, []

        for obs in eligible_observations:
            if obs.outcome in {ObservationOutcome.ERROR, ObservationOutcome.UNKNOWN, ObservationOutcome.TIMEOUT}:
                # If an error/unknown outcome occurs on a required check without alternative
                obj = objectives.get(obs.objective_id)
                if obj and obj.family in {CoverageFamily.CORRECTNESS, CoverageFamily.PROPERTY}:
                    return "blocked", eligible_observations, []

        # 5. Evaluate branch satisfaction
        branch_satisfactions: list[bool] = []
        has_any_partial_evidence = len(eligible_observations) > 0

        for branch in policy.branches:
            branch_ok = True
            for obj_id in branch.objective_ids:
                obj = objectives.get(obj_id)
                if not obj or obj.authoring_state != AuthoringState.READY:
                    branch_ok = False
                    break

                obj_obs = [o for o in eligible_observations if o.objective_id == obj_id]
                is_obj_satisfied = self._is_objective_satisfied(obj, obj_obs)
                if not is_obj_satisfied:
                    branch_ok = False
                    break

            branch_satisfactions.append(branch_ok)

        # If any branch is satisfied -> Satisfied
        if any(branch_satisfactions):
            return "satisfied", eligible_observations, []

        # 6. Check intent waiver
        active_waiver = False
        for waiver in campaign.waivers:
            if waiver.intent_id == intent.id and not waiver.revoked:
                if not waiver.profile_ids or profile.id in waiver.profile_ids:
                    if waiver.expires_at > now_iso:
                        active_waiver = True
                        break

        if active_waiver:
            return "waived", eligible_observations, []

        # 7. Open vs Not evaluated
        if has_any_partial_evidence:
            return "open", eligible_observations, []

        return "not_evaluated", eligible_observations, []

    def _is_objective_satisfied(
        self,
        obj: CoverageObjective,
        observations: list[EvidenceObservation],
    ) -> bool:
        """Evaluate if an objective meets its acceptance criteria."""
        if not observations:
            return False

        if obj.family in {CoverageFamily.SCENARIO, CoverageFamily.FUNCTIONAL}:
            if not obj.bins:
                return False

            required_bins = [b for b in obj.bins if b.status == BinStatus.REQUIRED]
            if not required_bins:
                return False

            # Bins hit mapping
            for b in required_bins:
                bin_obs = [o for o in observations if o.bin_id == b.id or len(required_bins) == 1]
                total_hits = sum(o.hit_count for o in bin_obs)
                if total_hits < b.required_hits:
                    return False

            return True

        elif obj.family == CoverageFamily.CORRECTNESS:
            min_evals = obj.acceptance.get("minimum_evaluations", 1)
            total_evals = sum(o.evaluation_count for o in observations)
            has_fail = any(o.outcome in {ObservationOutcome.FAIL, ObservationOutcome.ERROR} for o in observations)
            has_pass = any(o.outcome == ObservationOutcome.PASS for o in observations)
            return (total_evals >= min_evals) and has_pass and not has_fail

        elif obj.family == CoverageFamily.PROPERTY:
            claim = obj.acceptance.get("claim", PropertyClaimKind.UNBOUNDED)
            for o in observations:
                if o.outcome == ObservationOutcome.PROVEN:
                    # Unbounded check: require checked_nonvacuous
                    if claim == PropertyClaimKind.UNBOUNDED:
                        vacuity = o.property_fields.get("vacuity_result", "checked_nonvacuous")
                        if vacuity != "checked_nonvacuous":
                            return False
                    return True
                elif o.outcome == ObservationOutcome.BOUNDED_PASS:
                    if claim == PropertyClaimKind.UNBOUNDED:
                        # Bounded pass does not satisfy unbounded property objective (L2-10)
                        return False
                    min_bound = obj.acceptance.get("bound", 1)
                    obs_bound = o.property_fields.get("bound", 0)
                    return obs_bound >= min_bound
            return False

        elif obj.family == CoverageFamily.STRUCTURAL:
            target_elements = obj.acceptance.get("target_elements", [])
            threshold_bps = obj.acceptance.get("threshold_bps", 10000)
            if not target_elements:
                return False
            # Set union of hit elements
            hit_elements = set()
            for o in observations:
                hit_elements.update(o.structural_elements)
            coverage_bps = int((len(hit_elements) / len(target_elements)) * 10000)
            return coverage_bps >= threshold_bps

        return False

    def _propagate_profile_statuses(self, profile_statuses: dict[str, str]) -> str:
        """Combine per-profile statuses into overall intent status."""
        if not profile_statuses:
            return "not_evaluated"

        statuses = list(profile_statuses.values())
        if all(s == "satisfied" for s in statuses):
            return "satisfied"
        if any(s == "failed" for s in statuses):
            return "failed"
        if any(s == "blocked" for s in statuses):
            return "blocked"
        if any(s == "waived" for s in statuses):
            if any(s == "satisfied" for s in statuses):
                return "waived_in_part"
            return "waived"
        if any(s == "open" for s in statuses):
            return "open"
        return "not_evaluated"

    def _compute_family_cells(
        self,
        policy: IntentEvidencePolicy,
        objectives: dict[str, CoverageObjective],
        observations: list[EvidenceObservation],
    ) -> dict[str, str]:
        """Compute the 4 main family cell text summaries for an intent row."""
        linked_obj_ids = []
        for branch in policy.branches:
            linked_obj_ids.extend(branch.objective_ids)
        linked_objs = [objectives[oid] for oid in linked_obj_ids if oid in objectives]

        cells = {
            "scenario": "None planned",
            "functional": "None planned",
            "checking": "Missing",
            "property": "—",
        }

        # Scenario
        scen_objs = [o for o in linked_objs if o.family == CoverageFamily.SCENARIO]
        if scen_objs:
            total_req_bins = sum(len([b for b in o.bins if b.status == BinStatus.REQUIRED]) for o in scen_objs)
            hit_bins = 0
            for o in scen_objs:
                for b in o.bins:
                    if b.status == BinStatus.REQUIRED:
                        obs = [ob for ob in observations if ob.objective_id == o.id and (ob.bin_id == b.id or len(o.bins) == 1)]
                        if sum(x.hit_count for x in obs) >= b.required_hits:
                            hit_bins += 1
            cells["scenario"] = f"{hit_bins}/{total_req_bins}"

        # Functional
        func_objs = [o for o in linked_objs if o.family == CoverageFamily.FUNCTIONAL]
        if func_objs:
            total_req_bins = sum(len([b for b in o.bins if b.status == BinStatus.REQUIRED]) for o in func_objs)
            hit_bins = 0
            for o in func_objs:
                for b in o.bins:
                    if b.status == BinStatus.REQUIRED:
                        obs = [ob for ob in observations if ob.objective_id == o.id and (ob.bin_id == b.id or len(o.bins) == 1)]
                        if sum(x.hit_count for x in obs) >= b.required_hits:
                            hit_bins += 1
            cells["functional"] = f"{hit_bins}/{total_req_bins}"

        # Checking (Correctness)
        chk_objs = [o for o in linked_objs if o.family == CoverageFamily.CORRECTNESS]
        if chk_objs:
            chk_obs = [ob for ob in observations if ob.objective_id in {o.id for o in chk_objs}]
            if not chk_obs:
                cells["checking"] = "Not evaluated"
            elif any(ob.outcome in {ObservationOutcome.FAIL, ObservationOutcome.ERROR} for ob in chk_obs):
                cells["checking"] = "Failed"
            elif any(ob.outcome == ObservationOutcome.PASS for ob in chk_obs):
                cells["checking"] = "Passed"
            else:
                cells["checking"] = "Not evaluated"

        # Property
        prop_objs = [o for o in linked_objs if o.family == CoverageFamily.PROPERTY]
        if prop_objs:
            prop_obs = [ob for ob in observations if ob.objective_id in {o.id for o in prop_objs}]
            if not prop_obs:
                cells["property"] = "Not evaluated"
            elif any(ob.outcome == ObservationOutcome.COUNTEREXAMPLE for ob in prop_obs):
                cells["property"] = "Counterexample"
            elif any(ob.outcome == ObservationOutcome.PROVEN for ob in prop_obs):
                cells["property"] = "Proven"
            elif any(ob.outcome == ObservationOutcome.BOUNDED_PASS for ob in prop_obs):
                cells["property"] = "Bounded pass"
            else:
                cells["property"] = "Unknown"

        return cells

    def compute_matrix(
        self,
        intents: list[Intent],
        requirements: list[Requirement],
        policies: dict[str, IntentEvidencePolicy],
        objectives: dict[str, CoverageObjective],
        campaign: EvidenceCampaign | None,
        profiles: dict[str, EvaluationProfile],
        runs: dict[str, EvidenceRun],
        observations_by_run: dict[str, list[EvidenceObservation]],
        filtered_intent_ids: set[str] | None = None,
        status_filter: str | None = None,
    ) -> dict[str, Any]:
        """Compute the full coverage matrix and summary rollups."""
        now_iso = datetime.now(timezone.utc).isoformat()
        intent_evaluations: list[dict[str, Any]] = []

        # Whole baseline counts
        total_intents = len(intents)
        mapped_intents = 0
        satisfied_intents = 0
        failed_intents = 0
        blocked_intents = 0
        waived_intents = 0
        open_intents = 0
        not_evaluated_intents = 0

        # Objective bin rollup: count unique required bins across unique objectives (L2-03)
        unique_required_bins = 0
        unique_satisfied_bins = 0
        all_obs_flat = [obs for obs_list in observations_by_run.values() for obs in obs_list]

        for obj in objectives.values():
            if obj.archived or obj.family not in {CoverageFamily.SCENARIO, CoverageFamily.FUNCTIONAL}:
                continue
            for b in obj.bins:
                if b.status == BinStatus.REQUIRED:
                    unique_required_bins += 1
                    b_obs = [o for o in all_obs_flat if o.objective_id == obj.id and (o.bin_id == b.id or len(obj.bins) == 1)]
                    if sum(o.hit_count for o in b_obs) >= b.required_hits:
                        unique_satisfied_bins += 1

        for intent in intents:
            policy = policies.get(intent.id)
            eval_res = self.evaluate_intent_status(
                intent=intent,
                policy=policy,
                objectives=objectives,
                campaign=campaign,
                profiles=profiles,
                runs=runs,
                observations_by_run=observations_by_run,
                now_iso=now_iso,
            )
            intent_evaluations.append(eval_res)

            if eval_res["mapping_state"] == "mapped":
                mapped_intents += 1

            ach = eval_res["achievement_state"]
            if ach == "satisfied":
                satisfied_intents += 1
            elif ach == "failed":
                failed_intents += 1
            elif ach == "blocked":
                blocked_intents += 1
            elif ach in {"waived", "waived_in_part"}:
                waived_intents += 1
            elif ach == "open":
                open_intents += 1
            else:
                not_evaluated_intents += 1

        # Verifiable requirement rollup
        verifiable_reqs = [r for r in requirements if r.disposition == RequirementDisposition.VERIFY and not r.archived]
        mapped_reqs = 0
        satisfied_reqs = 0
        eval_by_intent_id = {e["intent_id"]: e for e in intent_evaluations}

        for req in verifiable_reqs:
            linked_intents = [i for i in intents if req.id in i.requirement_ids and not i.archived]
            if linked_intents:
                mapped_reqs += 1
                if all(eval_by_intent_id.get(i.id, {}).get("achievement_state") == "satisfied" for i in linked_intents):
                    satisfied_reqs += 1

        baseline_summary = {
            "total_intents": total_intents,
            "mapped_intents": mapped_intents,
            "satisfied_intents": satisfied_intents,
            "failed_intents": failed_intents,
            "blocked_intents": blocked_intents,
            "waived_intents": waived_intents,
            "open_intents": open_intents,
            "not_evaluated_intents": not_evaluated_intents,
            "verifiable_requirements_total": len(verifiable_reqs),
            "verifiable_requirements_mapped": mapped_reqs,
            "verifiable_requirements_satisfied": satisfied_reqs,
            "required_bins_total": unique_required_bins,
            "required_bins_satisfied": unique_satisfied_bins,
        }

        # Filtered rows
        filtered_rows = intent_evaluations
        if filtered_intent_ids is not None:
            filtered_rows = [r for r in filtered_rows if r["intent_id"] in filtered_intent_ids]
        if status_filter is not None:
            filtered_rows = [r for r in filtered_rows if r["achievement_state"] == status_filter]

        filtered_summary = {
            "visible_intents": len(filtered_rows),
            "satisfied_intents": sum(1 for r in filtered_rows if r["achievement_state"] == "satisfied"),
            "failed_intents": sum(1 for r in filtered_rows if r["achievement_state"] == "failed"),
            "blocked_intents": sum(1 for r in filtered_rows if r["achievement_state"] == "blocked"),
            "waived_intents": sum(1 for r in filtered_rows if r["achievement_state"] in {"waived", "waived_in_part"}),
            "open_intents": sum(1 for r in filtered_rows if r["achievement_state"] == "open"),
            "not_evaluated_intents": sum(1 for r in filtered_rows if r["achievement_state"] == "not_evaluated"),
        }

        return {
            "rows": filtered_rows,
            "baseline_summary": baseline_summary,
            "filtered_summary": filtered_summary,
        }

    def compute_gaps(
        self,
        intents: list[Intent],
        requirements: list[Requirement],
        policies: dict[str, IntentEvidencePolicy],
        objectives: dict[str, CoverageObjective],
        campaign: EvidenceCampaign | None,
        profiles: dict[str, EvaluationProfile],
        runs: dict[str, EvidenceRun],
        observations_by_run: dict[str, list[EvidenceObservation]],
    ) -> list[CoverageGap]:
        """Compute all typed deterministic gap records per Section 5."""
        gaps: list[CoverageGap] = []

        # 1. Requirement unmapped
        verifiable_reqs = [r for r in requirements if r.disposition == RequirementDisposition.VERIFY and not r.archived]
        for req in verifiable_reqs:
            linked = any(req.id in i.requirement_ids and not i.archived for i in intents)
            if not linked:
                gaps.append(
                    CoverageGap(
                        id=f"gap:req_unmapped:{req.id}",
                        gap_code=GapCode.REQUIREMENT_UNMAPPED,
                        severity=GapSeverity.ERROR,
                        title=f"Verifiable requirement lacks intent: {req.title}",
                        explanation=f"Requirement '{req.title}' ({req.key}) has no active linked intent.",
                        affected_record_ids=[req.id],
                        primary_action={"action": "add_intent", "label": "Add/link intent", "requirement_id": req.id},
                    )
                )

        # 2. Intent policy missing & checking missing
        for intent in intents:
            if intent.archived:
                continue
            policy = policies.get(intent.id)
            if not policy or not policy.branches:
                gaps.append(
                    CoverageGap(
                        id=f"gap:policy_missing:{intent.id}",
                        gap_code=GapCode.INTENT_POLICY_MISSING,
                        severity=GapSeverity.ERROR,
                        title=f"Evidence policy missing: {intent.title}",
                        explanation=f"Intent '{intent.title}' ({intent.key}) has no defined evidence policy.",
                        affected_record_ids=[intent.id],
                        primary_action={"action": "define_policy", "label": "Define evidence policy", "intent_id": intent.id},
                    )
                )
                continue

            # Check branches for missing checking/property objectives
            for b_idx, branch in enumerate(policy.branches):
                has_checking = False
                for oid in branch.objective_ids:
                    obj = objectives.get(oid)
                    if obj and obj.family in {CoverageFamily.CORRECTNESS, CoverageFamily.PROPERTY}:
                        has_checking = True
                        break
                if not has_checking:
                    gaps.append(
                        CoverageGap(
                            id=f"gap:checking_missing:{intent.id}:b{b_idx}",
                            gap_code=GapCode.CHECKING_MISSING,
                            severity=GapSeverity.ERROR,
                            title=f"Checking objective missing in branch '{branch.title}'",
                            explanation=f"Branch '{branch.title}' for intent '{intent.title}' contains only coverage and lacks correctness or property verification.",
                            affected_record_ids=[intent.id],
                            primary_action={"action": "add_checking_objective", "label": "Add correctness/property objective", "intent_id": intent.id},
                        )
                    )

        # 3. Objective completeness & bins
        for obj in objectives.values():
            if obj.archived:
                continue
            if obj.family in {CoverageFamily.SCENARIO, CoverageFamily.FUNCTIONAL}:
                req_bins = [b for b in obj.bins if b.status == BinStatus.REQUIRED]
                if not req_bins:
                    gaps.append(
                        CoverageGap(
                            id=f"gap:obj_no_bins:{obj.id}",
                            gap_code=GapCode.OBJECTIVE_INCOMPLETE,
                            severity=GapSeverity.ERROR,
                            title=f"Objective has zero required bins: {obj.title}",
                            explanation=f"Scenario/functional objective '{obj.title}' ({obj.key}) has zero non-excluded bins.",
                            affected_record_ids=[obj.id],
                            primary_action={"action": "edit_objective", "label": "Add bins to objective", "objective_id": obj.id},
                        )
                    )

        # 4. Result-based gaps (failures, unhit bins, weak check evidence)
        if campaign:
            matrix_res = self.compute_matrix(
                intents=intents,
                requirements=requirements,
                policies=policies,
                objectives=objectives,
                campaign=campaign,
                profiles=profiles,
                runs=runs,
                observations_by_run=observations_by_run,
            )
            for row in matrix_res["rows"]:
                if row["achievement_state"] == "failed":
                    for fail_msg in row.get("unresolved_failures", []):
                        gaps.append(
                            CoverageGap(
                                id=f"gap:check_failed:{row['intent_id']}",
                                gap_code=GapCode.CHECK_FAILED,
                                severity=GapSeverity.ERROR,
                                title=f"Check failed for {row['intent_id']}",
                                explanation=fail_msg,
                                affected_record_ids=[row["intent_id"]],
                                primary_action={"action": "inspect_failure", "label": "Inspect failed check", "intent_id": row["intent_id"]},
                            )
                        )
                elif row["achievement_state"] == "blocked":
                    gaps.append(
                        CoverageGap(
                            id=f"gap:blocked:{row['intent_id']}",
                            gap_code=GapCode.PROOF_INCONCLUSIVE,
                            severity=GapSeverity.ERROR,
                            title=f"Proof inconclusive or tool error for {row['intent_id']}",
                            explanation=row.get("explanation", "Verification is blocked"),
                            affected_record_ids=[row["intent_id"]],
                            primary_action={"action": "inspect_property", "label": "Inspect property evidence", "intent_id": row["intent_id"]},
                        )
                    )
                elif row["achievement_state"] in {"not_evaluated", "open"}:
                    gaps.append(
                        CoverageGap(
                            id=f"gap:evidence_missing:{row['intent_id']}",
                            gap_code=GapCode.EVIDENCE_MISSING,
                            severity=GapSeverity.WARNING,
                            title=f"Evidence missing or incomplete for {row['intent_id']}",
                            explanation=f"Intent '{row['intent_id']}' has not achieved required coverage.",
                            affected_record_ids=[row["intent_id"]],
                            primary_action={"action": "inspect_import", "label": "Inspect expected result/import path", "intent_id": row["intent_id"]},
                        )
                    )

        # 5. Check for unbound results
        seen_unbound_objs = set()
        for run_id, obs_list in observations_by_run.items():
            for obs in obs_list:
                if obs.objective_id not in objectives and obs.objective_id not in seen_unbound_objs:
                    seen_unbound_objs.add(obs.objective_id)
                    gaps.append(
                        CoverageGap(
                            id=f"gap:unbound_result:{obs.objective_id}",
                            gap_code=GapCode.UNBOUND_RESULT,
                            severity=GapSeverity.WARNING,
                            title=f"Unbound result: objective {obs.objective_id}",
                            explanation=f"Observation in run '{run_id}' references unknown objective '{obs.objective_id}'.",
                            affected_record_ids=[obs.objective_id],
                            primary_action={"action": "bind_result", "label": "Bind external result", "objective_id": obs.objective_id},
                        )
                    )

        return gaps

"""Coverage and evidence application service coordinating profiles, campaigns, and results."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
import uuid

from testplan_service.constants import SCHEMA_VERSION_RESULTS
from testplan_service.domain.coverage_evaluator import CoverageEvaluator
from testplan_service.domain.evidence import (
    CampaignPurpose,
    CampaignState,
    EvaluationProfile,
    EvidenceCampaign,
    EvidenceObservation,
    EvidenceReport,
    EvidenceRun,
    ObservationOutcome,
    RealizationDescriptor,
    RunStatus,
)
from testplan_service.domain.gaps import CoverageGap
from testplan_service.domain.hash import canonical_json, sha256_digest
from testplan_service.domain.models import Intent, Requirement
from testplan_service.domain.objectives import CoverageObjective
from testplan_service.domain.policies import IntentEvidencePolicy
from testplan_service.exceptions import (
    CampaignNotFoundError,
    DomainValidationError,
    ImportValidationError,
    PlanNotFoundError,
    ProfileNotFoundError,
    RecordNotFoundError,
)
from testplan_service.storage.sqlite_repo import SqlitePlanRepository


class CoverageService:
    """Application coordinator for Layer 2 coverage planning and evidence campaigns."""

    def __init__(self, repo: SqlitePlanRepository) -> None:
        self.repo = repo
        self.evaluator = CoverageEvaluator()

    # --- Profiles ---
    def create_profile(
        self,
        plan_id: str,
        display_name: str,
        coverage_checkpoint_id: str,
        source_snapshot_id: str,
        source_snapshot_hash: str,
        dut_source_hash: str,
        root_occurrence_id: str,
        resolved_parameters: dict[str, Any] | None = None,
        clock_reset_config: dict[str, Any] | None = None,
        realization_descriptors: list[dict[str, Any]] | None = None,
        profile_id: str | None = None,
    ) -> EvaluationProfile:
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        p_id = profile_id or str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        descriptors = [
            RealizationDescriptor.model_validate(d) for d in (realization_descriptors or [])
        ]

        content_dict = {
            "display_name": display_name,
            "coverage_checkpoint_id": coverage_checkpoint_id,
            "dut_source_hash": dut_source_hash,
            "root_occurrence_id": root_occurrence_id,
            "resolved_parameters": resolved_parameters or {},
            "clock_reset_config": clock_reset_config or {},
            "realization_descriptors": [d.model_dump() for d in descriptors],
        }
        content_hash = sha256_digest(canonical_json(content_dict))

        profile = EvaluationProfile(
            id=p_id,
            plan_id=plan_id,
            display_name=display_name,
            coverage_checkpoint_id=coverage_checkpoint_id,
            source_snapshot_id=source_snapshot_id,
            source_snapshot_hash=source_snapshot_hash,
            dut_source_hash=dut_source_hash,
            root_occurrence_id=root_occurrence_id,
            resolved_parameters=resolved_parameters or {},
            clock_reset_config=clock_reset_config or {},
            realization_descriptors=descriptors,
            content_hash=content_hash,
            created_at=now_iso,
        )

        self.repo.save_profile(profile)
        return profile

    def get_profile(self, plan_id: str, profile_id: str) -> EvaluationProfile | None:
        return self.repo.get_profile(plan_id, profile_id)

    def list_profiles(self, plan_id: str) -> list[EvaluationProfile]:
        return self.repo.list_profiles(plan_id)

    # --- Campaigns ---
    def create_campaign(
        self,
        plan_id: str,
        title: str,
        coverage_checkpoint_id: str = "",
        required_profile_ids: list[str] | None = None,
        purpose: str = "verification",
        campaign_id: str | None = None,
    ) -> EvidenceCampaign:
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        c_id = campaign_id or str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        campaign = EvidenceCampaign(
            id=c_id,
            plan_id=plan_id,
            title=title,
            coverage_checkpoint_id=coverage_checkpoint_id,
            required_profile_ids=required_profile_ids,
            included_run_ids=[],
            run_dispositions={},
            waivers=[],
            purpose=CampaignPurpose(purpose),
            state=CampaignState.OPEN,
            campaign_revision=1,
            created_at=now_iso,
            updated_at=now_iso,
        )

        self.repo.save_campaign(campaign)
        return campaign

    def get_campaign(self, plan_id: str, campaign_id: str) -> EvidenceCampaign | None:
        return self.repo.get_campaign(plan_id, campaign_id)

    def list_campaigns(self, plan_id: str) -> list[EvidenceCampaign]:
        return self.repo.list_campaigns(plan_id)

    def execute_campaign_commands(
        self,
        plan_id: str,
        campaign_id: str,
        base_campaign_revision: int,
        request_id: str,
        operations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload_hash = sha256_digest(canonical_json(operations))
        cached = self.repo.check_campaign_idempotency(campaign_id, request_id, payload_hash)
        if cached is not None:
            return cached

        now_iso = datetime.now(timezone.utc).isoformat()
        return self.repo.execute_campaign_command(
            plan_id=plan_id,
            campaign_id=campaign_id,
            request_id=request_id,
            base_campaign_revision=base_campaign_revision,
            payload_hash=payload_hash,
            operations=operations,
            now_iso=now_iso,
        )

    # --- Result Import ---
    def stage_result_import(self, plan_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        # Validate structure
        if "producer" not in payload or "run" not in payload or "observations" not in payload:
            raise ImportValidationError("Import payload missing required keys ('producer', 'run', 'observations').")

        # Validate non-negative numbers and valid outcomes
        for obs in payload["observations"]:
            eval_count = obs.get("evaluation_count", 0)
            hit_count = obs.get("hit_count", 0)
            if eval_count < 0 or hit_count < 0:
                raise ImportValidationError(f"Negative evaluation/hit count in observation '{obs.get('producer_observation_id')}'.")
            outcome = obs.get("outcome")
            try:
                ObservationOutcome(outcome)
            except ValueError:
                raise ImportValidationError(f"Unknown observation outcome '{outcome}'.")

        staging_id = str(uuid.uuid4())
        preview_digest = sha256_digest(canonical_json(payload))
        now_iso = datetime.now(timezone.utc).isoformat()

        raw_records = self.repo.get_records(plan_id, include_archived=False)
        known_obj_ids = {r["id"] for r in raw_records if r.get("record_type") == "objective"}

        observations = payload.get("observations", [])
        known_count = sum(1 for o in observations if o.get("objective_id") in known_obj_ids)
        unbound_count = len(observations) - known_count

        self.repo.save_result_import(
            import_id=staging_id,
            plan_id=plan_id,
            status_str="staged",
            preview_digest=preview_digest,
            payload_json=json.dumps(payload),
            created_at=now_iso,
        )

        return {
            "staging_id": staging_id,
            "preview_digest": preview_digest,
            "run_count": 1,
            "observations_count": len(observations),
            "known_observations_count": known_count,
            "unbound_observations_count": unbound_count,
            "created_at": now_iso,
        }

    def commit_result_import(
        self,
        plan_id: str,
        staging_id: str,
        expected_preview_digest: str | None = None,
        campaign_id: str | None = None,
        campaign_revision: int | None = None,
    ) -> dict[str, Any]:
        staged = self.repo.get_result_import(plan_id, staging_id)
        if not staged:
            raise RecordNotFoundError(plan_id, staging_id)

        if expected_preview_digest and staged["preview_digest"] != expected_preview_digest:
            raise ImportValidationError(f"Staged preview digest mismatch: expected '{expected_preview_digest}', got '{staged['preview_digest']}'.")

        payload = staged["payload"]
        run_data = payload["run"]
        producer_data = payload["producer"]
        now_iso = datetime.now(timezone.utc).isoformat()

        run_id = str(uuid.uuid4())
        run = EvidenceRun(
            id=run_id,
            plan_id=plan_id,
            producer_id=producer_data.get("id", "external-producer"),
            external_run_id=run_data["external_run_id"],
            attempt_id=run_data.get("attempt_id", "1"),
            profile_id=payload["profile_id"],
            coverage_checkpoint_id=payload.get("coverage_checkpoint_id", ""),
            producer_manifest_digest=payload.get("producer_manifest_digest", ""),
            dut_source_hash=run_data.get("dut_source_hash", ""),
            configuration_hash=run_data.get("configuration_hash", ""),
            tool_name=producer_data.get("tool_name", "simulator"),
            tool_version=producer_data.get("tool_version", "1.0"),
            seed=run_data.get("seed"),
            synthetic=payload.get("synthetic", False),
            producer_kind=producer_data.get("producer_kind", "generated"),
            trust_label=payload.get("trust_label", "imported_local"),
            status=RunStatus(run_data.get("status", RunStatus.COMPLETED)),
            raw_artifact_digests=payload.get("raw_artifact_digests", []),
            parser_adapter_id=payload.get("parser_adapter_id", SCHEMA_VERSION_RESULTS),
            validation_diagnostics=[],
            start_time=run_data.get("start_time"),
            end_time=run_data.get("end_time"),
            imported_at=now_iso,
            payload_hash=staged["preview_digest"],
        )

        raw_records = self.repo.get_records(plan_id, include_archived=False)
        obj_scope_map = {r["id"]: r.get("scope_id", "") for r in raw_records if r.get("record_type") == "objective"}
        if payload.get("coverage_checkpoint_id"):
            cp = self.repo.get_checkpoint(plan_id, payload["coverage_checkpoint_id"])
            if cp and cp.layer == "coverage":
                for o in cp.payload.get("objectives", []):
                    if o.get("id") and o.get("scope_id"):
                        obj_scope_map[o["id"]] = o["scope_id"]

        observations: list[EvidenceObservation] = []
        for obs_data in payload.get("observations", []):
            obs_scope = obs_data.get("scope_id") or obj_scope_map.get(obs_data["objective_id"], "")
            observations.append(
                EvidenceObservation(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    producer_observation_id=obs_data["producer_observation_id"],
                    objective_id=obs_data["objective_id"],
                    objective_definition_hash=obs_data.get("objective_definition_hash", ""),
                    scope_id=obs_scope,
                    bin_id=obs_data.get("bin_id"),
                    family=obs_data["family"],
                    outcome=ObservationOutcome(obs_data["outcome"]),
                    evaluation_count=obs_data.get("evaluation_count", 0),
                    hit_count=obs_data.get("hit_count", 0),
                    structural_elements=obs_data.get("structural_elements", []),
                    correctness_association_id=obs_data.get("correctness_association_id"),
                    property_fields=obs_data.get("property_fields", {}),
                    artifact_anchors=obs_data.get("artifact_anchors", []),
                    diagnostic_message=obs_data.get("diagnostic_message"),
                )
            )

        # Atomically save run and observations
        inserted = self.repo.save_evidence_run(run, observations)

        # Optional campaign enrollment
        enrolled = False
        if campaign_id:
            campaign = self.repo.get_campaign(plan_id, campaign_id)
            if campaign:
                target_rev = campaign_revision if campaign_revision is not None else campaign.campaign_revision
                self.execute_campaign_commands(
                    plan_id=plan_id,
                    campaign_id=campaign_id,
                    base_campaign_revision=target_rev,
                    request_id=f"enroll-{run_id}",
                    operations=[{"op": "run.include", "run_id": run_id}],
                )
                enrolled = True

        return {
            "run_id": run_id,
            "status": "committed" if inserted else "idempotent_duplicate",
            "campaign_enrolled": enrolled,
            "observations_count": len(observations),
        }

    # --- Matrix and Gaps ---
    def get_coverage_matrix(
        self,
        plan_id: str,
        checkpoint_id: str | None = None,
        campaign_id: str | None = None,
        filtered_intent_ids: set[str] | None = None,
        status_filter: str | None = None,
    ) -> dict[str, Any]:
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        campaign: EvidenceCampaign | None = None
        if campaign_id:
            campaign = self.repo.get_campaign(plan_id, campaign_id)
            if not checkpoint_id and campaign and campaign.coverage_checkpoint_id:
                checkpoint_id = campaign.coverage_checkpoint_id

        # 1. Load active intents, requirements, objectives and policies
        if checkpoint_id:
            cp = self.repo.get_checkpoint(plan_id, checkpoint_id)
            if not cp:
                raise RecordNotFoundError(plan_id, checkpoint_id)

            if cp.layer == "coverage":
                objectives = {
                    o["id"]: CoverageObjective.model_validate(o)
                    for o in cp.payload.get("objectives", [])
                    if not o.get("archived")
                }
                policies = {
                    p["intent_id"]: IntentEvidencePolicy.model_validate(p)
                    for p in cp.payload.get("policies", [])
                    if not p.get("archived")
                }
                upstream_id = cp.payload.get("upstream_checkpoint_id")
                upstream_cp = self.repo.get_checkpoint(plan_id, upstream_id) if upstream_id else None
                if upstream_cp:
                    intents = [Intent.model_validate(i) for i in upstream_cp.payload.get("intents", []) if not i.get("archived")]
                    requirements = [Requirement.model_validate(r) for r in upstream_cp.payload.get("requirements", []) if not r.get("archived")]
                else:
                    intents = []
                    requirements = []
            else:
                intents = [Intent.model_validate(i) for i in cp.payload.get("intents", []) if not i.get("archived")]
                requirements = [Requirement.model_validate(r) for r in cp.payload.get("requirements", []) if not r.get("archived")]
                raw_all = self.repo.get_records(plan_id, include_archived=False)
                objectives = {r["id"]: CoverageObjective.model_validate(r) for r in raw_all if r.get("record_type") == "objective"}
                policies = {r["intent_id"]: IntentEvidencePolicy.model_validate(r) for r in raw_all if r.get("record_type") == "policy"}
        else:
            raw_records = self.repo.get_records(plan_id, include_archived=False)
            intents = [Intent.model_validate(r) for r in raw_records if r.get("record_type") == "intent"]
            requirements = [Requirement.model_validate(r) for r in raw_records if r.get("record_type") == "requirement"]
            objectives = {r["id"]: CoverageObjective.model_validate(r) for r in raw_records if r.get("record_type") == "objective"}
            policies = {r["intent_id"]: IntentEvidencePolicy.model_validate(r) for r in raw_records if r.get("record_type") == "policy"}

        # 2. Load campaign profiles and runs
        profiles: dict[str, EvaluationProfile] = {}
        runs: dict[str, EvidenceRun] = {}
        observations_by_run: dict[str, list[EvidenceObservation]] = {}

        if campaign:
                for prof_id in campaign.required_profile_ids:
                    prof = self.repo.get_profile(plan_id, prof_id)
                    if prof:
                        profiles[prof.id] = prof

                for run_id in campaign.included_run_ids:
                    r = self.repo.get_run(plan_id, run_id)
                    if r:
                        runs[r.id] = r

                observations_by_run = self.repo.get_observations_for_runs(list(runs.keys()))
        else:
            # Load all profiles
            all_profs = self.repo.list_profiles(plan_id)
            profiles = {p.id: p for p in all_profs}

        return self.evaluator.compute_matrix(
            intents=intents,
            requirements=requirements,
            policies=policies,
            objectives=objectives,
            campaign=campaign,
            profiles=profiles,
            runs=runs,
            observations_by_run=observations_by_run,
            filtered_intent_ids=filtered_intent_ids,
            status_filter=status_filter,
        )

    def get_coverage_gaps(
        self,
        plan_id: str,
        checkpoint_id: str | None = None,
        campaign_id: str | None = None,
    ) -> list[CoverageGap]:
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        campaign = self.repo.get_campaign(plan_id, campaign_id) if campaign_id else None
        if not checkpoint_id and campaign and campaign.coverage_checkpoint_id:
            checkpoint_id = campaign.coverage_checkpoint_id

        if checkpoint_id:
            cp = self.repo.get_checkpoint(plan_id, checkpoint_id)
            if not cp:
                raise RecordNotFoundError(plan_id, checkpoint_id)
            if cp.layer == "coverage":
                objectives = {
                    o["id"]: CoverageObjective.model_validate(o)
                    for o in cp.payload.get("objectives", [])
                    if not o.get("archived")
                }
                policies = {
                    p["intent_id"]: IntentEvidencePolicy.model_validate(p)
                    for p in cp.payload.get("policies", [])
                    if not p.get("archived")
                }
                upstream_id = cp.payload.get("upstream_checkpoint_id")
                upstream_cp = self.repo.get_checkpoint(plan_id, upstream_id) if upstream_id else None
                if upstream_cp:
                    intents = [Intent.model_validate(i) for i in upstream_cp.payload.get("intents", []) if not i.get("archived")]
                    requirements = [Requirement.model_validate(r) for r in upstream_cp.payload.get("requirements", []) if not r.get("archived")]
                else:
                    intents = []
                    requirements = []
            else:
                intents = [Intent.model_validate(i) for i in cp.payload.get("intents", []) if not i.get("archived")]
                requirements = [Requirement.model_validate(r) for r in cp.payload.get("requirements", []) if not r.get("archived")]
                raw_all = self.repo.get_records(plan_id, include_archived=False)
                objectives = {r["id"]: CoverageObjective.model_validate(r) for r in raw_all if r.get("record_type") == "objective"}
                policies = {r["intent_id"]: IntentEvidencePolicy.model_validate(r) for r in raw_all if r.get("record_type") == "policy"}
        else:
            raw_records = self.repo.get_records(plan_id, include_archived=False)
            intents = [Intent.model_validate(r) for r in raw_records if r.get("record_type") == "intent"]
            requirements = [Requirement.model_validate(r) for r in raw_records if r.get("record_type") == "requirement"]
            objectives = {r["id"]: CoverageObjective.model_validate(r) for r in raw_records if r.get("record_type") == "objective"}
            policies = {r["intent_id"]: IntentEvidencePolicy.model_validate(r) for r in raw_records if r.get("record_type") == "policy"}

        campaign = self.repo.get_campaign(plan_id, campaign_id) if campaign_id else None
        profiles: dict[str, EvaluationProfile] = {}
        runs: dict[str, EvidenceRun] = {}
        observations_by_run: dict[str, list[EvidenceObservation]] = {}

        if campaign:
            for pid in campaign.required_profile_ids:
                p = self.repo.get_profile(plan_id, pid)
                if p:
                    profiles[p.id] = p
            for rid in campaign.included_run_ids:
                r = self.repo.get_run(plan_id, rid)
                if r:
                    runs[r.id] = r
            observations_by_run = self.repo.get_observations_for_runs(list(runs.keys()))

        return self.evaluator.compute_gaps(
            intents=intents,
            requirements=requirements,
            policies=policies,
            objectives=objectives,
            campaign=campaign,
            profiles=profiles,
            runs=runs,
            observations_by_run=observations_by_run,
        )

    # --- Evidence Reports ---
    def create_evidence_report(
        self,
        plan_id: str,
        coverage_checkpoint_id: str,
        campaign_id: str,
    ) -> EvidenceReport:
        matrix_data = self.get_coverage_matrix(
            plan_id=plan_id,
            checkpoint_id=coverage_checkpoint_id,
            campaign_id=campaign_id,
        )
        campaign = self.repo.get_campaign(plan_id, campaign_id)
        if not campaign:
            raise CampaignNotFoundError(campaign_id)

        b_sum = matrix_data["baseline_summary"]
        if b_sum["failed_intents"] > 0:
            status_label = "Incomplete evidence"
        elif b_sum["satisfied_intents"] == b_sum["total_intents"] and b_sum["total_intents"] > 0:
            status_label = "Complete evidence"
        elif (b_sum["satisfied_intents"] + b_sum["waived_intents"]) == b_sum["total_intents"] and b_sum["total_intents"] > 0:
            status_label = "Complete with waivers"
        else:
            status_label = "Incomplete evidence"

        report_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        report = EvidenceReport(
            id=report_id,
            plan_id=plan_id,
            coverage_checkpoint_id=coverage_checkpoint_id,
            campaign_id=campaign_id,
            campaign_revision=campaign.campaign_revision,
            evidence_sequence=len(campaign.included_run_ids),
            status=status_label,
            report_data=matrix_data,
            created_at=now_iso,
        )
        self.repo.save_evidence_report(report)
        return report

    def get_evidence_report(self, plan_id: str, report_id: str) -> EvidenceReport | None:
        return self.repo.get_evidence_report(plan_id, report_id)

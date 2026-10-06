"""Layer 2 Coverage, Profile, Campaign, Evidence Run, and Result Import endpoints."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from testplan_service.application.service import VerificationPlannerService
from testplan_service.domain.evidence import (
    EvaluationProfile,
    EvidenceCampaign,
    EvidenceReport,
    EvidenceRun,
)
from testplan_service.exceptions import (
    CampaignFrozenError,
    CampaignNotFoundError,
    CampaignRevisionConflictError,
    ImportValidationError,
    PlanNotFoundError,
    ProfileNotFoundError,
    RecordNotFoundError,
    RunNotFoundError,
)


class CreateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    display_name: str = Field(min_length=1)
    coverage_checkpoint_id: str = ""
    source_snapshot_id: str = ""
    source_snapshot_hash: str = ""
    dut_source_hash: str = ""
    root_occurrence_id: str = ""
    resolved_parameters: dict[str, Any] = Field(default_factory=dict)
    clock_reset_config: dict[str, Any] = Field(default_factory=dict)
    realization_descriptors: list[dict[str, Any]] = Field(default_factory=list)
    profile_id: str | None = None


class CreateCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1)
    coverage_checkpoint_id: str = ""
    required_profile_ids: list[str] = Field(min_length=1)
    purpose: str = "verification"
    campaign_id: str | None = None


class CampaignCommandBatchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    base_campaign_revision: int
    request_id: str = Field(min_length=1)
    operations: list[dict[str, Any]] = Field(min_length=1)


class CommitImportRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    expected_preview_digest: str | None = None
    campaign_id: str | None = None
    campaign_revision: int | None = None


class CreateEvidenceReportRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    coverage_checkpoint_id: str
    campaign_id: str


def create_coverage_router(get_service: Callable[[], VerificationPlannerService]) -> APIRouter:
    """Factory creating Layer 2 coverage and evidence routes."""
    router = APIRouter(tags=["Coverage & Evidence"])

    # --- Matrix, Gaps, Trace ---
    @router.get("/plans/{plan_id}/coverage/matrix")
    def get_coverage_matrix(
        plan_id: str,
        checkpoint: str | None = Query(None, alias="checkpoint"),
        checkpoint_id: str | None = Query(None, alias="checkpoint_id"),
        campaign: str | None = Query(None, alias="campaign"),
        campaign_id: str | None = Query(None, alias="campaign_id"),
        intent: str | None = Query(None, alias="intent"),
        status_filter: str | None = Query(None, alias="status"),
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Get computed coverage matrix and separate baseline and filtered summaries."""
        filtered_ids = {intent} if intent else None
        eff_campaign = campaign or campaign_id
        eff_checkpoint = checkpoint or checkpoint_id
        return service.get_coverage_matrix(
            plan_id=plan_id,
            checkpoint_id=eff_checkpoint,
            campaign_id=eff_campaign,
            filtered_intent_ids=filtered_ids,
            status_filter=status_filter,
        )

    @router.get("/plans/{plan_id}/coverage/gaps")
    def get_coverage_gaps(
        plan_id: str,
        checkpoint: str | None = Query(None, alias="checkpoint"),
        checkpoint_id: str | None = Query(None, alias="checkpoint_id"),
        campaign: str | None = Query(None, alias="campaign"),
        campaign_id: str | None = Query(None, alias="campaign_id"),
        service: VerificationPlannerService = Depends(get_service),
    ) -> list[dict[str, Any]]:
        """Get typed deterministic coverage gaps per Section 5."""
        eff_campaign = campaign or campaign_id
        eff_checkpoint = checkpoint or checkpoint_id
        gaps = service.get_coverage_gaps(
            plan_id=plan_id,
            checkpoint_id=eff_checkpoint,
            campaign_id=eff_campaign,
        )
        return [g.model_dump() for g in gaps]

    @router.get("/plans/{plan_id}/coverage/trace")
    def get_coverage_trace(
        plan_id: str,
        record_id: str = Query(...),
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Get bounded relationship trace graph/table."""
        # Simple bounded trace for UI inspection
        matrix = service.get_coverage_matrix(plan_id)
        return {
            "record_id": record_id,
            "relationships": [],
            "depth": 1,
        }

    # --- Profiles ---
    @router.post("/plans/{plan_id}/profiles", status_code=status.HTTP_201_CREATED, response_model=EvaluationProfile)
    def create_profile(
        plan_id: str,
        payload: CreateProfileRequest,
        service: VerificationPlannerService = Depends(get_service),
    ) -> Any:
        """Register an immutable evaluation profile."""
        return service.create_profile(
            plan_id=plan_id,
            display_name=payload.display_name,
            coverage_checkpoint_id=payload.coverage_checkpoint_id,
            source_snapshot_id=payload.source_snapshot_id,
            source_snapshot_hash=payload.source_snapshot_hash,
            dut_source_hash=payload.dut_source_hash,
            root_occurrence_id=payload.root_occurrence_id,
            resolved_parameters=payload.resolved_parameters,
            clock_reset_config=payload.clock_reset_config,
            realization_descriptors=payload.realization_descriptors,
            profile_id=payload.profile_id,
        )

    @router.get("/plans/{plan_id}/profiles")
    def list_profiles(
        plan_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> list[EvaluationProfile]:
        return service.list_profiles(plan_id)

    @router.get("/plans/{plan_id}/profiles/{profile_id}")
    def get_profile(
        plan_id: str,
        profile_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> EvaluationProfile:
        prof = service.get_profile(plan_id, profile_id)
        if not prof:
            raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found.")
        return prof

    # --- Campaigns ---
    @router.post("/plans/{plan_id}/campaigns", status_code=status.HTTP_201_CREATED, response_model=EvidenceCampaign)
    def create_campaign(
        plan_id: str,
        payload: CreateCampaignRequest,
        service: VerificationPlannerService = Depends(get_service),
    ) -> Any:
        """Create an evidence campaign with required profiles."""
        return service.create_campaign(
            plan_id=plan_id,
            title=payload.title,
            coverage_checkpoint_id=payload.coverage_checkpoint_id,
            required_profile_ids=payload.required_profile_ids,
            purpose=payload.purpose,
            campaign_id=payload.campaign_id,
        )

    @router.get("/plans/{plan_id}/campaigns")
    def list_campaigns(
        plan_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> list[EvidenceCampaign]:
        return service.list_campaigns(plan_id)

    @router.get("/plans/{plan_id}/campaigns/{campaign_id}")
    def get_campaign(
        plan_id: str,
        campaign_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> EvidenceCampaign:
        camp = service.get_campaign(plan_id, campaign_id)
        if not camp:
            raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found.")
        return camp

    @router.post("/plans/{plan_id}/campaigns/{campaign_id}/commands")
    def execute_campaign_commands(
        plan_id: str,
        campaign_id: str,
        payload: CampaignCommandBatchRequest,
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Apply revision-checked campaign operations."""
        return service.execute_campaign_commands(
            plan_id=plan_id,
            campaign_id=campaign_id,
            base_campaign_revision=payload.base_campaign_revision,
            request_id=payload.request_id,
            operations=payload.operations,
        )

    # --- Result Import & Reprocess ---
    @router.post("/plans/{plan_id}/result-imports", status_code=status.HTTP_201_CREATED)
    async def stage_result_import(
        plan_id: str,
        request: Request,
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Stage and validate a normalized verification results JSON payload."""
        payload = await request.json()
        return service.stage_result_import(plan_id, payload)

    @router.post("/plans/{plan_id}/result-imports/{import_id}/commit", status_code=status.HTTP_201_CREATED)
    def commit_result_import(
        plan_id: str,
        import_id: str,
        payload: CommitImportRequest,
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Commit staged results and optionally enroll in matching open campaign."""
        return service.commit_result_import(
            plan_id=plan_id,
            staging_id=import_id,
            expected_preview_digest=payload.expected_preview_digest,
            campaign_id=payload.campaign_id,
            campaign_revision=payload.campaign_revision,
        )

    @router.post("/plans/{plan_id}/result-imports/{import_id}/reprocess")
    def reprocess_result_import(
        plan_id: str,
        import_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Reprocess staged results using updated mappings."""
        return service.commit_result_import(plan_id=plan_id, staging_id=import_id)

    # --- Runs and Observations ---
    @router.get("/plans/{plan_id}/runs")
    def list_runs(
        plan_id: str,
        profile_id: str | None = Query(None),
        service: VerificationPlannerService = Depends(get_service),
    ) -> list[EvidenceRun]:
        return service.list_runs(plan_id, profile_id=profile_id)

    @router.get("/plans/{plan_id}/runs/{run_id}/observations")
    def get_run_observations(
        plan_id: str,
        run_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> list[dict[str, Any]]:
        obs = service.get_observations_for_run(run_id)
        return [o.model_dump() for o in obs]

    # --- Evidence Reports ---
    @router.post("/plans/{plan_id}/evidence-reports", status_code=status.HTTP_201_CREATED, response_model=EvidenceReport)
    def create_evidence_report(
        plan_id: str,
        payload: CreateEvidenceReportRequest,
        service: VerificationPlannerService = Depends(get_service),
    ) -> Any:
        return service.create_evidence_report(
            plan_id=plan_id,
            coverage_checkpoint_id=payload.coverage_checkpoint_id,
            campaign_id=payload.campaign_id,
        )

    @router.get("/plans/{plan_id}/evidence-reports/{report_id}")
    def get_evidence_report(
        plan_id: str,
        report_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> EvidenceReport:
        rep = service.get_evidence_report(plan_id, report_id)
        if not rep:
            raise HTTPException(status_code=404, detail=f"Evidence report '{report_id}' not found.")
        return rep

    return router

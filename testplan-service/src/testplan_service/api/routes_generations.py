"""Generation, artifact streaming, and producer manifest endpoints."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from testplan_service.application.service import VerificationPlannerService
from testplan_service.exceptions import (
    DomainValidationError,
    PlanNotFoundError,
    RecordNotFoundError,
)


class GenerationPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    checkpoint_id: str = Field(min_length=1)
    plugin_id: str | None = None
    plugin_version: str | None = None


class GenerationSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    checkpoint_id: str = Field(min_length=1)
    plugin_id: str | None = None
    plugin_version: str | None = None


def create_generations_router(get_service: Callable[[], VerificationPlannerService]) -> APIRouter:
    """Factory creating backend generation and artifact inspection endpoints."""
    router = APIRouter(tags=["Generations & Artifacts"])

    @router.post("/plans/{plan_id}/generations/preview")
    def preview_generation(
        plan_id: str,
        payload: GenerationPreviewRequest,
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Preview generation inputs, capabilities, and preflight diagnostics without modifying state."""
        try:
            return service.preview_generation(
                plan_id=plan_id,
                checkpoint_id=payload.checkpoint_id,
                plugin_id=payload.plugin_id,
                plugin_version=payload.plugin_version,
            )
        except (PlanNotFoundError, RecordNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except DomainValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/plans/{plan_id}/generations", status_code=status.HTTP_201_CREATED)
    def submit_generation(
        plan_id: str,
        payload: GenerationSubmitRequest,
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Submit an idempotent generation job against an immutable Implementation Checkpoint (I1)."""
        try:
            return service.run_generation(
                plan_id=plan_id,
                checkpoint_id=payload.checkpoint_id,
                plugin_id=payload.plugin_id,
                plugin_version=payload.plugin_version,
            )
        except (PlanNotFoundError, RecordNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except DomainValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.get("/plans/{plan_id}/generations")
    def list_generations(
        plan_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> list[dict[str, Any]]:
        """List all generation jobs for a plan."""
        return service.list_generation_jobs(plan_id)

    @router.get("/plans/{plan_id}/generations/{job_id}")
    def get_generation_job(
        plan_id: str,
        job_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Get status, diagnostics, and artifact handles for a specific generation job."""
        job = service.get_generation_job(plan_id, job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Generation job '{job_id}' not found.")
        return job

    @router.post("/plans/{plan_id}/generations/{job_id}/cancel")
    def cancel_generation(
        plan_id: str,
        job_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Cancel a running or queued generation job."""
        try:
            return service.cancel_generation(plan_id, job_id)
        except RecordNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @router.post("/plans/{plan_id}/generations/{job_id}/retry")
    def retry_generation(
        plan_id: str,
        job_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Retry generation from the identical saved immutable request."""
        try:
            return service.retry_generation(plan_id, job_id)
        except RecordNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @router.get("/plans/{plan_id}/artifacts/{artifact_id}")
    def get_artifact(
        plan_id: str,
        artifact_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> Response:
        """Stream or download a verified, immutable generated artifact."""
        artifact = service.get_generated_artifact(artifact_id)
        if not artifact:
            raise HTTPException(status_code=404, detail=f"Artifact '{artifact_id}' not found.")

        try:
            data = service.blob_store.get_bytes(artifact["blob_digest"])
        except FileNotFoundError:
            data = None
        if data is None:
            raise HTTPException(status_code=404, detail="Artifact content missing in storage.")

        filename = artifact["relative_path"].split("/")[-1]
        media_type = artifact.get("media_type", "text/plain")

        return Response(
            content=data,
            media_type=media_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "X-Artifact-Role": artifact["role"],
                "X-Artifact-Sha256": artifact["sha256"],
            },
        )

    @router.get("/plans/{plan_id}/producer-manifests/{digest}")
    def get_producer_manifest(
        plan_id: str,
        digest: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> Any:
        """Retrieve canonical verification.producer.v1 mapping authority manifest by digest."""
        manifest = service.get_producer_manifest(digest)
        if not manifest:
            raise HTTPException(
                status_code=404,
                detail=f"Producer manifest with digest '{digest}' not found.",
            )
        return manifest

    return router

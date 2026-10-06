"""Checkpoints and review baseline routes."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from testplan_service.application.service import VerificationPlannerService
from testplan_service.domain.models import PlanCheckpoint
from testplan_service.exceptions import CheckpointBlockerError, PlanNotFoundError

router = APIRouter()


class CreateCheckpointRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reviewer_label: str = Field(min_length=1)
    comment: str = Field(default="")
    expected_digest: str | None = None
    acknowledged_warnings: list[str] = Field(default_factory=list)
    layer: str = "plan"
    upstream_checkpoint_id: str | None = None


class PreviewCheckpointRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    layer: str = "plan"
    upstream_checkpoint_id: str | None = None


def create_checkpoints_router(get_service: Callable[[], VerificationPlannerService]) -> APIRouter:
    """Factory creating review checkpoint endpoints."""
    checkpoints_router = APIRouter(tags=["Checkpoints"])

    @checkpoints_router.post("/plans/{plan_id}/checkpoints/preview")
    def preview_checkpoint(
        plan_id: str,
        payload: PreviewCheckpointRequest = PreviewCheckpointRequest(),
        layer: str | None = None,
        upstream_checkpoint_id: str | None = None,
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Preview review checklist, blockers, warnings, and candidate content digest."""
        target_layer = layer or (payload.layer if payload else "plan")
        target_upstream = upstream_checkpoint_id or (payload.upstream_checkpoint_id if payload else None)
        try:
            return service.preview_checkpoint(
                plan_id=plan_id,
                layer=target_layer,
                upstream_checkpoint_id=target_upstream,
            )
        except PlanNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @checkpoints_router.post(
        "/plans/{plan_id}/checkpoints",
        status_code=status.HTTP_201_CREATED,
        response_model=PlanCheckpoint,
    )
    def create_checkpoint(
        plan_id: str,
        payload: CreateCheckpointRequest,
        service: VerificationPlannerService = Depends(get_service),
    ) -> Any:
        """Create an immutable Plan Checkpoint baseline (P1) or Coverage Checkpoint (C1)."""
        return service.create_checkpoint(
            plan_id=plan_id,
            reviewer_label=payload.reviewer_label,
            comment=payload.comment,
            expected_digest=payload.expected_digest,
            acknowledged_warnings=payload.acknowledged_warnings,
            layer=payload.layer,
            upstream_checkpoint_id=payload.upstream_checkpoint_id,
        )

    @checkpoints_router.get("/plans/{plan_id}/checkpoints")
    def list_checkpoints(
        plan_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> list[PlanCheckpoint]:
        """List all reviewed checkpoints for a plan."""
        return service.list_checkpoints(plan_id)

    @checkpoints_router.get("/plans/{plan_id}/checkpoints/{checkpoint_id}")
    def get_checkpoint(
        plan_id: str,
        checkpoint_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> PlanCheckpoint:
        """Get complete immutable snapshot data for a specific checkpoint."""
        cp = service.get_checkpoint(plan_id, checkpoint_id)
        if not cp:
            raise HTTPException(
                status_code=404,
                detail=f"Checkpoint '{checkpoint_id}' not found in plan '{plan_id}'.",
            )
        return cp

    @checkpoints_router.get("/plans/{plan_id}/checkpoints/{checkpoint_id}/source-sections")
    def get_checkpoint_source_sections(
        plan_id: str,
        checkpoint_id: str,
        service: VerificationPlannerService = Depends(get_service),
    ) -> list[dict[str, Any]]:
        """Get source sections as they existed when the checkpoint was reviewed."""
        cp = service.get_checkpoint(plan_id, checkpoint_id)
        if not cp:
            raise HTTPException(status_code=404, detail=f"Checkpoint '{checkpoint_id}' not found.")
        snapshot = service.get_snapshot_view(cp.snapshot_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail=f"Snapshot '{cp.snapshot_id}' not found.")
        results = []
        source_audit = cp.payload.get("source_audit", {})
        for s_sec in snapshot.source_sections:
            audit = source_audit.get(s_sec.section_id)
            results.append({
                "section_id": s_sec.section_id,
                "title": s_sec.title,
                "text": s_sec.text,
                "locator": s_sec.locator,
                "content_digest": s_sec.content_digest,
                "audit": audit,
            })
        return results

    return checkpoints_router

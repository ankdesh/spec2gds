"""REST API routes for plan management and read projections."""

from __future__ import annotations

from typing import Any, Callable
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from testplan_service.application.service import TestPlanService
from testplan_service.domain.models import PlanHeader
from testplan_service.exceptions import PlanNotFoundError, RecordNotFoundError

router = APIRouter()


class CreatePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    snapshot_id: str
    root_scope_id: str
    description: str = ""
    owner_label: str | None = None
    tags: list[str] = Field(default_factory=list)


def create_plans_router(get_service: Callable[[], TestPlanService]) -> APIRouter:
    """Factory creating the plans API router with injected TestPlanService."""
    plans_router = APIRouter(tags=["Plans"])

    @plans_router.post("/plans", status_code=status.HTTP_201_CREATED)
    def create_plan(
        payload: CreatePlanRequest,
        service: TestPlanService = Depends(get_service),
    ) -> PlanHeader:
        """Create a new plan bound to a validated snapshot root."""
        return service.create_plan(
            name=payload.name,
            snapshot_id=payload.snapshot_id,
            root_scope_id=payload.root_scope_id,
            description=payload.description,
            owner_label=payload.owner_label,
            tags=payload.tags,
        )

    @plans_router.get("/plans")
    def list_plans(
        service: TestPlanService = Depends(get_service),
    ) -> list[PlanHeader]:
        """List all plans in the library."""
        return service.list_plans()

    @plans_router.get("/plans/{plan_id}")
    def get_plan(
        plan_id: str,
        service: TestPlanService = Depends(get_service),
    ) -> dict[str, Any]:
        """Get plan header, revisions, active snapshot view, and checkpoints."""
        plan = service.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")

        snapshot = service.get_snapshot_view(plan.snapshot_id)
        checkpoints = service.list_checkpoints(plan_id)

        return {
            "plan": plan.model_dump(),
            "snapshot": snapshot.model_dump() if snapshot else None,
            "checkpoints": [cp.model_dump() for cp in checkpoints],
        }

    @plans_router.get("/plans/{plan_id}/records")
    def get_records(
        plan_id: str,
        record_type: str | None = Query(None, description="Filter by type (requirement, section, intent, issue)"),
        scope_id: str | None = Query(None, description="Filter by scope occurrence ID"),
        include_archived: bool = Query(False, description="Include soft-archived records"),
        service: TestPlanService = Depends(get_service),
    ) -> list[dict[str, Any]]:
        """Query canonical records with optional filtering."""
        return service.get_records(
            plan_id=plan_id,
            record_type=record_type,
            scope_id=scope_id,
            include_archived=include_archived,
        )

    @plans_router.get("/plans/{plan_id}/records/{record_id}")
    def get_record(
        plan_id: str,
        record_id: str,
        service: TestPlanService = Depends(get_service),
    ) -> dict[str, Any]:
        """Retrieve one canonical record by ID."""
        rec = service.get_record(plan_id, record_id)
        if not rec:
            raise HTTPException(status_code=404, detail=f"Record '{record_id}' not found in plan '{plan_id}'.")
        return rec

    @plans_router.get("/plans/{plan_id}/hierarchy")
    def get_hierarchy(
        plan_id: str,
        scope_id: str | None = Query(None, description="Filter by root scope"),
        service: TestPlanService = Depends(get_service),
    ) -> list[dict[str, Any]]:
        """Hierarchy tree read projection with descendant counts."""
        try:
            return service.get_hierarchy(plan_id, scope_id)
        except PlanNotFoundError:
            raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")

    @plans_router.get("/plans/{plan_id}/source-sections")
    def get_source_sections(
        plan_id: str,
        service: TestPlanService = Depends(get_service),
    ) -> list[dict[str, Any]]:
        """Source sections and their manual audit review dispositions."""
        plan = service.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")

        snapshot = service.get_snapshot_view(plan.snapshot_id)
        if not snapshot:
            return []

        results: list[dict[str, Any]] = []
        for s_sec in snapshot.source_sections:
            audit = plan.source_audit.get(s_sec.section_id)
            results.append({
                "section_id": s_sec.section_id,
                "title": s_sec.title,
                "text": s_sec.text,
                "locator": s_sec.locator,
                "content_digest": s_sec.content_digest,
                "audit": audit.model_dump() if audit else None,
            })
        return results

    @plans_router.get("/plans/{plan_id}/requirements")
    def get_requirements(
        plan_id: str,
        service: TestPlanService = Depends(get_service),
    ) -> list[dict[str, Any]]:
        """Captured requirements with linked intent counts."""
        records = service.get_records(plan_id, record_type="requirement", include_archived=False)
        intents = service.get_records(plan_id, record_type="intent", include_archived=False)

        req_intent_counts: dict[str, int] = {}
        for intent in intents:
            for r_id in intent.get("requirement_ids", []):
                req_intent_counts[r_id] = req_intent_counts.get(r_id, 0) + 1

        results: list[dict[str, Any]] = []
        for r in records:
            r_copy = dict(r)
            r_copy["linked_intent_count"] = req_intent_counts.get(r["id"], 0)
            results.append(r_copy)
        return results

    @plans_router.get("/plans/{plan_id}/intents")
    def get_intents(
        plan_id: str,
        scope_id: str | None = Query(None),
        service: TestPlanService = Depends(get_service),
    ) -> list[dict[str, Any]]:
        """Verification intents with Given/When/Then and authoring states."""
        return service.get_records(plan_id, record_type="intent", scope_id=scope_id, include_archived=False)

    @plans_router.get("/plans/{plan_id}/readiness")
    def get_readiness(
        plan_id: str,
        service: TestPlanService = Depends(get_service),
    ) -> dict[str, Any]:
        """Readiness checklist evaluation summary."""
        try:
            return service.preview_checkpoint(plan_id)
        except PlanNotFoundError:
            raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")

    @plans_router.get("/plans/{plan_id}/search")
    def search_plan(
        plan_id: str,
        q: str = Query(..., min_length=1),
        service: TestPlanService = Depends(get_service),
    ) -> list[dict[str, Any]]:
        """Search items across titles, keys, statements, and behavior."""
        return service.search_plan(plan_id, q)

    return plans_router

"""Export routes for .vplan bundle, Markdown reports, and CSV summaries."""

from __future__ import annotations

from typing import Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict

from spec2gds.agent_spec.spec_format.naming import filename_stem
from testplan_service.application.service import TestPlanService
from testplan_service.exceptions import PlanNotFoundError

router = APIRouter()


class ExportPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["bundle", "markdown", "csv"] = "bundle"


def create_exports_router(get_service: Callable[[], TestPlanService]) -> APIRouter:
    """Factory creating plan export endpoints."""
    exports_router = APIRouter(tags=["Exports"])

    @exports_router.post("/plans/{plan_id}/exports")
    def export_plan(
        plan_id: str,
        payload: ExportPlanRequest,
        service: TestPlanService = Depends(get_service),
    ) -> Response:
        """Export plan as portable .vplan bundle, Markdown document, or CSV table."""
        try:
            plan = service.get_plan(plan_id)
            stem = filename_stem(plan.name if plan else "Verification plan")
            if payload.format == "bundle":
                bundle_bytes = service.export_bundle(plan_id)
                return Response(
                    content=bundle_bytes,
                    media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{stem}.vplan"'},
                )
            elif payload.format == "markdown":
                md_text = service.export_markdown(plan_id)
                return Response(
                    content=md_text,
                    media_type="text/markdown",
                    headers={"Content-Disposition": f'attachment; filename="{stem}.md"'},
                )
            elif payload.format == "csv":
                csv_text = service.export_csv(plan_id)
                return Response(
                    content=csv_text,
                    media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{stem}.csv"'},
                )
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported export format: {payload.format}")
        except PlanNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    return exports_router

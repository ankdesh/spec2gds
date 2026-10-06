"""Source snapshot and bundle import endpoints."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict

from testplan_service.application.service import VerificationPlannerService
from testplan_service.constants import MAX_SOURCE_UPLOAD_BYTES
from testplan_service.exceptions import BundleError, SnapshotError

router = APIRouter()


class CommitBundleImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution: str = "create"  # "create" or "import_as_copy"


def create_imports_router(get_service: Callable[[], VerificationPlannerService]) -> APIRouter:
    """Factory creating snapshot upload and bundle import endpoints."""
    imports_router = APIRouter(tags=["Imports"])

    @imports_router.post("/source-imports", status_code=status.HTTP_201_CREATED)
    async def upload_source_snapshot(
        request: Request,
        file: UploadFile | None = File(None),
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Upload and decode an Activity Snapshot v1 container."""
        if file is not None:
            data = await file.read()
        else:
            data = await request.body()

        if not data:
            raise HTTPException(status_code=400, detail="Empty snapshot upload payload.")

        if len(data) > MAX_SOURCE_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Uploaded source exceeds maximum limit of {MAX_SOURCE_UPLOAD_BYTES} bytes.",
            )

        try:
            snapshot_id, view = service.import_source(data)
            return {
                "snapshot_id": snapshot_id,
                "source_document_id": view.source_document_id,
                "source_revision_hash": view.source_revision_hash,
                "root_ref": view.root_ref,
                "occurrences": [o.model_dump() for o in view.occurrences],
                "source_sections_count": len(view.source_sections),
                "preview": view.model_dump(),
            }
        except SnapshotError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    @imports_router.post("/bundle-imports", status_code=status.HTTP_201_CREATED)
    async def upload_bundle(
        request: Request,
        file: UploadFile | None = File(None),
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Upload, validate, and stage a portable .vplan bundle."""
        if file is not None:
            data = await file.read()
        else:
            data = await request.body()

        if not data:
            raise HTTPException(status_code=400, detail="Empty bundle payload.")

        staging_id = service.blob_store.stage_bytes(data)
        return {"staging_id": staging_id, "status": "staged"}

    @imports_router.post("/bundle-imports/{staging_id}/commit", status_code=status.HTTP_201_CREATED)
    def commit_bundle(
        staging_id: str,
        payload: CommitBundleImportRequest,
        service: VerificationPlannerService = Depends(get_service),
    ) -> dict[str, Any]:
        """Commit a staged bundle with conflict resolution ('create' or 'import_as_copy')."""
        staging_file = service.blob_store.staging_dir / f"{staging_id}.tmp"
        if not staging_file.is_file():
            raise HTTPException(status_code=404, detail=f"Staged bundle '{staging_id}' not found.")

        bundle_bytes = staging_file.read_bytes()
        try:
            plan_id = service.import_bundle(bundle_bytes, resolution=payload.resolution)
            staging_file.unlink(missing_ok=True)
            return {"plan_id": plan_id, "status": "committed"}
        except BundleError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return imports_router

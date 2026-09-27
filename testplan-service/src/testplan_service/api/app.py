"""FastAPI application factory and middleware configuration for Verification Planner."""

from __future__ import annotations

import logging
from pathlib import Path
import time
from typing import Any
import uuid

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from testplan_service.api.routes_checkpoints import create_checkpoints_router
from testplan_service.api.routes_commands import create_commands_router
from testplan_service.api.routes_coverage import create_coverage_router
from testplan_service.api.routes_events import create_events_router
from testplan_service.api.routes_exports import create_exports_router
from testplan_service.api.routes_generations import create_generations_router
from testplan_service.api.routes_imports import create_imports_router
from testplan_service.api.routes_meta import meta_router
from testplan_service.api.routes_plans import create_plans_router
from testplan_service.api.routes_plugins import create_plugins_router
from testplan_service.api.routes_recipes import create_recipes_router
from testplan_service.application.service import TestPlanService
from testplan_service.constants import (
    API_BASE_PATH,
    DEFAULT_PRODUCT_TITLE,
    DEFAULT_SERVICE_VERSION,
    DEFAULT_STORAGE_DIR,
    LEGACY_STORAGE_DIR,
)
from testplan_service.exceptions import (
    CampaignFrozenError,
    CampaignNotFoundError,
    CampaignRevisionConflictError,
    CheckpointBlockerError,
    DomainValidationError,
    IdempotencyMismatchError,
    ImportValidationError,
    PlanNotFoundError,
    PreconditionRequiredError,
    ProfileNotFoundError,
    RecordNotFoundError,
    RevisionConflictError,
    RunNotFoundError,
    SnapshotError,
    StorageError,
    VerificationPlannerError,
)

logger = logging.getLogger("testplan_service")


def create_app(
    storage_dir: Path | str | None = None,
    static_dir: Path | str | None = None,
) -> FastAPI:
    """Create and configure the production Verification Planner FastAPI service."""
    resolved_storage = Path(storage_dir or DEFAULT_STORAGE_DIR).resolve()
    resolved_storage.mkdir(parents=True, exist_ok=True)

    # Legacy storage notice
    legacy_path = Path(LEGACY_STORAGE_DIR)
    if legacy_path.is_dir() and any(legacy_path.iterdir()):
        logger.warning(
            "Legacy storage directory '%s' detected. Verification Planner uses independent SQLite "
            "storage at '%s'. Legacy files will not be converted or deleted.",
            legacy_path,
            resolved_storage,
        )

    service = TestPlanService(resolved_storage)

    app = FastAPI(
        title=DEFAULT_PRODUCT_TITLE,
        description="Hierarchical test planning, requirement tracing, and verification intent service.",
        version=DEFAULT_SERVICE_VERSION,
    )

    app.state.service = service

    # CORS support for browser application
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Correlation ID middleware
    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next: Any) -> Any:
        correlation_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.error(
                "Request %s %s failed in %.1f ms: %s",
                request.method,
                request.url.path,
                duration_ms,
                exc,
            )
            raise
        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = correlation_id
        return response

    # Exception Handlers
    @app.exception_handler(PlanNotFoundError)
    def handle_plan_not_found(_: Request, exc: PlanNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "PlanNotFound", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(RecordNotFoundError)
    def handle_record_not_found(_: Request, exc: RecordNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "RecordNotFound", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(RevisionConflictError)
    def handle_revision_conflict(_: Request, exc: RevisionConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": "revision_conflict",
                    "message": exc.message,
                    "request_id": exc.request_id,
                    "current_revision": exc.current_revision,
                    "diagnostics": exc.diagnostics,
                },
                "message": exc.message,
            },
        )

    @app.exception_handler(PreconditionRequiredError)
    def handle_precondition(_: Request, exc: PreconditionRequiredError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            content={"error": {"code": "precondition_required", "message": exc.message}, "message": exc.message},
        )

    @app.exception_handler(IdempotencyMismatchError)
    def handle_idempotency_mismatch(_: Request, exc: IdempotencyMismatchError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": {"code": "idempotency_mismatch", "message": exc.message}, "message": exc.message},
        )

    @app.exception_handler(DomainValidationError)
    def handle_domain_validation(_: Request, exc: DomainValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "domain_validation_failed",
                    "message": exc.message,
                    "diagnostics": exc.diagnostics,
                },
                "message": exc.message,
                "details": {"diagnostics": exc.diagnostics},
            },
        )

    @app.exception_handler(CheckpointBlockerError)
    def handle_checkpoint_blocker(_: Request, exc: CheckpointBlockerError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "checkpoint_blocked",
                    "message": exc.message,
                    "checklist": exc.checklist,
                    "blockers": exc.blockers,
                },
                "message": exc.message,
                "checklist": exc.checklist,
                "blockers": exc.blockers,
            },
        )

    @app.exception_handler(SnapshotError)
    def handle_snapshot_error(_: Request, exc: SnapshotError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "SnapshotError", "message": exc.message},
        )

    @app.exception_handler(CampaignRevisionConflictError)
    def handle_campaign_conflict(_: Request, exc: CampaignRevisionConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": "campaign_revision_conflict",
                    "message": exc.message,
                    "campaign_id": exc.campaign_id,
                    "base_revision": exc.base_revision,
                    "current_revision": exc.current_revision,
                },
                "message": exc.message,
            },
        )

    @app.exception_handler(CampaignFrozenError)
    def handle_campaign_frozen(_: Request, exc: CampaignFrozenError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": {"code": "campaign_frozen", "message": exc.message}, "message": exc.message},
        )

    @app.exception_handler(ImportValidationError)
    def handle_import_validation(_: Request, exc: ImportValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "import_validation_failed", "message": exc.message, "diagnostics": exc.diagnostics}, "message": exc.message},
        )

    @app.exception_handler(StorageError)
    def handle_storage_error(_: Request, exc: StorageError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "StorageError", "message": exc.message},
        )

    def get_service() -> TestPlanService:
        return app.state.service

    # Mount API routers at /api/verification/v1
    app.include_router(meta_router, prefix=API_BASE_PATH)
    app.include_router(create_plans_router(get_service), prefix=API_BASE_PATH)
    app.include_router(create_commands_router(get_service), prefix=API_BASE_PATH)
    app.include_router(create_checkpoints_router(get_service), prefix=API_BASE_PATH)
    app.include_router(create_coverage_router(get_service), prefix=API_BASE_PATH)
    app.include_router(create_imports_router(get_service), prefix=API_BASE_PATH)
    app.include_router(create_exports_router(get_service), prefix=API_BASE_PATH)
    app.include_router(create_events_router(get_service), prefix=API_BASE_PATH)
    app.include_router(create_plugins_router(), prefix=API_BASE_PATH)
    app.include_router(create_recipes_router(get_service), prefix=API_BASE_PATH)
    app.include_router(create_generations_router(get_service), prefix=API_BASE_PATH)

    # Also mount /health, /capabilities, /plugins, and /schemas at root for convenience
    app.include_router(meta_router, prefix="")
    app.include_router(create_plugins_router(), prefix="")

    # Static UI directory resolution
    resolved_static = (
        Path(static_dir).resolve()
        if static_dir
        else Path(__file__).resolve().parents[1] / "ui" / "static"
    )

    if resolved_static.is_dir():
        app.mount("/static", StaticFiles(directory=str(resolved_static)), name="static")

        @app.get("/", include_in_schema=False)
        @app.get("/ui", include_in_schema=False)
        def index_page() -> FileResponse:
            index_file = resolved_static / "index.html"
            return FileResponse(str(index_file))

    return app

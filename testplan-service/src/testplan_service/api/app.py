"""FastAPI application factory and middleware configuration for Testplan Service."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from testplan_service.api.routes_assistant import create_assistant_router
from testplan_service.api.routes_export import create_export_router
from testplan_service.api.routes_nodes import create_nodes_router
from testplan_service.api.routes_testplans import create_testplans_router
from testplan_service.constants import API_V1_PREFIX, DEFAULT_SERVICE_NAME, DEFAULT_SERVICE_VERSION
from testplan_service.exceptions import (
    CycleDetectedError,
    DuplicateNodeError,
    InvalidOperationError,
    MaxDepthExceededError,
    NodeNotFoundError,
    ProposalValidationError,
    StorageError,
    TestPlanAlreadyExistsError,
    TestPlanNotFoundError,
)
from testplan_service.logging import StructuredLogger
from testplan_service.service.export_service import ExportService
from testplan_service.service.manager import TestPlanManager
from testplan_service.service.proposal_handler import ProposalHandler
from testplan_service.storage.interface import TestPlanRepository
from testplan_service.storage.memory_repository import MemoryTestPlanRepository


def create_app(
    repository: TestPlanRepository | None = None,
    logger: StructuredLogger | None = None,
    static_dir: Path | str | None = None,
) -> FastAPI:
    """Create and configure a production-ready Testplan Service FastAPI app."""
    repo = repository or MemoryTestPlanRepository()
    log = logger or StructuredLogger(DEFAULT_SERVICE_NAME)

    manager = TestPlanManager(repo, log)
    proposal_handler = ProposalHandler(manager, log)
    export_service = ExportService()

    app = FastAPI(
        title="Testplan Management Service",
        description="Hierarchical testplan management and verification planning service.",
        version=DEFAULT_SERVICE_VERSION,
    )

    # Attach shared instances to app state
    app.state.manager = manager
    app.state.proposal_handler = proposal_handler
    app.state.export_service = export_service
    app.state.logger = log

    # CORS support for browser UI and external tools
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Logging and correlation ID middleware
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next: Any) -> Any:
        correlation_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - started) * 1000
            log.event(
                "http",
                "request_failed",
                f"{request.method} {request.url.path} failed: {exc}",
                severity="error",
                correlation_id=correlation_id,
                duration_ms=duration_ms,
                exception=exc,
            )
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = correlation_id
        if not request.url.path.startswith("/static"):
            log.event(
                "http",
                "request_completed",
                f"{request.method} {request.url.path} returned {response.status_code}",
                severity="error" if response.status_code >= 500 else "info",
                correlation_id=correlation_id,
                duration_ms=duration_ms,
                status=response.status_code,
            )
        return response

    # Exception Handlers
    @app.exception_handler(TestPlanNotFoundError)
    def handle_not_found(_: Request, exc: TestPlanNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "TestPlanNotFound", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(NodeNotFoundError)
    def handle_node_not_found(_: Request, exc: NodeNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "NodeNotFound", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(TestPlanAlreadyExistsError)
    def handle_already_exists(_: Request, exc: TestPlanAlreadyExistsError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "TestPlanAlreadyExists", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(DuplicateNodeError)
    def handle_duplicate_node(_: Request, exc: DuplicateNodeError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "DuplicateNode", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(CycleDetectedError)
    def handle_cycle(_: Request, exc: CycleDetectedError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "CycleDetected", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(MaxDepthExceededError)
    def handle_max_depth(_: Request, exc: MaxDepthExceededError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "MaxDepthExceeded", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(ProposalValidationError)
    def handle_proposal_validation(_: Request, exc: ProposalValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "ProposalValidationFailed", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(InvalidOperationError)
    def handle_invalid_operation(_: Request, exc: InvalidOperationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "InvalidOperation", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(StorageError)
    def handle_storage_error(_: Request, exc: StorageError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "StorageError", "message": exc.message, "details": exc.details},
        )

    # Dependency providers
    def get_manager() -> TestPlanManager:
        return app.state.manager

    def get_proposal_handler() -> ProposalHandler:
        return app.state.proposal_handler

    def get_export_service() -> ExportService:
        return app.state.export_service

    # Mount API routers
    app.include_router(create_testplans_router(get_manager), prefix=API_V1_PREFIX)
    app.include_router(create_nodes_router(get_manager), prefix=API_V1_PREFIX)
    app.include_router(create_export_router(get_manager, get_export_service), prefix=API_V1_PREFIX)
    app.include_router(
        create_assistant_router(get_manager, get_proposal_handler, get_export_service),
        prefix="",
    )

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

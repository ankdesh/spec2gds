from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import httpx

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
    create_rest_routes,
)
from a2a.server.tasks import DatabaseTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .a2a_agent import (
    CircuitEditingAgentExecutor,
    CombinedEditingAgentExecutor,
    SpecEditingAgentExecutor,
)
from .agents.circuit_editor import CircuitEditingAgent
from .agents.spec_editor import SpecEditingAgent
from .api import create_api_router, create_bound_spec_thread
from .circuit_client import CircuitDesignerClient, CircuitServiceError
from .config import Settings
from .database import AssistantDatabase
from .spec_client import SpecEditorClient, SpecServiceError


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    database = AssistantDatabase(settings.database_path)
    circuit_client = CircuitDesignerClient(
        settings.circuit_request_timeout_seconds,
        settings.circuit_service_allowlist,
    )
    spec_client = SpecEditorClient(
        settings.spec_request_timeout_seconds,
        settings.spec_service_allowlist,
    )

    task_engine = _task_engine(settings.database_path)
    task_store = DatabaseTaskStore(task_engine)
    agent_card = _agent_card(settings)
    request_handler = DefaultRequestHandler(
        agent_executor=CombinedEditingAgentExecutor(
            CircuitEditingAgentExecutor(CircuitEditingAgent(settings)),
            SpecEditingAgentExecutor(SpecEditingAgent(settings)),
        ),
        task_store=task_store,
        agent_card=agent_card,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        database.initialize()
        await task_store.initialize()
        yield
        await task_engine.dispose()

    app = FastAPI(
        title="spec2gds AI Assistant",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.a2a_task_store = task_store
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:4201",
            "http://localhost:4201",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # The A2A SDK installs a dynamic ``/{tenant}`` mount. Register Vite's
    # asset prefix first so requests such as ``/assets/index-*.js`` are not
    # interpreted as tenant-scoped A2A requests.
    web_assets_path = settings.web_dist_path / "assets"
    if web_assets_path.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=web_assets_path),
            name="web-assets",
        )

    app.include_router(
        create_api_router(
            database=database,
            circuit_client=circuit_client,
            spec_client=spec_client,
        )
    )

    @app.get("/api/services", include_in_schema=False)
    async def service_directory():
        """Return configured endpoints plus a quick liveness probe."""
        async def probe(url: str) -> tuple[bool, str]:
            try:
                async with httpx.AsyncClient(timeout=1.5) as client:
                    response = await client.get(url)
                return response.is_success, (
                    "Available" if response.is_success else f"HTTP {response.status_code}"
                )
            except httpx.HTTPError as reason:
                return False, str(reason)

        spec_status, circuit_status = await asyncio.gather(
            probe(f"{settings.spec_editor_service_url}/health"),
            probe(f"{settings.circuit_designer_service_url}/health"),
        )
        return {
            "schema_version": 1,
            "services": {
                "spec_editor": {
                    "service_url": settings.spec_editor_service_url,
                    "ui_url": settings.spec_editor_ui_url,
                    "available": spec_status[0],
                    "detail": spec_status[1],
                },
                "circuit_designer": {
                    "service_url": settings.circuit_designer_service_url,
                    "ui_url": settings.circuit_designer_ui_url,
                    "available": circuit_status[0],
                    "detail": circuit_status[1],
                },
                "ai_assistant": {
                    "service_url": settings.ai_assistant_service_url,
                    "ui_url": settings.ai_assistant_ui_url,
                    "available": True,
                    "detail": "Available",
                },
            },
        }

    @app.get("/launch/spec", include_in_schema=False)
    async def launch_spec(
        service_base_url: str,
        document_id: str,
        entity_kind: str,
        entity_id: str,
    ):
        """Intentionally create a fresh entity-bound chat for every editor click."""
        from fastapi import HTTPException
        from fastapi.responses import RedirectResponse

        try:
            thread = await create_bound_spec_thread(
                database,
                spec_client,
                base_url=service_base_url,
                document_id=document_id,
                entity_kind=entity_kind,
                entity_id=entity_id,
            )
        except ValueError as reason:
            raise HTTPException(status_code=400, detail=str(reason)) from reason
        except SpecServiceError as reason:
            raise HTTPException(status_code=reason.status_code, detail=reason.detail) from reason
        return RedirectResponse(url=f"/?thread={thread['id']}", status_code=303)

    @app.get("/launch/circuit", include_in_schema=False)
    async def launch_circuit(service_base_url: str, document_id: str):
        """Create a fresh Circuit chat after validating the requested document."""
        from fastapi import HTTPException
        from fastapi.responses import RedirectResponse

        try:
            base_url = circuit_client.normalize(service_base_url)
            await circuit_client.snapshot(base_url, document_id)
            thread = database.create_thread(
                title=f"Circuit: {document_id}", domain="circuit"
            )
            bound = database.bind_circuit(
                thread["id"], base_url=base_url, document_id=document_id
            )
            assert bound is not None
        except ValueError as reason:
            raise HTTPException(status_code=400, detail=str(reason)) from reason
        except CircuitServiceError as reason:
            raise HTTPException(
                status_code=reason.status_code, detail=reason.detail
            ) from reason
        return RedirectResponse(url=f"/?thread={bound['id']}", status_code=303)

    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(agent_card),
        jsonrpc_routes=create_jsonrpc_routes(
            request_handler, rpc_url="/a2a/jsonrpc"
        ),
        rest_routes=create_rest_routes(
            request_handler, path_prefix="/a2a"
        ),
    )

    if settings.web_dist_path.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=settings.web_dist_path, html=True),
            name="web",
        )
    return app


def _task_engine(database_path: Path) -> AsyncEngine:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(f"sqlite+aiosqlite:///{database_path}")


def _agent_card(settings: Settings) -> AgentCard:
    base = f"http://{settings.host}:{settings.port}"
    return AgentCard(
        name="spec2gds AI Assistant",
        description=(
            "Explores Spec entities and creates reviewable change proposals for "
            "Circuit Designer and Spec Editor."
        ),
        version="0.1.0",
        supported_interfaces=[
            AgentInterface(
                url=f"{base}/a2a",
                protocol_binding="HTTP+JSON",
                protocol_version="1.0",
            ),
            AgentInterface(
                url=f"{base}/a2a/jsonrpc",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            ),
        ],
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=[
            "text/plain",
            "application/json",
            "image/svg+xml",
            "image/png",
        ],
        default_output_modes=[
            "text/plain",
            "application/vnd.spec2gds.circuit-proposal+json",
            "application/vnd.spec2gds.spec-proposal+json",
        ],
        skills=[
            AgentSkill(
                id="propose_circuit_changes",
                name="Propose circuit instance and connectivity changes",
                description=(
                    "Translate a high-level request into reviewable Circuit "
                    "Designer instance and net operations."
                ),
                tags=["circuit", "instances", "nets", "review"],
                examples=[
                    (
                        "Add five instances of block_a in parallel and fan out "
                        "the output of source_b to them."
                    )
                ],
                input_modes=[
                    "text/plain",
                    "application/json",
                    "image/svg+xml",
                    "image/png",
                ],
                output_modes=[
                    "application/vnd.spec2gds.circuit-proposal+json"
                ],
            ),
            AgentSkill(
                id="explore_and_propose_spec_changes",
                name="Explore and propose specification changes",
                description=(
                    "Discuss one selected Spec entity and optionally prepare a "
                    "typed, reviewable source change proposal."
                ),
                tags=["spec", "ip-xact", "narrative", "review"],
                examples=[
                    "Explore adding a streaming interface, then prepare a proposal."
                ],
                input_modes=["text/plain", "application/json"],
                output_modes=[
                    "text/plain",
                    "application/vnd.spec2gds.spec-proposal+json",
                ],
            ),
        ],
    )

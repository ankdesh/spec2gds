"""Local single-user FastAPI app for agent-spec v1."""

import typing

import pydantic

import spec2gds.agent_spec.actions as agent_actions
import spec2gds.agent_spec.models as agent_models
import spec2gds.agent_spec.storage.repository as agent_repository
import spec2gds.agent_spec.runs.runner as agent_runner


class OpenDocumentRequest(pydantic.BaseModel):
    """Request body for opening a document in the action/run API."""

    path: str
    sidecar_root: str | None = None
    user_identity: str = "local"
    config_path: str | None = None


class TagUpdateRequest(pydantic.BaseModel):
    """Request body for replacing a block's action-discovery tags."""

    tags: list[str]


class RunActionRequest(pydantic.BaseModel):
    """Request body for triggering an action run."""

    parameters: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


class ServerSession:
    """Single active local document session."""

    repository: agent_repository.AgentSpecRepository
    registry: agent_actions.ActionRegistry
    runner: agent_runner.AgentSpecRunner

    def __init__(self, request: OpenDocumentRequest) -> None:
        self.repository = agent_repository.AgentSpecRepository(
            request.path,
            sidecar_root=request.sidecar_root,
            user_identity=request.user_identity,
        )
        self.registry = agent_actions.create_default_registry(request.config_path)
        self.runner = agent_runner.AgentSpecRunner(self.repository, self.registry)


def _document_state(session: ServerSession) -> dict[str, typing.Any]:
    """Return the API's compact view of graph state for the open document."""
    return {
        "document_id": session.repository.manifest.document_id,
        "blocks": [
            block.model_dump(mode="json")
            for block in session.repository.graph.blocks.values()
        ],
        "artifact_refs": {
            artifact_id: artifact.model_dump(mode="json")
            for artifact_id, artifact in session.repository.graph.artifact_refs.items()
        },
        "attachments": {
            block_id: [attachment.model_dump(mode="json") for attachment in attachments]
            for block_id, attachments in session.repository.graph.attachments.items()
        },
    }


def create_app() -> typing.Any:
    """Create the single-user FastAPI app for graph/actions/runs."""
    try:
        import fastapi
    except Exception as exc:
        raise RuntimeError("FastAPI is required for the agent-spec local server.") from exc

    app = fastapi.FastAPI(title="spec2gds Agent-Spec API")
    state: dict[str, ServerSession] = {}

    def active_session() -> ServerSession:
        """Return the current in-memory session or raise an HTTP error."""
        session = state.get("session")
        if session is None:
            raise fastapi.HTTPException(status_code=400, detail="No agent-spec document is open.")
        return session

    @app.get("/health")
    def health() -> dict[str, str]:
        """Simple process health probe."""
        return {"status": "ok"}

    @app.post("/documents/open")
    def open_document(request: OpenDocumentRequest) -> dict[str, typing.Any]:
        """Open a `.spec` document, project its graph, and save metadata."""
        session = ServerSession(request)
        session.repository.project_graph()
        session.repository.save()
        state["session"] = session
        return _document_state(session)

    @app.get("/blocks")
    def blocks() -> dict[str, typing.Any]:
        """Return the latest projected block graph for the active document."""
        session = active_session()
        session.repository.project_graph()
        return _document_state(session)

    @app.post("/blocks/{block_id}/tags")
    def set_tags(block_id: str, request: TagUpdateRequest) -> dict[str, typing.Any]:
        """Replace tags on a block and persist the document metadata."""
        session = active_session()
        try:
            session.repository.set_block_tags(block_id, request.tags)
            session.repository.save()
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc
        return session.repository.graph.blocks[block_id].model_dump(mode="json")

    @app.get("/blocks/{block_id}/actions")
    def block_actions(block_id: str) -> dict[str, typing.Any]:
        """Return actions available for a block's current tags."""
        session = active_session()
        try:
            actions = session.runner.available_actions(block_id)
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        return {"actions": [action.model_dump(mode="json") for action in actions]}

    @app.post("/blocks/{block_id}/actions/{action_id}/runs")
    def run_action(
        block_id: str,
        action_id: str,
        request: RunActionRequest,
    ) -> dict[str, typing.Any]:
        """Trigger an action run for a block and return the run record."""
        session = active_session()
        try:
            run_record = session.runner.trigger_action(action_id, block_id, request.parameters)
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc
        return run_record.model_dump(mode="json")

    @app.get("/events")
    def events() -> dict[str, typing.Any]:
        """Return events emitted during this in-memory server session."""
        session = active_session()
        return {"events": [event.model_dump(mode="json") for event in session.runner.events]}

    return app

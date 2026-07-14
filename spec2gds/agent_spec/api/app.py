"""Local single-user API for action discovery, execution, and reports."""

import json
import pathlib
import typing

import pydantic

import spec2gds.agent_spec.actions as agent_actions
import spec2gds.agent_spec.models as agent_models
import spec2gds.agent_spec.query as agent_query
import spec2gds.agent_spec.runs.runner as agent_runner
import spec2gds.agent_spec.storage.repository as agent_repository


class OpenDocumentRequest(pydantic.BaseModel):
    path: str
    sidecar_root: str | None = None
    user_identity: str = "local"
    config_path: str | None = None


class ActionInputsRequest(pydantic.BaseModel):
    inputs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


class ExecutorCompletionRequest(pydantic.BaseModel):
    outcome: str
    artifacts: list[agent_models.ArtifactRef] = pydantic.Field(default_factory=list)
    report: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


class ServerSession:
    def __init__(self, request: OpenDocumentRequest) -> None:
        self.repository = agent_repository.AgentSpecRepository(request.path, request.sidecar_root, request.user_identity)
        self.registry = agent_actions.create_default_registry(request.config_path)
        self.runner = agent_runner.AgentSpecRunner(self.repository, self.registry)


def create_app() -> typing.Any:
    try:
        import fastapi
    except Exception as exc:
        raise RuntimeError("FastAPI is required for the agent-spec local server.") from exc

    app = fastapi.FastAPI(title="spec2gds Agent-Spec Action API")
    state: dict[str, typing.Any] = {"active": None, "sessions": {}, "run_sessions": {}}

    def session_key(path: str) -> str:
        return str(pathlib.Path(path).expanduser().resolve())

    def index_runs(session: ServerSession) -> None:
        for path in session.repository.container.custom_files:
            prefix = "spec_data/agent-spec/runs/"
            if path.startswith(prefix) and path.endswith("/run.json"):
                run_id = pathlib.PurePosixPath(path).parent.name
                state["run_sessions"][run_id] = session

    def session_for_run(run_id: str) -> ServerSession:
        session = state["run_sessions"].get(run_id)
        if session is not None:
            return typing.cast(ServerSession, session)
        for candidate in state["sessions"].values():
            if f"spec_data/agent-spec/runs/{run_id}/run.json" in candidate.repository.container.custom_files:
                state["run_sessions"][run_id] = candidate
                return typing.cast(ServerSession, candidate)
        raise KeyError(f"Unknown run: {run_id}")

    def active_session() -> ServerSession:
        session = state.get("active")
        if session is None:
            raise fastapi.HTTPException(status_code=400, detail="No agent-spec document is open.")
        return session

    def query() -> agent_query.AgentSpecQueryService:
        return agent_query.AgentSpecQueryService(str(active_session().repository.document_path))

    def envelope(value: agent_query.ActionEnvelope) -> dict[str, typing.Any]:
        return value.model_dump(mode="json")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/documents/open")
    def open_document(request: OpenDocumentRequest) -> dict[str, typing.Any]:
        key = session_key(request.path)
        session = state["sessions"].get(key)
        if session is None:
            session = ServerSession(request)
            state["sessions"][key] = session
        session.repository.project_graph()
        session.repository.save()
        index_runs(session)
        state["active"] = session
        return {
            "document_id": session.repository.manifest.document_id,
            "blocks": [block.model_dump(mode="json") for block in session.repository.graph.blocks.values()],
            "artifact_refs": {key: item.model_dump(mode="json") for key, item in session.repository.graph.artifact_refs.items()},
            "attachments": {key: [item.model_dump(mode="json") for item in value] for key, value in session.repository.graph.attachments.items()},
        }

    @app.get("/actions")
    def actions() -> dict[str, typing.Any]:
        return {"actions": [item.model_dump(mode="json") for item in active_session().registry.list_actions()]}

    @app.get("/document")
    def document() -> dict[str, typing.Any]:
        return envelope(query().document_summary())

    @app.get("/blocks")
    def blocks() -> dict[str, typing.Any]:
        return envelope(query().blocks())

    @app.get("/blocks/{block_id}")
    def block(block_id: str) -> dict[str, typing.Any]:
        try:
            return envelope(query().block(block_id))
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/blocks/{block_id}/context")
    def block_context(block_id: str, version_id: str | None = None) -> dict[str, typing.Any]:
        try:
            return envelope(query().block_context(block_id, version_id))
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/blocks/{block_id}/actions/{action_id}/preconditions")
    def preconditions(block_id: str, action_id: str, request: ActionInputsRequest) -> dict[str, typing.Any]:
        try:
            return active_session().runner.check_preconditions(action_id, block_id, request.inputs).model_dump(mode="json")
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/blocks/{block_id}/actions/{action_id}/runs")
    def launch(block_id: str, action_id: str, request: ActionInputsRequest) -> dict[str, typing.Any]:
        try:
            launch_result = active_session().runner.launch_action(action_id, block_id, request.inputs)
            state["run_sessions"][launch_result.run.run_id] = active_session()
            return launch_result.model_dump(mode="json")
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/runs")
    def runs() -> dict[str, typing.Any]:
        items: list[dict[str, typing.Any]] = []
        for session in state["sessions"].values():
            index_runs(session)
            prefix = "spec_data/agent-spec/runs/"
            for path, raw in session.repository.container.custom_files.items():
                if not path.startswith(prefix) or not path.endswith("/run.json"):
                    continue
                run = json.loads(raw.decode("utf-8"))
                run_id = run["run_id"]
                report_path = f"{prefix}{run_id}/report.json"
                report = (
                    json.loads(session.repository.container.extract_file(report_path).decode("utf-8"))
                    if report_path in session.repository.container.custom_files
                    else None
                )
                items.append(
                    {
                        "document_id": session.repository.manifest.document_id,
                        "document_path": str(session.repository.document_path),
                        "run": run,
                        "report": report,
                    }
                )
        items.sort(key=lambda item: (item["run"].get("started_at", ""), item["run"]["run_id"]), reverse=True)
        return {"schema_version": agent_query.ACTION_SCHEMA_VERSION, "runs": items}

    @app.get("/runs/{run_id}")
    def run(run_id: str) -> dict[str, typing.Any]:
        try:
            session = session_for_run(run_id)
            return envelope(agent_query.AgentSpecQueryService(str(session.repository.document_path)).run(run_id))
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/runs/{run_id}/completion")
    def completion(run_id: str, request: ExecutorCompletionRequest) -> dict[str, typing.Any]:
        try:
            return session_for_run(run_id).runner.complete_action(run_id, request.outcome, request.artifacts, request.report).model_dump(mode="json")
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/ipxact")
    def ipxact() -> dict[str, typing.Any]:
        return envelope(query().ipxact_components())

    @app.get("/ipxact/raw")
    def raw_ipxact(file_path: str) -> typing.Any:
        try:
            data, media_type = query().raw_ipxact(file_path)
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        return fastapi.Response(content=data, media_type=media_type)

    @app.get("/artifacts")
    def artifacts() -> dict[str, typing.Any]:
        return envelope(query().artifacts())

    @app.get("/links")
    def links() -> dict[str, typing.Any]:
        return envelope(query().links())

    return app

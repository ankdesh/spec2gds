"""Production V1 local API and browser editor for deterministic ``.spec`` files.

The module is deliberately the only HTTP composition root.  It translates
JSON requests into immutable SpecIR reads, validated source transactions, and
activity-store operations; the browser never receives mutable package objects.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import json
import os
import time
import typing
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import pydantic
from spec2gds_runtime import StructuredLogger

from spec2gds.agent_spec.spec_format.actions import (
    ActionService,
    ActivityStore,
    ArtifactSidecar,
    AssistantChangeDecision,
    create_reference_registry,
)
from spec2gds.agent_spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.agent_spec.spec_format.assistant import (
    SpecChangeProposal,
    build_assistant_context,
    build_document_assistant_context,
    preview_assistant_proposal,
)
from spec2gds.agent_spec.spec_format.circuit_adapter import (
    CircuitAdapterError,
    CircuitDesignerConnectionError,
    project_source_to_circuit,
    publish_circuit_document,
)
from spec2gds.agent_spec.spec_format.document import build_a2ui_batch, build_document_projection
from spec2gds.agent_spec.spec_format.ir import (
    ConnectionIR,
    InstanceIR,
    InterfaceEndpointIR,
    PortEndpointIR,
    SpecRevision,
)
from spec2gds.agent_spec.spec_format.models import EntityRef, NarrativeBlock
from spec2gds.agent_spec.spec_format.transactions import (
    AddAsset,
    AddComponentPort,
    AddEntryDesign,
    ClearInternalDesign,
    CreateEntity,
    DeleteConnection,
    DeleteDocument,
    DeleteInstance,
    DeleteNarrativeBlock,
    RemoveAsset,
    RemoveEntryDesign,
    ReorderConnections,
    ReorderInstances,
    ReorderNarrativeBlocks,
    SetDocumentTitle,
    SetEntityMetadata,
    SetInternalDesign,
    SetNarrativeEntityLinks,
    SpecEditTransaction,
    StructuredPortInput,
    TransactionalPortInput,
    UpdateComponentPort,
    UpsertConnection,
    UpsertDocumentXml,
    UpsertInstance,
    UpsertNarrativeBlock,
    WirePortInput,
)
from spec2gds.service_registry import load_service_registry


class OpenDocumentRequest(pydantic.BaseModel):
    """Select one existing V1 package and its optional artifact sidecar."""

    path: str
    sidecar_root: str | None = None


class CreateDocumentRequest(pydantic.BaseModel):
    """Create and activate an empty deterministic V1 package."""

    path: str
    title: str | None = None
    document_id: str | None = None
    sidecar_root: str | None = None


class TransactionRequest(pydantic.BaseModel):
    """Optimistic source edit request expressed in the public operation vocabulary."""

    expected_source_revision_hash: str
    operations: list[dict[str, typing.Any]]


class ActionInputRequest(pydantic.BaseModel):
    """Normalized action inputs and optional immutable input artifacts."""

    inputs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    input_artifact_ids: list[str] = pydantic.Field(default_factory=list)


class ProposalRequest(pydantic.BaseModel):
    """Revision guard used while previewing or accepting a proposal."""

    expected_source_revision_hash: str


class AssetRequest(pydantic.BaseModel):
    """Base64-encoded source asset plus optimistic revision guard."""

    expected_source_revision_hash: str
    asset_id: str
    data_base64: str
    media_type: str
    extension: str


class CircuitLaunchRequest(pydantic.BaseModel):
    """Select one source component or design to project into Circuit Designer."""

    entity_kind: typing.Literal["component", "design"]
    entity_id: str


class AssistantLaunchRequest(pydantic.BaseModel):
    """Launch a fresh AI Assistant chat for one existing source entity."""

    entity_kind: typing.Literal[
        "component",
        "design",
        "bus_definition",
        "abstraction_definition",
        "narrative_block",
    ]
    entity_id: str


class V1Session:
    """One local document session that keeps source and activity concerns separate."""

    def __init__(self, path: str, sidecar_root: str | None = None) -> None:
        """Load and validate source before exposing the session to any route."""
        self.path = str(Path(path).expanduser().resolve())
        self.package = SpecPackage.load(self.path)
        self.revision = SpecRevision.from_package(self.package)
        self.sidecar = ArtifactSidecar(sidecar_root or f"{self.path}.artifacts")
        self.activity = ActivityStore(self.package, self.sidecar)
        self.actions = ActionService(create_reference_registry(), self.sidecar)

    @classmethod
    def create(
        cls,
        path: str,
        document_id: str | None,
        sidecar_root: str | None = None,
        title: str | None = None,
    ) -> "V1Session":
        """Create a package on disk, then reopen it through the normal validator."""
        destination = Path(path).expanduser().resolve()
        if title is not None and not title.strip():
            raise ValueError("Specification name is required.")
        package = SpecPackage.create(document_id, title=title.strip() if title is not None else destination.stem)
        if destination.exists():
            raise FileExistsError(f"Refusing to replace existing specification package: {destination}")
        package.save(str(destination))
        return cls(str(destination), sidecar_root)

    def save(self) -> None:
        """Persist source and activity using the package's deterministic writer."""
        self.package.save(self.path)

    def commit_revision(self, revision: SpecRevision) -> None:
        """Adopt validated source while retaining activity, which is not source state."""
        next_package = revision.to_package()
        if "activity/v1/actions.json" in self.package.files:
            next_package.files["activity/v1/actions.json"] = self.package.files["activity/v1/actions.json"]
        self.package = next_package
        self.revision = SpecRevision.from_package(self.package)
        self.activity = ActivityStore(self.package, self.sidecar)
        self.save()

    def commit_assistant_revision(
        self,
        revision: SpecRevision,
        decision: AssistantChangeDecision,
    ) -> None:
        """Atomically save source and its accepted assistant decision together."""
        next_package = revision.to_package()
        if "activity/v1/actions.json" in self.package.files:
            next_package.files["activity/v1/actions.json"] = self.package.files[
                "activity/v1/actions.json"
            ]
        next_activity = ActivityStore(next_package, self.sidecar)
        next_activity.record_assistant_change(decision)
        next_package.save(self.path)
        self.package = next_package
        self.revision = SpecRevision.from_package(next_package)
        self.activity = ActivityStore(next_package, self.sidecar)


def create_app() -> typing.Any:
    """Create the production local V1 API; only the deterministic source format is accepted."""
    try:
        import fastapi
        import fastapi.responses
        import fastapi.staticfiles
    except Exception as exc:  # pragma: no cover - import environment guard.
        raise RuntimeError("FastAPI is required for the V1 local editor API.") from exc

    app = fastapi.FastAPI(title="spec2gds V1 Hardware Specification API")
    registry = load_service_registry()
    logger = StructuredLogger("spec-editor", registry.logging)
    app.state.structured_logger = logger

    def service_urls() -> dict[str, dict[str, str]]:
        configured = registry.public_dict()
        configured["spec_editor"]["service_url"] = os.environ.get(
            "SPEC_EDITOR_SERVICE_URL", configured["spec_editor"]["service_url"]
        ).rstrip("/")
        configured["circuit_designer"]["service_url"] = os.environ.get(
            "CIRCUIT_DESIGNER_SERVICE_URL",
            configured["circuit_designer"]["service_url"],
        ).rstrip("/")
        configured["circuit_designer"]["ui_url"] = os.environ.get(
            "CIRCUIT_DESIGNER_UI_URL", configured["circuit_designer"]["ui_url"]
        ).rstrip("/")
        assistant_override = os.environ.get("AI_ASSISTANT_URL")
        if assistant_override:
            configured["ai_assistant"]["service_url"] = assistant_override.rstrip("/")
            configured["ai_assistant"]["ui_url"] = assistant_override.rstrip("/")
        return configured

    @app.middleware("http")
    async def log_request(request: typing.Any, call_next: typing.Any) -> typing.Any:
        """Record one request outcome and propagate a cross-service correlation ID."""
        correlation_id = request.headers.get("x-request-id") or uuid4().hex
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as reason:
            logger.event(
                "http",
                "request_failed",
                f"{request.method} {request.url.path} failed",
                severity="error",
                correlation_id=correlation_id,
                duration_ms=(time.perf_counter() - started) * 1000,
                exception=reason,
                details={"method": request.method, "url": str(request.url)},
            )
            raise
        response.headers["X-Request-ID"] = correlation_id
        logger.event(
            "http",
            "request_completed",
            f"{request.method} {request.url.path} returned {response.status_code}",
            severity="error" if response.status_code >= 500 else "warning" if response.status_code >= 400 else "info",
            correlation_id=correlation_id,
            duration_ms=(time.perf_counter() - started) * 1000,
            status=response.status_code,
            details={"method": request.method, "url": str(request.url)},
        )
        return response
    state: dict[str, typing.Any] = {
        "active": None,
        "source_event_sequence": 0,
        "source_event": None,
    }
    editor_root = Path(__file__).with_name("editor_dist")
    # StaticFiles is mounted from a package-relative path so launching the API
    # from another working directory cannot silently break the editor.
    app.mount(
        "/editor-assets",
        fastapi.staticfiles.StaticFiles(directory=editor_root),
        name="editor-assets",
    )
    def active() -> V1Session:
        """Return the active single-user session or an actionable HTTP error."""
        session = state["active"]
        if session is None:
            raise fastapi.HTTPException(status_code=400, detail="No V1 .spec package is open.")
        return session

    def ref(kind: str, entity_id: str) -> EntityRef:
        """Build a document-local stable entity reference from route segments."""
        session = active()
        try:
            return EntityRef(document_id=session.revision.document_id, entity_id=entity_id, entity_kind=kind)
        except pydantic.ValidationError as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    def result_or_error(result: typing.Any) -> dict[str, typing.Any]:
        """Commit a successful transaction or map diagnostics to HTTP status."""
        if result.succeeded and result.revision is not None:
            active().commit_revision(result.revision)
            _publish_source_event(state, active(), origin="editor", affected_entities=[])
            return {"committed": True, "snapshot": _snapshot(active())}
        status = 409 if any("Stale" in item or "stale" in item for item in result.diagnostics) else 422
        raise fastapi.HTTPException(status_code=status, detail={"diagnostics": list(result.diagnostics)})

    @app.get("/health")
    def health() -> dict[str, str]:
        """Report server liveness and the source-format generation it serves."""
        return {"status": "ok", "format": "spec2gds-v1"}

    @app.get("/services")
    def services() -> dict[str, typing.Any]:
        """Expose the resolved cross-application endpoints to the browser UI."""
        return {
            "schema_version": 2,
            "services": service_urls(),
            "logging": {"enabled": registry.logging.enabled, "level": registry.logging.level},
        }

    @app.post("/logs/events", status_code=204)
    def browser_log_events(payload: dict[str, typing.Any]) -> None:
        """Append a bounded batch of browser events using trusted server metadata."""
        encoded_size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        if encoded_size > 262_144:
            raise fastapi.HTTPException(status_code=413, detail="Browser log batch is too large.")
        events = payload.get("events")
        if not isinstance(events, list) or len(events) > 100:
            raise fastapi.HTTPException(status_code=422, detail="Browser log events must be a list of at most 100 items.")
        logger.browser_events(str(payload.get("session_id", "unknown")), [item for item in events if isinstance(item, dict)])

    @app.post("/documents/create")
    def create_document(request: CreateDocumentRequest) -> dict[str, typing.Any]:
        """Create, validate, activate, and return a new package snapshot."""
        try:
            logger.event("documents", "create_requested", "Creating specification", details=request)
            state["active"] = V1Session.create(
                request.path,
                request.document_id,
                request.sidecar_root,
                request.title,
            )
            return _snapshot(active())
        except (OSError, ValueError, SpecValidationError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/documents/open")
    def open_document(request: OpenDocumentRequest) -> dict[str, typing.Any]:
        """Validate and activate an existing deterministic package."""
        try:
            logger.event("documents", "open_requested", "Opening specification", details=request)
            state["active"] = V1Session(request.path, request.sidecar_root)
            return _snapshot(active())
        except (OSError, ValueError, SpecValidationError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/documents/snapshot")
    def document_snapshot() -> dict[str, typing.Any]:
        """Return the complete editor-facing immutable source projection."""
        return _snapshot(active())

    @app.post("/assistant/launch")
    def launch_assistant(request: AssistantLaunchRequest) -> dict[str, typing.Any]:
        """Return the AI Assistant launch URL without making the editor depend on it."""
        target = ref(request.entity_kind, request.entity_id)
        try:
            active().revision.resolve(target)
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        urls = service_urls()
        assistant_base = urls["ai_assistant"]["service_url"]
        service = urls["spec_editor"]["service_url"]
        query = urlencode(
            {
                "service_base_url": service,
                "document_id": active().revision.document_id,
                "entity_kind": target.entity_kind,
                "entity_id": target.entity_id,
            }
        )
        return {
            "assistant_url": f"{assistant_base}/launch/spec?{query}",
            "target": _jsonable(target),
        }

    @app.post("/assistant/launch/document")
    def launch_document_assistant() -> dict[str, typing.Any]:
        """Launch a fresh document-bound chat for the active specification."""
        session = active()
        urls = service_urls()
        query = urlencode(
            {
                "service_base_url": urls["spec_editor"]["service_url"],
                "document_id": session.revision.document_id,
            }
        )
        return {
            "assistant_url": (
                f"{urls['ai_assistant']['service_url']}/launch/spec-document?{query}"
            ),
            "document_id": session.revision.document_id,
            "source_revision_hash": session.revision.source_revision_hash,
            "scope": "document",
        }

    @app.post("/circuit-designer/launch")
    def launch_circuit(request: CircuitLaunchRequest) -> dict[str, typing.Any]:
        """Project one direct-port design, publish it, and return its browser URL."""
        try:
            projection = project_source_to_circuit(
                active().revision,
                request.entity_kind,
                request.entity_id,
            )
            launched = publish_circuit_document(
                projection.document,
                service_url=service_urls()["circuit_designer"]["service_url"],
                editor_url=service_urls()["circuit_designer"]["ui_url"],
            )
        except CircuitDesignerConnectionError as exc:
            raise fastapi.HTTPException(status_code=503, detail=str(exc)) from exc
        except CircuitAdapterError as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "document_id": launched.document_id,
            "entity_id": projection.source_entity_id,
            "entity_kind": projection.source_entity_kind,
            "editor_url": launched.editor_url,
            "reused_session": launched.reused_session,
            "omitted_bus_items": list(projection.omitted_bus_items),
            "omitted_ports": list(projection.omitted_ports),
        }

    @app.get("/documents/a2ui")
    def document_a2ui() -> dict[str, typing.Any]:
        """Return a deterministic A2UI v0.9 batch for the unified document."""
        projection = build_document_projection(active().revision)
        return build_a2ui_batch(projection).model_dump(mode="json")

    @app.get("/assistant/context")
    def assistant_context(
        document_id: str,
        entity_kind: str,
        entity_id: str,
    ) -> dict[str, typing.Any]:
        """Return entity-bound semantic context for the external Spec agent."""
        if document_id != active().revision.document_id:
            raise fastapi.HTTPException(status_code=409, detail="A different .spec document is active.")
        try:
            return build_assistant_context(active().revision, ref(entity_kind, entity_id))
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/assistant/context/document")
    def assistant_document_context(document_id: str) -> dict[str, typing.Any]:
        """Return immutable document-wide context for a read-only Spec chat."""
        if document_id != active().revision.document_id:
            raise fastapi.HTTPException(
                status_code=409,
                detail="A different .spec document is active.",
            )
        return build_document_assistant_context(active().revision)

    @app.post("/assistant/proposals/preview")
    def assistant_proposal_preview(proposal: SpecChangeProposal) -> dict[str, typing.Any]:
        """Validate and project an assistant proposal without persisting a draft."""
        try:
            result = preview_assistant_proposal(active().revision, proposal)
        except (KeyError, TypeError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc
        result.pop("_revision", None)
        return result

    @app.post("/assistant/proposals/apply")
    def assistant_proposal_apply(proposal: SpecChangeProposal) -> dict[str, typing.Any]:
        """Revalidate, atomically apply/save, and record one approved decision."""
        session = active()
        digest = proposal.operations_digest()
        existing = next(
            (
                item
                for item in session.activity.state.assistant_changes
                if item.proposal_id == proposal.proposal_id
            ),
            None,
        )
        if existing is not None:
            if existing.operations_digest != digest:
                raise fastapi.HTTPException(
                    status_code=409,
                    detail="Proposal ID was already applied with different operations.",
                )
            return {
                "status": "applied",
                "idempotent_replay": True,
                "proposal_id": proposal.proposal_id,
                "source_revision_hash": existing.result_source_revision_hash,
                "saved_at": existing.applied_at,
            }
        result = preview_assistant_proposal(session.revision, proposal)
        if result["status"] == "stale":
            raise fastapi.HTTPException(status_code=409, detail=result)
        if result["status"] != "valid" or result.get("_revision") is None:
            raise fastapi.HTTPException(status_code=422, detail=result)
        revision = typing.cast(SpecRevision, result.pop("_revision"))
        applied_at = datetime.now(UTC).isoformat()
        decision = AssistantChangeDecision(
            proposal_id=proposal.proposal_id,
            scope=proposal.scope,
            target=proposal.target,
            base_source_revision_hash=proposal.base_source_revision_hash,
            result_source_revision_hash=revision.source_revision_hash,
            operations_digest=digest,
            operations=tuple(proposal.operations),
            applied_at=applied_at,
        )
        try:
            session.commit_assistant_revision(revision, decision)
        except (OSError, ValueError, SpecValidationError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc
        _publish_source_event(
            state,
            session,
            origin="assistant",
            affected_entities=(
                [proposal.target.model_dump(mode="json")]
                if proposal.target is not None
                else []
            ),
        )
        return {
            "status": "applied",
            "idempotent_replay": False,
            "proposal_id": proposal.proposal_id,
            "source_revision_hash": session.revision.source_revision_hash,
            "saved_at": applied_at,
            "sections": result["candidate_sections"],
            "diff": result["diff"],
        }

    @app.get("/events")
    async def source_events() -> typing.Any:
        """Stream committed source changes; consumers decide when to refresh."""
        async def events() -> typing.AsyncIterator[str]:
            observed = int(state["source_event_sequence"])
            while True:
                if int(state["source_event_sequence"]) != observed:
                    observed = int(state["source_event_sequence"])
                    payload = json.dumps(state["source_event"], separators=(",", ":"))
                    yield f"id: {observed}\nevent: source.changed\ndata: {payload}\n\n"
                else:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(1)

        return fastapi.responses.StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/diagnostics")
    def diagnostics() -> dict[str, typing.Any]:
        """Return source diagnostics separately from artifact-sidecar diagnostics."""
        session = active()
        return {"source": list(session.revision.diagnostics), "artifacts": list(session.activity.artifact_diagnostics())}

    @app.get("/components")
    def components() -> dict[str, typing.Any]:
        """List component SpecIR nodes."""
        return {"components": [_jsonable(item) for item in active().revision.components]}

    @app.get("/components/{entity_id}")
    def component(entity_id: str) -> dict[str, typing.Any]:
        """Resolve one component by stable entity id."""
        try:
            return _jsonable(active().revision.resolve(ref("component", entity_id)))
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/designs")
    def designs() -> dict[str, typing.Any]:
        """List designs together with their derived read-only topology."""
        session = active()
        return {"designs": [_jsonable(item) for item in session.revision.designs], "topology": [_topology(item) for item in session.revision.designs]}

    @app.get("/designs/{entity_id}")
    def design(entity_id: str) -> dict[str, typing.Any]:
        """Resolve one design and derive its display topology."""
        try:
            item = active().revision.resolve(ref("design", entity_id))
            return {"design": _jsonable(item), "topology": _topology(item)}
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/entry-designs")
    def entry_designs() -> dict[str, typing.Any]:
        """List explicitly selected entry designs."""
        return {"entry_designs": [_jsonable(item) for item in active().revision.entry_designs()]}

    @app.get("/component-compositions")
    def component_compositions() -> dict[str, typing.Any]:
        """List component-to-internal-design ownership mappings."""
        return {"component_compositions": [_jsonable(item) for item in active().revision.manifest.component_compositions]}

    @app.get("/narrative")
    def narrative() -> dict[str, typing.Any]:
        """Return the typed narrative AST."""
        return _jsonable(active().revision.narrative)

    @app.get("/assets")
    def assets() -> dict[str, typing.Any]:
        """List source asset metadata without embedding binary content."""
        return {"assets": [_jsonable(item) for item in active().revision.assets]}

    @app.get("/assets/{asset_id}/content")
    def asset_content(asset_id: str) -> typing.Any:
        """Serve one validated source asset using its declared media type."""
        session = active()
        try:
            asset = session.revision.resolve(ref("asset", asset_id))
            data = session.package.files[asset.path]
            return fastapi.Response(content=data, media_type=asset.media_type)
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/transactions")
    def transaction(request: TransactionRequest) -> dict[str, typing.Any]:
        """Decode and atomically apply a revision-guarded edit transaction."""
        try:
            logger.event(
                "transactions",
                "apply_requested",
                f"Applying {len(request.operations)} specification operation(s)",
                details=request,
            )
            operations = _decode_transaction_operations(active().revision.document_id, request.operations)
        except (KeyError, ValueError, pydantic.ValidationError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc
        return result_or_error(SpecEditTransaction(request.expected_source_revision_hash, operations).apply(active().revision))

    @app.post("/assets")
    def add_asset(request: AssetRequest) -> dict[str, typing.Any]:
        """Add a content-addressed source asset through the transaction layer."""
        try:
            data = base64.b64decode(request.data_base64, validate=True)
        except ValueError as exc:
            raise fastapi.HTTPException(status_code=422, detail="data_base64 is invalid.") from exc
        return result_or_error(
            SpecEditTransaction(
                request.expected_source_revision_hash,
                (AddAsset(request.asset_id, data, request.media_type, request.extension),),
            ).apply(active().revision)
        )

    @app.get("/entities/{kind}/{entity_id}/actions")
    def entity_actions(kind: str, entity_id: str) -> dict[str, typing.Any]:
        """List action definitions compatible with a resolved source entity."""
        target = ref(kind, entity_id)
        try:
            active().revision.resolve(target)
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "actions": [
                _jsonable(action)
                for action in active().actions.registry.list()
                if kind in action.target_entity_kinds
            ]
        }

    @app.post("/entities/{kind}/{entity_id}/actions/{action_id}/preconditions")
    def action_preconditions(kind: str, entity_id: str, action_id: str, request: ActionInputRequest) -> dict[str, typing.Any]:
        """Validate action inputs and preconditions without executing a command."""
        try:
            action = active().actions.registry.get(action_id)
            snapshot = active().actions.create_snapshot(
                active().revision,
                action,
                ref(kind, entity_id),
                request.inputs,
                tuple(request.input_artifact_ids),
                active().activity,
            )
            return {"can_execute": True, "snapshot_id": snapshot.snapshot_id, "dependency_closure": [_jsonable(item) for item in snapshot.dependency_closure]}
        except (KeyError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/entities/{kind}/{entity_id}/actions/{action_id}/executions")
    def action_execution(kind: str, entity_id: str, action_id: str, request: ActionInputRequest) -> dict[str, typing.Any]:
        """Execute one trusted local action against an immutable snapshot."""
        try:
            execution = active().actions.execute(
                active().revision,
                active().activity,
                action_id,
                ref(kind, entity_id),
                request.inputs,
                tuple(request.input_artifact_ids),
            )
            active().save()
            return _jsonable(execution)
        except (KeyError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/executions")
    def executions() -> dict[str, typing.Any]:
        """List durable action-execution records for the active package."""
        return {"executions": [_jsonable(item) for item in active().activity.state.executions]}

    @app.get("/executions/{execution_id}")
    def execution(execution_id: str) -> dict[str, typing.Any]:
        """Return one durable action-execution record."""
        item = next((item for item in active().activity.state.executions if item.execution_id == execution_id), None)
        if item is None:
            raise fastapi.HTTPException(status_code=404, detail="Unknown action execution.")
        return _jsonable(item)

    @app.get("/artifacts")
    def artifacts(entity_kind: str | None = None, entity_id: str | None = None) -> dict[str, typing.Any]:
        """List artifacts, optionally filtered by attached source entity."""
        items = active().activity.state.artifacts
        if entity_kind and entity_id:
            target = ref(entity_kind, entity_id)
            items = tuple(item for item in items if target in item.source_entities)
        return {"artifacts": [_jsonable(item) for item in items]}

    @app.get("/artifacts/{artifact_id}/lineage")
    def artifact_lineage(artifact_id: str) -> dict[str, typing.Any]:
        """Return an artifact followed by its immutable parent lineage."""
        lineage = active().activity.artifact_lineage(artifact_id)
        if not lineage:
            raise fastapi.HTTPException(status_code=404, detail="Unknown artifact.")
        return {"lineage": [_jsonable(item) for item in lineage]}

    @app.get("/artifacts/{artifact_id}/content")
    def artifact_content(artifact_id: str) -> typing.Any:
        """Serve verified sidecar bytes for one immutable artifact."""
        artifact = next((item for item in active().activity.state.artifacts if item.artifact_id == artifact_id), None)
        if artifact is None:
            raise fastapi.HTTPException(status_code=404, detail="Unknown artifact.")
        try:
            data = active().sidecar.read(artifact)
        except (FileNotFoundError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc
        return fastapi.Response(content=data, media_type=artifact.media_type)

    @app.get("/proposals")
    def proposals() -> dict[str, typing.Any]:
        """List review-gated change proposals for the active package."""
        return {"proposals": [_jsonable(item) for item in active().activity.state.proposals]}

    @app.get("/assistant/changes")
    def assistant_changes() -> dict[str, typing.Any]:
        """List accepted assistant decisions stored in package activity."""
        return {
            "assistant_changes": [
                _jsonable(item) for item in active().activity.state.assistant_changes
            ]
        }

    @app.post("/proposals/{proposal_id}/preview")
    def preview_proposal(proposal_id: str, request: ProposalRequest) -> dict[str, typing.Any]:
        """Validate a pending proposal without changing source or review state."""
        if request.expected_source_revision_hash != active().revision.source_revision_hash:
            raise fastapi.HTTPException(status_code=409, detail="Expected source revision hash is stale.")
        result = active().actions.preview_proposal(active().revision, active().activity, proposal_id)
        return {"valid": result.succeeded, "diagnostics": list(result.diagnostics), "preview_source_revision_hash": result.revision.source_revision_hash if result.revision else None}

    @app.post("/proposals/{proposal_id}/accept")
    def accept_proposal(proposal_id: str, request: ProposalRequest) -> dict[str, typing.Any]:
        """Accept a current proposal through the normal transaction validator."""
        if request.expected_source_revision_hash != active().revision.source_revision_hash:
            raise fastapi.HTTPException(status_code=409, detail="Expected source revision hash is stale.")
        return result_or_error(active().actions.accept_proposal(active().revision, active().activity, proposal_id))

    @app.post("/proposals/{proposal_id}/reject")
    def reject_proposal(proposal_id: str) -> dict[str, typing.Any]:
        """Record proposal rejection without changing source state."""
        try:
            proposal = active().actions.reject_proposal(active().activity, proposal_id)
            active().save()
            return _jsonable(proposal)
        except (KeyError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/", include_in_schema=False)
    def root() -> typing.Any:
        """Make the visual editor the convenient default local-server page."""
        return fastapi.responses.RedirectResponse(url="/editor")

    @app.get("/editor", include_in_schema=False, response_class=fastapi.responses.HTMLResponse)
    def editor() -> str:
        """Serve the prebuilt React/A2UI editor bundled with the Python package."""
        return (editor_root / "index.html").read_text(encoding="utf-8")

    return app


def _decode_transaction_operations(document_id: str, raw_operations: list[dict[str, typing.Any]]) -> tuple[typing.Any, ...]:
    """Decode the JSON API operation vocabulary to V1.2 typed transactions."""
    def entity(value: typing.Any) -> EntityRef:
        """Accept compact ``kind:id`` or full public reference objects."""
        if isinstance(value, str):
            kind, entity_id = value.split(":", 1)
            return EntityRef(document_id=document_id, entity_id=entity_id, entity_kind=kind)
        return EntityRef.model_validate(value)

    operations: list[typing.Any] = []
    for raw in raw_operations:
        kind = raw.get("type")
        if kind == "upsert_document_xml":
            operations.append(UpsertDocumentXml(raw["kind"], str(raw["xml"]).encode("utf-8")))
        elif kind == "delete_document":
            operations.append(DeleteDocument(entity(raw["ref"])))
        elif kind == "create_entity":
            entity_kind = str(raw.get("kind", ""))
            if entity_kind not in {"component", "design"}:
                raise ValueError("create_entity kind must be component or design.")
            instances = raw.get("instances", [])
            if not isinstance(instances, list):
                raise ValueError("create_entity instances must be a list.")
            operations.append(
                CreateEntity(
                    typing.cast(typing.Any, entity_kind),
                    str(raw.get("name", "")),
                    str(raw["entity_id"]) if raw.get("entity_id") else None,
                    tuple(InstanceIR(**item) for item in instances),
                )
            )
        elif kind == "set_document_title":
            operations.append(SetDocumentTitle(str(raw.get("title", ""))))
        elif kind == "set_entity_metadata":
            operations.append(SetEntityMetadata(
                entity(raw["entity"]),
                _optional_text(raw.get("display_name")),
                _optional_text(raw.get("short_description")),
                _optional_text(raw.get("description")),
            ))
        elif kind in {"add_component_port", "update_component_port"}:
            value = raw.get("port")
            if not isinstance(value, dict):
                raise ValueError(f"{kind} requires a port object.")
            if kind == "update_component_port" and "name" in value:
                raise ValueError("Port names cannot be changed by update_component_port.")
            port_name = str(value.get("name", "")) if kind == "add_component_port" else str(raw.get("name", ""))
            operation_type = AddComponentPort if kind == "add_component_port" else UpdateComponentPort
            operations.append(operation_type(
                entity(raw["component"]),
                port_name,
                _decode_component_port_input(value, include_name=kind == "add_component_port"),
            ))
        elif kind == "upsert_instance":
            operations.append(UpsertInstance(entity(raw["design"]), InstanceIR(**raw["instance"])))
        elif kind == "delete_instance":
            operations.append(DeleteInstance(entity(raw["design"]), str(raw["instance_name"])))
        elif kind == "reorder_instances":
            operations.append(ReorderInstances(entity(raw["design"]), tuple(raw["instance_names"])))
        elif kind == "upsert_connection":
            connection = raw["connection"]
            operations.append(
                UpsertConnection(
                    entity(raw["design"]),
                    ConnectionIR(
                        name=connection["name"],
                        kind=connection["kind"],
                        interface_endpoints=tuple(
                            InterfaceEndpointIR(**item)
                            for item in connection.get("interface_endpoints", [])
                        ),
                        port_endpoints=tuple(PortEndpointIR(**item) for item in connection.get("port_endpoints", [])),
                        external_ports=tuple(connection.get("external_ports", [])),
                        hierarchy_interfaces=tuple(connection.get("hierarchy_interfaces", [])),
                    ),
                )
            )
        elif kind == "delete_connection":
            operations.append(DeleteConnection(entity(raw["design"]), str(raw["connection_name"])))
        elif kind == "reorder_connections":
            operations.append(ReorderConnections(entity(raw["design"]), raw["kind"], tuple(raw["connection_names"])))
        elif kind == "set_internal_design":
            operations.append(SetInternalDesign(entity(raw["component"]), entity(raw["internal_design"])))
        elif kind == "clear_internal_design":
            operations.append(ClearInternalDesign(entity(raw["component"])))
        elif kind == "add_entry_design":
            operations.append(AddEntryDesign(entity(raw["design"])))
        elif kind == "remove_entry_design":
            operations.append(RemoveEntryDesign(entity(raw["design"])))
        elif kind == "upsert_narrative_block":
            operations.append(UpsertNarrativeBlock(NarrativeBlock.model_validate(raw["block"]), raw.get("parent_block_id"), raw.get("index")))
        elif kind == "delete_narrative_block":
            operations.append(DeleteNarrativeBlock(str(raw["block_id"])))
        elif kind == "reorder_narrative_blocks":
            operations.append(ReorderNarrativeBlocks(tuple(raw["block_ids"]), raw.get("parent_block_id")))
        elif kind == "set_narrative_entity_links":
            operations.append(SetNarrativeEntityLinks(str(raw["block_id"]), tuple(EntityRef.model_validate(item) for item in raw["entity_refs"])))
        elif kind == "remove_asset":
            operations.append(RemoveAsset(str(raw["asset_id"])))
        else:
            raise ValueError(f"Unsupported transaction operation: {kind}")
    return tuple(operations)


def _optional_text(value: typing.Any) -> str | None:
    """Normalize optional public text fields without losing multiline content."""
    if value is None:
        return None
    return str(value)


def _decode_component_port_input(
    value: dict[str, typing.Any],
    *,
    include_name: bool,
) -> WirePortInput | TransactionalPortInput | StructuredPortInput:
    """Decode the strict public discriminated port union."""
    family = str(value.get("family", ""))
    common = {"family", "display_name", "description"}
    if include_name:
        common.add("name")
    display_name = _optional_text(value.get("display_name"))
    description = _optional_text(value.get("description"))
    if family == "wire":
        _reject_operation_fields(value, common | {"direction", "range"}, "wire port")
        direction = str(value.get("direction", ""))
        if direction not in {"in", "out", "inout"}:
            raise ValueError("Wire port direction must be in, out, or inout.")
        return WirePortInput(
            direction=typing.cast(typing.Any, direction),
            range=_optional_text(value.get("range")),
            display_name=display_name,
            description=description,
        )
    if family == "transactional":
        _reject_operation_fields(
            value,
            common | {"initiative", "kind", "custom_kind", "bus_width"},
            "transactional port",
        )
        initiative = str(value.get("initiative", ""))
        if initiative not in {"requires", "provides", "both"}:
            raise ValueError("Transactional port initiative must be requires, provides, or both.")
        transaction_kind = _optional_text(value.get("kind"))
        if transaction_kind not in {None, "tlm_port", "tlm_socket", "simple_socket", "multi_socket", "custom"}:
            raise ValueError("Unknown transactional port kind.")
        return TransactionalPortInput(
            initiative=typing.cast(typing.Any, initiative),
            kind=typing.cast(typing.Any, transaction_kind),
            custom_kind=_optional_text(value.get("custom_kind")),
            bus_width=_optional_text(value.get("bus_width")),
            display_name=display_name,
            description=description,
        )
    if family == "structured":
        _reject_operation_fields(value, common | {"direction"}, "structured port")
        direction = str(value.get("direction", ""))
        if direction not in {"in", "out", "inout"}:
            raise ValueError("Structured port direction must be in, out, or inout.")
        return StructuredPortInput(
            direction=typing.cast(typing.Any, direction),
            display_name=display_name,
            description=description,
        )
    raise ValueError("Port family must be wire, transactional, or structured.")


def _reject_operation_fields(value: dict[str, typing.Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"Unknown {label} fields: {', '.join(unknown)}")


def _snapshot(session: V1Session) -> dict[str, typing.Any]:
    """Build the single payload from which every editor view is rendered."""
    revision = session.revision
    return {
        "schema_version": "spec2gds.snapshot.v1",
        "document_id": revision.document_id,
        "source_revision_hash": revision.source_revision_hash,
        "components": [_jsonable(item) for item in revision.components],
        "designs": [_jsonable(item) for item in revision.designs],
        "bus_definitions": [_jsonable(item) for item in revision.bus_definitions],
        "abstraction_definitions": [_jsonable(item) for item in revision.abstraction_definitions],
        "entry_designs": [_jsonable(item) for item in revision.entry_designs()],
        "component_compositions": [_jsonable(item) for item in revision.manifest.component_compositions],
        "narrative": _jsonable(revision.narrative),
        "assets": [_jsonable(item) for item in revision.assets],
        "diagnostics": {"source": list(revision.diagnostics), "artifacts": list(session.activity.artifact_diagnostics())},
    }


def _topology(design: typing.Any) -> dict[str, typing.Any]:
    """Derive a compact graph without persisting a second topology model."""
    nodes = [{"id": instance.name, "component_vlnv": instance.component_vlnv} for instance in design.instances]
    edges: list[dict[str, typing.Any]] = []
    for connection in design.connections:
        endpoints = connection.interface_endpoints if connection.kind == "interface" else connection.port_endpoints
        for endpoint in endpoints[1:]:
            if endpoints:
                edges.append({"connection": connection.name, "kind": connection.kind, "from": endpoints[0].instance_name, "to": endpoint.instance_name})
    return {"design_id": design.ref.entity_id, "nodes": nodes, "edges": edges}


def _jsonable(value: typing.Any) -> typing.Any:
    """Recursively convert public Pydantic/dataclass contracts to JSON values."""
    if isinstance(value, pydantic.BaseModel):
        return {key: _jsonable(item) for key, item in value.model_dump(mode="json").items()}
    if dataclasses.is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value) if not field.name.startswith("_")}
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _publish_source_event(
    state: dict[str, typing.Any],
    session: V1Session,
    *,
    origin: str,
    affected_entities: list[dict[str, typing.Any]],
) -> None:
    """Publish one post-commit event for lightweight local SSE subscribers."""
    state["source_event_sequence"] = int(state["source_event_sequence"]) + 1
    state["source_event"] = {
        "sequence": state["source_event_sequence"],
        "document_id": session.revision.document_id,
        "source_revision_hash": session.revision.source_revision_hash,
        "origin": origin,
        "affected_entities": affected_entities,
    }

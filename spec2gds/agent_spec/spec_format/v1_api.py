"""Production V1 local API and browser editor for deterministic ``.spec`` files.

The module is deliberately the only HTTP composition root.  It translates
JSON requests into immutable SpecIR reads, validated source transactions, and
activity-store operations; the browser never receives mutable package objects.
"""

from __future__ import annotations

import base64
import dataclasses
import json
from pathlib import Path
import typing

import pydantic

from spec2gds.agent_spec.circuit_designer.projection import project_catalog
from spec2gds.agent_spec.circuit_designer.contracts import AgentProposal, CommandBatch
from spec2gds.agent_spec.circuit_designer.service import CircuitDesignerConflict, CircuitDesignerSession

from spec2gds.agent_spec.spec_format.actions import (
    ActionService,
    ActivityStore,
    ArtifactSidecar,
    create_reference_registry,
)
from spec2gds.agent_spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.agent_spec.spec_format.ir import ConnectionIR, InstanceIR, InterfaceEndpointIR, PortEndpointIR, SpecRevision
from spec2gds.agent_spec.spec_format.models import EntityRef, NarrativeBlock
from spec2gds.agent_spec.spec_format.transactions import (
    AddAsset,
    AddEntryDesign,
    ClearInternalDesign,
    DeleteConnection,
    DeleteDocument,
    DeleteInstance,
    DeleteNarrativeBlock,
    RemoveAsset,
    RemoveEntryDesign,
    ReorderConnections,
    ReorderInstances,
    ReorderNarrativeBlocks,
    SetInternalDesign,
    SetNarrativeEntityLinks,
    SpecEditTransaction,
    UpsertConnection,
    UpsertDocumentXml,
    UpsertInstance,
    UpsertNarrativeBlock,
)


class OpenDocumentRequest(pydantic.BaseModel):
    """Select one existing V1 package and its optional artifact sidecar."""

    path: str
    sidecar_root: str | None = None


class CreateDocumentRequest(pydantic.BaseModel):
    """Create and activate an empty deterministic V1 package."""

    path: str
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


class CircuitLeaseRequest(pydantic.BaseModel):
    owner_id: str
    owner_kind: typing.Literal["human", "agent"]
    ttl_seconds: int = 300


class CircuitApplyRequest(pydantic.BaseModel):
    batch: CommandBatch
    lease_id: str


class CircuitHistoryRequest(pydantic.BaseModel):
    lease_id: str
    design_id: str


class CircuitProposalDecisionRequest(pydantic.BaseModel):
    decision: typing.Literal["accepted", "rejected"]
    lease_id: str | None = None


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
    def create(cls, path: str, document_id: str | None, sidecar_root: str | None = None) -> "V1Session":
        """Create a package on disk, then reopen it through the normal validator."""
        package = SpecPackage.create(document_id)
        destination = str(Path(path).expanduser().resolve())
        package.save(destination)
        return cls(destination, sidecar_root)

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


def create_app() -> typing.Any:
    """Create the production local V1 API; only the deterministic source format is accepted."""
    try:
        import fastapi
        import fastapi.responses
        import fastapi.staticfiles
    except Exception as exc:  # pragma: no cover - import environment guard.
        raise RuntimeError("FastAPI is required for the V1 local editor API.") from exc

    app = fastapi.FastAPI(title="spec2gds V1 Hardware Specification API")
    state: dict[str, typing.Any] = {"active": None, "circuit": None}
    editor_root = Path(__file__).with_name("editor")
    sample_root = Path(__file__).with_name("samples") / "generated"
    # A source checkout also exposes the larger real-document corpus.  Keep
    # this optional so installed wheels still work without repository data.
    benchmark_root = Path(__file__).resolve().parents[3] / "benchmarks" / "agent_spec" / "hw_docs" / "generated"

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

    def circuit() -> CircuitDesignerSession:
        session = active()
        service = state["circuit"]
        if service is None or service.session is not session:
            service = CircuitDesignerSession(session)
            state["circuit"] = service
        return typing.cast(CircuitDesignerSession, service)

    def circuit_conflict(action: typing.Callable[[], typing.Any]) -> typing.Any:
        try:
            return action()
        except CircuitDesignerConflict as exc:
            raise fastapi.HTTPException(status_code=409, detail=str(exc)) from exc

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
            return {"committed": True, "snapshot": _snapshot(active())}
        status = 409 if any("Stale" in item or "stale" in item for item in result.diagnostics) else 422
        raise fastapi.HTTPException(status_code=status, detail={"diagnostics": list(result.diagnostics)})

    @app.get("/health")
    def health() -> dict[str, str]:
        """Report server liveness and the source-format generation it serves."""
        return {"status": "ok", "format": "spec2gds-v1"}

    @app.get("/samples")
    def samples() -> dict[str, typing.Any]:
        """List checked-in V1 packages that can be opened by the visual editor."""
        entries = []
        roots = ((sample_root, ""), (benchmark_root, "Hardware · "))
        for root, label_prefix in roots:
            for path in sorted(root.glob("*.spec")):
                name = path.stem.replace("_", " ").title()
                entries.append({"name": f"{label_prefix}{name}", "path": str(path.resolve())})
        return {"samples": entries}

    @app.post("/documents/create")
    def create_document(request: CreateDocumentRequest) -> dict[str, typing.Any]:
        """Create, validate, activate, and return a new package snapshot."""
        try:
            state["active"] = V1Session.create(request.path, request.document_id, request.sidecar_root)
            state["circuit"] = None
            return _snapshot(active())
        except (OSError, ValueError, SpecValidationError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/documents/open")
    def open_document(request: OpenDocumentRequest) -> dict[str, typing.Any]:
        """Validate and activate an existing package; legacy containers fail closed."""
        try:
            state["active"] = V1Session(request.path, request.sidecar_root)
            state["circuit"] = None
            return _snapshot(active())
        except (OSError, ValueError, SpecValidationError) as exc:
            # In particular, legacy ODT containers fail with an explicit V1 package diagnostic.
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/documents/snapshot")
    def document_snapshot() -> dict[str, typing.Any]:
        """Return the complete editor-facing immutable source projection."""
        return _snapshot(active())

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

    @app.get("/circuit-designer/catalog")
    def circuit_designer_catalog() -> dict[str, typing.Any]:
        """Return the renderer-neutral design catalog for the active revision."""
        return project_catalog(active().revision).model_dump(mode="json")

    @app.get("/circuit-designer/designs/{entity_id}")
    def circuit_designer_graph(entity_id: str) -> dict[str, typing.Any]:
        """Project one active SpecIR design into the shared circuit graph contract."""
        try:
            return circuit().graph(entity_id).model_dump(mode="json")
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/circuit-designer/lease")
    def circuit_designer_lease() -> dict[str, typing.Any]:
        lease = circuit().active_lease()
        return {"lease": lease.model_dump(mode="json") if lease else None}

    @app.post("/circuit-designer/lease")
    def acquire_circuit_designer_lease(request: CircuitLeaseRequest) -> dict[str, typing.Any]:
        lease = circuit_conflict(lambda: circuit().acquire_lease(request.owner_id, request.owner_kind, request.ttl_seconds))
        return lease.model_dump(mode="json")

    @app.delete("/circuit-designer/lease/{lease_id}")
    def release_circuit_designer_lease(lease_id: str) -> dict[str, bool]:
        circuit_conflict(lambda: circuit().release_lease(lease_id))
        return {"released": True}

    @app.post("/circuit-designer/commands/preview")
    def preview_circuit_designer_commands(batch: CommandBatch) -> dict[str, typing.Any]:
        return circuit().preview(batch).model_dump(mode="json")

    @app.post("/circuit-designer/commands/apply")
    def apply_circuit_designer_commands(request: CircuitApplyRequest) -> dict[str, typing.Any]:
        result = circuit_conflict(lambda: circuit().apply(request.batch, request.lease_id))
        return result.model_dump(mode="json")

    @app.get("/circuit-designer/history")
    def circuit_designer_history() -> dict[str, bool]:
        return circuit().history_status()

    @app.post("/circuit-designer/history/undo")
    def undo_circuit_designer(request: CircuitHistoryRequest) -> dict[str, typing.Any]:
        graph = circuit_conflict(lambda: circuit().undo(request.lease_id, request.design_id))
        return {"graph": graph.model_dump(mode="json"), **circuit().history_status()}

    @app.post("/circuit-designer/history/redo")
    def redo_circuit_designer(request: CircuitHistoryRequest) -> dict[str, typing.Any]:
        graph = circuit_conflict(lambda: circuit().redo(request.lease_id, request.design_id))
        return {"graph": graph.model_dump(mode="json"), **circuit().history_status()}

    @app.get("/circuit-designer/proposals")
    def circuit_designer_proposals() -> dict[str, typing.Any]:
        return {"proposals": [item.model_dump(mode="json") for item in circuit().proposals.values()]}

    @app.post("/circuit-designer/proposals")
    def submit_circuit_designer_proposal(proposal: AgentProposal) -> dict[str, typing.Any]:
        stored = circuit_conflict(lambda: circuit().submit_proposal(proposal))
        return stored.model_dump(mode="json")

    @app.post("/circuit-designer/proposals/{proposal_id}/decision")
    def decide_circuit_designer_proposal(proposal_id: str, request: CircuitProposalDecisionRequest) -> dict[str, typing.Any]:
        try:
            proposal = circuit_conflict(lambda: circuit().decide_proposal(proposal_id, request.decision, request.lease_id))
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=proposal_id) from exc
        return proposal.model_dump(mode="json")

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
        """Serve the no-build V1 editor shell bundled with the Python package.

        Reading the small shell directly also keeps the route callable in
        acceptance tests; linked CSS and JavaScript remain static resources.
        """
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


def _snapshot(session: V1Session) -> dict[str, typing.Any]:
    """Build the single payload from which every editor view is rendered."""
    revision = session.revision
    return {
        "document_id": revision.document_id,
        "source_revision_hash": revision.source_revision_hash,
        "components": [_jsonable(item) for item in revision.components],
        "designs": [_jsonable(item) for item in revision.designs],
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

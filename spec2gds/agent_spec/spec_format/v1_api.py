"""Production V1 local API and small editor surface with no ODT dependencies."""

from __future__ import annotations

import base64
import dataclasses
import json
from pathlib import Path
import typing

import pydantic

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
    path: str
    sidecar_root: str | None = None


class CreateDocumentRequest(pydantic.BaseModel):
    path: str
    document_id: str | None = None
    sidecar_root: str | None = None


class TransactionRequest(pydantic.BaseModel):
    expected_source_revision_hash: str
    operations: list[dict[str, typing.Any]]


class ActionInputRequest(pydantic.BaseModel):
    inputs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    input_artifact_ids: list[str] = pydantic.Field(default_factory=list)


class ProposalRequest(pydantic.BaseModel):
    expected_source_revision_hash: str


class AssetRequest(pydantic.BaseModel):
    expected_source_revision_hash: str
    asset_id: str
    data_base64: str
    media_type: str
    extension: str


class V1Session:
    """One local document session that keeps source and activity concerns separate."""

    def __init__(self, path: str, sidecar_root: str | None = None) -> None:
        self.path = str(Path(path).expanduser().resolve())
        self.package = SpecPackage.load(self.path)
        self.revision = SpecRevision.from_package(self.package)
        self.sidecar = ArtifactSidecar(sidecar_root or f"{self.path}.artifacts")
        self.activity = ActivityStore(self.package, self.sidecar)
        self.actions = ActionService(create_reference_registry(), self.sidecar)

    @classmethod
    def create(cls, path: str, document_id: str | None, sidecar_root: str | None = None) -> "V1Session":
        package = SpecPackage.create(document_id)
        destination = str(Path(path).expanduser().resolve())
        package.save(destination)
        return cls(destination, sidecar_root)

    def save(self) -> None:
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
    except Exception as exc:  # pragma: no cover - import environment guard.
        raise RuntimeError("FastAPI is required for the V1 local editor API.") from exc

    app = fastapi.FastAPI(title="spec2gds V1 Hardware Specification API")
    state: dict[str, V1Session | None] = {"active": None}

    def active() -> V1Session:
        session = state["active"]
        if session is None:
            raise fastapi.HTTPException(status_code=400, detail="No V1 .spec package is open.")
        return session

    def ref(kind: str, entity_id: str) -> EntityRef:
        session = active()
        try:
            return EntityRef(document_id=session.revision.document_id, entity_id=entity_id, entity_kind=kind)
        except pydantic.ValidationError as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    def result_or_error(result: typing.Any) -> dict[str, typing.Any]:
        if result.succeeded and result.revision is not None:
            active().commit_revision(result.revision)
            return {"committed": True, "snapshot": _snapshot(active())}
        status = 409 if any("Stale" in item or "stale" in item for item in result.diagnostics) else 422
        raise fastapi.HTTPException(status_code=status, detail={"diagnostics": list(result.diagnostics)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "format": "spec2gds-v1"}

    @app.post("/documents/create")
    def create_document(request: CreateDocumentRequest) -> dict[str, typing.Any]:
        try:
            state["active"] = V1Session.create(request.path, request.document_id, request.sidecar_root)
            return _snapshot(active())
        except (OSError, ValueError, SpecValidationError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/documents/open")
    def open_document(request: OpenDocumentRequest) -> dict[str, typing.Any]:
        try:
            state["active"] = V1Session(request.path, request.sidecar_root)
            return _snapshot(active())
        except (OSError, ValueError, SpecValidationError) as exc:
            # In particular, legacy ODT containers fail with an explicit V1 package diagnostic.
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/documents/snapshot")
    def document_snapshot() -> dict[str, typing.Any]:
        return _snapshot(active())

    @app.get("/diagnostics")
    def diagnostics() -> dict[str, typing.Any]:
        session = active()
        return {"source": list(session.revision.diagnostics), "artifacts": list(session.activity.artifact_diagnostics())}

    @app.get("/components")
    def components() -> dict[str, typing.Any]:
        return {"components": [_jsonable(item) for item in active().revision.components]}

    @app.get("/components/{entity_id}")
    def component(entity_id: str) -> dict[str, typing.Any]:
        try:
            return _jsonable(active().revision.resolve(ref("component", entity_id)))
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/designs")
    def designs() -> dict[str, typing.Any]:
        session = active()
        return {"designs": [_jsonable(item) for item in session.revision.designs], "topology": [_topology(item) for item in session.revision.designs]}

    @app.get("/designs/{entity_id}")
    def design(entity_id: str) -> dict[str, typing.Any]:
        try:
            item = active().revision.resolve(ref("design", entity_id))
            return {"design": _jsonable(item), "topology": _topology(item)}
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/entry-designs")
    def entry_designs() -> dict[str, typing.Any]:
        return {"entry_designs": [_jsonable(item) for item in active().revision.entry_designs()]}

    @app.get("/component-compositions")
    def component_compositions() -> dict[str, typing.Any]:
        return {"component_compositions": [_jsonable(item) for item in active().revision.manifest.component_compositions]}

    @app.get("/narrative")
    def narrative() -> dict[str, typing.Any]:
        return _jsonable(active().revision.narrative)

    @app.get("/assets")
    def assets() -> dict[str, typing.Any]:
        return {"assets": [_jsonable(item) for item in active().revision.assets]}

    @app.get("/assets/{asset_id}/content")
    def asset_content(asset_id: str) -> typing.Any:
        session = active()
        try:
            asset = session.revision.resolve(ref("asset", asset_id))
            data = session.package.files[asset.path]
            return fastapi.Response(content=data, media_type=asset.media_type)
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/transactions")
    def transaction(request: TransactionRequest) -> dict[str, typing.Any]:
        try:
            operations = _decode_transaction_operations(active().revision.document_id, request.operations)
        except (KeyError, ValueError, pydantic.ValidationError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc
        return result_or_error(SpecEditTransaction(request.expected_source_revision_hash, operations).apply(active().revision))

    @app.post("/assets")
    def add_asset(request: AssetRequest) -> dict[str, typing.Any]:
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
        return {"executions": [_jsonable(item) for item in active().activity.state.executions]}

    @app.get("/executions/{execution_id}")
    def execution(execution_id: str) -> dict[str, typing.Any]:
        item = next((item for item in active().activity.state.executions if item.execution_id == execution_id), None)
        if item is None:
            raise fastapi.HTTPException(status_code=404, detail="Unknown action execution.")
        return _jsonable(item)

    @app.get("/artifacts")
    def artifacts(entity_kind: str | None = None, entity_id: str | None = None) -> dict[str, typing.Any]:
        items = active().activity.state.artifacts
        if entity_kind and entity_id:
            target = ref(entity_kind, entity_id)
            items = tuple(item for item in items if target in item.source_entities)
        return {"artifacts": [_jsonable(item) for item in items]}

    @app.get("/artifacts/{artifact_id}/lineage")
    def artifact_lineage(artifact_id: str) -> dict[str, typing.Any]:
        lineage = active().activity.artifact_lineage(artifact_id)
        if not lineage:
            raise fastapi.HTTPException(status_code=404, detail="Unknown artifact.")
        return {"lineage": [_jsonable(item) for item in lineage]}

    @app.get("/proposals")
    def proposals() -> dict[str, typing.Any]:
        return {"proposals": [_jsonable(item) for item in active().activity.state.proposals]}

    @app.post("/proposals/{proposal_id}/preview")
    def preview_proposal(proposal_id: str, request: ProposalRequest) -> dict[str, typing.Any]:
        if request.expected_source_revision_hash != active().revision.source_revision_hash:
            raise fastapi.HTTPException(status_code=409, detail="Expected source revision hash is stale.")
        result = active().actions.preview_proposal(active().revision, active().activity, proposal_id)
        return {"valid": result.succeeded, "diagnostics": list(result.diagnostics), "preview_source_revision_hash": result.revision.source_revision_hash if result.revision else None}

    @app.post("/proposals/{proposal_id}/accept")
    def accept_proposal(proposal_id: str, request: ProposalRequest) -> dict[str, typing.Any]:
        if request.expected_source_revision_hash != active().revision.source_revision_hash:
            raise fastapi.HTTPException(status_code=409, detail="Expected source revision hash is stale.")
        return result_or_error(active().actions.accept_proposal(active().revision, active().activity, proposal_id))

    @app.post("/proposals/{proposal_id}/reject")
    def reject_proposal(proposal_id: str) -> dict[str, typing.Any]:
        try:
            proposal = active().actions.reject_proposal(active().activity, proposal_id)
            active().save()
            return _jsonable(proposal)
        except (KeyError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/editor", response_class=fastapi.responses.HTMLResponse)
    def editor() -> str:
        return _EDITOR_HTML

    return app


def _decode_transaction_operations(document_id: str, raw_operations: list[dict[str, typing.Any]]) -> tuple[typing.Any, ...]:
    """Decode the JSON API operation vocabulary to V1.2 typed transactions."""
    def entity(value: typing.Any) -> EntityRef:
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
    nodes = [{"id": instance.name, "component_vlnv": instance.component_vlnv} for instance in design.instances]
    edges: list[dict[str, typing.Any]] = []
    for connection in design.connections:
        endpoints = connection.interface_endpoints if connection.kind == "interface" else connection.port_endpoints
        for endpoint in endpoints[1:]:
            if endpoints:
                edges.append({"connection": connection.name, "kind": connection.kind, "from": endpoints[0].instance_name, "to": endpoint.instance_name})
    return {"design_id": design.ref.entity_id, "nodes": nodes, "edges": edges}


def _jsonable(value: typing.Any) -> typing.Any:
    if isinstance(value, pydantic.BaseModel):
        return {key: _jsonable(item) for key, item in value.model_dump(mode="json").items()}
    if dataclasses.is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value) if not field.name.startswith("_")}
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


_EDITOR_HTML = """<!doctype html><html><head><meta charset='utf-8'><title>spec2gds V1 Editor</title>
<style>body{font:14px system-ui;margin:0;display:grid;grid-template-columns:190px 1fr}nav{padding:16px;background:#172033;color:#fff}button,input,textarea{box-sizing:border-box;width:100%;margin:6px 0;padding:8px}main{padding:20px;max-width:1000px}pre{white-space:pre-wrap;background:#f4f6f9;padding:12px;max-height:50vh;overflow:auto}textarea{height:170px;font:12px ui-monospace,monospace}.row{display:flex;gap:8px}.row>*{flex:1}</style></head>
<body><nav><h3>V1 Editor</h3><button onclick="show('components')">Components</button><button onclick="show('designs')">Designs / topology</button><button onclick="show('narrative')">Narrative</button><button onclick="show('executions')">Action executions</button><button onclick="show('artifacts')">Artifacts / reports</button><button onclick="show('diagnostics')">Diagnostics</button></nav>
<main><h1>spec2gds V1</h1><p>Open a deterministic V1 package, inspect its source graph, and apply a validated entity-targeted transaction.</p>
<div class='row'><input id='path' placeholder='/absolute/path/to/design.spec'><button onclick='openPackage()'>Open package</button></div>
<textarea id='ops' placeholder='Transaction operations JSON, for example: [{"type":"upsert_narrative_block","block":{"block_id":"note","type":"paragraph","text":"Architect note"}}]'></textarea><button onclick='applyTransaction()'>Apply transaction</button>
<pre id='data'>No V1 package is open.</pre></main>
<script>let snapshot=null;const output=()=>document.querySelector('#data');async function body(r){let j=await r.json();if(!r.ok)throw new Error(typeof j.detail==='string'?j.detail:JSON.stringify(j.detail));return j}async function openPackage(){try{snapshot=await body(await fetch('/documents/open',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({path:document.querySelector('#path').value})}));output().textContent=JSON.stringify(snapshot,null,2)}catch(e){output().textContent=e}}async function show(name){try{output().textContent=JSON.stringify(await body(await fetch('/'+name)),null,2)}catch(e){output().textContent=e}}async function applyTransaction(){try{if(!snapshot)throw new Error('Open a package first.');let ops=JSON.parse(document.querySelector('#ops').value);let result=await body(await fetch('/transactions',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({expected_source_revision_hash:snapshot.source_revision_hash,operations:ops})}));snapshot=result.snapshot;output().textContent=JSON.stringify(result,null,2)}catch(e){output().textContent=e}}</script></body></html>"""

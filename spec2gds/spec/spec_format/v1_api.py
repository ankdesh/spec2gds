"""Production V1 local API and browser editor for deterministic ``.spec`` files.

The module is deliberately the only HTTP composition root.  It translates
JSON requests into immutable SpecIR reads, validated source transactions, and
activity-store operations; the browser never receives mutable package objects.

Reviewer path: V1Session owns package/journal identity and guarded saves;
create_app mounts reads, transactions and event projections. The editor's visible
session is distinct from packages reopened by immutable Assistant owner keys.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import fcntl
import json
import os
import threading
import time
import typing
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import pydantic
from spec2gds_runtime import StructuredLogger

from spec2gds.service_registry import load_service_registry
from spec2gds.spec.activities import (
    ActivitySnapshot,
    SpecExtensionRegistry,
    activity_availability,
    load_extension_modules,
)
from spec2gds.spec.activities.contracts import ActivityAvailability, ActivityResult
from spec2gds.spec.activities.reference import specification_summary
from spec2gds.spec.activities.rtl import register_extensions as register_rtl
from spec2gds.spec.activities.systemc_at import register_extensions as register_systemc_at
from spec2gds.spec.activities.systemc_rtl import (
    register_extensions as register_systemc_rtl,
)
from spec2gds.spec.spec_format.actions import (
    ActionRegistry,
    ActionService,
    ActivityExecutionRecord,
    ActivityStore,
    ArtifactRef,
    ArtifactSidecar,
    AssistantChangeDecision,
    ChangeProposal,
    _decode_operations,
)
from spec2gds.spec.spec_format.activity_jobs import ActivityJobManager, JobEnvelope
from spec2gds.spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.spec.spec_format.assistant import (
    SpecChangeProposal,
    build_assistant_context,
    build_document_assistant_context,
    preview_assistant_proposal,
)
from spec2gds.spec.spec_format.assistant_context_pages import build_context_page
from spec2gds.spec.spec_format.assistant_integration import ASSISTANT_ACTIONS, integration_metadata
from spec2gds.spec.spec_format.assistant_operation_contract import operation_contract
from spec2gds.spec.spec_format.catalog_import import (
    CatalogClient,
    CatalogImportRequest,
    CatalogUnavailable,
    origins,
    prepare_import,
)
from spec2gds.spec.spec_format.circuit_adapter import (
    CircuitAdapterError,
    CircuitDesignerConnectionError,
    compile_circuit_sync_operations,
    project_source_to_circuit,
    publish_circuit_document,
    register_circuit_source_binding,
    source_session_document_id,
)
from spec2gds.spec.spec_format.document import build_a2ui_batch, build_document_projection
from spec2gds.spec.spec_format.ir import (
    ConnectionIR,
    EndpointSliceIR,
    ExternalPortEndpointIR,
    InstanceIR,
    InterfaceEndpointIR,
    PortEndpointIR,
    SpecRevision,
)
from spec2gds.spec.spec_format.models import EntityRef, NarrativeBlock, new_entity_id
from spec2gds.spec.spec_format.naming import reference_name
from spec2gds.spec.spec_format.proposal_service import (
    ProposalApplyError,
    apply_assistant_proposal,
    reconcile_assistant_receipts,
)
from spec2gds.spec.spec_format.spec_service_store import (
    SpecServiceBindings,
    SpecServiceJournal,
    document_key,
)
from spec2gds.spec.spec_format.sv_validation import cached_revision_sections
from spec2gds.spec.spec_format.transactions import (
    AddAsset,
    AddComponentPort,
    AddEntryDesign,
    ClearInternalDesign,
    CreateHardware,
    DeleteComponentPort,
    DeleteConnection,
    DeleteDocument,
    DeleteInstance,
    DeleteNarrativeBlock,
    DeleteParameter,
    DeleteSection,
    RemoveAsset,
    RemoveEntryDesign,
    ReorderConnections,
    ReorderInstances,
    ReorderNarrativeBlocks,
    SetDocumentTitle,
    SetHardwareMetadata,
    SetInternalDesign,
    SetNarrativeLinks,
    SpecEditTransaction,
    StructuredPortInput,
    TransactionalPortInput,
    UpdateComponentPort,
    UpdateParameter,
    UpsertConnection,
    UpsertDocumentXml,
    UpsertInstance,
    UpsertNarrativeBlock,
    UpsertSection,
    WirePortInput,
)


from spec2gds.spec.spec_format.hosted_files import SpecFilesystem
from spec2gds.spec.spec_format.edit_access import SpecEditAccess, EditAccessError

_request_context: ContextVar[dict] = ContextVar("spec_request", default={})


class OpenDocumentRequest(pydantic.BaseModel):
    """Select one existing V1 package and its optional artifact sidecar."""

    path: str
    sidecar_root: str | None = None
    context_id: str | None = None
    participant_id: str | None = None


class CreateDocumentRequest(pydantic.BaseModel):
    """Create and activate an empty deterministic V1 package."""

    path: str
    title: str | None = None
    document_id: str | None = None
    sidecar_root: str | None = None
    request_id: str | None = None
    derive_named_path: bool = False


class CopyDocumentRequest(pydantic.BaseModel):
    source_key: str
    expected_source_revision_hash: str
    path: str
    title: str
    request_id: str


class EditAccessRequest(pydantic.BaseModel):
    context_id: str | None = None
    participant_id: str | None = None


class CreateDirectoryRequest(pydantic.BaseModel):
    """Create one child folder for the editor's server-local directory picker."""

    parent: str
    name: str


class TransactionRequest(pydantic.BaseModel):
    """Optimistic source edit request expressed in the public operation vocabulary."""

    expected_source_revision_hash: str
    operations: list[dict[str, typing.Any]]
    validation_mode: typing.Literal["strict", "authoring"] = "strict"


class ActionInputRequest(pydantic.BaseModel):
    """Normalized action inputs and optional immutable input artifacts."""

    inputs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    input_artifact_ids: list[str] = pydantic.Field(default_factory=list)


class ActivityExecutionRequest(pydantic.BaseModel):
    """Revision guard for one entity-scoped Activity launch."""

    expected_source_revision_hash: str


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


class CircuitRecoveryRequest(pydantic.BaseModel):
    expected_lease_id: str = pydantic.Field(min_length=1)
    owner_id: str = pydantic.Field(min_length=1)


class CircuitLaunchRequest(pydantic.BaseModel):
    """Select one source component or design to project into Circuit Designer."""

    entity_kind: typing.Literal["component", "design"]
    entity_id: str
    recovery: CircuitRecoveryRequest | None = None


class CircuitSourceSyncRequest(pydantic.BaseModel):
    """Candidate Circuit document submitted by the bound Circuit service."""

    request_id: str
    base_source_revision_hash: str
    candidate_document: dict[str, typing.Any] | None = None


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


class AssistantDocumentLaunchRequest(pydantic.BaseModel):
    """State of the requesting editor tab for a document-level launch."""

    attach_active_document: bool = True


class SpecDiskConflict(ValueError):
    """The open editor snapshot no longer matches the package on disk."""


class HostedArtifactSidecar(ArtifactSidecar):
    """Keep generated artifact reads and writes below the hosted root."""
    def __init__(self, root: str, filesystem: SpecFilesystem) -> None:
        super().__init__(root)
        self.filesystem = filesystem

    def ingest(self, data: bytes) -> tuple[str, str]:
        digest = "sha256:" + sha256(data).hexdigest()
        locator = self.locator(digest)
        target = self.path_for_locator(locator)
        self.filesystem.ensure_directory(target.parent)
        try:
            self.filesystem.publish(target, data, spec=False)
        except FileExistsError:
            if self.filesystem.read(target, spec=False) != data:
                raise ValueError("Content-addressed sidecar collision.")
        return digest, locator

    def read(self, artifact: ArtifactRef) -> bytes:
        data = self.filesystem.read(self.path_for_locator(artifact.storage_locator), spec=False)
        if "sha256:" + sha256(data).hexdigest() != artifact.sha256:
            raise ValueError("Artifact sidecar hash mismatch.")
        return data


class V1Session:
    """One local document session that keeps source and activity concerns separate."""

    def __init__(self, path: str, sidecar_root: str | None = None, *, filesystem: SpecFilesystem | None = None) -> None:
        """Load and validate source before exposing the session to any route."""
        self.filesystem = filesystem
        self.edit_access: SpecEditAccess | None = None
        self.path = str(filesystem.path(path, spec=True) if filesystem else Path(path).expanduser().resolve())
        self.lock = _path_lock(self.path)
        data = self._read()
        self.package = SpecPackage.from_bytes(data)
        self.revision = SpecRevision.from_package(self.package)
        self.sidecar = HostedArtifactSidecar(sidecar_root or f"{self.path}.artifacts", filesystem) if filesystem else ArtifactSidecar(sidecar_root or f"{self.path}.artifacts")
        self.activity = ActivityStore(self.package, self.sidecar)
        self.actions = ActionService(ActionRegistry(), self.sidecar)
        self._disk_digest = sha256(data).hexdigest()
        self.service_document_key = document_key(self.path, self.revision.document_id)
        self._journal: SpecServiceJournal | None = None
        self.reconciled_proposals: set[str] = set()
        self.name_catalog: SpecServiceBindings | None = None
        self.verifications: dict[str, dict[str, typing.Any]] = {}

    def _read(self) -> bytes:
        return self.filesystem.read(self.path) if self.filesystem else Path(self.path).read_bytes()

    def _publish(self, package: SpecPackage) -> None:
        if self.filesystem:
            self.filesystem.publish(self.path, package.to_bytes(), replace=True)
        else:
            package.save(self.path)

    @property
    def journal(self) -> SpecServiceJournal:
        if self._journal is None:
            if self.filesystem:
                from .workspace_target import assistant_state_root
                state_root = self.filesystem.ensure_directory(assistant_state_root(Path(self.path)))
                for name in ("spec_service.sqlite3", "owner.sqlite3"):
                    self.filesystem.path(state_root / name)
            self._journal = SpecServiceJournal(self.path)
        return self._journal

    def refresh_from_disk(self) -> bool:
        """Reload authoritative disk state without changing a browser's draft."""
        with self.lock:
            data = self._read()
            digest = sha256(data).hexdigest()
            if digest == self._disk_digest:
                return False
            package = SpecPackage.from_bytes(data)
            if package.manifest.document_id != self.revision.document_id:
                raise ValueError("Bound package was replaced by a different document.")
            revision = SpecRevision.from_package(package)
            changed = revision.source_revision_hash != self.revision.source_revision_hash
            self.package = package
            self.revision = revision
            self.activity = ActivityStore(package, self.sidecar)
            self._disk_digest = digest
            return changed

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
            raise ValueError("Spec name is required.")
        package = SpecPackage.create(document_id, title=title.strip() if title is not None else destination.stem)
        if destination.exists():
            raise FileExistsError(f"Refusing to replace existing specification package: {destination}")
        package.save(str(destination))
        return cls(str(destination), sidecar_root)

    @contextmanager
    def _guarded_save(self) -> typing.Iterator[None]:
        """Serialize cross-process writers and reject an externally changed package."""
        context = _request_context.get()
        access = self.edit_access.guard(self.service_document_key, context.get("context_id"), context.get("participant_id")) if self.edit_access else nullcontext()
        parent_context = self.filesystem.directory(Path(self.path).parent.relative_to(self.filesystem.root)) if self.filesystem else nullcontext(None)
        with self.lock, access, parent_context as parent:
            lock_path = Path(self.path).name + ".lock" if parent is not None else self.path + ".lock"
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(fd, "rb") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    current = sha256(self._read()).hexdigest()
                    if current != self._disk_digest:
                        raise SpecDiskConflict("Specification changed on disk; refresh from disk before saving.")
                    yield
                    self._disk_digest = sha256(self._read()).hexdigest()
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def save(self) -> None:
        """Persist source and activity using the package's deterministic writer."""
        with self._guarded_save():
            self._publish(self.package)

    def commit_revision(self, revision: SpecRevision) -> None:
        """Adopt validated source while retaining activity, which is not source state."""
        from contextlib import nullcontext
        reservation = self.name_catalog.reserve_name(self.path, revision.document_id, revision.narrative.title) if self.name_catalog else nullcontext()
        with self._guarded_save(), reservation:
            next_package = revision.to_package()
            if "activity/v1/actions.json" in self.package.files:
                next_package.files["activity/v1/actions.json"] = self.package.files["activity/v1/actions.json"]
            self._publish(next_package)
            self.package = next_package
            self.revision = SpecRevision.from_package(self.package)
            self.activity = ActivityStore(self.package, self.sidecar)

    def commit_assistant_revision(
        self,
        revision: SpecRevision,
        decision: AssistantChangeDecision,
    ) -> None:
        """Atomically save source and its accepted assistant decision together."""
        from contextlib import nullcontext
        reservation = self.name_catalog.reserve_name(self.path, revision.document_id, revision.narrative.title) if self.name_catalog else nullcontext()
        with self._guarded_save(), reservation:
            next_package = revision.to_package()
            if "activity/v1/actions.json" in self.package.files:
                next_package.files["activity/v1/actions.json"] = self.package.files[
                    "activity/v1/actions.json"
                ]
            next_activity = ActivityStore(next_package, self.sidecar)
            next_activity.record_assistant_change(decision)
            self._publish(next_package)
            self.package = next_package
            self.revision = SpecRevision.from_package(next_package)
            self.activity = ActivityStore(next_package, self.sidecar)


_PATH_LOCKS: dict[str, threading.RLock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def _path_lock(path: str) -> threading.RLock:
    canonical = str(Path(path).expanduser().resolve())
    with _PATH_LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(canonical, threading.RLock())


def _product_activity_registry(extension_modules: tuple[str, ...]) -> SpecExtensionRegistry:
    registry = SpecExtensionRegistry()
    registry.register_activity(specification_summary)
    register_rtl(registry)
    register_systemc_at(registry)
    register_systemc_rtl(registry)
    return load_extension_modules(extension_modules, registry)


def create_app(require_designer_approval: bool | None = None, *, require_human_approval: bool | None = None, service_config: Path | None = None, service_registry: typing.Any = None, spec_root: str | Path | None = None) -> typing.Any:
    """Create the production local V1 API; only the deterministic source format is accepted."""
    try:
        import fastapi
        import fastapi.responses
        import fastapi.staticfiles
    except Exception as exc:  # pragma: no cover - import environment guard.
        raise RuntimeError("FastAPI is required for the V1 local editor API.") from exc

    app = fastapi.FastAPI(title="spec2hw V1 Hardware Specification API")
    approval_policy = "review" if (
        require_designer_approval if require_designer_approval is not None
        else require_human_approval if require_human_approval is not None
        else os.environ.get("SPEC2GDS_REQUIRE_DESIGNER_APPROVAL", os.environ.get("SPEC2GDS_REQUIRE_HUMAN_APPROVAL", "0")) == "1"
    ) else "automatic"
    bindings = SpecServiceBindings()

    @app.exception_handler(EditAccessError)
    async def edit_access_error(_request: typing.Any, exc: EditAccessError) -> typing.Any:
        return fastapi.responses.JSONResponse(status_code=423, content={"detail": {"code": "EDIT_ACCESS_REQUIRED", "message": str(exc)}})

    @app.exception_handler(SpecDiskConflict)
    async def disk_conflict_handler(_request: typing.Any, exc: SpecDiskConflict) -> typing.Any:
        return fastapi.responses.JSONResponse(status_code=409, content={"detail": str(exc)})
    registry = service_registry or load_service_registry(service_config)
    root_path = Path(spec_root or registry.config["spec_editor"]["spec_root"])
    if spec_root is None and root_path.name == "specs":
        root_path.mkdir(parents=True, exist_ok=True)
    filesystem = SpecFilesystem(root_path)
    bindings.filesystem = filesystem
    access = SpecEditAccess(bindings.path.with_name("edit-access.sqlite3"))
    app.state.filesystem = filesystem
    app.state.edit_access = access
    activity_registry = _product_activity_registry(registry.activities.extension_modules)
    logger = StructuredLogger("spec-editor", registry.logging)
    app.state.structured_logger = logger

    def named_execution(item: typing.Any, session: V1Session) -> dict[str, typing.Any]:
        from spec2gds.spec.spec_format.naming import presentation_text, reference_name
        payload = _jsonable(item)
        try:
            payload["title"] = (activity_registry.activity(item.activity_id).definition.title
                                if hasattr(item, "activity_id") else session.actions.registry.get(item.action_id).title)
        except KeyError:
            payload["title"] = "Activity" if hasattr(item, "activity_id") else "Action"
        target = getattr(item, "target", None)
        if target:
            try:
                payload["target_name"] = reference_name(session.revision, target)
            except KeyError:
                payload["target_name"] = "Unavailable target"
        report = payload.get("report", {})
        payload["presentation_summary"] = presentation_text(session.revision, str(report.get("summary", "")))
        payload["presentation_warnings"] = [presentation_text(session.revision, str(value)) for value in report.get("warnings", [])]
        payload["presentation_diagnostics"] = [presentation_text(session.revision, str(value)) for value in payload.get("diagnostics", [])]
        return payload

    def service_urls() -> dict[str, dict[str, str]]:
        return registry.public_dict()

    @app.middleware("http")
    async def log_request(request: typing.Any, call_next: typing.Any) -> typing.Any:
        """Record one request outcome and propagate a cross-service correlation ID."""
        # Canonical query names take precedence over the legacy V1 transport alias.
        from urllib.parse import parse_qsl, urlencode
        query = parse_qsl(request.scope.get("query_string", b"").decode(), keep_blank_values=True)
        canonical = [value for key, value in query if key == "service_document_key"]
        if canonical:
            query = [(key, value) for key, value in query if key not in {"service_document_key", "owner_document_key"}]
            query.append(("owner_document_key", canonical[-1]))
            request.scope["query_string"] = urlencode(query).encode()
        values = dict(query)
        token = _request_context.set({"key": values.get("owner_document_key"),
            "context_id": request.headers.get("x-spec-edit-context") or values.get("edit_context_id"),
            "participant_id": request.headers.get("x-spec-participant") or values.get("edit_participant_id"),
            "write": request.method not in {"GET", "HEAD", "OPTIONS"} and not request.url.path.endswith(("/preview", "/preconditions", "/verify", "/launch", "/launch/document", "/resolve")) and not request.url.path.startswith("/documents/edit-access")})
        correlation_id = request.headers.get("x-request-id") or uuid4().hex
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as reason:
            _request_context.reset(token)
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
        _request_context.reset(token)
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
        "sessions": {},
        "source_event_sequence": 0,
        "source_event": None,
        "circuit_source_bindings": {},
        "circuit_source_results": {},
    }

    def finalize_activity(
        envelope: JobEnvelope,
        result: ActivityResult | None,
    ) -> ActivityExecutionRecord:
        """Persist a terminal Activity record and validated result into its owning package."""
        lock = _path_lock(envelope.package_path)
        with lock:
            _request_context.set({"context_id": envelope.edit_context_id, "participant_id": envelope.record.execution_id})
            filesystem.path(envelope.package_path, spec=True)
            session = V1Session(envelope.package_path, envelope.sidecar_root, filesystem=filesystem)
            session.edit_access = access
            session.refresh_from_disk()
            if session.revision.document_id != envelope.record.target.document_id:
                raise ValueError("Activity result package identity no longer matches its snapshot.")
            artifact_ids: list[str] = []
            if result is not None:
                definition = activity_registry.activity(envelope.record.activity_id).definition
                existing_artifacts = tuple(
                    item for item in session.activity.state.artifacts
                    if item.producer_execution_id == envelope.record.execution_id
                )
                if existing_artifacts:
                    artifact_ids.extend(item.artifact_id for item in existing_artifacts)
                else:
                    for output in result.artifacts:
                        if output.role not in definition.artifact_roles:
                            raise ValueError(f"Activity returned an undeclared artifact role: {output.role}")
                        digest, locator = session.sidecar.ingest(output.data)
                        artifact = ArtifactRef(
                            artifact_id=new_entity_id("artifact"),
                            role=output.role,
                            kind="file",
                            media_type=output.media_type,
                            sha256=digest,
                            size=output.size,
                            storage_locator=locator,
                            producer_execution_id=envelope.record.execution_id,
                            producer_action_id=envelope.record.activity_id,
                            source_revision_hash=envelope.record.source_revision_hash,
                            source_entities=output.source_entities,
                            toolchain_identity=(
                                f"{envelope.record.activity_id}/{envelope.record.activity_version}"
                            ),
                        )
                        session.activity._append_artifacts((artifact,))
                        artifact_ids.append(artifact.artifact_id)
                if not any(
                    proposal.producer_execution_id == envelope.record.execution_id
                    for proposal in session.activity.state.proposals
                ):
                    for draft in result.proposals:
                        _decode_operations(draft.operations)
                        session.activity._append_proposals((ChangeProposal(
                            proposal_id=new_entity_id("proposal"),
                            base_source_revision_hash=envelope.record.source_revision_hash,
                            producer_execution_id=envelope.record.execution_id,
                            rationale=draft.rationale,
                            operations=draft.operations,
                        ),))
            updated = envelope.record.model_copy(update={"artifact_ids": tuple(artifact_ids)})
            session.activity.replace_activity_execution(updated)
            session.activity.save()
            session.save()
            return updated

    activity_jobs = ActivityJobManager(
        activity_registry,
        registry.activities.workspace_root,
        finalize_activity, edit_access=access, filesystem=filesystem,
    )
    app.state.activity_jobs = activity_jobs

    app.router.add_event_handler("shutdown", activity_jobs.close)
    editor_root = Path(__file__).with_name("editor_dist")
    editor_asset_version = sha256(
        b"".join(
            (editor_root / "assets" / name).read_bytes()
            for name in ("index.js", "index.css")
        )
    ).hexdigest()[:12]
    # StaticFiles is mounted from a package-relative path so launching the API
    # from another working directory cannot silently break the editor.
    app.mount(
        "/editor-assets",
        fastapi.staticfiles.StaticFiles(directory=editor_root),
        name="editor-assets",
    )
    def active() -> V1Session:
        """Resolve this request's exact file, without a shared active Spec."""
        key = _request_context.get().get("key")
        if not key:
            raise fastapi.HTTPException(status_code=400, detail="Select an exact Spec binding.")
        return bound_session(key)

    def register_session(session: V1Session, sidecar_root: str | None = None, *, origin: str = "editor") -> V1Session:
        bindings.register(session.path, session.revision.document_id, sidecar_root)
        session.name_catalog = bindings
        session.edit_access = access
        state["sessions"][session.service_document_key] = session
        session.journal.observe(_source_event(session, origin, []), seed=True)
        reconcile_session(session)
        return session

    def load_file(path: str, sidecar_root: str | None = None) -> V1Session:
        canonical = filesystem.path(path, spec=True)
        expected = str(canonical) + ".artifacts"
        if sidecar_root is not None and str(filesystem.path(sidecar_root)) != expected:
            raise ValueError("Artifacts must use this Spec's own artifact directory.")
        filesystem.path(expected)
        return V1Session(str(canonical), expected, filesystem=filesystem)

    def in_root(path: str) -> bool:
        try:
            filesystem.path(path, spec=True)
            return True
        except (OSError, ValueError):
            return False

    def access_snapshot(session: V1Session) -> dict:
        context = _request_context.get()
        return {**_snapshot(session), "relative_path": str(Path(session.path).relative_to(filesystem.root)),
                "edit_access": access.status(session.service_document_key, context.get("context_id"), context.get("participant_id"))}

    def bound_session(owner_document_key: str | None = None, document_id: str | None = None) -> V1Session:
        owner_document_key = owner_document_key or _request_context.get().get("key")
        if owner_document_key is None and document_id is not None:
            matches = [record for record in bindings.matching(document_id) if in_root(record["path"])]
            if len(matches) != 1:
                raise fastapi.HTTPException(status_code=409, detail={
                    "error_code": "BINDING_REQUIRED", "document_id": document_id,
                    "message": "Select an exact package binding; the document ID is absent or ambiguous.",
                })
            owner_document_key = matches[0]["key"]
        if owner_document_key is None:
            session = active()
        else:
            record = bindings.get(owner_document_key)
            if record is None or not in_root(record["path"]):
                raise fastapi.HTTPException(status_code=404, detail="Unknown package binding.")
            session = state["sessions"].get(owner_document_key)
            if session is None:
                try:
                    session = register_session(load_file(record["path"], record["sidecar_root"]), record["sidecar_root"])
                except (OSError, ValueError) as exc:
                    raise fastapi.HTTPException(status_code=409, detail={"error_code": "BINDING_UNAVAILABLE", "message": str(exc)}) from exc
                if session.service_document_key != owner_document_key:
                    raise fastapi.HTTPException(status_code=409, detail="Bound package identity changed.")
                state["sessions"][owner_document_key] = session
        request_context = _request_context.get()
        if request_context.get("write") and access.status(session.service_document_key, request_context.get("context_id"), request_context.get("participant_id"))["mode"] != "edit":
            raise EditAccessError("This Spec is read-only. Resume editing or create a copy.")
        try:
            filesystem.path(session.path, spec=True)
            changed = session.refresh_from_disk()
        except (OSError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=409, detail={"error_code": "BINDING_UNAVAILABLE", "message": str(exc)}) from exc
        if document_id is not None and document_id != session.revision.document_id:
            raise fastapi.HTTPException(status_code=409, detail="Proposal and package binding identify different documents.")
        if changed:
            register_session(session, origin="external")
            _publish_source_event(state, session, origin="external", affected_entities=[])
        reconcile_session(session)
        return session

    def reconcile_session(session: V1Session) -> None:
        """Repair interrupted journal writes from atomically saved decisions."""
        reconcile_assistant_receipts(session)

    def ref(kind: str, entity_id: str) -> EntityRef:
        """Build a document-local stable entity reference from route segments."""
        session = active()
        try:
            return EntityRef(document_id=session.revision.document_id, entity_id=entity_id, entity_kind=kind)
        except pydantic.ValidationError as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    def result_or_error(result: typing.Any, session: V1Session | None = None) -> dict[str, typing.Any]:
        """Commit a successful transaction or map diagnostics to HTTP status."""
        session = session or active()
        if result.succeeded and result.revision is not None:
            try:
                session.commit_revision(result.revision)
            except ValueError as exc:
                raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc
            _publish_source_event(state, session, origin="editor", affected_entities=[])
            return {
                "committed": True,
                "snapshot": _snapshot(session),
                "section_validation": [item.as_json() for item in result.section_validation],
            }
        status = 409 if any("Stale" in item or "stale" in item for item in result.diagnostics) else 422
        raise fastapi.HTTPException(status_code=status, detail={
            "diagnostics": list(result.diagnostics),
            "section_validation": [item.as_json() for item in result.section_validation],
        })

    @app.post(ASSISTANT_ACTIONS["resolve_interface"]["path"])
    def resolve_assistant_interface(payload: dict[str, typing.Any]) -> dict[str, typing.Any]:
        from spec2gds.spec.spec_format.rtl_interface import resolve_interface
        try:
            return resolve_interface(**payload)
        except (ValueError, TypeError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/assistant/integration-metadata")
    def assistant_integration_metadata() -> dict[str, typing.Any]:
        return integration_metadata()

    @app.get(ASSISTANT_ACTIONS["health"]["path"])
    def health() -> dict[str, str]:
        """Report server liveness and the source-format generation it serves."""
        return {"status": "ok", "format": "spec2gds-v1"}

    @app.get(ASSISTANT_ACTIONS["capabilities"]["path"])
    def assistant_capabilities() -> dict[str, typing.Any]:
        return {"schema_version": 1, "approval_policy": approval_policy,
                "stable_package_bindings": True, "document_refinement": True,
                "submission_endpoint": "/assistant/proposals/submit", "creation_receipts": True,
                "edit_contexts": True, "spec_root": str(filesystem.root)}

    @app.get("/services")
    def services() -> dict[str, typing.Any]:
        """Expose the resolved cross-application endpoints to the browser UI."""
        return {
            "schema_version": 2,
            "services": service_urls(),
            "spec_root": str(filesystem.root),
            "logging": {"enabled": registry.logging.enabled, "level": registry.logging.level},
        }

    @app.get("/filesystem/directories")
    def filesystem_directories(path: str | None = None) -> dict[str, typing.Any]:
        """List server-local directories for the editor's portable folder picker."""
        try:
            return filesystem.listing(path)
        except (OSError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail="Select an accessible directory within the Spec root.") from exc

    @app.post("/filesystem/directories")
    def create_directory(request: CreateDirectoryRequest) -> dict[str, typing.Any]:
        """Create and enter one portable child directory on the specification server."""
        name = request.name.strip()
        reserved_stem = name.split(".", 1)[0].casefold()
        invalid_name = (
            not name
            or name in {".", ".."}
            or any(character in name for character in '<>:"/\\|?*')
            or any(ord(character) < 32 for character in name)
            or name.endswith((".", " "))
            or reserved_stem in {
                "con", "prn", "aux", "nul",
                *(f"com{index}" for index in range(1, 10)),
                *(f"lpt{index}" for index in range(1, 10)),
            }
        )
        if invalid_name:
            raise fastapi.HTTPException(
                status_code=422,
                detail="Enter a valid folder name without path separators or reserved characters.",
            )
        try:
            return filesystem.mkdir(request.parent, name)
        except FileExistsError as exc:
            raise fastapi.HTTPException(
                status_code=409,
                detail=f"A file or folder named '{name}' already exists.",
            ) from exc
        except (OSError, RuntimeError, ValueError) as exc:
            raise fastapi.HTTPException(
                status_code=422,
                detail=f"Could not create folder '{name}' in {request.parent}.",
            ) from exc

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

    @app.post("/documents/edit-access/{action}")
    def document_edit_access(action: str, request: EditAccessRequest, owner_document_key: str) -> dict:
        session = bound_session(owner_document_key)
        if action == "acquire":
            return access.acquire(session.service_document_key, request.context_id, request.participant_id)
        if not request.context_id or not request.participant_id:
            raise EditAccessError("An edit context and participant are required.")
        if action == "renew":
            return access.renew(session.service_document_key, request.context_id, request.participant_id)
        if action == "release":
            access.release(session.service_document_key, request.context_id, request.participant_id)
            return {"mode": "read_only"}
        raise fastapi.HTTPException(status_code=404, detail="Unknown edit-access action.")

    def created_snapshot(session: V1Session, request_id: str | None) -> dict:
        receipt = bindings.creation_receipt(request_id) if request_id else None
        previous = json.loads(receipt["edit_access_json"]) if receipt and receipt.get("edit_access_json") else {}
        grant = access.acquire(session.service_document_key, previous.get("context_id"), previous.get("participant_id"))
        if request_id and grant["mode"] == "edit":
            bindings.remember_creation_access(request_id, grant)
        return {**access_snapshot(session), "edit_access": grant}

    @app.post(ASSISTANT_ACTIONS["create_document"]["path"])
    def create_document(request: CreateDocumentRequest) -> dict[str, typing.Any]:
        try:
            destination = str(filesystem.path(request.path, spec=True))
            if request.sidecar_root is not None and str(filesystem.path(request.sidecar_root)) != destination + ".artifacts":
                raise ValueError("Artifacts must use this Spec's own artifact directory.")
            if request.sidecar_root is not None and request.derive_named_path:
                raise ValueError("A named destination must use its default artifact directory.")
            values = {**request.model_dump(mode="json"), "path": destination}
            identity = request.document_id or new_entity_id("spec")
            reserved = False
            if request.request_id:
                destination, identity, reserved = bindings.reserve_creation(request.request_id, values)
            filesystem.path(destination, spec=True)
            if reserved and Path(destination).exists():
                session = load_file(destination, request.sidecar_root)
                if session.revision.document_id != identity:
                    raise ValueError("Creation receipt does not match the saved package.")
            else:
                from spec2gds.spec.spec_format.naming import readable_name
                title = request.title if request.title is not None else readable_name(Path(destination).stem)
                with bindings.reserve_name(destination, identity, title) as name:
                    filesystem.publish(destination, SpecPackage.create(identity, title=name).to_bytes())
                session = load_file(destination, request.sidecar_root)
            register_session(session, request.sidecar_root)
            return created_snapshot(session, request.request_id)
        except (OSError, ValueError, SpecValidationError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/documents/open")
    def open_document(request: OpenDocumentRequest) -> dict[str, typing.Any]:
        try:
            session = load_file(request.path, request.sidecar_root)
            grant = access.acquire(session.service_document_key, request.context_id or _request_context.get().get("context_id"), request.participant_id or _request_context.get().get("participant_id"))
            session.edit_access = access
            if grant["mode"] == "edit":
                from .naming import normalize_package_names, readable_name
                token = _request_context.set({**_request_context.get(), "context_id": grant["context_id"], "participant_id": grant["participant_id"]})
                original_title = session.revision.narrative.title
                normalized = False
                try:
                    with session._guarded_save(), bindings.reserve_name(session.path, session.revision.document_id, original_title or readable_name(Path(session.path).stem), normalize=True) as title:
                        package = session.revision.to_package()
                        normalized = normalize_package_names(package, title)
                        if normalized:
                            # Normalize only with exclusive edit access. Preserve
                            # completed history when adopting normalized source.
                            if "activity/v1/actions.json" in session.package.files:
                                package.files["activity/v1/actions.json"] = session.package.files["activity/v1/actions.json"]
                            session._publish(package)
                            session.package = package
                            session.revision = SpecRevision.from_package(package)
                            session.activity = ActivityStore(package, session.sidecar)
                finally:
                    _request_context.reset(token)
            register_session(session, request.sidecar_root)
            result = {**access_snapshot(session), "edit_access": grant}
            if grant["mode"] == "edit" and normalized:
                result["open_notice"] = f'Opened Spec. Its saved name changed from "{original_title}" to "{session.revision.narrative.title}" to keep names unique.' if original_title != session.revision.narrative.title else "Opened Spec. Saved names were normalized; hardware identities are unchanged."
            return result
        except (OSError, ValueError, SpecValidationError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/documents/copy-suggestion")
    def copy_suggestion(owner_document_key: str) -> dict:
        from .naming import unique_name, readable_name
        source = bound_session(owner_document_key)
        path = Path(source.path)
        names = []
        for item in filesystem.listing(str(path.parent))["specifications"]:
            try:
                names.append(SpecPackage.from_bytes(filesystem.read(item["path"])).narrative.title)
            except (OSError, ValueError):
                continue
        stem = path.stem.encode("utf-8")[:180].decode("utf-8", errors="ignore") + "-copy"
        destination = path.with_name(stem + ".spec")
        number = 2
        while destination.exists():
            destination = path.with_name(f"{stem}-{number}.spec")
            number += 1
        title = unique_name((source.revision.narrative.title or readable_name(path.stem))[:190] + " copy", names)
        return {"path": str(destination), "title": title}

    @app.post("/documents/copy")
    def copy_document(request: CopyDocumentRequest) -> dict:
        # Copy reads saved source; it does not need the source's edit context.
        token = _request_context.set({**_request_context.get(), "write": False})
        try:
            canonical_input = {**request.model_dump(mode="json"), "path": str(filesystem.path(request.path, spec=True))}
            receipt = bindings.creation_receipt(request.request_id)
            if receipt:
                recorded = json.loads(receipt["input_json"])
                if any(recorded.get(key) != value for key, value in canonical_input.items()):
                    raise ValueError("Copy request ID was reused with different values.")
                if Path(receipt["destination"]).exists():
                    copied = register_session(load_file(receipt["destination"]))
                    if copied.revision.document_id != receipt["document_id"]:
                        raise ValueError("Copy receipt does not match the saved package.")
                    return created_snapshot(copied, request.request_id)
            source = bound_session(request.source_key)
            with source.lock:
                source.refresh_from_disk()
                revision = source.revision
                if revision.source_revision_hash != request.expected_source_revision_hash:
                    raise fastapi.HTTPException(status_code=409, detail="Saved source changed. Refresh before copying.")
            destination = str(filesystem.path(request.path, spec=True))
            if destination == source.path:
                raise ValueError("Select a different destination for the copy.")
            values = canonical_input
            # Reuse durable creation reservations, including source/revision, so
            # an uncertain retry cannot create a second file or change inputs.
            values.update(document_id=revision.document_id)
            try:
                destination, identity, replay = bindings.reserve_creation(request.request_id, values)
            except ValueError as exc:
                if Path(destination).exists():
                    raise fastapi.HTTPException(status_code=409, detail="Copy destination already exists.") from exc
                raise
            if not (replay and Path(destination).exists()):
                package = revision.to_package()
                package.files = {name: value for name, value in package.files.items() if not name.startswith("activity/")}
                with bindings.reserve_name(destination, identity, request.title) as title:
                    package.narrative = package.narrative.model_copy(update={"title": title})
                    filesystem.publish(destination, package.to_bytes())
            copied = register_session(load_file(destination))
            return created_snapshot(copied, request.request_id)
        except FileExistsError as exc:
            raise fastapi.HTTPException(status_code=409, detail="Copy destination already exists.") from exc
        except (OSError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            _request_context.reset(token)

    @app.get(ASSISTANT_ACTIONS["list_documents"]["path"])
    def named_documents() -> dict[str, typing.Any]:
        from spec2gds.spec.spec_format.naming import document_name, entity_name
        documents = []
        for record in bindings.catalog():
            try:
                session = bound_session(record["key"], record["document_id"])
            except fastapi.HTTPException:
                continue
            documents.append({"document_id": session.revision.document_id, "title": document_name(session.revision),
                "service_document_key": session.service_document_key,
                "owner_document_key": session.service_document_key,
                "relative_path": str(Path(session.path).relative_to(filesystem.root)),
                "entities": [{**item.ref.model_dump(mode="json"), "title": entity_name(item)}
                    for item in (*session.revision.components, *session.revision.designs,
                                 *session.revision.bus_definitions, *session.revision.abstraction_definitions)]})
        return {"documents": documents}

    @app.get(ASSISTANT_ACTIONS["resolve_document"]["path"])
    def resolve_named_target(name: str | None = None, owner_document_key: str | None = None,
                             document_id: str | None = None, entity_name: str | None = None,
                             entity_kind: str | None = None) -> dict[str, typing.Any]:
        """Resolve human input within an explicit owner and exact package."""
        from spec2gds.spec.spec_format.naming import document_name, name_key, select_reference
        try:
            if name is not None:
                catalog = named_documents()["documents"]
                matches = [item for item in catalog if name_key(item["title"]) == name_key(name)
                           and (owner_document_key is None or item["owner_document_key"] == owner_document_key)
                           and (document_id is None or item["document_id"] == document_id)]
                if len(matches) != 1:
                    raise ValueError(f'Unknown or ambiguous document "{name}". Choose: '
                                     + ", ".join(item["title"] for item in catalog))
                owner_document_key = matches[0]["owner_document_key"]
                document_id = matches[0]["document_id"]
            if not owner_document_key and not document_id:
                raise ValueError("Select a document name or exact package before selecting an entity.")
            session = bound_session(owner_document_key, document_id)
            result = {"document_id": session.revision.document_id,
                      "service_document_key": session.service_document_key,
                      "owner_document_key": session.service_document_key,
                      "name": document_name(session.revision)}
            if entity_name is not None:
                target = select_reference(session.revision, entity_name, entity_kind)
                result.update(target.model_dump(mode="json"))
            return result
        except ValueError as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get(ASSISTANT_ACTIONS["snapshot"]["path"])
    def document_snapshot(owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """Return the complete editor-facing immutable source projection."""
        return access_snapshot(bound_session(owner_document_key))

    @app.get(ASSISTANT_ACTIONS["names"]["path"])
    def document_names(owner_document_key: str | None = None, document_id: str | None = None,
                       entity_kind: str | None = None, entity_id: str | None = None) -> dict[str, typing.Any]:
        from spec2gds.spec.spec_format.naming import document_name, reference_name
        session = bound_session(owner_document_key, document_id)
        name = document_name(session.revision)
        target_name = name
        if entity_kind and entity_id:
            try:
                target_name = reference_name(session.revision, EntityRef(document_id=session.revision.document_id,
                    entity_kind=entity_kind, entity_id=entity_id))
            except (KeyError, ValueError) as exc:
                raise fastapi.HTTPException(status_code=404, detail="The selected target was removed.") from exc
        return {"name": name, "target_name": target_name, "owner_document_key": session.service_document_key}

    def document_executions(session: V1Session) -> list[dict[str, typing.Any]]:
        """Merge saved records with current jobs for this bound Spec only."""
        legacy = [{"execution_type": "action", **named_execution(item, session)}
                  for item in session.activity.state.executions]
        persisted = {item.execution_id: item for item in session.activity.state.activity_executions}
        for item in activity_jobs.list_for_package(session.path):
            persisted[item.execution_id] = item
        return [*legacy, *[named_execution(item, session) for item in persisted.values()]]

    @app.get("/documents/view")
    def document_view(owner_document_key: str | None = None) -> dict[str, typing.Any]:
        session = bound_session(owner_document_key)
        with session.lock:
            cursor = session.journal.observe(_source_event(session, "external", []))
            activity = session.activity.state
            pending_reviews = session.journal.pending_review_ids() | {
                item.proposal_id for item in activity.proposals if item.review_status == "pending"
            }
            return {"snapshot": access_snapshot(session),
                    "a2ui": build_a2ui_batch(build_document_projection(session.revision)).model_dump(mode="json"),
                    "activity": {"executions": document_executions(session),
                                 "pending_review_count": len(pending_reviews),
                                 "artifacts": [_jsonable(item) for item in activity.artifacts],
                                 "proposals": [_jsonable(item) for item in activity.proposals],
                                 "assistant_changes": [_jsonable(item) for item in activity.assistant_changes[-50:]]},
                    "approval_policy": approval_policy, "event_cursor": cursor,
                    "source_revision_hash": session.revision.source_revision_hash}

    @app.post("/assistant/launch")
    def launch_assistant(request: AssistantLaunchRequest, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """Return the AI Assistant launch URL without making the editor depend on it."""
        session = bound_session(owner_document_key)
        target = EntityRef(document_id=session.revision.document_id, entity_kind=request.entity_kind, entity_id=request.entity_id)
        try:
            session.revision.resolve(target)
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        urls = service_urls()
        assistant_base = urls["ai_assistant"]["service_url"]
        service = urls["spec_editor"]["service_url"]
        query = urlencode(
            {
                "service_base_url": service,
                "document_id": session.revision.document_id,
                "service_document_key": session.service_document_key,
                "owner_document_key": session.service_document_key,
                "edit_context_id": _request_context.get().get("context_id") or "",
                "entity_kind": target.entity_kind,
                "entity_id": target.entity_id,
            }
        )
        return {
            "assistant_url": f"{assistant_base}/launch/spec?{query}",
            "target": _jsonable(target),
        }

    @app.post("/assistant/launch/document")
    def launch_document_assistant(
        request: AssistantDocumentLaunchRequest | None = None,
        owner_document_key: str | None = None,
    ) -> dict[str, typing.Any]:
        """Launch the Assistant, binding it when a specification is active."""
        urls = service_urls()
        session = bound_session(owner_document_key) if owner_document_key or _request_context.get().get("key") else None
        if session is None or (
            request is not None and not request.attach_active_document
        ):
            return {
                "assistant_url": f"{urls['ai_assistant']['service_url']}/launch",
                "document_id": None,
                "source_revision_hash": None,
                "scope": "unbound",
            }
        query = urlencode(
            {
                "service_base_url": urls["spec_editor"]["service_url"],
                "document_id": session.revision.document_id,
                "service_document_key": session.service_document_key,
                "owner_document_key": session.service_document_key,
                "edit_context_id": _request_context.get().get("context_id") or "",
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
    def launch_circuit(request: CircuitLaunchRequest, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """Project one design and register its revision-guarded source binding."""
        session = bound_session(owner_document_key)
        try:
            initial_projection = project_source_to_circuit(
                session.revision,
                request.entity_kind,
                request.entity_id,
            )
            request_access = _request_context.get()
            source_access = access.status(session.service_document_key, request_access.get("context_id"), request_access.get("participant_id"))
            projection_context = request_access.get("context_id") if source_access["mode"] == "edit" else uuid4().hex
            session_id = source_session_document_id(
                session.revision,
                initial_projection.editable_design_id or initial_projection.source_entity_id,
                service_document_key=session.service_document_key + ":" + projection_context,
            )
            projection = project_source_to_circuit(
                session.revision,
                request.entity_kind,
                request.entity_id,
                session_document_id=session_id,
                include_catalog=initial_projection.editable_design_id is not None,
            )
            projection.document["label"] = f"{Path(session.path).relative_to(filesystem.root)} › {projection.document['label']}"
            launched = publish_circuit_document(
                projection.document,
                service_url=service_urls()["circuit_designer"]["service_url"],
                editor_url=service_urls()["circuit_designer"]["ui_url"],
                refresh_existing=False,
            )
            token = uuid4().hex
            binding_id = f"source_{uuid4().hex}"
            current_context = _request_context.get()
            permitted = access.status(session.service_document_key, current_context.get("context_id"), current_context.get("participant_id"))["mode"] == "edit"
            participation = access.acquire(session.service_document_key, current_context.get("context_id"), "circuit:" + launched.document_id) if permitted else {"mode": "read_only"}
            writable = projection.editable_design_id is not None and permitted
            binding = {
                "schema_version": 1,
                "binding_id": binding_id,
                "source_document_id": session.revision.document_id,
                "source_name": session.revision.narrative.title,
                "source_entity_name": reference_name(session.revision, EntityRef(document_id=session.revision.document_id,
                    entity_kind=projection.source_entity_kind, entity_id=projection.source_entity_id)),
                "source_owner_document_key": session.service_document_key,
                "source_service_url": service_urls()["spec_editor"]["service_url"],
                "source_entity": {
                    "document_id": session.revision.document_id,
                    "entity_id": projection.source_entity_id,
                    "entity_kind": projection.source_entity_kind,
                },
                **({"editable_design_id": projection.editable_design_id} if projection.editable_design_id else {}),
                "base_source_revision_hash": session.revision.source_revision_hash,
                "writable": writable,
                "capabilities": ([
                    "topology", "layout", "timing", "local-components", "numeric-part-selects",
                    *(["boundary-ports"] if projection.parent_component_id else []),
                ] if writable else []),
                "omitted_bus_items": list(projection.omitted_bus_items),
                "omitted_ports": list(projection.omitted_ports),
                **({"message": "Leaf-component previews have no internal design and remain read-only."} if not writable else {}),
            }
            state["circuit_source_bindings"][token] = {
                "binding": binding,
                "entity_kind": request.entity_kind,
                "entity_id": request.entity_id,
                "session_document_id": launched.document_id,
                "edit_access": participation,
                "projection_label": projection.document["label"],
            }
            recovered = register_circuit_source_binding(
                launched.document_id,
                binding,
                service_url=service_urls()["circuit_designer"]["service_url"],
                callback_url=f"{service_urls()['spec_editor']['service_url']}/circuit-designer/source",
                token=token,
                reload_source=launched.reused_session,
                recovery=request.recovery.model_dump() if request.recovery else None,
            )
        except CircuitDesignerConnectionError as exc:
            if exc.status_code == 423:
                raise fastapi.HTTPException(status_code=423, detail={
                    "code": "lock_conflict", "message": str(exc),
                    **exc.details, "editor_url": launched.editor_url,
                }) from exc
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
            "source_binding": binding,
            **({"recovery": recovered} if recovered is not None else {}),
        }

    def circuit_source_session(record: dict[str, typing.Any]) -> V1Session:
        """Keep a Circuit binding attached to its exact package, across other opens."""
        context = record.get("edit_access", {})
        _request_context.set({**_request_context.get(), "key": record["binding"].get("source_owner_document_key"), "context_id": context.get("context_id"), "participant_id": context.get("participant_id")})
        return bound_session(record["binding"].get("source_owner_document_key"))

    def circuit_source_record(authorization: str | None) -> dict[str, typing.Any]:
        prefix = "Bearer "
        if not authorization or not authorization.startswith(prefix):
            raise fastapi.HTTPException(status_code=401, detail="Missing Circuit source-provider token.")
        record = state["circuit_source_bindings"].get(authorization[len(prefix):])
        if record is None:
            raise fastapi.HTTPException(status_code=403, detail="Unknown Circuit source-provider token.")
        if record["binding"]["source_document_id"] != circuit_source_session(record).revision.document_id:
            raise fastapi.HTTPException(status_code=409, detail="A different .spec document is active.")
        return typing.cast(dict[str, typing.Any], record)

    def circuit_source_projection(record: dict[str, typing.Any], revision: SpecRevision | None = None) -> typing.Any:
        session = circuit_source_session(record)
        projection = project_source_to_circuit(
            revision or session.revision, record["entity_kind"], record["entity_id"],
            session_document_id=record["session_document_id"], include_catalog=True,
        )
        projection.document["label"] = record["projection_label"]
        return projection

    @app.post("/circuit-designer/source/renew")
    def renew_circuit_source(authorization: str | None = fastapi.Header(default=None)) -> dict:
        record = circuit_source_record(authorization)
        session = circuit_source_session(record)
        participant = record.get("edit_access", {})
        if participant.get("mode") != "edit":
            return {"mode": "read_only"}
        return access.renew(session.service_document_key, participant["context_id"], participant["participant_id"])

    def sync_failure(code: str, message: str, revision_hash: str | None = None) -> dict[str, typing.Any]:
        return {
            "accepted": False,
            "source_revision_hash": revision_hash or active().revision.source_revision_hash,
            "diagnostics": [{"severity": "error", "code": code, "message": message}],
        }

    @app.post("/circuit-designer/source/resolve")
    def resolve_circuit_source(
        request: CircuitSourceSyncRequest,
        authorization: str | None = fastapi.Header(default=None),
    ) -> dict[str, typing.Any]:
        """Return the current authoritative projection for one registered session."""
        record = circuit_source_record(authorization)
        session = circuit_source_session(record)
        try:
            projection = circuit_source_projection(record)
        except CircuitAdapterError as exc:
            return sync_failure("source_projection_failed", str(exc), session.revision.source_revision_hash)
        record["binding"]["base_source_revision_hash"] = session.revision.source_revision_hash
        return {
            "accepted": True,
            "source_revision_hash": session.revision.source_revision_hash,
            "document": projection.document,
            "diagnostics": [],
        }

    def preview_circuit_source_change(
        request: CircuitSourceSyncRequest,
        authorization: str | None,
    ) -> tuple[dict[str, typing.Any], dict[str, typing.Any], typing.Any | None]:
        record = circuit_source_record(authorization)
        session = circuit_source_session(record)
        def fail(code: str, message: str) -> dict[str, typing.Any]:
            return sync_failure(code, message, session.revision.source_revision_hash)
        if request.base_source_revision_hash != session.revision.source_revision_hash:
            return record, fail(
                "source_revision_conflict",
                "The Spec changed after Circuit editing began. Reopen the latest source or download the draft.",
            ), None
        if request.candidate_document is None:
            return record, fail("candidate_required", "A candidate Circuit document is required."), None
        try:
            projection = circuit_source_projection(record)
            operations = compile_circuit_sync_operations(session.revision, projection, request.candidate_document)
            result = SpecEditTransaction(session.revision.source_revision_hash, operations, "authoring").apply(session.revision)
        except (CircuitAdapterError, KeyError, TypeError, ValueError, pydantic.ValidationError) as exc:
            return record, fail("source_sync_invalid", str(exc)), None
        if not result.succeeded or result.revision is None:
            return record, fail("source_sync_rejected", " · ".join(result.diagnostics)), None
        authoritative = circuit_source_projection(record, result.revision)
        response = {
            "accepted": True,
            "source_revision_hash": result.revision.source_revision_hash,
            "document": authoritative.document,
            "diagnostics": [],
            "impact": {
                "operation_count": len(operations),
                "affected_design_id": authoritative.editable_design_id,
            },
        }
        return record, response, result.revision

    @app.post("/circuit-designer/source/preview")
    def preview_circuit_source(
        request: CircuitSourceSyncRequest,
        authorization: str | None = fastapi.Header(default=None),
    ) -> dict[str, typing.Any]:
        """Validate a candidate without changing the active package."""
        record = circuit_source_record(authorization)
        replay = state["circuit_source_results"].get(
            (record["binding"]["binding_id"], request.request_id)
        )
        if replay is not None:
            return typing.cast(dict[str, typing.Any], replay)
        with circuit_source_session(record).lock:
            _, response, _ = preview_circuit_source_change(request, authorization)
            return response

    @app.post("/circuit-designer/source/commit")
    def commit_circuit_source(
        request: CircuitSourceSyncRequest,
        authorization: str | None = fastapi.Header(default=None),
    ) -> dict[str, typing.Any]:
        """Atomically commit a candidate and return its authoritative re-projection."""
        record = circuit_source_record(authorization)
        session = circuit_source_session(record)
        with session.lock:
            replay_key = (record["binding"]["binding_id"], request.request_id)
            replay = state["circuit_source_results"].get(replay_key)
            if replay is not None:
                return typing.cast(dict[str, typing.Any], replay)
            record, response, revision = preview_circuit_source_change(request, authorization)
            if not response["accepted"] or revision is None:
                return response
            session.commit_revision(revision)
            record["binding"]["base_source_revision_hash"] = revision.source_revision_hash
            _publish_source_event(
                state,
                session,
                origin="circuit-designer",
                affected_entities=[{
                    "document_id": revision.document_id,
                    "entity_id": record["binding"]["editable_design_id"],
                    "entity_kind": "design",
                }],
            )
            state["circuit_source_results"][replay_key] = response
            return response

    @app.get("/documents/a2ui")
    def document_a2ui(owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """Return a deterministic A2UI v0.9 batch for the unified document."""
        projection = build_document_projection(bound_session(owner_document_key).revision)
        return build_a2ui_batch(projection).model_dump(mode="json")

    @app.get(ASSISTANT_ACTIONS["context_entity"]["path"])
    def assistant_context(
        document_id: str,
        entity_kind: str,
        entity_id: str,
        owner_document_key: str | None = None,
        paged: bool = False,
        entity_ids: str | None = None,
        cursor: str | None = None,
    ) -> dict[str, typing.Any]:
        """Return entity-bound semantic context for the external Spec agent."""
        session = bound_session(owner_document_key, document_id)
        try:
            target = EntityRef(document_id=document_id, entity_kind=entity_kind, entity_id=entity_id)
            content = build_context_page(session.revision, target, entity_ids=_context_selection(entity_ids), cursor=cursor) if paged else build_assistant_context(session.revision, target)
            from spec2gds.spec.spec_format.naming import document_name, reference_name
            return {**content, "name": document_name(session.revision), "target_name": reference_name(session.revision, target),
                    "service_document_key": session.service_document_key,
                    "owner_document_key": session.service_document_key, "approval_policy": approval_policy}
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get(ASSISTANT_ACTIONS["context_document"]["path"])
    def assistant_document_context(document_id: str, owner_document_key: str | None = None,
                                   paged: bool = False, entity_ids: str | None = None, cursor: str | None = None) -> dict[str, typing.Any]:
        """Return document-wide context and supported refinement boundaries."""
        session = bound_session(owner_document_key, document_id)
        try:
            content = build_context_page(session.revision, entity_ids=_context_selection(entity_ids), cursor=cursor) if paged else build_document_assistant_context(session.revision)
            from spec2gds.spec.spec_format.naming import document_name
            return {**content, "name": document_name(session.revision), "owner_document_key": session.service_document_key, "approval_policy": approval_policy}
        except (TypeError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get(ASSISTANT_ACTIONS["operation_schema"]["path"])
    def assistant_operation_schema(
        document_id: str,
        scope: str,
        entity_kind: str | None = None,
        entity_id: str | None = None,
        owner_document_key: str | None = None,
    ) -> dict[str, typing.Any]:
        """Return the assistant operation schema owned by this specification."""
        session = bound_session(owner_document_key, document_id)
        target = None
        if scope == "entity":
            if not entity_kind or not entity_id:
                raise fastapi.HTTPException(status_code=422, detail="Entity scope requires entity_kind and entity_id.")
            try:
                target = EntityRef(document_id=document_id, entity_kind=entity_kind, entity_id=entity_id)
                session.revision.resolve(target)
            except (KeyError, TypeError, ValueError) as exc:
                raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        try:
            return operation_contract(
                scope, entity_kind,
                bool(target and target.entity_kind == "component" and session.revision.internal_design(target)),
            )
        except ValueError as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post(ASSISTANT_ACTIONS["preview_proposal"]["path"])
    def assistant_proposal_preview(proposal: SpecChangeProposal, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """Validate and project an assistant proposal without persisting a draft."""
        try:
            result = preview_assistant_proposal(bound_session(owner_document_key, proposal.document_id).revision, proposal)
        except (KeyError, TypeError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc
        result.pop("_revision", None)
        return result

    def commit_proposal(session: V1Session, proposal: SpecChangeProposal, mode: typing.Literal["automatic", "review"], session_id: str | None = None) -> dict[str, typing.Any]:
        session.journal.update(proposal.proposal_id, state="applying")
        try:
            result = apply_assistant_proposal(session, proposal, application_mode=mode, session_id=session_id)
        except ProposalApplyError as exc:
            session.journal.update(proposal.proposal_id, state="stale" if exc.status == 409 else "rejected", diagnostics=exc.detail)
            raise fastapi.HTTPException(status_code=exc.status, detail=exc.detail) from exc
        except SpecDiskConflict:
            session.journal.update(proposal.proposal_id, state="stale", diagnostics="Package changed on disk; reread context.")
            raise
        except OSError as exc:
            # The package may have been saved before the response/journal failed.
            # Leave an uncertain receipt for reconciliation, never claim success.
            session.journal.update(proposal.proposal_id, state="reconcile", diagnostics=str(exc))
            raise fastapi.HTTPException(status_code=503, detail=str(exc)) from exc
        except (ValueError, SpecValidationError) as exc:
            session.journal.update(proposal.proposal_id, state="rejected", diagnostics=str(exc))
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc
        session.journal.update(proposal.proposal_id, state="applied", service_result=result, diagnostics=[])
        session.reconciled_proposals.add(proposal.proposal_id)
        if not result["idempotent_replay"]:
            affected = [proposal.target.model_dump(mode="json")] if proposal.target else [
                item.ref.model_dump(mode="json") for item in (*session.revision.components, *session.revision.designs)
            ]
            _publish_source_event(
                state, session, origin="assistant", affected_entities=affected,
            )
        return result

    def stage_proposal(proposal: SpecChangeProposal, owner_document_key: str | None, session_id: str | None) -> tuple[V1Session, dict[str, typing.Any]]:
        session = bound_session(owner_document_key, proposal.document_id)
        try:
            record = session.journal.register(proposal.model_dump(mode="json"), session_id)
        except ValueError as exc:
            raise fastapi.HTTPException(status_code=409, detail=str(exc)) from exc
        if record["state"] == "applied":
            try:
                # Validate the complete replay envelope and package identity,
                # including receipts copied into another package.
                result = apply_assistant_proposal(session, proposal)
            except ProposalApplyError as exc:
                raise fastapi.HTTPException(status_code=exc.status, detail=exc.detail) from exc
            record = {**record, "service_result": result}
            return session, record
        if record["state"] == "discarded":
            raise fastapi.HTTPException(status_code=409, detail="This proposal was explicitly rejected.")
        preview = preview_assistant_proposal(session.revision, proposal)
        preview.pop("_revision", None)
        if preview["status"] != "valid":
            session.journal.update(proposal.proposal_id, state="stale" if preview["status"] == "stale" else "rejected", preview=preview, diagnostics=preview["diagnostics"])
            raise fastapi.HTTPException(status_code=409 if preview["status"] == "stale" else 422, detail=preview)
        return session, session.journal.update(proposal.proposal_id, state="ready", preview=preview, diagnostics=[])

    @app.post(ASSISTANT_ACTIONS["stage_proposal"]["path"])
    def assistant_proposal_stage(proposal: SpecChangeProposal, owner_document_key: str | None = None, session_id: str | None = None) -> dict[str, typing.Any]:
        """Import a reviewed legacy artifact without automatically applying it."""
        session = bound_session(owner_document_key, proposal.document_id)
        with session.lock:
            _, record = stage_proposal(proposal, session.service_document_key, session_id)
            if record["state"] != "applied":
                record = session.journal.update(proposal.proposal_id, requires_review=True)
            return record

    @app.post(ASSISTANT_ACTIONS["submit_proposal"]["path"])
    def assistant_proposal_submit(proposal: SpecChangeProposal, owner_document_key: str | None = None, session_id: str | None = None) -> dict[str, typing.Any]:
        """Apply automatically or persist a review, according to owner policy."""
        session = bound_session(owner_document_key, proposal.document_id)
        with session.lock:
            _, record = stage_proposal(proposal, session.service_document_key, session_id)
            if record["state"] == "applied":
                return {**record["service_result"], "idempotent_replay": True, "review_number": session.journal.get(proposal.proposal_id)["ordinal"]}
            if approval_policy == "review" or record.get("requires_review"):
                session.journal.update(proposal.proposal_id, requires_review=True)
                return {"status": "approval_required", "proposal_id": proposal.proposal_id,
                        "review_number": session.journal.get(proposal.proposal_id)["ordinal"],
                        "source_revision_hash": session.revision.source_revision_hash,
                        "preview": record["preview"]}
            return {**commit_proposal(session, proposal, "automatic", session_id),
                    "review_number": session.journal.get(proposal.proposal_id)["ordinal"]}

    @app.post(ASSISTANT_ACTIONS["apply_proposal"]["path"])
    def assistant_proposal_apply(proposal: SpecChangeProposal, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """Compatibility route; review-required Spec services require the stored-ID action."""
        if approval_policy == "review":
            raise fastapi.HTTPException(status_code=403, detail={"error_code": "APPROVAL_REQUIRED", "message": "Submit the proposal, then explicitly approve its stored ID."})
        return assistant_proposal_submit(proposal, owner_document_key)

    @app.get("/assistant/history")
    def assistant_history(owner_document_key: str | None = None, before: int | None = None, limit: int = 50) -> dict[str, typing.Any]:
        try:
            return bound_session(owner_document_key).journal.history(before, limit)
        except ValueError as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get(ASSISTANT_ACTIONS["proposal_receipt"]["path"])
    def assistant_submission(proposal_id: str, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        record = bound_session(owner_document_key).journal.get(proposal_id)
        if record is None:
            raise fastapi.HTTPException(status_code=404, detail="Unknown assistant submission.")
        return record

    @app.post(ASSISTANT_ACTIONS["approve_proposal"]["path"])
    def assistant_submission_approve(proposal_id: str, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        session = bound_session(owner_document_key)
        with session.lock:
            record = assistant_submission(proposal_id, session.service_document_key)
            if record["state"] == "applied":
                try:
                    return apply_assistant_proposal(session, SpecChangeProposal.model_validate(record["artifact"]))
                except ProposalApplyError as exc:
                    raise fastapi.HTTPException(status_code=exc.status, detail=exc.detail) from exc
            if record["state"] not in {"ready", "reconcile", "applying"}:
                raise fastapi.HTTPException(status_code=409, detail=f"Proposal is {record['state']}; reread context and submit a new proposal.")
            return commit_proposal(session, SpecChangeProposal.model_validate(record["artifact"]), "review", record["session_id"])

    @app.post(ASSISTANT_ACTIONS["reject_proposal"]["path"])
    def assistant_submission_reject(proposal_id: str, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        session = bound_session(owner_document_key)
        with session.lock:
            record = assistant_submission(proposal_id, session.service_document_key)
            if record["state"] == "applied":
                raise fastapi.HTTPException(status_code=409, detail="A saved change cannot be rejected retroactively.")
            return session.journal.update(proposal_id, state="discarded")

    @app.get("/events/history")
    def source_event_history(owner_document_key: str | None = None, after: int = 0) -> dict[str, typing.Any]:
        session = bound_session(owner_document_key)
        cursor = session.journal.observe(_source_event(session, "external", []))
        return {"events": session.journal.events_after(after),
                "event_cursor": cursor}

    @app.get("/events")
    async def source_events(owner_document_key: str | None = None, cursor: int = 0, last_event_id: str | None = fastapi.Header(default=None)) -> typing.Any:
        """Replay durable events and resynchronize on every connection."""
        session = bound_session(owner_document_key)
        key = session.service_document_key
        try:
            requested = int(last_event_id) if isinstance(last_event_id, str) else cursor
        except ValueError:
            requested = cursor

        async def events() -> typing.AsyncIterator[str]:
            observed = max(0, requested)
            # No event ID here: replay must not skip changes racing connection.
            yield f"event: source.resync\ndata: {json.dumps(_source_event(session, 'external', []))}\n\n"
            while True:
                try:
                    current = bound_session(key)
                    latest = current.journal.observe(_source_event(current, "external", []))
                    if observed > latest:
                        observed = latest
                        yield f"event: source.resync\ndata: {json.dumps(_source_event(current, 'external', []))}\n\n"
                    updates = current.journal.events_after(observed)
                    for update in updates:
                        observed = update["sequence"]
                        yield f"id: {observed}\nevent: {update.get('event_type', 'source.changed')}\ndata: {json.dumps(update)}\n\n"
                    if not updates:
                        yield ": keep-alive\n\n"
                except fastapi.HTTPException as exc:
                    yield f"event: source.unavailable\ndata: {json.dumps({'detail': exc.detail})}\n\n"
                await asyncio.sleep(1)

        return fastapi.responses.StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/activities")
    def activities() -> dict[str, typing.Any]:
        """List product Activities and isolated extension-load diagnostics."""
        key = _request_context.get().get("key")
        workspace_root = Path(bound_session(key).path + ".artifacts") / "generated" if key else registry.activities.workspace_root
        return {
            "activities": [_jsonable(item) for item in activity_registry.activities()],
            "diagnostics": [_jsonable(item) for item in activity_registry.diagnostics],
            "workspace_root": str(workspace_root),
        }

    @app.get("/entities/{kind}/{entity_id}/activities")
    def entity_activities(kind: str, entity_id: str, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """List target-compatible Activities with pure availability preflight."""
        session = bound_session(owner_document_key)
        target = EntityRef(document_id=session.revision.document_id, entity_kind=kind, entity_id=entity_id)
        try:
            session.revision.resolve(target)
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        snapshot = ActivitySnapshot.create(session.revision, target)
        values: list[dict[str, typing.Any]] = []
        for definition in activity_registry.activities():
            if not definition.scopes.supports(target):
                continue
            if definition.activity_id == "rtl.generate":
                # Discovery is a pure read. Verification runs on launch.
                availability = ActivityAvailability(available=True, diagnostics=())
            else:
                availability = activity_availability(
                    activity_registry,
                    definition.activity_id,
                    snapshot,
                )
            values.append({
                "definition": _jsonable(definition),
                "availability": _jsonable(availability),
            })
        return {"activities": values}

    @app.post(
        "/entities/{kind}/{entity_id}/activities/{activity_id}/executions",
        status_code=202,
    )
    def launch_activity(
        kind: str,
        entity_id: str,
        activity_id: str,
        request: ActivityExecutionRequest,
        owner_document_key: str | None = None,
    ) -> dict[str, typing.Any]:
        """Capture the current source revision and enqueue one Activity execution."""
        session = bound_session(owner_document_key)
        with session.lock:
            if request.expected_source_revision_hash != session.revision.source_revision_hash:
                raise fastapi.HTTPException(status_code=409, detail="Expected source revision hash is stale.")
            target = EntityRef(document_id=session.revision.document_id, entity_kind=kind, entity_id=entity_id)
            try:
                definition = activity_registry.activity(activity_id).definition
                if not definition.scopes.supports(target):
                    raise ValueError("Activity does not support the selected entity kind.")
                if activity_id == "rtl.generate":
                    from spec2gds.spec.spec_format.component_verification import verify_target
                    result = verify_target(session.revision, target)
                    session.verifications[f"{kind}:{entity_id}"] = result
                    if result["status"] != "passed":
                        unavailable = result["tool_version"] == "Unavailable" or any(
                            item["code"] in {"VERILATOR_UNAVAILABLE", "VERILATOR_TIMEOUT"}
                            for item in result["diagnostics"]
                        )
                        raise fastapi.HTTPException(status_code=503 if unavailable else 422,
                                                    detail={"verification": result})
                snapshot = ActivitySnapshot.create(session.revision, target)
                availability = activity_availability(activity_registry, activity_id, snapshot)
                if not availability.available:
                    raise ValueError("Activity is unavailable: " + "; ".join(availability.diagnostics))
                record = activity_jobs.enqueue(
                    activity_id=activity_id,
                    snapshot=snapshot,
                    package_path=session.path,
                    sidecar_root=str(session.sidecar.root),
                    workspace_root=Path(session.path + ".artifacts") / "generated",
                    edit_context_id=_request_context.get().get("context_id"),
                )
                return _jsonable(record)
            except KeyError as exc:
                raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
            except (ValueError, SpecValidationError) as exc:
                raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/activity-events")
    async def activity_events(owner_document_key: str | None = None) -> typing.Any:
        """Stream background Activity execution transitions for the active package."""
        session = bound_session(owner_document_key)
        package_path = session.path

        async def events() -> typing.AsyncIterator[str]:
            observed = 0
            while True:
                updates = await asyncio.to_thread(activity_jobs.events_after, observed, 15.0)
                if not updates:
                    yield ": keep-alive\n\n"
                    continue
                for update in updates:
                    observed = max(observed, int(update["sequence"]))
                    execution = typing.cast(dict[str, typing.Any], update["execution"])
                    envelope = activity_jobs.get(str(execution["execution_id"]))
                    if envelope is None or envelope.package_path != package_path:
                        continue
                    with session.lock:
                        payload = json.dumps(named_execution(ActivityExecutionRecord.model_validate(execution), session), separators=(",", ":"))
                    yield f"id: {observed}\nevent: activity.execution.changed\ndata: {payload}\n\n"

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

    from spec2gds_runtime.service_config import endpoint_url
    catalog = CatalogClient(endpoint_url(registry.config["spec_catalog"]["service"], registry.public_host, local=True))
    app.state.catalog_client = catalog

    def catalog_error(exc: Exception) -> typing.NoReturn:
        status = 503 if isinstance(exc, CatalogUnavailable) else 404 if isinstance(exc, KeyError) else 409 if "Stale" in str(exc) else 422
        raise fastapi.HTTPException(status_code=status, detail=str(exc)) from exc

    @app.get("/catalog/capabilities")
    def catalog_capabilities() -> dict:
        try:
            return catalog.get("/capabilities")
        except (CatalogUnavailable, KeyError, ValueError) as exc:
            catalog_error(exc)

    @app.get("/catalog/components")
    def catalog_components(q: str = "", category: str = "", implementation: str = "", functional_status: str = "", limit: int = 25, offset: int = 0) -> dict:
        try:
            return catalog.get("/components", {key: value for key, value in {"q": q, "category": category, "implementation": implementation, "functional_status": functional_status, "limit": limit, "offset": offset}.items() if value != ""})
        except (CatalogUnavailable, KeyError, ValueError) as exc:
            catalog_error(exc)

    @app.get("/catalog/components/{key}")
    def catalog_component(key: str) -> dict:
        from urllib.parse import quote
        try:
            return catalog.get("/components/" + quote(key, safe=""))
        except (CatalogUnavailable, KeyError, ValueError) as exc:
            catalog_error(exc)

    @app.get("/catalog/components/{key}/versions/{version}")
    def catalog_version(key: str, version: str) -> dict:
        from urllib.parse import quote
        try:
            details = catalog.get(f"/components/{quote(key, safe='')}/versions/{quote(version, safe='')}")
            request = CatalogImportRequest(component_key=key, version=version, package_sha256=details["package_sha256"], expected_source_revision_hash="")
            source, details = catalog.release(request)
            root = source.resolve(EntityRef.model_validate(details["metadata"]["root"]))
            return {**details, "ports": [dataclasses.asdict(p) for p in root.ports], "parameters": [dataclasses.asdict(p) for p in root.parameters]}
        except (CatalogUnavailable, KeyError, ValueError) as exc:
            catalog_error(exc)

    def catalog_import(request: CatalogImportRequest, owner_document_key: str | None, *, commit: bool) -> dict:
        from spec2gds.spec.spec_format.transactions import ImportCatalogPackage
        session = bound_session(owner_document_key)
        try:
            # Network operations do not hold the destination document lock.
            source, details = catalog.release(request)
            with session.lock:
                preview, candidate = prepare_import(session.revision, source, details, request)
                if not commit:
                    return preview
                if candidate is None:
                    raise fastapi.HTTPException(status_code=409, detail={"message": "Resolve import conflicts.", "preview": preview})
                if preview["reused"]:
                    return {"committed": False, "reused": True, "root": preview["root"], "snapshot": _snapshot(session)}
                result = SpecEditTransaction(request.expected_source_revision_hash, (ImportCatalogPackage(source, details, request),), "authoring").apply(session.revision)
                return {**result_or_error(result, session), "root": preview["root"], "reused": False}
        except (CatalogUnavailable, KeyError, ValueError) as exc:
            catalog_error(exc)

    @app.post("/catalog/imports/preview")
    def preview_catalog_import(request: CatalogImportRequest, owner_document_key: str | None = None) -> dict:
        return catalog_import(request, owner_document_key, commit=False)

    @app.post("/catalog/imports")
    def commit_catalog_import(request: CatalogImportRequest, owner_document_key: str | None = None) -> dict:
        return catalog_import(request, owner_document_key, commit=True)

    @app.post("/transactions")
    def transaction(request: TransactionRequest, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """Decode and atomically apply a revision-guarded edit transaction."""
        try:
            logger.event(
                "transactions",
                "apply_requested",
                f"Applying {len(request.operations)} specification operation(s)",
                details=request,
            )
            session = bound_session(owner_document_key)
            operations = _decode_transaction_operations(session.revision.document_id, request.operations)
        except (KeyError, ValueError, pydantic.ValidationError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc
        with session.lock:
            return result_or_error(SpecEditTransaction(request.expected_source_revision_hash, operations, request.validation_mode).apply(session.revision), session)

    @app.post("/entities/{kind}/{entity_id}/verify")
    def verify_component(kind: str, entity_id: str, request: ActivityExecutionRequest,
                         owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """Run lint only after an explicit designer request, against a guarded revision."""
        from spec2gds.spec.spec_format.component_verification import verify_target
        session = bound_session(owner_document_key)
        with session.lock:
            if request.expected_source_revision_hash != session.revision.source_revision_hash:
                raise fastapi.HTTPException(status_code=409, detail="The saved source changed. Verify the current revision.")
            try:
                target = EntityRef(document_id=session.revision.document_id, entity_kind=kind, entity_id=entity_id)
                result = verify_target(session.revision, target)
            except (KeyError, ValueError) as exc:
                raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc
            session.verifications[f"{kind}:{entity_id}"] = result
            return result

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
    def entity_actions(kind: str, entity_id: str, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """List action definitions compatible with a resolved source entity."""
        session = bound_session(owner_document_key)
        target = EntityRef(document_id=session.revision.document_id, entity_kind=kind, entity_id=entity_id)
        try:
            session.revision.resolve(target)
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "actions": [
                _jsonable(action)
                for action in session.actions.registry.list()
                if kind in action.target_entity_kinds
            ]
        }

    @app.post("/entities/{kind}/{entity_id}/actions/{action_id}/preconditions")
    def action_preconditions(kind: str, entity_id: str, action_id: str, request: ActionInputRequest, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """Validate action inputs and preconditions without executing a command."""
        session = bound_session(owner_document_key)
        try:
            action = session.actions.registry.get(action_id)
            snapshot = session.actions.create_snapshot(
                session.revision,
                action,
                EntityRef(document_id=session.revision.document_id, entity_kind=kind, entity_id=entity_id),
                request.inputs,
                tuple(request.input_artifact_ids),
                session.activity,
            )
            return {"can_execute": True, "snapshot_id": snapshot.snapshot_id, "dependency_closure": [_jsonable(item) for item in snapshot.dependency_closure]}
        except (KeyError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/entities/{kind}/{entity_id}/actions/{action_id}/executions")
    def action_execution(kind: str, entity_id: str, action_id: str, request: ActionInputRequest, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """Execute one trusted local action against an immutable snapshot."""
        session = bound_session(owner_document_key)
        try:
            execution = session.actions.execute(
                session.revision,
                session.activity,
                action_id,
                EntityRef(document_id=session.revision.document_id, entity_kind=kind, entity_id=entity_id),
                request.inputs,
                tuple(request.input_artifact_ids),
            )
            session.save()
            return _jsonable(execution)
        except SpecDiskConflict:
            raise
        except (KeyError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/executions")
    def executions(owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """List legacy actions and Activity jobs for the active package."""
        session = bound_session(owner_document_key)
        with session.lock:
            return {"executions": document_executions(session)}

    @app.get("/executions/{execution_id}")
    def execution(execution_id: str, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """Return one legacy action or Activity execution record."""
        session = bound_session(owner_document_key)
        item = next((item for item in session.activity.state.executions if item.execution_id == execution_id), None)
        if item is not None:
            return {"execution_type": "action", **_jsonable(item)}
        envelope = activity_jobs.get(execution_id)
        if envelope is not None and envelope.package_path == session.path:
            return _jsonable(envelope.record)
        activity_item = next(
            (item for item in session.activity.state.activity_executions if item.execution_id == execution_id),
            None,
        )
        if activity_item is None:
            raise fastapi.HTTPException(status_code=404, detail="Unknown execution.")
        return _jsonable(activity_item)

    @app.post("/executions/{execution_id}/cancel")
    def cancel_execution(execution_id: str, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """Cancel one queued Activity or request cooperative running cancellation."""
        envelope = activity_jobs.get(execution_id)
        if envelope is None or envelope.package_path != bound_session(owner_document_key).path:
            raise fastapi.HTTPException(status_code=404, detail="Unknown Activity execution.")
        try:
            return _jsonable(activity_jobs.cancel(execution_id))
        except KeyError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc

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
    def artifact_content(artifact_id: str, owner_document_key: str | None = None) -> typing.Any:
        """Serve verified sidecar bytes for one immutable artifact."""
        session = bound_session(owner_document_key)
        artifact = next((item for item in session.activity.state.artifacts if item.artifact_id == artifact_id), None)
        if artifact is None:
            raise fastapi.HTTPException(status_code=404, detail="Unknown artifact.")
        try:
            data = session.sidecar.read(artifact)
        except (FileNotFoundError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc
        return fastapi.Response(content=data, media_type=artifact.media_type)

    @app.get("/proposals")
    def proposals() -> dict[str, typing.Any]:
        """List review-gated change proposals for the active package."""
        return {"proposals": [_jsonable(item) for item in active().activity.state.proposals]}

    @app.get(ASSISTANT_ACTIONS["changes"]["path"])
    def assistant_changes(owner_document_key: str | None = None) -> dict[str, typing.Any]:
        """List accepted assistant decisions stored in package activity."""
        return {
            "assistant_changes": [
                _jsonable(item) for item in bound_session(owner_document_key).activity.state.assistant_changes
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
        except SpecDiskConflict:
            raise
        except (KeyError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/", include_in_schema=False)
    def root() -> typing.Any:
        """Make the visual editor the convenient default local-server page."""
        return fastapi.responses.RedirectResponse(url="/editor")

    @app.get("/editor", include_in_schema=False)
    def editor() -> typing.Any:
        """Serve the prebuilt React/A2UI editor bundled with the Python package."""
        html = (editor_root / "index.html").read_text(encoding="utf-8")
        for name in ("index.js", "index.css"):
            path = f"/editor-assets/assets/{name}"
            html = html.replace(path, f"{path}?v={editor_asset_version}")
        return fastapi.responses.HTMLResponse(
            content=html,
            headers={"Cache-Control": "no-store"},
        )

    # Normalize the service-known catalog deterministically before serving it.
    # Invalid/unavailable bindings remain catalogued for explicit recovery.
    for record in bindings.catalog():
        try:
            register_session(load_file(record["path"], record["sidecar_root"]), record["sidecar_root"])
        except (OSError, ValueError, SpecValidationError):
            continue
    @app.get("/components/{component_id}/activities")
    def component_activities(component_id: str, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        return entity_activities("component", component_id, owner_document_key)

    @app.get("/components/{component_id}/actions")
    def component_actions(component_id: str, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        return entity_actions("component", component_id, owner_document_key)

    @app.post("/components/{component_id}/actions/{action_id}/preconditions")
    def component_action_preconditions(component_id: str, action_id: str, request: ActionInputRequest, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        return action_preconditions("component", component_id, action_id, request, owner_document_key)

    @app.post("/components/{component_id}/actions/{action_id}/executions")
    def component_action_execution(component_id: str, action_id: str, request: ActionInputRequest, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        return action_execution("component", component_id, action_id, request, owner_document_key)

    @app.get("/designs/{design_id}/activities")
    def design_activities(design_id: str, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        return entity_activities("design", design_id, owner_document_key)

    @app.get("/designs/{design_id}/actions")
    def design_actions(design_id: str, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        return entity_actions("design", design_id, owner_document_key)

    @app.post("/designs/{design_id}/actions/{action_id}/preconditions")
    def design_action_preconditions(design_id: str, action_id: str, request: ActionInputRequest, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        return action_preconditions("design", design_id, action_id, request, owner_document_key)

    @app.post("/designs/{design_id}/actions/{action_id}/executions")
    def design_action_execution(design_id: str, action_id: str, request: ActionInputRequest, owner_document_key: str | None = None) -> dict[str, typing.Any]:
        return action_execution("design", design_id, action_id, request, owner_document_key)

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
        from spec2gds.spec.spec_format.assistant import normalize_operation_aliases
        raw = normalize_operation_aliases(raw)
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
            entry_design = raw.get("entry_design", True)
            if type(entry_design) is not bool or ("entry_design" in raw and entity_kind != "design"):
                raise ValueError("entry_design must be a boolean on a design creation.")
            vlnv = raw.get("vlnv")
            if vlnv is not None and not isinstance(vlnv, str):
                raise ValueError("create_entity vlnv must be a string.")
            operations.append(
                CreateHardware(
                    typing.cast(typing.Any, entity_kind),
                    str(raw.get("name", "")),
                    str(raw["entity_id"]) if raw.get("entity_id") else None,
                    tuple(InstanceIR(**item) for item in instances),
                    entry_design=entry_design,
                    vlnv=vlnv,
                )
            )
        elif kind == "set_document_title":
            operations.append(SetDocumentTitle(str(raw.get("title", ""))))
        elif kind == "set_entity_metadata":
            operations.append(SetHardwareMetadata(
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
        elif kind == "delete_component_port":
            operations.append(DeleteComponentPort(entity(raw["component"]), str(raw["name"])))
        elif kind == "update_parameter":
            value = raw.get("parameter")
            if not isinstance(value, dict):
                raise ValueError("update_parameter requires a parameter object.")
            operations.append(UpdateParameter(entity(raw["component"]), value))
        elif kind == "delete_parameter":
            operations.append(DeleteParameter(entity(raw["component"]), str(raw["name"])))
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
                        port_endpoints=tuple(
                            PortEndpointIR(
                                instance_name=item["instance_name"],
                                port_name=item["port_name"],
                                slice=EndpointSliceIR(**item["slice"]) if item.get("slice") else None,
                            )
                            for item in connection.get("port_endpoints", [])
                        ),
                        external_ports=tuple(
                            ExternalPortEndpointIR(
                                port_name=item if isinstance(item, str) else item["port_name"],
                                slice=EndpointSliceIR(**item["slice"]) if isinstance(item, dict) and item.get("slice") else None,
                            )
                            for item in connection.get("external_ports", [])
                        ),
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
            operations.append(SetNarrativeLinks(str(raw["block_id"]), tuple(EntityRef.model_validate(item) for item in raw["entity_refs"])))
        elif kind == "upsert_entity_section":
            payload = raw.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("upsert_entity_section requires a typed payload object.")
            operations.append(UpsertSection(
                parent=entity(raw.get("parent", raw.get("owner"))),
                section_type=str(raw.get("section_type", "")),
                payload=payload,
                section_id=str(raw["section_id"]) if raw.get("section_id") else None,
                type_version=int(raw.get("type_version", 1)),
            ))
        elif kind == "delete_entity_section":
            operations.append(DeleteSection(
                parent=entity(raw.get("parent", raw.get("owner"))),
                section_type=str(raw.get("section_type", "")),
                section_id=str(raw["section_id"]) if raw.get("section_id") else None,
            ))
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
    common = {"family", "description"}
    if include_name:
        common.add("name")
    description = _optional_text(value.get("description"))
    if family == "wire":
        _reject_operation_fields(value, common | {"direction", "range"}, "wire port")
        direction = str(value.get("direction", ""))
        if direction not in {"in", "out", "inout"}:
            raise ValueError("Wire port direction must be in, out, or inout.")
        return WirePortInput(
            direction=typing.cast(typing.Any, direction),
            range=_optional_text(value.get("range")),
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
            description=description,
        )
    if family == "structured":
        _reject_operation_fields(value, common | {"direction"}, "structured port")
        direction = str(value.get("direction", ""))
        if direction not in {"in", "out", "inout"}:
            raise ValueError("Structured port direction must be in, out, or inout.")
        return StructuredPortInput(
            direction=typing.cast(typing.Any, direction),
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
    from spec2gds.spec.spec_format.naming import document_name
    section_validation = cached_revision_sections(revision)
    return {
        "schema_version": "spec2gds.snapshot.v2",
        "document_id": revision.document_id,
        "name": document_name(revision),
        "service_document_key": session.service_document_key,
        "owner_document_key": session.service_document_key,
        "source_path": session.path,
        "source_revision_hash": revision.source_revision_hash,
        "components": [_jsonable(item) for item in revision.components],
        "designs": [_jsonable(item) for item in revision.designs],
        "bus_definitions": [_jsonable(item) for item in revision.bus_definitions],
        "abstraction_definitions": [_jsonable(item) for item in revision.abstraction_definitions],
        "entry_designs": [_jsonable(item) for item in revision.entry_designs()],
        "component_compositions": [_jsonable(item) for item in revision.manifest.component_compositions],
        "narrative": _jsonable(revision.narrative),
        "assets": [_jsonable(item) for item in revision.assets],
        "catalog_origins": origins(revision),
        "entity_sections": [_jsonable(item) for item in revision.entity_sections],
        "section_validation": [item.as_json() for item in section_validation],
        "verifications": [{**item, "status": item["status"] if item["source_revision_hash"] == revision.source_revision_hash else "stale"}
                          for item in session.verifications.values()],
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
    event = _source_event(session, origin, affected_entities)
    sequence = session.journal.observe(event)
    state["source_event_sequence"] = sequence
    state["source_event"] = {**event, "sequence": sequence}


def _source_event(session: V1Session, origin: str, affected_entities: list[dict[str, typing.Any]]) -> dict[str, typing.Any]:
    return {
        "document_id": session.revision.document_id,
        "service_document_key": session.service_document_key,
        "owner_document_key": session.service_document_key,
        "source_revision_hash": session.revision.source_revision_hash,
        "origin": origin,
        "affected_entities": affected_entities,
    }


def _context_selection(value: str | None) -> list[str] | None:
    if value is None:
        return None
    selected = json.loads(value)
    if not isinstance(selected, list) or not all(isinstance(item, str) for item in selected):
        raise ValueError("entity_ids must be a JSON list of strings.")
    return selected

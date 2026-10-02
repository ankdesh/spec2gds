"""Host-neutral Python contracts for Activities and Context Renderers.

Reviewer path: plugin inputs are immutable reads and constrained capabilities.
The execution host owns queue/storage/process choices. Results carry reports,
artifacts and optional proposals; a plugin result never self-approves source edits.
"""

from __future__ import annotations

import base64
import io
import json
import re
import typing
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pydantic

from spec2gds.agent_spec.activities.snapshot import ActivitySnapshotManifest
from spec2gds.agent_spec.activities.view import SpecAccess
from spec2gds.agent_spec.spec_format.models import (
    EntityKind,
    EntityRef,
    StrictModel,
    sha256_digest,
    validate_safe_path,
)

_EXTENSION_ID = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$")
_FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


class ActivityScopes(StrictModel):
    """Invocation scopes supported by one Activity definition."""

    document: bool = False
    entity_kinds: tuple[EntityKind, ...] = ()

    @pydantic.model_validator(mode="after")
    def _nonempty(self) -> "ActivityScopes":
        if not self.document and not self.entity_kinds:
            raise ValueError("An Activity must support document or entity scope.")
        if len(self.entity_kinds) != len(set(self.entity_kinds)):
            raise ValueError("Activity entity scopes must be unique.")
        return self

    def supports(self, target: EntityRef | None) -> bool:
        """Return whether this definition accepts the document or entity target."""
        return self.document if target is None else target.entity_kind in self.entity_kinds


class ActivityDefinition(StrictModel):
    """Stable catalog metadata with no execution-host configuration."""

    activity_id: str
    version: str
    title: str
    description: str
    snapshot_api_version: typing.Literal[1] = 1
    scopes: ActivityScopes
    report_schema: dict[str, typing.Any]
    artifact_roles: tuple[str, ...] = ()
    may_propose_changes: bool = False
    requires_workspace_output: bool = False

    @pydantic.field_validator("activity_id")
    @classmethod
    def _activity_id(cls, value: str) -> str:
        if not _EXTENSION_ID.fullmatch(value):
            raise ValueError("Activity ids must be lower-case namespaced identifiers.")
        return value

    @pydantic.field_validator("version")
    @classmethod
    def _version(cls, value: str) -> str:
        if not _VERSION.fullmatch(value):
            raise ValueError("Activity versions must use semantic version syntax.")
        return value

    @pydantic.model_validator(mode="after")
    def _definition(self) -> "ActivityDefinition":
        if not self.title.strip() or not self.description.strip():
            raise ValueError("Activity title and description are required.")
        if len(self.artifact_roles) != len(set(self.artifact_roles)):
            raise ValueError("Activity artifact roles must be unique.")
        return self


class ActivityAvailability(StrictModel):
    """Pure preflight result for one snapshot and Activity."""

    available: bool
    diagnostics: tuple[str, ...] = ()


class ArtifactOutput(StrictModel):
    """Portable staged artifact returned before a host chooses durable storage."""

    role: str
    name: str
    media_type: str
    sha256: str
    size: int
    data_base64: str
    source_entities: tuple[EntityRef, ...] = ()

    @pydantic.model_validator(mode="after")
    def _content(self) -> "ArtifactOutput":
        validate_safe_path(self.name)
        if not self.role.strip() or not self.media_type.strip():
            raise ValueError("Artifact role and media type are required.")
        try:
            data = base64.b64decode(self.data_base64, validate=True)
        except ValueError as exc:
            raise ValueError("Artifact data_base64 is invalid.") from exc
        if len(data) != self.size or sha256_digest(data) != self.sha256:
            raise ValueError("Artifact size or digest does not match its content.")
        return self

    @property
    def data(self) -> bytes:
        """Decode a defensive immutable content value."""
        return base64.b64decode(self.data_base64, validate=True)


class SpecChangeProposalDraft(StrictModel):
    """Review-gated typed-operation envelope produced by an Activity."""

    rationale: str
    operations: tuple[dict[str, typing.Any], ...]

    @pydantic.model_validator(mode="after")
    def _proposal(self) -> "SpecChangeProposalDraft":
        if not self.rationale.strip() or not self.operations:
            raise ValueError("Change proposals require a rationale and operations.")
        for operation in self.operations:
            if not isinstance(operation.get("type"), str) or not operation["type"].strip():
                raise ValueError("Every proposed operation requires a non-empty type.")
        return self


class ActivityResult(StrictModel):
    """Successful plugin result, independent of host-owned run status."""

    schema_version: typing.Literal["spec2gds.activity-result.v1"] = "spec2gds.activity-result.v1"
    summary: str
    report: dict[str, typing.Any]
    artifacts: tuple[ArtifactOutput, ...] = ()
    proposals: tuple[SpecChangeProposalDraft, ...] = ()
    diagnostics: tuple[str, ...] = ()

    @pydantic.field_validator("summary")
    @classmethod
    def _summary(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Activity result summary is required.")
        return value


class ContextRendererDefinition(StrictModel):
    """Catalog metadata for deterministic text rendering from SpecIR."""

    renderer_id: str
    version: str
    title: str
    scopes: ActivityScopes
    snapshot_api_version: typing.Literal[1] = 1

    @pydantic.field_validator("renderer_id")
    @classmethod
    def _renderer_id(cls, value: str) -> str:
        if not _EXTENSION_ID.fullmatch(value):
            raise ValueError("Renderer ids must be lower-case namespaced identifiers.")
        return value

    @pydantic.field_validator("version")
    @classmethod
    def _renderer_version(cls, value: str) -> str:
        if not _VERSION.fullmatch(value):
            raise ValueError("Renderer versions must use semantic version syntax.")
        return value


class RenderedContext(StrictModel):
    """Deterministic textual result suitable for an LLM or another text client."""

    schema_version: typing.Literal["spec2gds.rendered-context.v1"] = (
        "spec2gds.rendered-context.v1"
    )
    renderer_id: str
    renderer_version: str
    snapshot_id: str
    document_id: str
    source_revision_hash: str
    target: EntityRef | None = None
    text: str
    diagnostics: tuple[str, ...] = ()


class CancellationToken(typing.Protocol):
    """Minimal cooperative cancellation port supplied by any future host."""

    @property
    def cancelled(self) -> bool:
        """Report whether the host has requested cooperative cancellation."""
        ...

    def raise_if_cancelled(self) -> None:
        """Raise the host-specific cancellation exception when requested."""
        ...


class NeverCancelled:
    """Default token used by local tests and direct invocation."""

    @property
    def cancelled(self) -> bool:
        """Remain false for direct invocations that have no cancelling host."""
        return False

    def raise_if_cancelled(self) -> None:
        """Do nothing because this token can never be cancelled."""
        return None


class WorkspaceFile(StrictModel):
    """One deterministic file published through a host-owned workspace."""

    path: str
    sha256: str
    size: int

    @pydantic.field_validator("path")
    @classmethod
    def _path(cls, value: str) -> str:
        return validate_safe_path(value)


class PublishedDirectory(StrictModel):
    """Validated description of one directory committed by a workspace host."""

    relative_path: str
    tree_sha256: str
    files: tuple[WorkspaceFile, ...]

    @pydantic.field_validator("relative_path")
    @classmethod
    def _relative_path(cls, value: str) -> str:
        return validate_safe_path(value)


class ActivityWorkspaceWriter(typing.Protocol):
    """Sandboxed host capability for atomically publishing generated files."""

    def replace_directory(
        self,
        *,
        relative_path: str,
        files: typing.Mapping[str, bytes],
        generator_id: str,
        document_id: str,
        design_id: str,
    ) -> PublishedDirectory:
        """Atomically replace one validated, generator-owned relative directory."""
        ...


class ActivityOutputWriter:
    """Host-neutral convenience API for constructing validated artifacts."""

    def add_bytes(
        self,
        *,
        role: str,
        name: str,
        media_type: str,
        data: bytes,
        source_entities: tuple[EntityRef, ...] = (),
    ) -> ArtifactOutput:
        """Wrap immutable bytes with validated name, size, digest, and provenance."""
        content = bytes(data)
        return ArtifactOutput(
            role=role,
            name=validate_safe_path(name),
            media_type=media_type,
            sha256=sha256_digest(content),
            size=len(content),
            data_base64=base64.b64encode(content).decode("ascii"),
            source_entities=source_entities,
        )

    def add_text(
        self,
        *,
        role: str,
        name: str,
        text: str,
        media_type: str = "text/plain",
        source_entities: tuple[EntityRef, ...] = (),
    ) -> ArtifactOutput:
        """Create a UTF-8 text artifact through the common byte path."""
        return self.add_bytes(
            role=role,
            name=name,
            media_type=media_type,
            data=text.encode("utf-8"),
            source_entities=source_entities,
        )

    def add_json(
        self,
        *,
        role: str,
        name: str,
        value: typing.Any,
        source_entities: tuple[EntityRef, ...] = (),
    ) -> ArtifactOutput:
        """Serialize a deterministic, human-readable JSON artifact."""
        data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
        return self.add_bytes(
            role=role,
            name=name,
            media_type="application/json",
            data=data,
            source_entities=source_entities,
        )

    def add_file(
        self,
        *,
        role: str,
        path: str | Path,
        media_type: str,
        name: str | None = None,
        source_entities: tuple[EntityRef, ...] = (),
    ) -> ArtifactOutput:
        """Read one local file into a portable artifact envelope."""
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        return self.add_bytes(
            role=role,
            name=name or source.name,
            media_type=media_type,
            data=source.read_bytes(),
            source_entities=source_entities,
        )

    def add_directory(
        self,
        *,
        role: str,
        path: str | Path,
        name: str,
        source_entities: tuple[EntityRef, ...] = (),
    ) -> ArtifactOutput:
        """Package a directory as a byte-for-byte deterministic ZIP artifact."""
        source = Path(path)
        if not source.is_dir():
            raise NotADirectoryError(source)
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for candidate in sorted(path for path in source.rglob("*") if path.is_file()):
                relative = validate_safe_path(candidate.relative_to(source).as_posix())
                info = zipfile.ZipInfo(relative, date_time=_FIXED_ZIP_DATE)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, candidate.read_bytes())
        return self.add_bytes(
            role=role,
            name=name,
            media_type="application/zip",
            data=output.getvalue(),
            source_entities=source_entities,
        )


@dataclass(frozen=True)
class ActivitySelectionContext:
    """Read-only context for fast availability checks."""

    snapshot: ActivitySnapshotManifest
    spec: SpecAccess

    @property
    def target(self) -> EntityRef | None:
        """Expose the selected entity, or ``None`` for document scope."""
        return self.snapshot.scope.target


@dataclass(frozen=True)
class ActivityContext:
    """Complete host-neutral context passed to Activity logic."""

    snapshot: ActivitySnapshotManifest
    spec: SpecAccess
    outputs: ActivityOutputWriter
    cancellation: CancellationToken
    workspace: ActivityWorkspaceWriter | None = None

    @property
    def target(self) -> EntityRef | None:
        """Expose the selected entity, or ``None`` for document scope."""
        return self.snapshot.scope.target


@dataclass(frozen=True)
class ContextRenderContext:
    """Read-only context passed to a synchronous Context Renderer."""

    snapshot: ActivitySnapshotManifest
    spec: SpecAccess

    @property
    def target(self) -> EntityRef | None:
        """Expose the selected entity, or ``None`` for document scope."""
        return self.snapshot.scope.target


class Activity(typing.Protocol):
    """Python Activity plugin protocol."""

    definition: ActivityDefinition
    report_model: type[pydantic.BaseModel]

    def availability(self, context: ActivitySelectionContext) -> ActivityAvailability:
        """Run a read-only preflight before allocating outputs or a workspace."""
        ...

    def run(self, context: ActivityContext) -> ActivityResult:
        """Execute the Activity against an immutable snapshot context."""
        ...


class BaseActivity:
    """Convenient base class providing the normal availability behavior."""

    definition: ActivityDefinition
    report_model: type[pydantic.BaseModel]

    def availability(self, context: ActivitySelectionContext) -> ActivityAvailability:
        """Accept supported scopes; subclasses may add domain preflight checks."""
        if not self.definition.scopes.supports(context.target):
            return ActivityAvailability(
                available=False,
                diagnostics=("Activity does not support this snapshot scope.",),
            )
        return ActivityAvailability(available=True)


class ContextRenderer(typing.Protocol):
    """Deterministic text renderer sharing the Activity snapshot APIs."""

    definition: ContextRendererDefinition

    def render(self, context: ContextRenderContext) -> RenderedContext:
        """Render deterministic text from an immutable snapshot context."""
        ...

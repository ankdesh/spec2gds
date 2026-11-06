"""V1.3 entity-targeted external actions, sidecar artifacts, and proposals."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import typing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pydantic

from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.ir import ComponentIR, DesignIR, SpecRevision
from spec2gds.spec.spec_format.models import (
    SHA256_PATTERN,
    EntityRef,
    NarrativeBlock,
    StrictModel,
    new_entity_id,
    sha256_digest,
    validate_safe_path,
)
from spec2gds.spec.spec_format.transactions import (
    EditResult,
    SetNarrativeLinks,
    SpecEditTransaction,
    UpsertNarrativeBlock,
)

_ACTIVITY_PATH = "activity/v1/actions.json"
_BUNDLE_VERSION = 1


def _utc_now() -> str:
    """Return a stable UTC timestamp string for durable action events."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _json_bytes(value: typing.Any) -> bytes:
    """Serialize model or plain data to deterministic, human-readable JSON."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


class ActionDefinition(StrictModel):
    """A trusted local action contract, independent of SystemC or RTL tooling."""

    action_id: str
    version: str
    title: str
    target_entity_kinds: tuple[typing.Literal["component", "design"], ...]
    input_schema: dict[str, typing.Any]
    required_capabilities: tuple[str, ...] = ()
    consumed_artifact_roles: tuple[str, ...] = ()
    produced_artifact_roles: tuple[str, ...] = ()
    report_schema: dict[str, typing.Any]
    executor: tuple[str, ...]
    preconditions: tuple[str, ...] = ()
    postconditions: tuple[str, ...] = ()
    allows_change_proposals: bool = False
    timeout_seconds: float = 30.0

    @pydantic.field_validator("action_id", "version")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        """Reject identifiers that would be unusable in provenance."""
        if not value.strip():
            raise ValueError("Action id and version cannot be empty.")
        return value

    @pydantic.model_validator(mode="after")
    def _validate_contract(self) -> "ActionDefinition":
        """Enforce the minimum executable contract at registration time."""
        if not self.target_entity_kinds or not self.executor:
            raise ValueError("Actions require target entity kinds and an executor command.")
        if self.timeout_seconds <= 0:
            raise ValueError("Action timeout_seconds must be positive.")
        return self


class ArtifactRef(StrictModel):
    """Immutable metadata for sidecar content attached to stable source entities."""

    artifact_id: str
    role: str
    kind: str
    media_type: str
    sha256: str
    size: int
    storage_locator: str
    producer_execution_id: str
    producer_action_id: str
    source_revision_hash: str
    source_entities: tuple[EntityRef, ...]
    input_artifact_ids: tuple[str, ...] = ()
    parent_artifact_ids: tuple[str, ...] = ()
    toolchain_identity: str = ""
    normalized_inputs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)

    @pydantic.field_validator("sha256")
    @classmethod
    def _hash(cls, value: str) -> str:
        """Require the canonical prefixed digest representation."""
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("Artifact sha256 must use sha256:<64 lowercase hex>.")
        return value

    @pydantic.field_validator("size")
    @classmethod
    def _size(cls, value: int) -> int:
        """Reject impossible negative byte counts."""
        if value < 0:
            raise ValueError("Artifact size cannot be negative.")
        return value

    @pydantic.model_validator(mode="after")
    def _metadata(self) -> "ArtifactRef":
        """Ensure every artifact remains attributable and entity-addressable."""
        if not all((self.role, self.kind, self.media_type, self.storage_locator, self.producer_execution_id, self.producer_action_id)):
            raise ValueError("Artifact role, kind, media type, locator, and producer metadata are required.")
        if not self.source_entities:
            raise ValueError("Artifacts must attach to at least one stable source entity.")
        return self


class ActionEvent(StrictModel):
    """One immutable, ordered event in an action execution record."""

    sequence: int
    event_type: str
    timestamp: str
    payload: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


class ActionExecution(StrictModel):
    """Durable metadata for one invocation of an action definition."""

    execution_id: str
    action_id: str
    action_version: str
    snapshot_id: str
    status: typing.Literal["succeeded", "failed"]
    events: tuple[ActionEvent, ...]
    result_refs: tuple[str, ...] = ()
    report: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    diagnostics: tuple[str, ...] = ()
    toolchain_identity: str = ""


class ActivityExecutionRecord(StrictModel):
    """Durable provenance for one host-launched Activity execution."""

    execution_type: typing.Literal["activity"] = "activity"
    execution_id: str
    activity_id: str
    activity_version: str
    snapshot_id: str
    source_revision_hash: str
    target: EntityRef
    status: typing.Literal["queued", "running", "succeeded", "failed", "cancelled"]
    cancel_requested: bool = False
    created_at: str
    started_at: str = ""
    finished_at: str = ""
    events: tuple[ActionEvent, ...] = ()
    artifact_ids: tuple[str, ...] = ()
    report: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    diagnostics: tuple[str, ...] = ()
    workspace_output_path: str = ""


class ChangeProposal(StrictModel):
    """A review-gated source patch generated by an action execution."""

    proposal_id: str
    base_source_revision_hash: str
    producer_execution_id: str
    rationale: str
    operations: tuple[dict[str, typing.Any], ...]
    diagnostics: tuple[str, ...] = ()
    review_status: typing.Literal["pending", "accepted", "rejected"] = "pending"


class AssistantChangeDecision(StrictModel):
    """Minimal accepted assistant decision persisted with package activity."""

    proposal_id: str
    scope: typing.Literal["document", "entity"] = "entity"
    target: EntityRef | None = None
    base_source_revision_hash: str
    result_source_revision_hash: str
    operations_digest: str
    operations: tuple[dict[str, typing.Any], ...]
    decision: typing.Literal["accepted"] = "accepted"
    applied_at: str
    application_mode: typing.Literal["automatic", "review"] = "review"
    title: str = ""
    summary: str = ""
    rationale: str = ""
    assumptions: tuple[str, ...] = ()
    session_id: str | None = None
    service_document_key: str | None = pydantic.Field(default=None, validation_alias=pydantic.AliasChoices("service_document_key", "owner_document_key"))
    diff: tuple[dict[str, typing.Any], ...] = ()

    @pydantic.model_validator(mode="after")
    def _scope(self) -> "AssistantChangeDecision":
        if (self.scope == "entity") != (self.target is not None):
            raise ValueError("Assistant decision scope and target do not match.")
        return self


class _ActivityState(StrictModel):
    """Private serializable activity state stored inside a package's activity area."""

    version: int = 2
    artifacts: tuple[ArtifactRef, ...] = ()
    executions: tuple[ActionExecution, ...] = ()
    activity_executions: tuple[ActivityExecutionRecord, ...] = ()
    proposals: tuple[ChangeProposal, ...] = ()
    assistant_changes: tuple[AssistantChangeDecision, ...] = ()


@dataclass(frozen=True)
class ActionSnapshot:
    """Immutable action input derived from one source revision and entity target."""

    snapshot_id: str
    source_revision_hash: str
    target: EntityRef
    dependency_closure: tuple[EntityRef, ...]
    linked_narrative: tuple[NarrativeBlock, ...]
    accepted_annotations: tuple[tuple[str, bytes], ...]
    input_artifacts: tuple[ArtifactRef, ...]
    _normalized_inputs_json: str
    _revision: SpecRevision

    @property
    def normalized_inputs(self) -> dict[str, typing.Any]:
        """Return a defensive JSON-compatible copy of the normalized action inputs."""
        return typing.cast(dict[str, typing.Any], json.loads(self._normalized_inputs_json))

    def sdk(self) -> "SnapshotSdk":
        """Return a read-only Python accessor for in-process trusted actions."""
        return SnapshotSdk(self)

    def write_bundle(self, destination: str | Path, sidecar: "ArtifactSidecar") -> Path:
        """Write a language-neutral source/artifact bundle to an empty directory."""
        root = Path(destination)
        if root.exists() and any(root.iterdir()):
            raise ValueError("Snapshot bundle destination must be empty.")
        root.mkdir(parents=True, exist_ok=True)
        package = self._revision.to_package()
        closure_ids = {reference.entity_id for reference in self.dependency_closure}
        source_documents: list[dict[str, str]] = []
        for entry in package.manifest.documents:
            if entry.entity_id not in closure_ids:
                continue
            target = root / "source" / entry.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(package.files[entry.path])
            source_documents.append({"entity_id": entry.entity_id, "kind": entry.kind, "vlnv": entry.vlnv, "path": f"source/{entry.path}"})
        (root / "source" / "manifest.json").write_bytes(_json_bytes(package.manifest))
        (root / "source" / "document.json").write_bytes(_json_bytes(package.narrative))
        for asset in package.manifest.assets:
            target = root / "assets" / Path(asset.path).name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(package.files[asset.path])
        annotations: list[dict[str, str]] = []
        for path, data in self.accepted_annotations:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            annotations.append({"path": path, "sha256": sha256_digest(data)})
        input_artifacts: list[dict[str, typing.Any]] = []
        for artifact in self.input_artifacts:
            content = sidecar.read(artifact)
            filename = f"{artifact.artifact_id}-{artifact.sha256.removeprefix('sha256:')}"
            target = root / "input-artifacts" / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            input_artifacts.append({**artifact.model_dump(mode="json"), "bundle_path": f"input-artifacts/{filename}"})
        manifest = {
            "bundle_version": _BUNDLE_VERSION,
            "snapshot_id": self.snapshot_id,
            "source_revision_hash": self.source_revision_hash,
            "target": self.target.model_dump(mode="json"),
            "dependency_closure": [reference.model_dump(mode="json") for reference in self.dependency_closure],
            "source_documents": source_documents,
            "linked_narrative": [block.model_dump(mode="json") for block in self.linked_narrative],
            "accepted_annotations": annotations,
            "normalized_inputs": self.normalized_inputs,
            "input_artifacts": input_artifacts,
        }
        (root / "snapshot.json").write_bytes(_json_bytes(manifest))
        return root


class SnapshotSdk:
    """Read-only convenience view of an ``ActionSnapshot`` for Python actions."""

    def __init__(self, snapshot: ActionSnapshot) -> None:
        """Wrap one immutable snapshot without exposing mutable internals."""
        self._snapshot = snapshot

    @property
    def target(self) -> ComponentIR | DesignIR:
        """Resolve the action target from the captured revision."""
        return typing.cast(ComponentIR | DesignIR, self._snapshot._revision.resolve(self._snapshot.target))

    @property
    def inputs(self) -> dict[str, typing.Any]:
        """Return a defensive copy of normalized action inputs."""
        return json.loads(json.dumps(self._snapshot.normalized_inputs, sort_keys=True))

    def resolve(self, reference: EntityRef) -> typing.Any:
        """Resolve an entity only from the captured source revision."""
        return self._snapshot._revision.resolve(reference)

    def closure(self) -> tuple[EntityRef, ...]:
        """Return the dependency closure captured for execution."""
        return self._snapshot.dependency_closure


class ArtifactSidecar:
    """Content-addressed filesystem storage for immutable generated artifact bytes."""

    def __init__(self, root: str | Path) -> None:
        """Bind storage to one explicit filesystem root."""
        self.root = Path(root)

    def locator(self, digest: str) -> str:
        """Convert a canonical digest into its portable sidecar locator."""
        return f"sha256/{digest.removeprefix('sha256:')}"

    def path_for_locator(self, locator: str) -> Path:
        """Validate a locator before resolving it beneath the sidecar root."""
        if not re.fullmatch(r"sha256/[0-9a-f]{64}", locator):
            raise ValueError("Unsupported artifact sidecar locator.")
        return self.root / locator

    def ingest(self, data: bytes) -> tuple[str, str]:
        """Store bytes once and return their digest and stable locator."""
        digest = sha256_digest(data)
        target = self.path_for_locator(self.locator(digest))
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != data:
            raise ValueError("Content-addressed sidecar collision.")
        if not target.exists():
            target.write_bytes(data)
        return digest, self.locator(digest)

    def read(self, artifact: ArtifactRef) -> bytes:
        """Read artifact bytes and verify them against durable metadata."""
        target = self.path_for_locator(artifact.storage_locator)
        if not target.is_file():
            raise FileNotFoundError(f"Artifact sidecar content is missing: {artifact.artifact_id}")
        data = target.read_bytes()
        if sha256_digest(data) != artifact.sha256:
            raise ValueError(f"Artifact sidecar hash mismatch: {artifact.artifact_id}")
        return data


class ActivityStore:
    """Mutable activity facade that never mutates V1 source entries."""

    def __init__(self, package: SpecPackage, sidecar: ArtifactSidecar) -> None:
        """Load activity metadata while generated bytes stay in the sidecar."""
        self.package = package
        self.sidecar = sidecar
        raw = package.files.get(_ACTIVITY_PATH)
        loaded = _ActivityState.model_validate_json(raw) if raw else _ActivityState()
        self.state = loaded.model_copy(update={"version": 2})

    def save(self) -> None:
        """Persist activity without changing the source revision hash."""
        self.package.files[_ACTIVITY_PATH] = _json_bytes(self.state)

    def artifacts_for(self, target: EntityRef) -> tuple[ArtifactRef, ...]:
        """Return artifacts whose provenance names the target entity."""
        return tuple(artifact for artifact in self.state.artifacts if target in artifact.source_entities)

    def artifact_lineage(self, artifact_id: str) -> tuple[ArtifactRef, ...]:
        """Traverse parent links once, tolerating missing ancestors."""
        by_id = {artifact.artifact_id: artifact for artifact in self.state.artifacts}
        result: list[ArtifactRef] = []
        pending = [artifact_id]
        visited: set[str] = set()
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            artifact = by_id.get(current)
            if artifact is None:
                continue
            result.append(artifact)
            pending.extend(artifact.parent_artifact_ids)
        return tuple(result)

    def artifact_diagnostics(self) -> tuple[str, ...]:
        """Report missing or corrupted sidecar content without raising."""
        diagnostics: list[str] = []
        for artifact in self.state.artifacts:
            try:
                self.sidecar.read(artifact)
            except (FileNotFoundError, ValueError) as exc:
                diagnostics.append(str(exc))
        return tuple(sorted(set(diagnostics)))

    def _append_execution(self, execution: ActionExecution) -> None:
        """Append one immutable execution record."""
        self.state = self.state.model_copy(update={"executions": (*self.state.executions, execution)})

    def append_activity_execution(self, execution: ActivityExecutionRecord) -> None:
        """Append a new Activity execution without replacing an existing id."""
        if any(item.execution_id == execution.execution_id for item in self.state.activity_executions):
            raise ValueError(f"Activity execution already exists: {execution.execution_id}")
        self.state = self.state.model_copy(
            update={"activity_executions": (*self.state.activity_executions, execution)}
        )

    def replace_activity_execution(self, execution: ActivityExecutionRecord) -> None:
        """Replace one Activity execution while retaining deterministic order."""
        found = False
        values: list[ActivityExecutionRecord] = []
        for item in self.state.activity_executions:
            if item.execution_id == execution.execution_id:
                values.append(execution)
                found = True
            else:
                values.append(item)
        if not found:
            values.append(execution)
        self.state = self.state.model_copy(update={"activity_executions": tuple(values)})

    def _append_artifacts(self, artifacts: tuple[ArtifactRef, ...]) -> None:
        """Append accepted artifact metadata after content verification."""
        self.state = self.state.model_copy(update={"artifacts": (*self.state.artifacts, *artifacts)})

    def _append_proposals(self, proposals: tuple[ChangeProposal, ...]) -> None:
        """Append review-gated proposals generated by an execution."""
        self.state = self.state.model_copy(update={"proposals": (*self.state.proposals, *proposals)})

    def _replace_proposal(self, proposal: ChangeProposal) -> None:
        """Replace one proposal while preserving durable list order."""
        self.state = self.state.model_copy(
            update={"proposals": tuple(item if item.proposal_id != proposal.proposal_id else proposal for item in self.state.proposals)}
        )

    def record_assistant_change(self, decision: AssistantChangeDecision) -> None:
        """Append one accepted assistant decision, rejecting conflicting replay IDs."""
        existing = next(
            (
                item
                for item in self.state.assistant_changes
                if item.proposal_id == decision.proposal_id
            ),
            None,
        )
        if existing is not None:
            if existing.operations_digest != decision.operations_digest:
                raise ValueError("Assistant proposal ID was reused with different operations.")
            return
        self.state = self.state.model_copy(
            update={
                "assistant_changes": (*self.state.assistant_changes, decision),
            }
        )
        self.save()


class ActionRegistry:
    """Small explicit registry for trusted V1.3 local actions."""

    def __init__(self, actions: typing.Iterable[ActionDefinition] = ()) -> None:
        """Index trusted action definitions by stable action id."""
        self._actions = {action.action_id: action for action in actions}

    def register(self, action: ActionDefinition) -> None:
        """Register a definition without silently replacing an action."""
        if action.action_id in self._actions:
            raise ValueError(f"Action already registered: {action.action_id}")
        self._actions[action.action_id] = action

    def get(self, action_id: str) -> ActionDefinition:
        """Resolve a definition or raise an actionable key error."""
        if action_id not in self._actions:
            raise KeyError(f"Unknown V1.3 action: {action_id}")
        return self._actions[action_id]

    def list(self) -> tuple[ActionDefinition, ...]:
        """Return definitions in deterministic identifier order."""
        return tuple(self._actions[action_id] for action_id in sorted(self._actions))


class ActionService:
    """Creates snapshots, invokes local commands, accepts artifacts, and reviews proposals."""

    def __init__(self, registry: ActionRegistry, sidecar: ArtifactSidecar) -> None:
        """Compose trusted definitions with verified artifact storage."""
        self.registry = registry
        self.sidecar = sidecar

    def create_snapshot(
        self,
        revision: SpecRevision,
        action: ActionDefinition,
        target: EntityRef,
        inputs: dict[str, typing.Any] | None = None,
        input_artifact_ids: tuple[str, ...] = (),
        activity: ActivityStore | None = None,
    ) -> ActionSnapshot:
        """Validate inputs and capture deterministic source/artifact action input."""
        inputs = inputs or {}
        if target.entity_kind not in action.target_entity_kinds:
            raise ValueError(f"Action {action.action_id} cannot target {target.entity_kind}.")
        target_entity = revision.resolve(target)
        if not isinstance(target_entity, (ComponentIR, DesignIR)):
            raise ValueError("V1.3 actions target components or designs only.")
        try:
            jsonschema.validate(inputs, action.input_schema)
        except jsonschema.ValidationError as exc:
            raise ValueError(f"Action input schema failed: {exc.message}") from exc
        selected_artifacts: list[ArtifactRef] = []
        if input_artifact_ids:
            if activity is None:
                raise ValueError("Input artifact selection requires an activity store.")
            by_id = {artifact.artifact_id: artifact for artifact in activity.state.artifacts}
            for artifact_id in input_artifact_ids:
                artifact = by_id.get(artifact_id)
                if artifact is None:
                    raise KeyError(f"Unknown input artifact: {artifact_id}")
                if action.consumed_artifact_roles and artifact.role not in action.consumed_artifact_roles:
                    raise ValueError(f"Action cannot consume artifact role {artifact.role}.")
                self.sidecar.read(artifact)
                selected_artifacts.append(artifact)
        closure = revision.dependency_closure(target)
        linked: list[NarrativeBlock] = []
        for reference in closure:
            linked.extend(revision.narrative_blocks_for(reference))
        linked.extend(revision.narrative_blocks_for(target))
        unique_blocks = {block.block_id: block for block in linked}
        for precondition in action.preconditions:
            if precondition == "has_linked_narrative" and not unique_blocks:
                raise ValueError("Action precondition failed: target has no linked narrative blocks.")
            if precondition == "has_input_artifacts" and not selected_artifacts:
                raise ValueError("Action precondition failed: selected input artifacts are required.")
            if precondition not in {"has_linked_narrative", "has_input_artifacts"}:
                raise ValueError(f"Unknown action precondition: {precondition}")
        normalized_inputs = json.loads(json.dumps(inputs, sort_keys=True))
        identity = {
            "action_id": action.action_id,
            "action_version": action.version,
            "source_revision_hash": revision.source_revision_hash,
            "target": target.model_dump(mode="json"),
            "closure": [reference.model_dump(mode="json") for reference in closure],
            "inputs": normalized_inputs,
            "input_artifacts": list(input_artifact_ids),
        }
        snapshot_id = "snapshot_" + hashlib.sha256(_json_bytes(identity)).hexdigest()
        return ActionSnapshot(
            snapshot_id=snapshot_id,
            source_revision_hash=revision.source_revision_hash,
            target=EntityRef.model_validate(target.model_dump(mode="json")),
            dependency_closure=closure,
            linked_narrative=tuple(unique_blocks[block_id] for block_id in sorted(unique_blocks)),
            accepted_annotations=tuple((item.path, bytes(item.data)) for item in revision.annotations),
            input_artifacts=tuple(selected_artifacts),
            _normalized_inputs_json=json.dumps(normalized_inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            _revision=revision,
        )

    def execute(
        self,
        revision: SpecRevision,
        activity: ActivityStore,
        action_id: str,
        target: EntityRef,
        inputs: dict[str, typing.Any] | None = None,
        input_artifact_ids: tuple[str, ...] = (),
    ) -> ActionExecution:
        """Build a consistent failed record for timeout or contract failures."""
        """Execute one trusted local command and append only activity metadata."""
        action = self.registry.get(action_id)
        snapshot = self.create_snapshot(revision, action, target, inputs, input_artifact_ids, activity)
        execution_id = new_entity_id("execution")
        events = [ActionEvent(sequence=1, event_type="action.execution.started", timestamp=_utc_now(), payload={"snapshot_id": snapshot.snapshot_id})]
        with tempfile.TemporaryDirectory(prefix="spec2gds-action-") as temporary:
            root = Path(temporary)
            input_dir = root / "input"
            output_dir = root / "output"
            output_dir.mkdir()
            snapshot.write_bundle(input_dir, self.sidecar)
            command = [*action.executor, "--input", str(input_dir), "--output", str(output_dir)]
            try:
                completed = subprocess.run(command, capture_output=True, text=True, timeout=action.timeout_seconds, check=False)
            except subprocess.TimeoutExpired:
                execution = self._failed_execution(execution_id, action, snapshot, events, f"Action execution timed out after {action.timeout_seconds} seconds.")
                activity._append_execution(execution)
                activity.save()
                return execution
            if completed.returncode != 0:
                execution = self._failed_execution(execution_id, action, snapshot, events, f"Action executor exited with status {completed.returncode}: {completed.stderr.strip()}")
                activity._append_execution(execution)
                activity.save()
                return execution
            try:
                completion = _load_completion(output_dir)
                artifacts = self._ingest_completion_artifacts(action, snapshot, execution_id, output_dir, completion)
                proposals = self._completion_proposals(action, snapshot, execution_id, completion)
                jsonschema.validate(completion["report"], action.report_schema)
                if "requires_artifact" in action.postconditions and not artifacts:
                    raise ValueError("Action postcondition failed: at least one artifact is required.")
                if "report_summary" in action.postconditions and not str(completion["report"].get("summary", "")).strip():
                    raise ValueError("Action postcondition failed: report summary is required.")
                unknown_postconditions = set(action.postconditions) - {"requires_artifact", "report_summary"}
                if unknown_postconditions:
                    raise ValueError("Unknown action postcondition: " + ", ".join(sorted(unknown_postconditions)))
            except (KeyError, ValueError, jsonschema.ValidationError, FileNotFoundError) as exc:
                execution = self._failed_execution(execution_id, action, snapshot, events, f"Malformed action completion: {exc}")
                activity._append_execution(execution)
                activity.save()
                return execution
        events.extend(
            [
                ActionEvent(sequence=2, event_type="action.artifacts.accepted", timestamp=_utc_now(), payload={"artifact_ids": [artifact.artifact_id for artifact in artifacts]}),
                ActionEvent(sequence=3, event_type="action.execution.succeeded", timestamp=_utc_now(), payload={"proposal_ids": [proposal.proposal_id for proposal in proposals]}),
            ]
        )
        execution = ActionExecution(
            execution_id=execution_id,
            action_id=action.action_id,
            action_version=action.version,
            snapshot_id=snapshot.snapshot_id,
            status="succeeded",
            events=tuple(events),
            result_refs=tuple(artifact.artifact_id for artifact in artifacts),
            report=completion["report"],
            toolchain_identity=str(completion.get("toolchain_identity", "")),
        )
        activity._append_artifacts(artifacts)
        activity._append_proposals(proposals)
        activity._append_execution(execution)
        activity.save()
        return execution

    def preview_proposal(self, revision: SpecRevision, activity: ActivityStore, proposal_id: str) -> EditResult:
        """Validate a pending proposal without mutating either source or review state."""
        proposal = _proposal(activity, proposal_id)
        if proposal.base_source_revision_hash != revision.source_revision_hash:
            return EditResult(revision=None, diagnostics=("Proposal base source revision is stale.",))
        try:
            operations = _decode_operations(proposal.operations)
        except (KeyError, ValueError, pydantic.ValidationError) as exc:
            return EditResult(revision=None, diagnostics=(str(exc),))
        return SpecEditTransaction(revision.source_revision_hash, operations).apply(revision)

    def accept_proposal(self, revision: SpecRevision, activity: ActivityStore, proposal_id: str) -> EditResult:
        """Apply a pending, current proposal through V1.2's transaction validator."""
        proposal = _proposal(activity, proposal_id)
        if proposal.review_status != "pending":
            return EditResult(revision=None, diagnostics=(f"Proposal is already {proposal.review_status}.",))
        result = self.preview_proposal(revision, activity, proposal_id)
        if not result.succeeded or result.revision is None:
            activity._replace_proposal(proposal.model_copy(update={"diagnostics": result.diagnostics}))
            activity.save()
            return result
        accepted = proposal.model_copy(update={"review_status": "accepted", "diagnostics": ()})
        activity._replace_proposal(accepted)
        activity.save()
        # Retain activity alongside the new source revision; it is excluded from its hash.
        next_package = result.revision.to_package()
        next_package.files[_ACTIVITY_PATH] = _json_bytes(activity.state)
        next_revision = SpecRevision.from_package(next_package)
        return EditResult(revision=next_revision, diagnostics=())

    def reject_proposal(self, activity: ActivityStore, proposal_id: str) -> ChangeProposal:
        """Record architect rejection without changing source or execution history."""
        proposal = _proposal(activity, proposal_id)
        if proposal.review_status != "pending":
            raise ValueError(f"Proposal is already {proposal.review_status}.")
        rejected = proposal.model_copy(update={"review_status": "rejected"})
        activity._replace_proposal(rejected)
        activity.save()
        return rejected

    def _failed_execution(
        self,
        execution_id: str,
        action: ActionDefinition,
        snapshot: ActionSnapshot,
        events: list[ActionEvent],
        diagnostic: str,
    ) -> ActionExecution:
        """Build one consistent failed record for timeout or contract errors."""
        events.append(ActionEvent(sequence=len(events) + 1, event_type="action.execution.failed", timestamp=_utc_now(), payload={"diagnostic": diagnostic}))
        return ActionExecution(
            execution_id=execution_id,
            action_id=action.action_id,
            action_version=action.version,
            snapshot_id=snapshot.snapshot_id,
            status="failed",
            events=tuple(events),
            diagnostics=(diagnostic,),
        )

    def _ingest_completion_artifacts(
        self,
        action: ActionDefinition,
        snapshot: ActionSnapshot,
        execution_id: str,
        output_dir: Path,
        completion: dict[str, typing.Any],
    ) -> tuple[ArtifactRef, ...]:
        """Validate declared outputs and ingest immutable artifact content."""
        artifacts: list[ArtifactRef] = []
        for declared in completion.get("artifacts", []):
            if not isinstance(declared, dict):
                raise ValueError("Artifact declaration must be an object.")
            role = str(declared.get("role", ""))
            if action.produced_artifact_roles and role not in action.produced_artifact_roles:
                raise ValueError(f"Artifact role is not declared by action: {role}")
            output_path = validate_safe_path(str(declared.get("path", "")))
            file_path = output_dir / output_path
            if not file_path.is_file():
                raise FileNotFoundError(f"Declared artifact output is missing: {output_path}")
            data = file_path.read_bytes()
            declared_hash = str(declared.get("sha256", sha256_digest(data)))
            if declared_hash != sha256_digest(data):
                raise ValueError(f"Declared artifact hash does not match output: {output_path}")
            declared_size = int(declared.get("size", len(data)))
            if declared_size != len(data):
                raise ValueError(f"Declared artifact size does not match output: {output_path}")
            digest, locator = self.sidecar.ingest(data)
            source_entities = tuple(EntityRef.model_validate(item) for item in declared.get("source_entities", [snapshot.target.model_dump(mode="json")]))
            closure_keys = {(reference.entity_kind, reference.entity_id) for reference in snapshot.dependency_closure}
            if not source_entities or any(
                reference.document_id != snapshot.target.document_id or (reference.entity_kind, reference.entity_id) not in closure_keys
                for reference in source_entities
            ):
                raise ValueError("Artifact source entities must belong to the action snapshot closure.")
            parent_ids = tuple(str(item) for item in declared.get("parent_artifact_ids", ()))
            selected_ids = {artifact.artifact_id for artifact in snapshot.input_artifacts}
            if any(parent_id not in selected_ids for parent_id in parent_ids):
                raise ValueError("Artifact parents must be selected input artifacts.")
            artifacts.append(
                ArtifactRef(
                    artifact_id=new_entity_id("artifact"),
                    role=role,
                    kind=str(declared.get("kind", "file")),
                    media_type=str(declared.get("media_type", "")),
                    sha256=digest,
                    size=len(data),
                    storage_locator=locator,
                    producer_execution_id=execution_id,
                    producer_action_id=action.action_id,
                    source_revision_hash=snapshot.source_revision_hash,
                    source_entities=source_entities,
                    input_artifact_ids=tuple(artifact.artifact_id for artifact in snapshot.input_artifacts),
                    parent_artifact_ids=parent_ids,
                    toolchain_identity=str(completion.get("toolchain_identity", "")),
                    normalized_inputs=snapshot.normalized_inputs,
                )
            )
        return tuple(artifacts)

    def _completion_proposals(
        self,
        action: ActionDefinition,
        snapshot: ActionSnapshot,
        execution_id: str,
        completion: dict[str, typing.Any],
    ) -> tuple[ChangeProposal, ...]:
        """Decode executor proposals and enforce action-level permission."""
        declared = completion.get("proposals", [])
        if declared and not action.allows_change_proposals:
            raise ValueError("Action is not permitted to create source proposals.")
        proposals: list[ChangeProposal] = []
        for item in declared:
            if not isinstance(item, dict) or not isinstance(item.get("operations"), list):
                raise ValueError("Proposal requires an operations list.")
            operations = tuple(typing.cast(dict[str, typing.Any], operation) for operation in item["operations"])
            # Decode now so malformed source operations fail the action rather than review.
            _decode_operations(operations)
            proposals.append(
                ChangeProposal(
                    proposal_id=new_entity_id("proposal"),
                    base_source_revision_hash=snapshot.source_revision_hash,
                    producer_execution_id=execution_id,
                    rationale=str(item.get("rationale", "Action-generated source proposal.")),
                    operations=operations,
                )
            )
        return tuple(proposals)


def _load_completion(output_dir: Path) -> dict[str, typing.Any]:
    """Load and minimally validate the executor completion manifest."""
    path = output_dir / "completion.json"
    if not path.is_file():
        raise FileNotFoundError("Action output is missing completion.json.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("status") != "succeeded" or not isinstance(payload.get("report"), dict):
        raise ValueError("Completion manifest must declare status=succeeded and an object report.")
    if not isinstance(payload.get("artifacts", []), list) or not isinstance(payload.get("proposals", []), list):
        raise ValueError("Completion artifacts and proposals must be lists.")
    return typing.cast(dict[str, typing.Any], payload)


def _proposal(activity: ActivityStore, proposal_id: str) -> ChangeProposal:
    """Resolve a durable proposal by id."""
    proposal = next((item for item in activity.state.proposals if item.proposal_id == proposal_id), None)
    if proposal is None:
        raise KeyError(f"Unknown proposal: {proposal_id}")
    return proposal


def _decode_operations(raw_operations: tuple[dict[str, typing.Any], ...]) -> tuple[typing.Any, ...]:
    """Decode the deliberately narrow, language-neutral V1.3 proposal patch vocabulary."""
    operations: list[typing.Any] = []
    for raw in raw_operations:
        operation_type = raw.get("type")
        if operation_type == "upsert_narrative_block":
            operations.append(
                UpsertNarrativeBlock(
                    block=NarrativeBlock.model_validate(raw["block"]),
                    parent_block_id=typing.cast(str | None, raw.get("parent_block_id")),
                    index=typing.cast(int | None, raw.get("index")),
                )
            )
        elif operation_type == "set_narrative_entity_links":
            operations.append(
                SetNarrativeLinks(
                    block_id=str(raw["block_id"]),
                    entity_refs=tuple(EntityRef.model_validate(item) for item in raw["entity_refs"]),
                )
            )
        else:
            raise ValueError(f"Unsupported V1.3 proposal operation: {operation_type}")
    return tuple(operations)


def create_reference_registry() -> ActionRegistry:
    """Return the three generic out-of-process reference actions required by V1.3."""
    base = (sys.executable, "-m", "spec2gds.spec.spec_format.reference_actions")
    empty_schema = {"type": "object", "properties": {}, "additionalProperties": False}
    report_schema = {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"], "additionalProperties": True}
    return ActionRegistry(
        (
            ActionDefinition(
                action_id="reference.snapshot_summary",
                version="1.0.0",
                title="Snapshot summary",
                target_entity_kinds=("component", "design"),
                input_schema=empty_schema,
                report_schema=report_schema,
                executor=(*base, "snapshot-summary"),
                produced_artifact_roles=("snapshot.summary",),
            ),
            ActionDefinition(
                action_id="reference.artifact_transform",
                version="1.0.0",
                title="Artifact transform",
                target_entity_kinds=("component", "design"),
                input_schema=empty_schema,
                report_schema=report_schema,
                executor=(*base, "artifact-transform"),
                consumed_artifact_roles=("snapshot.summary", "text.input"),
                produced_artifact_roles=("text.transformed",),
            ),
            ActionDefinition(
                action_id="reference.narrative_proposal",
                version="1.0.0",
                title="Narrative proposal",
                target_entity_kinds=("component", "design"),
                input_schema=empty_schema,
                report_schema=report_schema,
                executor=(*base, "narrative-proposal"),
                allows_change_proposals=True,
            ),
        )
    )

""".spec repository for agent-spec v1 metadata.

The repository is the server-owned facade over one document. It projects the
human-readable ODT body into a block graph, stores graph/run metadata back into
`spec_data/agent-spec/`, and guards saves against concurrent file edits.
"""

import datetime
import hashlib
import json
import pathlib
import typing
import uuid

import pydantic

import spec2gds.agent_spec.models as agent_models
import spec2gds.agent_spec.package.archive as archive
import spec2gds.agent_spec.document.semantic as editor_document


MANIFEST_PATH: str = "spec_data/agent-spec/manifest.json"
GRAPH_PATH: str = "spec_data/agent-spec/graph.json"
MEDIA_TYPE_JSON: str = "application/vnd.spec2gds.agent-spec+json"


def utc_now() -> str:
    """Return compact UTC timestamps used in persisted metadata."""
    return datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_hash(data: bytes) -> str:
    """Return the repository-standard SHA-256 hash string."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def stable_id(prefix: str) -> str:
    """Return an opaque stable-format id with a readable prefix."""
    return f"{prefix}_{uuid.uuid4().hex}"


def _json_bytes(model: pydantic.BaseModel | dict[str, typing.Any]) -> bytes:
    """Serialize Pydantic models/dicts deterministically for archive storage."""
    if isinstance(model, pydantic.BaseModel):
        raw_data = model.model_dump(mode="json")
    else:
        raw_data = model
    return json.dumps(raw_data, indent=2, sort_keys=True).encode("utf-8")


def _load_json_model(
    custom_files: dict[str, bytes],
    path: str,
    model_type: type[pydantic.BaseModel],
) -> pydantic.BaseModel | None:
    """Load one persisted JSON model from the archive cache if present."""
    if path not in custom_files:
        return None
    raw_data = json.loads(custom_files[path].decode("utf-8"))
    return model_type.model_validate(raw_data)


class AgentSpecRepository:
    """Server-owned facade for one agent-spec document."""

    document_path: pathlib.Path
    sidecar_root: pathlib.Path
    user_identity: str
    container: archive.AgentSpecArchive
    manifest: agent_models.AgentSpecManifest
    graph: agent_models.SpecGraph
    loaded_file_hash: str

    def __init__(
        self,
        document_path: str,
        sidecar_root: str | None = None,
        user_identity: str = "local",
    ) -> None:
        """Open a document and initialize sidecar, manifest, and graph state."""
        self.document_path = pathlib.Path(document_path)
        if sidecar_root is None:
            # The sidecar keeps large/generated artifacts next to the document
            # without bloating the `.spec` archive itself.
            sidecar_root = f"{document_path}.agent-spec-sidecar"
        self.sidecar_root = pathlib.Path(sidecar_root)
        self.sidecar_root.mkdir(parents=True, exist_ok=True)
        self.user_identity = user_identity
        self.container = archive.AgentSpecArchive(str(self.document_path))
        self.loaded_file_hash = self._file_hash()
        self.manifest = self._load_or_create_manifest()
        self.graph = self._load_or_create_graph()

    def _file_hash(self) -> str:
        """Hash the on-disk document for optimistic save-conflict detection."""
        if self.document_path.exists() and self.document_path.stat().st_size > 0:
            return stable_hash(self.document_path.read_bytes())
        return ""

    def _load_or_create_manifest(self) -> agent_models.AgentSpecManifest:
        """Load persisted manifest metadata or create a new document identity."""
        loaded = _load_json_model(
            self.container.custom_files,
            MANIFEST_PATH,
            agent_models.AgentSpecManifest,
        )
        if isinstance(loaded, agent_models.AgentSpecManifest):
            return loaded
        timestamp = utc_now()
        return agent_models.AgentSpecManifest(
            document_id=stable_id("doc"),
            created_at=timestamp,
            updated_at=timestamp,
            user_identity=self.user_identity,
            sidecar_root=str(self.sidecar_root),
        )

    def _load_or_create_graph(self) -> agent_models.SpecGraph:
        """Load the persisted graph or start with an empty projection."""
        loaded = _load_json_model(
            self.container.custom_files,
            GRAPH_PATH,
            agent_models.SpecGraph,
        )
        if isinstance(loaded, agent_models.SpecGraph):
            return loaded
        return agent_models.SpecGraph()

    def _content_xml(self) -> bytes:
        """Return raw `content.xml` bytes from the ODT package."""
        content_part: typing.Any = self.container.document.get_part("content.xml")
        if hasattr(content_part, "serialize"):
            return typing.cast(bytes, content_part.serialize())
        if isinstance(content_part, bytes):
            return content_part
        return str(content_part).encode("utf-8")

    def _set_content_xml(self, content_xml: bytes) -> None:
        """Replace the document body XML inside the package."""
        self.container.document.set_part("content.xml", content_xml)

    def _persist_model(self, path: str, model: pydantic.BaseModel) -> None:
        """Persist one Pydantic model under `spec_data/agent-spec/`."""
        self.container.inject_file(path, _json_bytes(model), MEDIA_TYPE_JSON)

    def _persist_bytes(self, path: str, data: bytes) -> None:
        """Persist pre-serialized agent-spec metadata bytes."""
        self.container.inject_file(path, data, MEDIA_TYPE_JSON)

    def project_graph(self) -> agent_models.SpecGraph:
        """Project current .spec headings into blocks and immutable versions."""
        content_xml = self._content_xml()
        # Heading ids are the bridge between visible sections and graph blocks.
        # Assign missing ids before parsing so later saves/runs can refer to
        # stable block ids.
        content_with_ids = editor_document.ensure_heading_ids(content_xml)
        if content_with_ids != content_xml:
            self._set_content_xml(content_with_ids)
        semantic_document = editor_document.parse_content_xml(content_with_ids)
        if semantic_document.has_blocking_diagnostics:
            messages = [diagnostic.message for diagnostic in semantic_document.diagnostics]
            raise ValueError(f"Cannot project invalid agent-spec content: {messages}")

        now = utc_now()
        for index, block in enumerate(semantic_document.blocks):
            if block.block_type != "heading" or block.heading_id is None:
                continue
            # A block version covers the heading and all following semantic
            # blocks until the next same-or-higher-level heading.
            block_ids = self._section_block_ids(semantic_document.blocks, index)
            artifact_ids = [attachment.artifact_id for attachment in self.graph.attachments.get(block.heading_id, [])]
            content_hash = self._block_content_hash(semantic_document.blocks, block_ids, artifact_ids)
            version_id = f"v-{content_hash.removeprefix('sha256:')[:12]}"
            existing = self.graph.blocks.get(block.heading_id)
            if existing is None:
                existing = agent_models.BlockRecord(
                    block_id=block.heading_id,
                    heading_id=block.heading_id,
                    title=block.display_text or block.text,
                    level=block.level or 1,
                )
            existing.title = block.display_text or block.text
            existing.level = block.level or 1
            is_new_version = not any(version.version_id == version_id for version in existing.versions)
            if is_new_version:
                # Versions are append-only snapshots. Changing text or attached
                # artifact ids produces a new content hash and therefore a new
                # version id.
                existing.versions.append(
                    agent_models.BlockVersionRecord(
                        version_id=version_id,
                        block_id=block.heading_id,
                        content_hash=content_hash,
                        block_ids=block_ids,
                        artifact_ref_ids=artifact_ids,
                        created_at=now,
                    )
                )
            if block.heading_id not in self.graph.active_versions or is_new_version:
                # New content becomes active by default so user edits are visible
                # to subsequent action runs unless a caller selects otherwise.
                self.graph.active_versions[block.heading_id] = version_id
            self.graph.blocks[block.heading_id] = existing
        return self.graph

    def _section_block_ids(
        self,
        blocks: list[editor_document.SemanticBlock],
        heading_index: int,
    ) -> list[str]:
        """Return semantic block ids belonging to one heading section."""
        heading = blocks[heading_index]
        heading_level = heading.level or 1
        block_ids: list[str] = [heading.block_id]
        for candidate in blocks[heading_index + 1:]:
            if candidate.block_type == "heading" and (candidate.level or 1) <= heading_level:
                break
            block_ids.append(candidate.block_id)
        return block_ids

    def _block_content_hash(
        self,
        blocks: list[editor_document.SemanticBlock],
        block_ids: list[str],
        artifact_ids: list[str],
    ) -> str:
        """Hash section text plus attached artifact ids to identify versions."""
        block_by_id = {block.block_id: block for block in blocks}
        data: dict[str, typing.Any] = {
            "blocks": [
                {
                    "block_id": block_id,
                    "type": block_by_id[block_id].block_type,
                    "text": block_by_id[block_id].text,
                }
                for block_id in block_ids
                if block_id in block_by_id
            ],
            "artifact_ids": sorted(artifact_ids),
        }
        return stable_hash(_json_bytes(data))

    def set_block_tags(self, block_id: str, tags: list[str]) -> None:
        """Set validated action-discovery tags on a block."""
        self.project_graph()
        if block_id not in self.graph.blocks:
            raise KeyError(f"Unknown block: {block_id}")
        clean_tags: list[str] = []
        for tag in tags:
            if tag not in agent_models.V1_TAGS:
                raise ValueError(f"Unsupported v1 tag: {tag}")
            if tag not in clean_tags:
                clean_tags.append(tag)
        self.graph.blocks[block_id].tags = clean_tags

    def active_version(self, block_id: str) -> agent_models.BlockVersionRecord:
        """Return a defensive copy of the active version for a block."""
        self.project_graph()
        if block_id not in self.graph.blocks:
            raise KeyError(f"Unknown block: {block_id}")
        active_version_id = self.graph.active_versions[block_id]
        for version in self.graph.blocks[block_id].versions:
            if version.version_id == active_version_id:
                return version.model_copy(deep=True)
        raise KeyError(f"Active version missing for block {block_id}: {active_version_id}")

    def set_active_version(self, block_id: str, version_id: str) -> None:
        """Select which immutable version future actions should read."""
        self.project_graph()
        if block_id not in self.graph.blocks:
            raise KeyError(f"Unknown block: {block_id}")
        if not any(version.version_id == version_id for version in self.graph.blocks[block_id].versions):
            raise KeyError(f"Unknown version for block {block_id}: {version_id}")
        self.graph.active_versions[block_id] = version_id

    def attachment_artifacts(self, block_id: str) -> list[agent_models.ArtifactRef]:
        """Return artifact metadata attached to a block."""
        artifacts: list[agent_models.ArtifactRef] = []
        for attachment in self.graph.attachments.get(block_id, []):
            artifact = self.graph.artifact_refs.get(attachment.artifact_id)
            if artifact is not None:
                artifacts.append(artifact.model_copy(deep=True))
        return artifacts

    def append_artifact(
        self,
        artifact: agent_models.ArtifactRef,
        block_id: str,
        run_id: str,
    ) -> agent_models.AttachmentRecord:
        """Attach an accepted artifact to a block and return the attachment row."""
        if block_id not in self.graph.blocks:
            raise KeyError(f"Unknown block: {block_id}")
        self.graph.artifact_refs[artifact.artifact_id] = artifact.model_copy(deep=True)
        attachment = agent_models.AttachmentRecord(
            attachment_id=stable_id("att"),
            block_id=block_id,
            artifact_id=artifact.artifact_id,
            role=artifact.role,
            run_id=run_id,
            created_at=utc_now(),
        )
        self.graph.attachments.setdefault(block_id, []).append(attachment)
        return attachment

    def persist_run(
        self,
        run_record: agent_models.RunRecord,
        events: list[agent_models.RunEvent],
    ) -> None:
        """Persist a run record and its event stream into the archive."""
        run_path = f"spec_data/agent-spec/runs/{run_record.run_id}/run.json"
        events_path = f"spec_data/agent-spec/runs/{run_record.run_id}/events.ndjson"
        event_lines = b"\n".join(
            json.dumps(event.model_dump(mode="json"), sort_keys=True).encode("utf-8")
            for event in events
        )
        self._persist_model(run_path, run_record)
        self._persist_bytes(events_path, event_lines + b"\n")

    def persist_snapshot(self, run_id: str, snapshot: agent_models.InputSnapshot) -> None:
        """Persist the immutable action input snapshot for reproducibility."""
        self._persist_model(f"spec_data/agent-spec/runs/{run_id}/input_snapshot.json", snapshot)

    def persist_writeback(self, writeback: agent_models.WritebackRecord) -> None:
        """Persist the writeback decision produced by the runner."""
        self._persist_model(f"spec_data/agent-spec/writebacks/{writeback.writeback_id}.json", writeback)

    def persist_checkpoint(self, checkpoint_id: str, data: dict[str, typing.Any]) -> None:
        """Persist a compact checkpoint/index for a run writeback."""
        self._persist_bytes(f"spec_data/agent-spec/checkpoints/{checkpoint_id}.json", _json_bytes(data))

    def save(self) -> None:
        """Persist graph metadata and save the package if no external edit occurred."""
        current_file_hash = self._file_hash()
        if self.loaded_file_hash and current_file_hash and current_file_hash != self.loaded_file_hash:
            raise RuntimeError("Refusing to save because the agent-spec changed outside the server session.")
        self.manifest.updated_at = utc_now()
        # Re-project immediately before saving so graph metadata reflects the
        # current document body, including any heading ids just assigned.
        self.project_graph()
        self._persist_model(MANIFEST_PATH, self.manifest)
        self._persist_model(GRAPH_PATH, self.graph)
        for block in self.graph.blocks.values():
            for version in block.versions:
                self._persist_model(
                    f"spec_data/agent-spec/versions/{block.block_id}/{version.version_id}.json",
                    version,
                )
        for artifact in self.graph.artifact_refs.values():
            self._persist_model(f"spec_data/agent-spec/artifacts/{artifact.artifact_id}.json", artifact)
        self.container.save(str(self.document_path))
        self.loaded_file_hash = self._file_hash()

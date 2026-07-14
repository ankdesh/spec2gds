"""Shared read/query services for UI and action-facing `.spec` APIs.

The editor and external executors need different response shapes, but they
should agree on the same source facts: semantic blocks, active versions,
relations, IP-XACT attachments, links, artifacts, and diagnostics. This module
assembles those facts without saving or sanitizing the source document.
"""

import datetime
import hashlib
import json
import pathlib
import typing

import pydantic

import spec2gds.agent_spec.document.session as editor_session
import spec2gds.agent_spec.models as agent_models
import spec2gds.agent_spec.package.archive as archive
import spec2gds.agent_spec.storage.repository as repository


ACTION_SCHEMA_VERSION: str = "agent-spec.actions.v1"


class ActionEnvelope(pydantic.BaseModel):
    """Versioned response wrapper for action and executor read APIs."""

    schema_version: str = ACTION_SCHEMA_VERSION
    document_hash: str
    loaded_at: str
    data: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    diagnostics: list[agent_models.AgentSpecDiagnostic] = pydantic.Field(default_factory=list)


class AgentSpecQueryService:
    """Read-only facade over a `.spec` document for UI and executor consumers."""

    document_path: pathlib.Path
    container: archive.AgentSpecArchive
    snapshot: editor_session.EditorSnapshot
    graph: agent_models.SpecGraph
    manifest: agent_models.AgentSpecManifest | None
    document_hash: str
    loaded_at: str

    def __init__(self, document_path: str) -> None:
        """Open a document and build read models without writing the package."""
        self.document_path = pathlib.Path(document_path)
        self.container = archive.AgentSpecArchive(str(self.document_path))
        self.document_hash = _file_hash(self.document_path)
        self.loaded_at = _utc_now()
        self.snapshot = editor_session.EditorSession(self.container).snapshot()
        self.manifest = _load_manifest(self.container)
        self.graph = self._project_graph_readonly()

    def editor_snapshot(self) -> editor_session.EditorSnapshot:
        """Return the UI snapshot shape from the shared query layer."""
        return self.snapshot.model_copy(deep=True)

    def envelope(
        self,
        data: dict[str, typing.Any],
        diagnostics: list[agent_models.AgentSpecDiagnostic] | None = None,
    ) -> ActionEnvelope:
        """Wrap endpoint data in the v1 action response envelope."""
        return ActionEnvelope(
            document_hash=self.document_hash,
            loaded_at=self.loaded_at,
            data=data,
            diagnostics=diagnostics or [],
        )

    def document_summary(self) -> ActionEnvelope:
        """Return document-level identity and diagnostic summary."""
        manifest_value = self.manifest.model_dump(mode="json") if self.manifest is not None else None
        return self.envelope(
            {
                "path": str(self.document_path),
                "document_id": self._document_id(),
                "manifest": manifest_value,
                "block_count": len(self.graph.blocks),
                "ipxact_count": len(self.snapshot.ipxact_components),
                "artifact_count": len(self.graph.artifact_refs),
                "run_count": len(self._run_paths()),
                "writeback_count": len(self._writeback_paths()),
                "has_blocking_diagnostics": self.snapshot.has_blocking_diagnostics,
            },
            self._all_diagnostics(),
        )

    def blocks(self) -> ActionEnvelope:
        """Return executor-friendly block summaries."""
        return self.envelope({"blocks": [self._block_summary(block) for block in self.graph.blocks.values()]})

    def block(self, block_id: str) -> ActionEnvelope:
        """Return one block with all version records."""
        block = self._require_block(block_id)
        return self.envelope({"block": self._block_detail(block)})

    def block_context(self, block_id: str, version_id: str | None = None) -> ActionEnvelope:
        """Return a section bundle for one block and active or explicit version."""
        block = self._require_block(block_id)
        selected_version = self._select_version(block, version_id)
        semantic_blocks = [
            item.model_dump(mode="json")
            for item in self.snapshot.document.blocks
            if item.block_id in set(selected_version.block_ids)
        ]
        link_block_ids = {item["block_id"] for item in semantic_blocks}
        links = [
            link.model_dump(mode="json")
            for link in self.snapshot.document.links
            if link.block_id in link_block_ids
        ]
        attached_paths = self._attached_ipxact_paths(block_id)
        ipxact_components = [
            self._ipxact_summary(summary)
            for summary in self.snapshot.ipxact_components
            if summary.file_path in attached_paths
        ]
        attachments = self.graph.attachments.get(block_id, [])
        artifacts = [
            self.graph.artifact_refs[attachment.artifact_id].model_dump(mode="json")
            for attachment in attachments
            if attachment.artifact_id in self.graph.artifact_refs
        ]
        data = {
            "block": self._block_detail(block),
            "selected_version": selected_version.model_dump(mode="json"),
            "active_version_id": self.graph.active_versions.get(block_id, ""),
            "semantic_blocks": semantic_blocks,
            "links": links,
            "relations": {
                "ipxact_attachments": [
                    item.model_dump(mode="json")
                    for item in self.snapshot.relations.ipxact_attachments.get(block_id, [])
                ],
                "section_groups": [
                    group.model_dump(mode="json")
                    for group in self.snapshot.relations.section_groups
                    if any(variant.heading_id == block_id for variant in group.variants)
                ],
            },
            "ipxact_components": ipxact_components,
            "artifacts": artifacts,
            "attachments": [attachment.model_dump(mode="json") for attachment in attachments],
        }
        return self.envelope(data, self._context_diagnostics(block_id, attached_paths))

    def ipxact_components(self) -> ActionEnvelope:
        """Return summaries for all embedded IP-XACT payloads."""
        return self.envelope(
            {"components": [self._ipxact_summary(summary) for summary in self.snapshot.ipxact_components]},
            [
                _diagnostic_from_ipxact(item)
                for summary in self.snapshot.ipxact_components
                for item in summary.diagnostics
            ],
        )

    def raw_ipxact(self, file_path: str) -> tuple[bytes, str]:
        """Return raw embedded IP-XACT XML bytes and media type."""
        normalized = file_path if file_path.startswith("spec_data/ipxact/") else f"spec_data/ipxact/{file_path}"
        if normalized not in self.container.custom_files:
            raise KeyError(f"Unknown IP-XACT file: {file_path}")
        return self.container.extract_file(normalized), "application/xml+ipxact"

    def artifacts(self) -> ActionEnvelope:
        """Return all persisted artifact refs and block attachments."""
        return self.envelope(
            {
                "artifact_refs": {
                    artifact_id: artifact.model_dump(mode="json")
                    for artifact_id, artifact in self.graph.artifact_refs.items()
                },
                "attachments": {
                    block_id: [attachment.model_dump(mode="json") for attachment in attachments]
                    for block_id, attachments in self.graph.attachments.items()
                },
            }
        )

    def runs(self) -> ActionEnvelope:
        """Return persisted run and artifact-application summaries."""
        return self.envelope(
            {
                "runs": [self._json_file(path) for path in self._run_paths()],
                "writebacks": [self._json_file(path) for path in self._writeback_paths()],
            }
        )

    def run(self, run_id: str) -> ActionEnvelope:
        """Return persisted metadata for one run."""
        run_path = f"spec_data/agent-spec/runs/{run_id}/run.json"
        if run_path not in self.container.custom_files:
            raise KeyError(f"Unknown run: {run_id}")
        snapshot_path = f"spec_data/agent-spec/runs/{run_id}/input_snapshot.json"
        events_path = f"spec_data/agent-spec/runs/{run_id}/events.ndjson"
        report_path = f"spec_data/agent-spec/runs/{run_id}/report.json"
        a2ui_path = f"spec_data/agent-spec/runs/{run_id}/report.a2ui.jsonl"
        data = {
            "run": self._json_file(run_path),
            "input_snapshot": self._json_file(snapshot_path) if snapshot_path in self.container.custom_files else None,
            "events": self._ndjson_file(events_path) if events_path in self.container.custom_files else [],
            "report": self._json_file(report_path) if report_path in self.container.custom_files else None,
            "a2ui_messages": self._ndjson_file(a2ui_path) if a2ui_path in self.container.custom_files else [],
        }
        return self.envelope(data)

    def links(self) -> ActionEnvelope:
        """Return all visible document links and current link diagnostics."""
        link_diagnostics = [
            _diagnostic_from_editor(item)
            for item in self.snapshot.diagnostics
            if item.source == "spec-link"
        ]
        return self.envelope(
            {"links": [link.model_dump(mode="json") for link in self.snapshot.document.links]},
            link_diagnostics,
        )

    def _project_graph_readonly(self) -> agent_models.SpecGraph:
        """Project heading blocks into a graph without saving graph metadata."""
        graph = _load_graph(self.container) or agent_models.SpecGraph()
        graph = graph.model_copy(deep=True)
        now = _utc_now()
        for index, block in enumerate(self.snapshot.document.blocks):
            if block.block_type != "heading" or block.heading_id is None:
                continue
            block_ids = _section_block_ids(self.snapshot.document.blocks, index)
            artifact_ids = [attachment.artifact_id for attachment in graph.attachments.get(block.heading_id, [])]
            content_hash = _block_content_hash(self.snapshot.document.blocks, block_ids, artifact_ids)
            version_id = f"v-{content_hash.removeprefix('sha256:')[:12]}"
            existing = graph.blocks.get(block.heading_id)
            if existing is None:
                existing = agent_models.BlockRecord(
                    block_id=block.heading_id,
                    heading_id=block.heading_id,
                    title=block.display_text or block.text,
                    level=block.level or 1,
                )
            existing.title = block.display_text or block.text
            existing.level = block.level or 1
            if not any(version.version_id == version_id for version in existing.versions):
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
            if block.heading_id not in graph.active_versions:
                graph.active_versions[block.heading_id] = version_id
            graph.blocks[block.heading_id] = existing
        return graph

    def _document_id(self) -> str:
        """Return persisted document id or a deterministic transient id."""
        if self.manifest is not None:
            return self.manifest.document_id
        return f"transient-{self.document_hash.removeprefix('sha256:')[:16]}"

    def _block_summary(self, block: agent_models.BlockRecord) -> dict[str, typing.Any]:
        """Return compact block data for list endpoints."""
        attachments = self.graph.attachments.get(block.block_id, [])
        return {
            "block_id": block.block_id,
            "heading_id": block.heading_id,
            "title": block.title,
            "level": block.level,
            "active_version_id": self.graph.active_versions.get(block.block_id, ""),
            "version_count": len(block.versions),
            "artifact_count": len(attachments),
            "ipxact_attachment_count": len(self.snapshot.relations.ipxact_attachments.get(block.block_id, [])),
        }

    def _block_detail(self, block: agent_models.BlockRecord) -> dict[str, typing.Any]:
        """Return block data including all known versions."""
        data = self._block_summary(block)
        data["versions"] = [version.model_dump(mode="json") for version in block.versions]
        return data

    def _require_block(self, block_id: str) -> agent_models.BlockRecord:
        """Return a block or raise a clear lookup error."""
        if block_id not in self.graph.blocks:
            raise KeyError(f"Unknown block: {block_id}")
        return self.graph.blocks[block_id]

    def _select_version(
        self,
        block: agent_models.BlockRecord,
        version_id: str | None,
    ) -> agent_models.BlockVersionRecord:
        """Return the active or explicitly requested version for a block."""
        selected_id = version_id or self.graph.active_versions.get(block.block_id, "")
        for version in block.versions:
            if version.version_id == selected_id:
                return version
        raise KeyError(f"Unknown version for block {block.block_id}: {selected_id}")

    def _attached_ipxact_paths(self, block_id: str) -> set[str]:
        """Return normalized IP-XACT file paths attached to one heading block."""
        return {attachment.file_path for attachment in self.snapshot.relations.ipxact_attachments.get(block_id, [])}

    def _ipxact_summary(self, summary: typing.Any) -> dict[str, typing.Any]:
        """Return an action-context summary with a stable raw XML endpoint hint."""
        data = summary.model_dump(mode="json")
        data["raw_endpoint"] = "/agent-spec/ipxact/raw"
        data["raw_query"] = {"file_path": summary.file_path}
        return data

    def _context_diagnostics(
        self,
        block_id: str,
        attached_paths: set[str],
    ) -> list[agent_models.AgentSpecDiagnostic]:
        """Return diagnostics relevant to one section context."""
        diagnostics = self._all_diagnostics()
        existing_paths = {summary.file_path for summary in self.snapshot.ipxact_components}
        for attached_path in sorted(attached_paths - existing_paths):
            diagnostics.append(
                agent_models.AgentSpecDiagnostic(
                    severity="warning",
                    source="relations",
                    message=f"Attached IP-XACT file is missing: {attached_path}.",
                    target_id=block_id,
                )
            )
        return diagnostics

    def _all_diagnostics(self) -> list[agent_models.AgentSpecDiagnostic]:
        """Merge editor, semantic, and IP-XACT diagnostics into one shape."""
        diagnostics = [_diagnostic_from_editor(item) for item in self.snapshot.document.diagnostics]
        diagnostics.extend(_diagnostic_from_editor(item) for item in self.snapshot.diagnostics)
        diagnostics.extend(
            _diagnostic_from_ipxact(item)
            for summary in self.snapshot.ipxact_components
            for item in summary.diagnostics
        )
        return diagnostics

    def _json_file(self, file_path: str) -> dict[str, typing.Any]:
        """Decode one embedded JSON metadata file."""
        return json.loads(self.container.extract_file(file_path).decode("utf-8"))

    def _ndjson_file(self, file_path: str) -> list[dict[str, typing.Any]]:
        """Decode one embedded NDJSON event stream."""
        text = self.container.extract_file(file_path).decode("utf-8")
        try:
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            events: list[dict[str, typing.Any]] = []
            index = 0
            while index < len(text):
                while index < len(text) and text[index].isspace():
                    index += 1
                if index >= len(text):
                    break
                event, index = decoder.raw_decode(text, index)
                events.append(typing.cast(dict[str, typing.Any], event))
            return events

    def _run_paths(self) -> list[str]:
        """Return persisted run record paths."""
        return sorted(
            path
            for path in self.container.custom_files
            if path.startswith("spec_data/agent-spec/runs/") and path.endswith("/run.json")
        )

    def _writeback_paths(self) -> list[str]:
        """Return persisted writeback record paths."""
        return sorted(
            path
            for path in self.container.custom_files
            if path.startswith("spec_data/agent-spec/writebacks/") and path.endswith(".json")
        )


def _load_manifest(container: archive.AgentSpecArchive) -> agent_models.AgentSpecManifest | None:
    """Load persisted agent-spec manifest metadata when present."""
    return typing.cast(
        agent_models.AgentSpecManifest | None,
        _load_json_model(container, repository.MANIFEST_PATH, agent_models.AgentSpecManifest),
    )


def _load_graph(container: archive.AgentSpecArchive) -> agent_models.SpecGraph | None:
    """Load persisted graph metadata when present."""
    return typing.cast(
        agent_models.SpecGraph | None,
        _load_json_model(container, repository.GRAPH_PATH, agent_models.SpecGraph),
    )


def _load_json_model(
    container: archive.AgentSpecArchive,
    file_path: str,
    model_type: type[pydantic.BaseModel],
) -> pydantic.BaseModel | None:
    """Decode a Pydantic model from custom package bytes if available."""
    if file_path not in container.custom_files:
        return None
    raw_data = json.loads(container.extract_file(file_path).decode("utf-8"))
    return model_type.model_validate(raw_data)


def _section_block_ids(blocks: list[typing.Any], heading_index: int) -> list[str]:
    """Return semantic block ids included in one heading-delimited section."""
    heading = blocks[heading_index]
    heading_level = heading.level or 1
    block_ids = [heading.block_id]
    for candidate in blocks[heading_index + 1:]:
        if candidate.block_type == "heading" and (candidate.level or 1) <= heading_level:
            break
        block_ids.append(candidate.block_id)
    return block_ids


def _block_content_hash(
    blocks: list[typing.Any],
    block_ids: list[str],
    artifact_ids: list[str],
) -> str:
    """Return the same section content hash used by the write repository."""
    block_by_id = {block.block_id: block for block in blocks}
    data = {
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
    return repository.stable_hash(json.dumps(data, indent=2, sort_keys=True).encode("utf-8"))


def _diagnostic_from_editor(diagnostic: typing.Any) -> agent_models.AgentSpecDiagnostic:
    """Convert editor diagnostics into the action diagnostic contract."""
    return agent_models.AgentSpecDiagnostic(
        severity=diagnostic.severity,
        source=diagnostic.source,
        message=diagnostic.message,
        target_id=getattr(diagnostic, "block_id", None) or "",
    )


def _diagnostic_from_ipxact(diagnostic: typing.Any) -> agent_models.AgentSpecDiagnostic:
    """Convert IP-XACT summary diagnostics into the action diagnostic contract."""
    return agent_models.AgentSpecDiagnostic(
        severity=diagnostic.severity,
        source=diagnostic.source,
        message=diagnostic.message,
    )


def _file_hash(path: pathlib.Path) -> str:
    """Return the repository-standard SHA-256 digest for a document path."""
    if not path.exists() or path.stat().st_size == 0:
        return ""
    return repository.stable_hash(path.read_bytes())


def _utc_now() -> str:
    """Return compact UTC timestamps for response envelopes."""
    return datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

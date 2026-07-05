import json
import typing

import pydantic

import spec2gds.spec.odt_container.container as container
import spec2gds.spec.odt_container.editor_core.document as document
import spec2gds.spec.odt_container.editor_core.ipxact_view as ipxact_view
import spec2gds.spec.odt_container.editor_core.relations as relation_model
import spec2gds.spec.odt_container.ipxact_plugin as ipxact_plugin
import spec2gds.spec.odt_container.json_plugin as json_plugin
import spec2gds.spec.odt_container.manager as manager


ACTIVE_STATE_PATH: str = "spec_data/odt-editor/active_section_versions.json"
ACTIVE_STATE_MEDIA_TYPE: str = "application/vnd.spec2gds.odt-editor-state+json"


class EditorSnapshot(pydantic.BaseModel):
    """Complete v1 snapshot consumed by the local web editor."""

    document: document.SemanticDocument
    ipxact_components: list[ipxact_view.IpxactComponentSummary]
    relations: relation_model.EditorRelations = pydantic.Field(default_factory=relation_model.EditorRelations)
    active_section_versions: dict[str, str] = pydantic.Field(default_factory=dict)
    diagnostics: list[document.Diagnostic] = pydantic.Field(default_factory=list)

    @property
    def has_blocking_diagnostics(self) -> bool:
        for diagnostic in self.diagnostics:
            if diagnostic.blocks_save:
                return True
        if self.document.has_blocking_diagnostics:
            return True
        for component in self.ipxact_components:
            if component.has_blocking_diagnostics:
                return True
        return False


class EditorSession:
    """Stateful v1 editor facade around a HybridODTContainer."""

    _container: container.HybridODTContainer
    _manager: manager.PluginManager
    _active_versions: dict[str, str]
    _relations: relation_model.EditorRelations

    def __init__(self, container_instance: container.HybridODTContainer) -> None:
        self._container = container_instance
        self._manager = manager.PluginManager()
        self._manager.register_plugin(json_plugin.SimpleJSONPlugin())
        self._manager.register_plugin(ipxact_plugin.IPXACTPlugin())
        self._active_versions = self._load_active_versions()
        self._relations = self._load_relations()

    @classmethod
    def from_path(cls, path: str) -> "EditorSession":
        return cls(container.HybridODTContainer(path))

    @property
    def active_versions(self) -> dict[str, str]:
        if self._relations.section_groups:
            return self._relations.active_versions()
        return dict(self._active_versions)

    @property
    def editor_relations(self) -> relation_model.EditorRelations:
        return self._relations.model_copy(deep=True)

    def _load_active_versions(self) -> dict[str, str]:
        if ACTIVE_STATE_PATH not in self._container.custom_files:
            return {}
        try:
            raw_bytes = self._container.extract_file(ACTIVE_STATE_PATH)
            raw_data = json.loads(raw_bytes.decode("utf-8"))
        except Exception:
            return {}
        if not isinstance(raw_data, dict):
            return {}
        section_versions = raw_data.get("active_section_versions", {})
        if not isinstance(section_versions, dict):
            return {}
        active_versions: dict[str, str] = {}
        for key, value in section_versions.items():
            if isinstance(key, str) and isinstance(value, str):
                active_versions[key] = value
        return active_versions

    def persist_active_versions(self, active_versions: dict[str, str]) -> None:
        self._active_versions = dict(active_versions)
        if self._relations.section_groups:
            for group in self._relations.section_groups:
                if group.group_id in active_versions:
                    group.active_version = active_versions[group.group_id]
            self._persist_relations(self._relations)
        state = {
            "version": 1,
            "active_section_versions": self._active_versions,
        }
        self._container.inject_file(
            ACTIVE_STATE_PATH,
            json.dumps(state, indent=2, sort_keys=True).encode("utf-8"),
            ACTIVE_STATE_MEDIA_TYPE,
        )

    def _load_relations(self) -> relation_model.EditorRelations:
        if relation_model.RELATIONS_PATH not in self._container.custom_files:
            return relation_model.EditorRelations()
        return relation_model.load_relations(self._container.extract_file(relation_model.RELATIONS_PATH))

    def _persist_relations(self, editor_relations: relation_model.EditorRelations) -> None:
        self._relations = editor_relations.model_copy(deep=True)
        self._container.inject_file(
            relation_model.RELATIONS_PATH,
            relation_model.dump_relations(self._relations),
            relation_model.RELATIONS_MEDIA_TYPE,
        )

    def _content_xml(self) -> bytes:
        content_part: typing.Any = self._container.document.get_part("content.xml")
        if hasattr(content_part, "serialize"):
            return typing.cast(bytes, content_part.serialize())
        if isinstance(content_part, bytes):
            return content_part
        return str(content_part).encode("utf-8")

    def _set_content_xml(self, content_xml: bytes) -> None:
        self._container.document.set_part("content.xml", content_xml)

    def _content_xml_with_heading_ids(self) -> bytes:
        content_xml = self._content_xml()
        updated_xml = document.ensure_heading_ids(content_xml)
        if updated_xml != content_xml:
            self._set_content_xml(updated_xml)
        return updated_xml

    def _extract_ipxact_components(self) -> list[ipxact_view.IpxactComponentSummary]:
        summaries: list[ipxact_view.IpxactComponentSummary] = []
        for file_path in sorted(self._container.custom_files.keys()):
            if not file_path.startswith("spec_data/ipxact/"):
                continue
            xml_bytes = self._container.extract_file(file_path)
            summaries.append(ipxact_view.extract_ipxact_summary(file_path, xml_bytes))
        return summaries

    def _ipxact_summary_by_path(self) -> dict[str, ipxact_view.IpxactComponentSummary]:
        return {summary.file_path: summary for summary in self._extract_ipxact_components()}

    def _link_diagnostics(
        self,
        semantic_document: document.SemanticDocument,
    ) -> list[document.Diagnostic]:
        diagnostics: list[document.Diagnostic] = []
        for link in semantic_document.links:
            if not link.href.startswith("spec://"):
                continue
            try:
                self._manager.resolve_uri(self._container, link.href)
            except Exception as exc:
                diagnostics.append(
                    document.Diagnostic(
                        severity="warning",
                        source="spec-link",
                        message=f"Unresolved spec link {link.href}: {exc}",
                        block_id=link.block_id,
                    )
                )
        return diagnostics

    def _attachment_diagnostics(self, heading_ids: set[str]) -> list[document.Diagnostic]:
        diagnostics: list[document.Diagnostic] = []
        for heading_id, attachments in self._relations.ipxact_attachments.items():
            if heading_id not in heading_ids:
                diagnostics.append(
                    document.Diagnostic(
                        severity="warning",
                        source="relations",
                        message=f"IP-XACT attachments target missing heading {heading_id}.",
                        block_id=heading_id,
                    )
                )
            for path in relation_model.attachment_paths(attachments):
                if path not in self._container.custom_files:
                    diagnostics.append(
                        document.Diagnostic(
                            severity="warning",
                            source="relations",
                            message=f"Attached IP-XACT file is missing: {path}.",
                            block_id=heading_id,
                        )
                    )
        return diagnostics

    def _build_relations_from_legacy(
        self,
        semantic_document: document.SemanticDocument,
    ) -> relation_model.EditorRelations:
        editor_relations = self._relations.model_copy(deep=True)
        if not editor_relations.section_groups:
            for group in semantic_document.section_groups:
                variants: list[relation_model.SectionVersionRef] = []
                for variant in group.variants:
                    variants.append(
                        relation_model.SectionVersionRef(
                            version=variant.version,
                            heading_id=variant.heading_block_id,
                            block_ids=variant.block_ids,
                        )
                    )
                active_version = self._active_versions.get(group.group_id, group.active_version)
                editor_relations.section_groups.append(
                    relation_model.SectionVersionGroup(
                        group_id=group.group_id,
                        title=group.title,
                        level=group.level,
                        variants=variants,
                        active_version=active_version,
                    )
                )
        self._migrate_legacy_ipxact_attachments(semantic_document, editor_relations)
        return editor_relations

    def _migrate_legacy_ipxact_attachments(
        self,
        semantic_document: document.SemanticDocument,
        editor_relations: relation_model.EditorRelations,
    ) -> None:
        if editor_relations.ipxact_attachments:
            return
        ipxact_paths = sorted(
            path
            for path in self._container.custom_files.keys()
            if path.startswith("spec_data/ipxact/")
        )
        if not ipxact_paths:
            return

        heading_before_block: dict[str, str] = {}
        active_heading_id: str | None = None
        ipxact_heading_ids: list[str] = []
        for block in semantic_document.blocks:
            if block.block_type == "heading" and block.heading_id is not None:
                active_heading_id = block.heading_id
                if "ip-xact" in block.display_text.lower() or "ipxact" in block.display_text.lower():
                    ipxact_heading_ids.append(block.heading_id)
            heading_before_block[block.block_id] = active_heading_id or ""

        for link in semantic_document.links:
            if not link.href.startswith("spec://ipxact/"):
                continue
            heading_id = heading_before_block.get(link.block_id, "")
            if not heading_id:
                continue
            file_part = link.href.removeprefix("spec://ipxact/").split("/", 1)[0]
            path = relation_model.normalize_ipxact_path(file_part)
            if path not in self._container.custom_files:
                continue
            existing = editor_relations.ipxact_attachments.setdefault(heading_id, [])
            if path not in relation_model.attachment_paths(existing):
                existing.append(relation_model.HeadingIpxactAttachment(file_path=path))

        if editor_relations.ipxact_attachments:
            return
        if len(ipxact_heading_ids) == 1:
            editor_relations.ipxact_attachments[ipxact_heading_ids[0]] = [
                relation_model.HeadingIpxactAttachment(file_path=path)
                for path in ipxact_paths
            ]

    def _relations_as_document_groups(
        self,
        editor_relations: relation_model.EditorRelations,
    ) -> list[document.SectionVariantGroup]:
        groups: list[document.SectionVariantGroup] = []
        for group in editor_relations.section_groups:
            groups.append(
                document.SectionVariantGroup(
                    group_id=group.group_id,
                    title=group.title,
                    level=group.level,
                    variants=[
                        document.SectionVariant(
                            version=variant.version,
                            heading_block_id=variant.heading_id,
                            block_ids=variant.block_ids,
                        )
                        for variant in group.variants
                    ],
                    active_version=group.active_version,
                )
            )
        return groups

    def snapshot(self) -> EditorSnapshot:
        content_xml = self._content_xml_with_heading_ids()
        semantic_document = document.parse_content_xml(
            content_xml,
            self._active_versions,
        )
        editor_relations = self._build_relations_from_legacy(semantic_document)
        semantic_document.section_groups = self._relations_as_document_groups(editor_relations)
        if editor_relations.section_groups and not self._relations.section_groups:
            self._relations = editor_relations
        diagnostics = self._link_diagnostics(semantic_document)
        heading_id_set = {
            block.heading_id
            for block in semantic_document.blocks
            if block.block_type == "heading" and block.heading_id is not None
        }
        diagnostics.extend(self._attachment_diagnostics(heading_id_set))
        return EditorSnapshot(
            document=semantic_document,
            ipxact_components=self._extract_ipxact_components(),
            relations=editor_relations,
            active_section_versions=self.active_versions,
            diagnostics=diagnostics,
        )

    def apply_text_edits(self, edits: dict[str, str]) -> None:
        updated_xml = document.apply_text_edits_to_content_xml(self._content_xml_with_heading_ids(), edits)
        self._container.document.set_part("content.xml", updated_xml)

    def persist_relations(self, editor_relations: relation_model.EditorRelations) -> None:
        for heading_id, attachments in list(editor_relations.ipxact_attachments.items()):
            normalized = [
                relation_model.HeadingIpxactAttachment(file_path=path)
                for path in relation_model.attachment_paths(attachments)
            ]
            editor_relations.ipxact_attachments[heading_id] = normalized
        self._persist_relations(editor_relations)

    def apply_editor_save(
        self,
        text_edits: dict[str, str],
        editor_relations: relation_model.EditorRelations | None,
        ipxact_xml_edits: dict[str, str],
    ) -> None:
        if text_edits:
            self.apply_text_edits(text_edits)
        if editor_relations is not None:
            self.persist_relations(editor_relations)
        for file_path, xml_text in ipxact_xml_edits.items():
            self.update_ipxact_xml(file_path, xml_text)

    def preview_ipxact_xml(
        self,
        file_path: str,
        xml_text: str,
    ) -> ipxact_view.IpxactComponentSummary:
        full_path = self._normalize_ipxact_path(file_path)
        return ipxact_view.extract_ipxact_summary(full_path, xml_text.encode("utf-8"))

    def update_ipxact_xml(self, file_path: str, xml_text: str) -> None:
        full_path = self._normalize_ipxact_path(file_path)
        preview = ipxact_view.extract_ipxact_summary(full_path, xml_text.encode("utf-8"))
        if preview.has_blocking_diagnostics:
            raise ValueError("Cannot update IP-XACT XML while preview diagnostics remain.")
        self._container.inject_file(
            full_path,
            xml_text.encode("utf-8"),
            "application/xml+ipxact",
        )

    def _normalize_ipxact_path(self, file_path: str) -> str:
        return relation_model.normalize_ipxact_path(file_path)

    def asset_bytes(self, asset_id: str) -> tuple[bytes, str]:
        snapshot = self.snapshot()
        for block in snapshot.document.blocks:
            if block.image is None or block.image.asset_id != asset_id:
                continue
            href = block.image.href
            if href in self._container.document.get_parts():
                data = self._container.document.get_part(href)
                if isinstance(data, bytes):
                    return data, "application/octet-stream"
            raise KeyError(f"Asset {href} is not readable.")
        raise KeyError(f"Unknown asset id: {asset_id}")

    def save(self, path: str) -> None:
        if self._relations.section_groups or self._relations.ipxact_attachments:
            self._persist_relations(self._relations)
        snapshot = self.snapshot()
        if snapshot.has_blocking_diagnostics:
            raise ValueError("Cannot save ODT while blocking editor diagnostics remain.")
        self._container.save(path)

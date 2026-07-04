import json
import typing

import pydantic

import spec2gds.spec.odt_container.container as container
import spec2gds.spec.odt_container.editor_core.document as document
import spec2gds.spec.odt_container.editor_core.ipxact_view as ipxact_view
import spec2gds.spec.odt_container.ipxact_plugin as ipxact_plugin
import spec2gds.spec.odt_container.json_plugin as json_plugin
import spec2gds.spec.odt_container.manager as manager


ACTIVE_STATE_PATH: str = "spec_data/odt-editor/active_section_versions.json"
ACTIVE_STATE_MEDIA_TYPE: str = "application/vnd.spec2gds.odt-editor-state+json"


class EditorSnapshot(pydantic.BaseModel):
    """Complete v1 snapshot consumed by the local web editor."""

    document: document.SemanticDocument
    ipxact_components: list[ipxact_view.IpxactComponentSummary]
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

    def __init__(self, container_instance: container.HybridODTContainer) -> None:
        self._container = container_instance
        self._manager = manager.PluginManager()
        self._manager.register_plugin(json_plugin.SimpleJSONPlugin())
        self._manager.register_plugin(ipxact_plugin.IPXACTPlugin())
        self._active_versions = self._load_active_versions()

    @classmethod
    def from_path(cls, path: str) -> "EditorSession":
        return cls(container.HybridODTContainer(path))

    @property
    def active_versions(self) -> dict[str, str]:
        return dict(self._active_versions)

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
        state = {
            "version": 1,
            "active_section_versions": self._active_versions,
        }
        self._container.inject_file(
            ACTIVE_STATE_PATH,
            json.dumps(state, indent=2, sort_keys=True).encode("utf-8"),
            ACTIVE_STATE_MEDIA_TYPE,
        )

    def _content_xml(self) -> bytes:
        content_part: typing.Any = self._container.document.get_part("content.xml")
        if hasattr(content_part, "serialize"):
            return typing.cast(bytes, content_part.serialize())
        if isinstance(content_part, bytes):
            return content_part
        return str(content_part).encode("utf-8")

    def _extract_ipxact_components(self) -> list[ipxact_view.IpxactComponentSummary]:
        summaries: list[ipxact_view.IpxactComponentSummary] = []
        for file_path in sorted(self._container.custom_files.keys()):
            if not file_path.startswith("spec_data/ipxact/"):
                continue
            xml_bytes = self._container.extract_file(file_path)
            summaries.append(ipxact_view.extract_ipxact_summary(file_path, xml_bytes))
        return summaries

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

    def snapshot(self) -> EditorSnapshot:
        semantic_document = document.parse_content_xml(
            self._content_xml(),
            self._active_versions,
        )
        diagnostics = self._link_diagnostics(semantic_document)
        return EditorSnapshot(
            document=semantic_document,
            ipxact_components=self._extract_ipxact_components(),
            active_section_versions=self.active_versions,
            diagnostics=diagnostics,
        )

    def apply_text_edits(self, edits: dict[str, str]) -> None:
        updated_xml = document.apply_text_edits_to_content_xml(self._content_xml(), edits)
        self._container.document.set_part("content.xml", updated_xml)

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
        if file_path.startswith("spec_data/ipxact/"):
            return file_path
        if file_path.endswith(".xml"):
            return f"spec_data/ipxact/{file_path}"
        return f"spec_data/ipxact/{file_path}.xml"

    def save(self, path: str) -> None:
        snapshot = self.snapshot()
        if snapshot.has_blocking_diagnostics:
            raise ValueError("Cannot save ODT while blocking editor diagnostics remain.")
        self._container.save(path)

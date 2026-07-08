"""Structural and semantic verifier for hybrid `.spec` archives.

The verifier checks both sides of the package contract: custom files must be
registered and schema-valid, and visible `spec://` links in `content.xml` must
resolve through the plugin manager.
"""

import datetime
import json
import typing

import pydantic
import lxml.etree as etree

import spec2gds.agent_spec.package.archive as container
import spec2gds.agent_spec.plugins.manager as manager


class FileVerification(pydantic.BaseModel):
    """Validation result for one `spec_data/` file inside the archive."""

    file_path: str = pydantic.Field(..., description="Target file path under spec_data/")
    media_type: str = pydantic.Field(..., description="Media type string registered in manifest")
    is_registered: bool = pydantic.Field(..., description="True if path is in manifest.xml")
    is_valid: bool = pydantic.Field(..., description="True if payload complies with schema")
    error_message: typing.Optional[str] = pydantic.Field(None, description="Schema error message if invalid")

class LinkVerification(pydantic.BaseModel):
    """Validation result for one visible `spec://` hyperlink in `content.xml`."""

    anchor_text: str = pydantic.Field(..., description="Visual text displayed for the link")
    uri: str = pydantic.Field(..., description="Custom URI pointing to the spec resource")
    is_valid: bool = pydantic.Field(..., description="True if URI resolves successfully to a value")
    error_message: typing.Optional[str] = pydantic.Field(None, description="Resolution error message if invalid")

class ContainerVerificationReport(pydantic.BaseModel):
    """Top-level report combining custom-file and semantic-link checks."""

    container_path: str = pydantic.Field(..., description="Path to verified agent-spec archive")
    timestamp: datetime.datetime = pydantic.Field(..., description="Execution timestamp")
    files: list[FileVerification] = pydantic.Field(default_factory=list, description="Validated custom data files list")
    links: list[LinkVerification] = pydantic.Field(default_factory=list, description="Parsed and validated spec hyperlinks list")
    is_fully_consistent: bool = pydantic.Field(..., description="True if all files are registered/valid AND all links resolve successfully")

class ContainerVerifier:
    """
    Verification engine executing syntactic and semantic validation on hybrid agent-spec archives.
    It verifies both embedded files (manifest presence, schema correctness) and 
    referential integrity of spec:// links embedded in content.xml.
    """
    # Pre-declared attributes (Mojo compile-time compatibility)
    _container: container.AgentSpecArchive
    _manager: manager.PluginManager

    def __init__(
        self,
        container_instance: container.AgentSpecArchive,
        manager_instance: manager.PluginManager
    ) -> None:
        """
        Initialize the verifier.
        
        Args:
            container_instance: AgentSpecArchive to verify.
            manager_instance: PluginManager containing registered modality plugins.
        """
        self._container = container_instance
        self._manager = manager_instance

    def verify_all(self) -> ContainerVerificationReport:
        """
        Execute full container verification.

        The first pass validates payloads under `spec_data/`; the second pass
        scans `content.xml` links and asks `PluginManager` to resolve each
        `spec://` reference. Any failed file or link marks the container
        inconsistent, but the method still returns a complete report.
        
        Returns:
            A ContainerVerificationReport instance detailing the consistency report.
        """
        files_results: list[FileVerification] = []
        links_results: list[LinkVerification] = []
        is_consistent: bool = True

        # Phase 1: custom files. The archive cache tells us what is present,
        # while the ODT manifest tells us what office tools are expected to
        # preserve.
        manifest: typing.Any = self._container.document.get_part("META-INF/manifest.xml")
        registered_paths: list[str] = []
        if manifest is not None and hasattr(manifest, "get_paths"):
            registered_paths = manifest.get_paths()

        # Iterate over all cached files under spec_data/ and validate them
        for file_path in self._container.custom_files.keys():
            is_registered: bool = file_path in registered_paths
            media_type: str = ""
            if manifest is not None and hasattr(manifest, "get_media_type"):
                try:
                    media_type = manifest.get_media_type(file_path)
                except Exception:
                    pass

            is_valid: bool = True
            error_msg: typing.Optional[str] = None

            # Custom file paths follow
            # `spec_data/<modality_id>/<relative_file_path>`. The modality
            # segment selects the plugin that knows how to parse/validate it.
            parts: list[str] = file_path.split("/")
            if len(parts) >= 3:
                modality_id: str = parts[1]
                sub_file_path: str = "/".join(parts[2:])
                try:
                    if modality_id == "agent-spec-editor":
                        # Internal editor metadata is package state, not a user modality.
                        file_bytes: bytes = self._container.extract_file(file_path)
                        if sub_file_path.endswith(".json"):
                            json.loads(file_bytes.decode("utf-8"))
                    else:
                        # Resolve plugin, extract the plugin-native value, and
                        # run its schema validator.
                        target_plugin = self._manager.get_plugin(modality_id)
                        if modality_id == "ipxact":
                            data = self._container.extract_file(file_path)
                        else:
                            data = target_plugin.extract_data(self._container, sub_file_path)
                        target_plugin.validate_data(data)
                except Exception as e:
                    is_valid = False
                    error_msg = str(e)
            else:
                is_valid = False
                error_msg = "Invalid custom file path hierarchy in agent-spec archive."

            # A file failure compromises container consistency, but we keep
            # accumulating results so users can fix all issues in one pass.
            if not is_registered or not is_valid:
                is_consistent = False

            files_results.append(
                FileVerification(
                    file_path=file_path,
                    media_type=media_type,
                    is_registered=is_registered,
                    is_valid=is_valid,
                    error_message=error_msg
                )
            )

        # Phase 2: visible semantic links. Only `spec://` links are owned by
        # agent-spec; normal web/file links are ignored by this verifier.
        try:
            content_part: typing.Any = self._container.document.get_part("content.xml")
            if content_part is not None:
                # Retrieve raw XML representation of the human-readable document.
                xml_bytes: bytes = b""
                if hasattr(content_part, "serialize"):
                    xml_bytes = content_part.serialize()
                else:
                    xml_bytes = str(content_part).encode("utf-8")

                # Parse with lxml so namespace-aware XPath can find ODT links.
                root = etree.fromstring(xml_bytes)
                
                # Standard office XML namespaces used by `<text:a xlink:href=...>`.
                ns: dict[str, str] = {
                    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
                    "xlink": "http://www.w3.org/1999/xlink"
                }
                
                # Locate all hyperlink elements (`<text:a>`) in document XML.
                text_links: list[etree._Element] = root.xpath("//text:a", namespaces=ns)
                for link in text_links:
                    href: typing.Optional[str] = link.get("{http://www.w3.org/1999/xlink}href")
                    # Verify only custom agent-spec links.
                    if href is not None and href.startswith("spec://"):
                        # Anchor text helps humans find the bad link in the document.
                        anchor_text: str = "".join(link.itertext()).strip()
                        
                        link_valid: bool = True
                        link_error: typing.Optional[str] = None
                        
                        # Resolution exercises the same plugin path the editor
                        # and actions use at runtime.
                        try:
                            self._manager.resolve_uri(self._container, href)
                        except Exception as e:
                            link_valid = False
                            link_error = str(e)
                            # Dangling or malformed links break consistency validation
                            is_consistent = False

                        links_results.append(
                            LinkVerification(
                                anchor_text=anchor_text,
                                uri=href,
                                is_valid=link_valid,
                                error_message=link_error
                            )
                        )
        except Exception as e:
            is_consistent = False
            # XML parsing failures are reported as a synthetic link error so the
            # CLI output keeps one consistent shape.
            links_results.append(
                LinkVerification(
                    anchor_text="N/A",
                    uri="content.xml",
                    is_valid=False,
                    error_message=f"Failed to parse content.xml: {e}"
                )
            )

        cont_path: str = self._container.container_path if self._container.container_path else "memory"
        return ContainerVerificationReport(
            container_path=cont_path,
            timestamp=datetime.datetime.now(),
            files=files_results,
            links=links_results,
            is_fully_consistent=is_consistent
        )

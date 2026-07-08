"""IP-XACT modality plugin and safe wrapper for pyEDAA component objects."""

import copy
import os
import tempfile
import typing
from pathlib import Path

import lxml.etree
import pyEDAA.IPXACT.Component

import spec2gds.agent_spec.package.archive as container
import spec2gds.agent_spec.plugins.base as plugin


class HybridIPXACTComponent(pyEDAA.IPXACT.Component.Component):
    """
    Subclass of pyEDAA.IPXACT's Component that implements a custom __deepcopy__
    to support value copy semantics without crashing on un-picklable lxml objects.
    """
    def __deepcopy__(self, memo: dict[int, typing.Any]) -> "HybridIPXACTComponent":
        """Rebuild a component from XML bytes instead of copying lxml internals."""
        # pyEDAA components contain lxml objects that are not normal pickle/copy
        # friendly values. Serializing and reparsing gives callers an independent
        # component with equivalent XML content.
        xml_bytes = lxml.etree.tostring(self._xmlRoot, pretty_print=True)
        
        # pyEDAA's parser works from a file path, so the copy route mirrors the
        # normal parse path through a short-lived temp file.
        temp_fd: int
        temp_path_str: str
        temp_fd, temp_path_str = tempfile.mkstemp(suffix=".xml")
        os.close(temp_fd)
        temp_path = Path(temp_path_str)
        
        try:
            with open(temp_path, "wb") as f:
                f.write(xml_bytes)
            new_comp = HybridIPXACTComponent(temp_path, parse=True)
            memo[id(self)] = new_comp
            return new_comp
        finally:
            if temp_path.exists():
                os.remove(temp_path)

class IPXACTPlugin:
    """
    Concrete IP-XACT modality plugin implementing the abstract ModalityPlugin protocol.
    Provides dynamic version-aware IEEE 1685 schema validation, serialization, and 
    hybrid path resolution.
    """
    # Pre-declare all instance attributes for Mojo readiness
    config: plugin.ModalityPluginConfig

    def __init__(self) -> None:
        """Initialize plugin configuration."""
        self.config = plugin.ModalityPluginConfig(
            modality_id="ipxact",
            file_extensions=[".xml"],
            media_type="application/xml+ipxact"
        )

    def validate_data(self, data: typing.Any) -> bool:
        """
        Validate input payload strictly conforms to the IP-XACT schema using pyEDAA.IPXACT.
        
        Args:
            data: Raw XML bytes representing the IP-XACT document.
            
        Returns:
            True if data is valid, raises standard exceptions on failure.
        """
        if not isinstance(data, bytes):
            raise TypeError("IP-XACT data payload must be raw XML bytes.")

        # pyEDAA.IPXACT requires a file path on disk to run its validation
        # suite, so validation writes the candidate bytes to a temp file first.
        temp_fd: int
        temp_path_str: str
        temp_fd, temp_path_str = tempfile.mkstemp(suffix=".xml")
        os.close(temp_fd)
        temp_path: Path = Path(temp_path_str)

        try:
            with open(temp_path, "wb") as f:
                f.write(data)
            
            # Parsing triggers Accellera XSD schema validation matching the
            # document namespace.
            HybridIPXACTComponent(temp_path, parse=True)
            return True
        except Exception as e:
            raise ValueError(f"IP-XACT XML validation failed: {e}")
        finally:
            if temp_path.exists():
                os.remove(temp_path)

    def inject_data(
        self,
        container_instance: container.AgentSpecArchive,
        file_path: str,
        data: typing.Any
    ) -> None:
        """
        Inject validated IP-XACT XML payload into the container and update manifest.
        
        Args:
            container_instance: AgentSpecArchive instance.
            file_path: Target XML file path inside the container.
            data: Raw XML bytes payload.
        """
        # Accept both friendly names and explicit `.xml` paths from the CLI/UI.
        has_ext: bool = False
        for ext in self.config.file_extensions:
            if file_path.endswith(ext):
                has_ext = True
                break
        if not has_ext:
            file_path = file_path + self.config.file_extensions[0]

        # Validate before injection so bad XML never replaces a good archive part.
        self.validate_data(data)

        # IP-XACT payloads are stored under the modality-owned `spec_data/ipxact/`
        # subtree, where editor relation metadata can reference them by path.
        full_path: str = f"spec_data/ipxact/{file_path}"
        container_instance.inject_file(full_path, data, self.config.media_type)

    def extract_data(
        self,
        container_instance: container.AgentSpecArchive,
        file_path: str
    ) -> typing.Any:
        """
        Extract IP-XACT parsed component DOM tree from the container.
        
        Args:
            container_instance: AgentSpecArchive instance.
            file_path: File name inside the spec_data/ipxact/ directory.
            
        Returns:
            Decoupled parsed HybridIPXACTComponent instance.
        """
        has_ext: bool = False
        for ext in self.config.file_extensions:
            if file_path.endswith(ext):
                has_ext = True
                break
        if not has_ext:
            file_path = file_path + self.config.file_extensions[0]

        full_path: str = f"spec_data/ipxact/{file_path}"
        
        # Retrieve raw bytes from the archive cache.
        file_bytes: bytes = container_instance.extract_file(full_path)

        # Parse into a pyEDAA Component via a temporary file because the library
        # API is path-oriented.
        temp_fd: int
        temp_path_str: str
        temp_fd, temp_path_str = tempfile.mkstemp(suffix=".xml")
        os.close(temp_fd)
        temp_path: Path = Path(temp_path_str)

        try:
            with open(temp_path, "wb") as f:
                f.write(file_bytes)
            comp = HybridIPXACTComponent(temp_path, parse=True)
            # Return parsed component directly; the manager performs defensive
            # copying when values leave the plugin boundary.
            return comp
        except Exception as e:
            raise ValueError(f"Failed to parse extracted IP-XACT data: {e}")
        finally:
            if temp_path.exists():
                os.remove(temp_path)

    def resolve_path(
        self,
        container_instance: container.AgentSpecArchive,
        file_path: str,
        node_path: str
    ) -> typing.Any:
        """
        Traverse the IP-XACT hierarchy using a Hybrid strategy.
        First tries logical object attributes, then falls back to lxml XPath.
        
        Args:
            container_instance: AgentSpecArchive instance.
            file_path: Target XML file inside ipxact modality.
            node_path: Slash-separated selector path (logical or XPath).
            
        Returns:
            Resolved attribute value or serialized XML node.
        """
        # A root query returns the parsed component object.
        clean_path: str = node_path.strip("/")
        if not clean_path:
            return self.extract_data(container_instance, file_path)

        # First try the pyEDAA object model so common paths can use domain names
        # instead of raw XML namespace-aware XPath.
        comp: typing.Any = self.extract_data(container_instance, file_path)
        parts: list[str] = clean_path.split("/")

        # Attempt logical attribute traversal. This accepts exact, capitalized,
        # dict-key, list-index, and case-insensitive attribute segments.
        try:
            current_node: typing.Any = comp
            for part in parts:
                if not part:
                    continue
                if hasattr(current_node, part):
                    current_node = getattr(current_node, part)
                elif hasattr(current_node, part.capitalize()):
                    current_node = getattr(current_node, part.capitalize())
                elif isinstance(current_node, dict) and part in current_node:
                    current_node = current_node[part]
                elif isinstance(current_node, list):
                    try:
                        current_node = current_node[int(part)]
                    except (ValueError, IndexError):
                        raise AttributeError()
                else:
                    found: bool = False
                    for attr in dir(current_node):
                        if attr.lower() == part.lower():
                            current_node = getattr(current_node, attr)
                            found = True
                            break
                    if not found:
                        raise AttributeError()
            return copy.deepcopy(current_node)
        except AttributeError:
            # If object traversal cannot satisfy the selector, try XML XPath.
            pass

        # Fallback to lxml XPath for callers who need exact XML-level access or
        # whose IP-XACT version is not exposed by the pyEDAA object model.
        has_ext: bool = False
        for ext in self.config.file_extensions:
            if file_path.endswith(ext):
                has_ext = True
                break
        if not has_ext:
            file_path = file_path + self.config.file_extensions[0]

        full_path: str = f"spec_data/ipxact/{file_path}"
        file_bytes: bytes = container_instance.extract_file(full_path)

        try:
            root = lxml.etree.fromstring(file_bytes)
            # Support the common Accellera/SPIRIT namespace revisions seen in
            # legacy and current benchmark files.
            ns: dict[str, str] = {
                "spirit": "http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009",
                "ipxact": "http://www.accellera.org/XMLSchema/IPXACT/1685-2014",
            }
            results = root.xpath(node_path, namespaces=ns)
            if not results:
                raise KeyError(f"Node or XPath query '{node_path}' not found in IP-XACT.")
            
            resolved_results: list[str] = []
            for res in results:
                if isinstance(res, lxml.etree._Element):
                    # Return leaf text for simple XML nodes and serialized XML
                    # for structured subtrees.
                    if len(res) == 0 and res.text:
                        resolved_results.append(res.text.strip())
                    else:
                        resolved_results.append(lxml.etree.tostring(res, pretty_print=True).decode("utf-8"))
                else:
                    resolved_results.append(str(res))
            
            if len(resolved_results) == 1:
                return copy.deepcopy(resolved_results[0])
            return copy.deepcopy(resolved_results)
        except Exception as e:
            raise KeyError(f"Failed to resolve path '{node_path}' via XPath: {e}")

import copy
import os
import tempfile
import typing
from pathlib import Path

import lxml.etree
import pyEDAA.IPXACT.Component
import spec2gds.spec.odt_container.container as container
import spec2gds.spec.odt_container.plugin as plugin

class HybridIPXACTComponent(pyEDAA.IPXACT.Component.Component):
    """
    Subclass of pyEDAA.IPXACT's Component that implements a custom __deepcopy__
    to support value copy semantics without crashing on un-picklable lxml objects.
    """
    def __deepcopy__(self, memo: dict[int, typing.Any]) -> "HybridIPXACTComponent":
        # Serialize the internal XML root to bytes using lxml
        xml_bytes = lxml.etree.tostring(self._xmlRoot, pretty_print=True)
        
        # Write to a temporary file and re-parse a clean copy
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

        # pyEDAA.IPXACT requires a file path on disk to run its validation suite.
        # We create a temporary file securely to perform this check.
        temp_fd: int
        temp_path_str: str
        temp_fd, temp_path_str = tempfile.mkstemp(suffix=".xml")
        os.close(temp_fd)
        temp_path: Path = Path(temp_path_str)

        try:
            with open(temp_path, "wb") as f:
                f.write(data)
            
            # This parses the document and triggers Accellera XSD schema validation
            # matching the namespace of the document.
            HybridIPXACTComponent(temp_path, parse=True)
            return True
        except Exception as e:
            raise ValueError(f"IP-XACT XML validation failed: {e}")
        finally:
            if temp_path.exists():
                os.remove(temp_path)

    def inject_data(
        self,
        container_instance: container.HybridODTContainer,
        file_path: str,
        data: typing.Any
    ) -> None:
        """
        Inject validated IP-XACT XML payload into the container and update manifest.
        
        Args:
            container_instance: HybridODTContainer instance.
            file_path: Target XML file path inside the container.
            data: Raw XML bytes payload.
        """
        # Ensure correct file extension is present
        has_ext: bool = False
        for ext in self.config.file_extensions:
            if file_path.endswith(ext):
                has_ext = True
                break
        if not has_ext:
            file_path = file_path + self.config.file_extensions[0]

        # 1. Run schema validation prior to injection
        self.validate_data(data)

        # 2. Inject XML bytes into the spec_data/ipxact/ sub-directory within ODT ZIP
        full_path: str = f"spec_data/ipxact/{file_path}"
        container_instance.inject_file(full_path, data, self.config.media_type)

    def extract_data(
        self,
        container_instance: container.HybridODTContainer,
        file_path: str
    ) -> typing.Any:
        """
        Extract IP-XACT parsed component DOM tree from the container.
        
        Args:
            container_instance: HybridODTContainer instance.
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
        
        # Retrieve raw bytes from the ZIP cache
        file_bytes: bytes = container_instance.extract_file(full_path)

        # Parse into pyEDAA Component via a temporary file
        temp_fd: int
        temp_path_str: str
        temp_fd, temp_path_str = tempfile.mkstemp(suffix=".xml")
        os.close(temp_fd)
        temp_path: Path = Path(temp_path_str)

        try:
            with open(temp_path, "wb") as f:
                f.write(file_bytes)
            comp = HybridIPXACTComponent(temp_path, parse=True)
            # Return parsed component directly; deepcopy is handled by caller or manager
            return comp
        except Exception as e:
            raise ValueError(f"Failed to parse extracted IP-XACT data: {e}")
        finally:
            if temp_path.exists():
                os.remove(temp_path)

    def resolve_path(
        self,
        container_instance: container.HybridODTContainer,
        file_path: str,
        node_path: str
    ) -> typing.Any:
        """
        Traverse the IP-XACT hierarchy using a Hybrid strategy.
        First tries logical object attributes, then falls back to lxml XPath.
        
        Args:
            container_instance: HybridODTContainer instance.
            file_path: Target XML file inside ipxact modality.
            node_path: Slash-separated selector path (logical or XPath).
            
        Returns:
            Resolved attribute value or serialized XML node.
        """
        # Clean path and handle root query
        clean_path: str = node_path.strip("/")
        if not clean_path:
            return self.extract_data(container_instance, file_path)

        # Extract parsed object model for logical traversal
        comp: typing.Any = self.extract_data(container_instance, file_path)
        parts: list[str] = clean_path.split("/")

        # 1. Attempt Logical Attribute Traversal
        try:
            current_node: typing.Any = comp
            for part in parts:
                if not part:
                    continue
                # Exact match
                if hasattr(current_node, part):
                    current_node = getattr(current_node, part)
                # Capitalized match
                elif hasattr(current_node, part.capitalize()):
                    current_node = getattr(current_node, part.capitalize())
                # Dict match
                elif isinstance(current_node, dict) and part in current_node:
                    current_node = current_node[part]
                # List index match
                elif isinstance(current_node, list):
                    try:
                        current_node = current_node[int(part)]
                    except (ValueError, IndexError):
                        raise AttributeError()
                else:
                    # Case-insensitive attribute match
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
            pass  # Fallback to XPath

        # 2. Fallback to lxml XPath
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
            # Accellera/SPIRIT standard XML namespaces
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

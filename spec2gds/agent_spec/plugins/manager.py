"""Registry and URI router for agent-spec structured payload plugins."""

import copy
import typing

import spec2gds.agent_spec.plugins.base as plugin
import spec2gds.agent_spec.package.archive as container


class PluginManager:
    """
    Registry for modality plugins, routing data operations (injection, extraction,
    and cross-link resolution) to the appropriate plugin based on modality ID.
    
    This manager enforces loose coupling by decoupling the core container implementation
    from the schema and validation logic of individual custom hardware specs (e.g. JSON, SystemRDL).
    """
    # Pre-declared typed instance attributes (Mojo compile-time compatibility)
    _plugins: dict[str, plugin.ModalityPlugin]

    def __init__(self) -> None:
        """Initialize the plugin manager with an empty registry."""
        self._plugins = {}

    def register_plugin(self, plugin_inst: plugin.ModalityPlugin) -> None:
        """
        Register a new modality plugin.
        
        Args:
            plugin_inst: An object implementing the ModalityPlugin protocol.
        """
        mod_id: str = plugin_inst.config.modality_id
        # Modality IDs are the first path segment beneath `spec_data/` and the
        # first segment of `spec://` links, so registration must be unique.
        self._plugins[mod_id] = plugin_inst

    def get_plugin(self, modality_id: str) -> plugin.ModalityPlugin:
        """
        Retrieve a registered plugin by its modality identifier.
        
        Args:
            modality_id: Unique string identifier of the modality.
            
        Returns:
            The registered ModalityPlugin instance.
        """
        if modality_id not in self._plugins:
            raise KeyError(f"No modality plugin registered for ID '{modality_id}'.")
        return self._plugins[modality_id]

    def list_plugins(self) -> list[str]:
        """
        List all registered modality IDs.
        
        Returns:
            List of registered modality ID strings.
        """
        return list(self._plugins.keys())

    def inject_payload(
        self,
        container_instance: container.AgentSpecArchive,
        modality_id: str,
        file_path: str,
        data: typing.Any
    ) -> None:
        """
        Delegate validation and injection of a payload into the agent-spec archive.
        
        Args:
            container_instance: AgentSpecArchive instance.
            modality_id: Target modality plugin ID.
            file_path: Output file name within the spec_data/ directory.
            data: Payload data (e.g. dictionary or object).
        """
        target_plugin: plugin.ModalityPlugin = self.get_plugin(modality_id)
        
        # Validate before mutating the archive so a failed injection leaves the
        # existing package bytes untouched.
        is_valid: bool = target_plugin.validate_data(data)
        if not is_valid:
            raise ValueError(f"Payload validation failed for modality '{modality_id}'.")

        # The plugin owns serialization details and the precise container path.
        target_plugin.inject_data(container_instance, file_path, data)

    def extract_payload(
        self,
        container_instance: container.AgentSpecArchive,
        modality_id: str,
        file_path: str
    ) -> typing.Any:
        """
        Extract modality data payload from the container, returning a decoupled copy.
        
        Args:
            container_instance: AgentSpecArchive instance.
            modality_id: Registered modality plugin ID.
            file_path: Custom file name inside the spec_data/ sub-directory.
            
        Returns:
            Decoupled deep copy of the parsed data payload.
        """
        target_plugin: plugin.ModalityPlugin = self.get_plugin(modality_id)
        
        # Extract parsed payload (for example, a JSON dict or IP-XACT object).
        extracted_data: typing.Any = target_plugin.extract_data(container_instance, file_path)
        
        # Enforce value semantics at the manager boundary. Callers can mutate the
        # returned data without accidentally changing plugin internals.
        return copy.deepcopy(extracted_data)

    def resolve_uri(
        self,
        container_instance: container.AgentSpecArchive,
        uri: str
    ) -> typing.Any:
        """
        Parse and resolve a custom URI syntax to extract targeted spec parameters.
        
        Syntax:
            spec://<modality_id>/<file_path>/<node_path>
            
        Example:
            spec://simple-json/registers.json/metadata/0/value
            
        Args:
            container_instance: AgentSpecArchive instance.
            uri: String URI conforming to the custom spec:// protocol.
            
        Returns:
            The decoupled deep-copied value of the resolved node.
        """
        if not uri.startswith("spec://"):
            raise ValueError(f"Invalid URI protocol. Expected 'spec://', got: '{uri}'")

        # Strip the scheme and split the URI into plugin id, file path, and a
        # plugin-specific selector path.
        uri_body: str = uri[7:]
        components: list[str] = uri_body.split("/")
        if len(components) < 2:
            raise ValueError(f"Malformed spec URI structure: '{uri}'")

        modality_id: str = components[0]
        file_path: str = components[1]
        
        # Reconstruct the inner selector path (for example,
        # `/metadata/0/value` for JSON).
        node_path: str = "/"
        if len(components) > 2:
            node_path = "/" + "/".join(components[2:])

        # Locate the modality plugin and delegate query traversal. Each modality
        # decides whether the selector means object fields, list indices, XPath,
        # or another domain-specific addressing scheme.
        target_plugin: plugin.ModalityPlugin = self.get_plugin(modality_id)
        resolved_value: typing.Any = target_plugin.resolve_path(
            container_instance,
            file_path,
            node_path
        )

        # Keep resolved values decoupled from any parser-owned mutable objects.
        return copy.deepcopy(resolved_value)

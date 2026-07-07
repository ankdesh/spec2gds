import typing
import pydantic

class ModalityPluginConfig(pydantic.BaseModel):
    """Configuration schema for a custom modality plugin."""
    modality_id: str = pydantic.Field(..., description="Unique alphanumeric identifier of the modality")
    file_extensions: list[str] = pydantic.Field(..., description="List of supported file extensions (e.g. ['.json'])")
    media_type: str = pydantic.Field(..., description="MIME type registered in manifest")

class ModalityPlugin(typing.Protocol):
    """Abstract protocol defining the capabilities for custom modality plugins."""
    config: ModalityPluginConfig

    def validate_data(self, data: typing.Any) -> bool:
        """Validate that input data conforms to the modality's constraints."""
        ...

    def inject_data(
        self,
        container_instance: typing.Any,
        file_path: str,
        data: typing.Any
    ) -> None:
        """Inject data into the agent-spec archive and synchronize its manifest entry."""
        ...

    def extract_data(
        self,
        container_instance: typing.Any,
        file_path: str
    ) -> typing.Any:
        """Extract data from the agent-spec archive, returning a decoupled copy."""
        ...

    def resolve_path(
        self,
        container_instance: typing.Any,
        file_path: str,
        node_path: str
    ) -> typing.Any:
        """Resolve a specific node path query within the parsed data structure."""
        ...

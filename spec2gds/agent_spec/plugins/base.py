"""Shared protocol that every embedded-modality plugin implements.

Plugins are intentionally tiny adapters: they know how to validate, store,
extract, and resolve one kind of structured payload, while the archive layer
only knows about bytes under `spec_data/`.
"""

import typing

import pydantic


class ModalityPluginConfig(pydantic.BaseModel):
    """Static registration data used to route payloads to a plugin."""

    modality_id: str = pydantic.Field(..., description="Unique alphanumeric identifier of the modality")
    file_extensions: list[str] = pydantic.Field(..., description="List of supported file extensions (e.g. ['.json'])")
    media_type: str = pydantic.Field(..., description="MIME type registered in manifest")


class ModalityPlugin(typing.Protocol):
    """Runtime protocol for archive-backed structured payload plugins.

    Implementations should treat all values crossing the plugin boundary as
    copyable data. Callers may deep-copy extracted/resolved values to prevent
    accidental mutation of archive-owned state.
    """

    config: ModalityPluginConfig

    def validate_data(self, data: typing.Any) -> bool:
        """Validate that input data conforms to this modality's constraints."""
        ...

    def inject_data(
        self,
        container_instance: typing.Any,
        file_path: str,
        data: typing.Any
    ) -> None:
        """Inject data into the archive and synchronize its manifest entry."""
        ...

    def extract_data(
        self,
        container_instance: typing.Any,
        file_path: str
    ) -> typing.Any:
        """Extract data from the archive, returning a plugin-native value."""
        ...

    def resolve_path(
        self,
        container_instance: typing.Any,
        file_path: str,
        node_path: str
    ) -> typing.Any:
        """Resolve a specific node path inside the parsed payload."""
        ...

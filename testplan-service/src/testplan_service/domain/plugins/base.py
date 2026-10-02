"""Base interfaces for backend plugins, result adapters, and safe artifact writers."""

from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
from pathlib import PurePosixPath
from typing import Any

from testplan_service.constants import MAX_GENERATION_OUTPUT_BYTES
from testplan_service.domain.plugins.models import (
    ArtifactDescriptor,
    GenerationRequest,
    GenerationResult,
    PluginManifest,
)
from testplan_service.exceptions import DomainValidationError


class OutputWriter:
    """Safe, sandboxed writer for plugin artifact generation."""

    def __init__(self, max_bytes: int = MAX_GENERATION_OUTPUT_BYTES) -> None:
        self.max_bytes = max_bytes
        self._artifacts: dict[str, tuple[bytes, str, str]] = {}  # rel_path -> (bytes, role, media_type)
        self._total_bytes: int = 0

    def write_artifact(
        self,
        relative_path: str,
        content: bytes | str,
        role: str,
        media_type: str = "text/plain",
    ) -> ArtifactDescriptor:
        """Safely stage an artifact, validating paths and enforcing byte quotas."""
        # This capability stages bytes, never opens plugin-selected filesystem paths.
        # It limits output admission; installed Python plugins still run in-process
        # and are trusted code, not isolated by an OS sandbox.
        # Normalize and validate path
        p = PurePosixPath(relative_path)
        if p.is_absolute() or ".." in p.parts:
            raise DomainValidationError(
                f"Invalid artifact path '{relative_path}': path traversal or absolute paths forbidden."
            )
        clean_path = str(p)
        if clean_path in self._artifacts:
            raise DomainValidationError(f"Conflicting artifact path '{clean_path}' already written.")

        data = content.encode("utf-8") if isinstance(content, str) else content
        if self._total_bytes + len(data) > self.max_bytes:
            raise DomainValidationError(
                f"Generation exceeded maximum output limit of {self.max_bytes} bytes."
            )

        self._artifacts[clean_path] = (data, role, media_type)
        self._total_bytes += len(data)

        sha = hashlib.sha256(data).hexdigest()
        return ArtifactDescriptor(
            relative_path=clean_path,
            role=role,
            media_type=media_type,
            sha256=sha,
            size_bytes=len(data),
        )

    def get_all_artifacts(self) -> dict[str, tuple[bytes, str, str]]:
        """Return all staged artifacts."""
        return dict(self._artifacts)

    def get_descriptors(self) -> list[ArtifactDescriptor]:
        """Return descriptors for all written artifacts in sorted path order."""
        descriptors = []
        for path in sorted(self._artifacts.keys()):
            data, role, media_type = self._artifacts[path]
            sha = hashlib.sha256(data).hexdigest()
            descriptors.append(
                ArtifactDescriptor(
                    relative_path=path,
                    role=role,
                    media_type=media_type,
                    sha256=sha,
                    size_bytes=len(data),
                )
            )
        return descriptors


class BackendPlugin(ABC):
    """Abstract interface that all verification backend plugins must implement."""

    @abstractmethod
    def describe(self) -> PluginManifest:
        """Return immutable metadata, version, and declared capabilities."""
        ...

    @abstractmethod
    def validate(self, request: GenerationRequest) -> list[dict[str, Any]]:
        """Validate request against backend capabilities without generating files."""
        ...

    @abstractmethod
    def lower(self, request: GenerationRequest) -> dict[str, Any]:
        """Lower canonical Test IR and bindings into backend-specific realization plan."""
        ...

    @abstractmethod
    def generate(
        self,
        request: GenerationRequest,
        lowered_plan: dict[str, Any],
        writer: OutputWriter,
    ) -> GenerationResult:
        """Generate output files via OutputWriter and return manifest."""
        ...


class ResultAdapterPlugin(ABC):
    """Abstract interface for parsing and normalizing third-party test reports."""

    @abstractmethod
    def describe(self) -> PluginManifest:
        """Return adapter plugin manifest."""
        ...

    @abstractmethod
    def inspect(self, raw_artifact_manifest: dict[str, Any]) -> bool:
        """Inspect raw reports to determine if this adapter can normalize them."""
        ...

    @abstractmethod
    def normalize(
        self,
        raw_artifacts: dict[str, bytes],
        producer_manifest: dict[str, Any],
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        """Normalize raw artifacts into candidate verification.results.v1 payload."""
        ...

"""Plugins domain package for Verification Planner."""

from testplan_service.domain.plugins.base import BackendPlugin, OutputWriter, ResultAdapterPlugin
from testplan_service.domain.plugins.models import (
    ArtifactDescriptor,
    GenerationRequest,
    GenerationResult,
    PluginKind,
    PluginManifest,
    PluginPortability,
)
from testplan_service.domain.plugins.reference_bundle import ReferenceBundlePlugin
from testplan_service.domain.plugins.registry import PluginRegistry, default_plugin_registry

__all__ = [
    "ArtifactDescriptor",
    "BackendPlugin",
    "GenerationRequest",
    "GenerationResult",
    "OutputWriter",
    "PluginKind",
    "PluginManifest",
    "PluginPortability",
    "PluginRegistry",
    "ReferenceBundlePlugin",
    "ResultAdapterPlugin",
    "default_plugin_registry",
]

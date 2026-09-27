"""Plugin Registry for registering, discovering, and dispatching verification plugins."""

from __future__ import annotations

import threading
from typing import Any

from testplan_service.domain.plugins.base import BackendPlugin, ResultAdapterPlugin
from testplan_service.domain.plugins.models import PluginKind, PluginManifest
from testplan_service.domain.plugins.reference_bundle import PLUGIN_ID as REF_BUNDLE_ID, ReferenceBundlePlugin
from testplan_service.exceptions import DomainValidationError


class PluginRegistry:
    """Thread-safe catalog of registered backend and result adapter plugins."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._backends: dict[str, dict[str, BackendPlugin]] = {}  # id -> {version: plugin}
        self._adapters: dict[str, dict[str, ResultAdapterPlugin]] = {}  # id -> {version: plugin}
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register host builtin foundation plugins."""
        ref_plugin = ReferenceBundlePlugin()
        self.register_backend(ref_plugin)

    def register_backend(self, plugin: BackendPlugin) -> None:
        """Register a backend plugin instance."""
        manifest = plugin.describe()
        with self._lock:
            if manifest.plugin_id not in self._backends:
                self._backends[manifest.plugin_id] = {}
            self._backends[manifest.plugin_id][manifest.version] = plugin

    def register_adapter(self, adapter: ResultAdapterPlugin) -> None:
        """Register a result adapter plugin instance."""
        manifest = adapter.describe()
        with self._lock:
            if manifest.plugin_id not in self._adapters:
                self._adapters[manifest.plugin_id] = {}
            self._adapters[manifest.plugin_id][manifest.version] = adapter

    def get_backend(self, plugin_id: str, version: str | None = None) -> BackendPlugin | None:
        """Retrieve backend plugin by ID and optional version (defaults to highest/latest)."""
        with self._lock:
            versions = self._backends.get(plugin_id)
            if not versions:
                return None
            if version:
                return versions.get(version)
            # Pick highest version alphabetically or first
            sorted_keys = sorted(versions.keys(), reverse=True)
            return versions[sorted_keys[0]]

    def get_adapter(self, adapter_id: str, version: str | None = None) -> ResultAdapterPlugin | None:
        """Retrieve result adapter plugin by ID and optional version."""
        with self._lock:
            versions = self._adapters.get(adapter_id)
            if not versions:
                return None
            if version:
                return versions.get(version)
            sorted_keys = sorted(versions.keys(), reverse=True)
            return versions[sorted_keys[0]]

    def list_plugins(self) -> list[PluginManifest]:
        """Return manifests for all registered backend and result adapter plugins."""
        manifests: list[PluginManifest] = []
        with self._lock:
            for versions in self._backends.values():
                for p in versions.values():
                    manifests.append(p.describe())
            for versions in self._adapters.values():
                for a in versions.values():
                    manifests.append(a.describe())
        return manifests


# Global singleton registry instance
default_plugin_registry = PluginRegistry()

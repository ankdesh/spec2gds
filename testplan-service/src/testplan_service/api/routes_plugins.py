"""Plugin discovery, manifest, and public schema endpoints."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException

from testplan_service.constants import SCHEMA_VERSION_TEST_IR
from testplan_service.domain.hash import canonical_json, sha256_digest
from testplan_service.domain.plugins import PluginManifest, default_plugin_registry
from testplan_service.domain.test_ir import TestIR


def create_plugins_router() -> APIRouter:
    """Factory creating plugin discovery endpoints."""
    router = APIRouter(tags=["Plugins & Schemas"])

    @router.get("/plugins", response_model=list[PluginManifest])
    def list_plugins() -> list[PluginManifest]:
        """List all installed backend and result adapter plugins, their capabilities and statuses."""
        return default_plugin_registry.list_plugins()

    @router.get("/plugins/{plugin_id}/configuration-schema")
    def get_plugin_configuration_schema(plugin_id: str, version: str | None = None) -> dict[str, Any]:
        """Return configuration JSON Schema and content digest for a specific plugin."""
        plugin = default_plugin_registry.get_backend(plugin_id, version)
        if not plugin:
            adapter = default_plugin_registry.get_adapter(plugin_id, version)
            if not adapter:
                raise HTTPException(
                    status_code=404,
                    detail=f"Plugin '{plugin_id}' not found.",
                )
            manifest = adapter.describe()
        else:
            manifest = plugin.describe()

        schema = manifest.configuration_schema
        return {
            "plugin_id": manifest.plugin_id,
            "version": manifest.version,
            "configuration_schema": schema,
            "schema_digest": sha256_digest(canonical_json(schema)),
        }

    @router.get("/schemas/verification.test-ir.v1")
    def get_test_ir_schema() -> dict[str, Any]:
        """Return the public machine-readable JSON Schema for Test IR v1."""
        schema = TestIR.model_json_schema()
        return {
            "schema_version": SCHEMA_VERSION_TEST_IR,
            "schema": schema,
            "schema_digest": sha256_digest(canonical_json(schema)),
        }

    return router

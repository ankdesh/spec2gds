"""Shared hosted-service endpoint registry for the local spec2gds tools."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spec2gds_runtime import LogSettings, load_log_settings


@dataclass(frozen=True, slots=True)
class ServiceEndpoint:
    """One HTTP listener or browser UI endpoint."""

    scheme: str
    host: str
    port: int
    base_path: str = ""

    @property
    def url(self) -> str:
        """Render the endpoint as a normalized absolute URL."""
        path = f"/{self.base_path.strip('/')}" if self.base_path.strip("/") else ""
        return f"{self.scheme}://{self.host}:{self.port}{path}"


@dataclass(frozen=True, slots=True)
class HostedService:
    """Pair a machine-facing API endpoint with its browser-facing UI."""
    service: ServiceEndpoint
    ui: ServiceEndpoint


@dataclass(frozen=True, slots=True)
class ServiceRegistry:
    """Validated addresses and logging policy shared by every application."""
    spec_editor: HostedService
    circuit_designer: HostedService
    ai_assistant: HostedService
    logging: LogSettings

    def public_dict(self) -> dict[str, dict[str, str]]:
        """Return the safe URL-only directory exposed to browser clients."""
        return {
            name: {"service_url": value.service.url, "ui_url": value.ui.url}
            for name, value in (
                ("spec_editor", self.spec_editor),
                ("circuit_designer", self.circuit_designer),
                ("ai_assistant", self.ai_assistant),
            )
        }


def service_config_path() -> Path:
    """Resolve an explicit registry or the repository's tracked default."""
    configured = os.environ.get("SPEC2GDS_SERVICE_CONFIG")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "config" / "services.json"


def load_service_registry(path: Path | None = None) -> ServiceRegistry:
    """Read and validate the small versioned JSON registry."""
    source = path or service_config_path()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 2:
        raise ValueError("Service registry schema_version must be 2.")
    return ServiceRegistry(
        spec_editor=_hosted_service(payload, "spec_editor"),
        circuit_designer=_hosted_service(payload, "circuit_designer"),
        ai_assistant=_hosted_service(payload, "ai_assistant"),
        logging=load_log_settings(source),
    )


def _hosted_service(payload: dict[str, Any], name: str) -> HostedService:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"Service registry is missing {name}.")
    return HostedService(
        service=_endpoint(value.get("service"), f"{name}.service"),
        ui=_endpoint(value.get("ui"), f"{name}.ui"),
    )


def _endpoint(value: Any, name: str) -> ServiceEndpoint:
    if not isinstance(value, dict):
        raise ValueError(f"Service registry is missing {name}.")
    scheme = value.get("scheme")
    host = value.get("host")
    port = value.get("port")
    base_path = value.get("base_path", "")
    if scheme not in {"http", "https"}:
        raise ValueError(f"{name}.scheme must be http or https.")
    if not isinstance(host, str) or not host.strip():
        raise ValueError(f"{name}.host is required.")
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError(f"{name}.port must be between 1 and 65535.")
    if not isinstance(base_path, str):
        raise ValueError(f"{name}.base_path must be a string.")
    return ServiceEndpoint(scheme=scheme, host=host.strip(), port=port, base_path=base_path)

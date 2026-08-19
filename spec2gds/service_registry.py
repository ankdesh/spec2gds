"""Shared hosted-service endpoint registry for the local spec2gds tools."""

from __future__ import annotations

import json
import os
import socket
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
    public_host: str = ""

    @property
    def url(self) -> str:
        """Render the endpoint as a normalized absolute URL."""
        path = f"/{self.base_path.strip('/')}" if self.base_path.strip("/") else ""
        host = self.public_host or self.host
        authority = f"[{host}]" if ":" in host and not host.startswith("[") else host
        return f"{self.scheme}://{authority}:{self.port}{path}"


@dataclass(frozen=True, slots=True)
class HostedService:
    """Pair a machine-facing API endpoint with its browser-facing UI."""
    service: ServiceEndpoint
    ui: ServiceEndpoint


@dataclass(frozen=True, slots=True)
class ActivitySettings:
    """Host-owned settings for UI-launched Activity execution."""

    workspace_root: Path
    extension_modules: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ServiceRegistry:
    """Validated addresses and logging policy shared by every application."""
    spec_editor: HostedService
    circuit_designer: HostedService
    ai_assistant: HostedService
    logging: LogSettings
    activities: ActivitySettings
    public_host: str

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
    public_host = _public_host(payload)
    return ServiceRegistry(
        spec_editor=_hosted_service(payload, "spec_editor", public_host),
        circuit_designer=_hosted_service(payload, "circuit_designer", public_host),
        ai_assistant=_hosted_service(payload, "ai_assistant", public_host),
        logging=load_log_settings(source),
        activities=_activity_settings(payload, source),
        public_host=public_host,
    )


def _activity_settings(payload: dict[str, Any], source: Path) -> ActivitySettings:
    """Resolve the generated workspace and optional extension registrations."""
    value = payload.get("activities", {})
    if not isinstance(value, dict):
        raise ValueError("activities must be an object.")
    configured_root = value.get("workspace_root", "../generated")
    extensions = value.get("extension_modules", [])
    if not isinstance(configured_root, str) or not configured_root.strip():
        raise ValueError("activities.workspace_root must be a non-empty string.")
    if not isinstance(extensions, list) or any(
        not isinstance(item, str) or not item.strip() for item in extensions
    ):
        raise ValueError("activities.extension_modules must contain non-empty strings.")
    candidate = Path(configured_root).expanduser()
    if not candidate.is_absolute():
        candidate = source.parent / candidate
    return ActivitySettings(
        workspace_root=candidate.resolve(),
        extension_modules=tuple(item.strip() for item in extensions),
    )


def _hosted_service(payload: dict[str, Any], name: str, public_host: str) -> HostedService:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"Service registry is missing {name}.")
    return HostedService(
        service=_endpoint(value.get("service"), f"{name}.service", public_host),
        ui=_endpoint(value.get("ui"), f"{name}.ui", public_host),
    )


def _endpoint(value: Any, name: str, public_host: str) -> ServiceEndpoint:
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
    return ServiceEndpoint(
        scheme=scheme,
        host=host.strip(),
        port=port,
        base_path=base_path,
        public_host=public_host,
    )


def _public_host(payload: dict[str, Any]) -> str:
    """Resolve the host advertised to browsers separately from wildcard binds."""
    configured = os.environ.get("SPEC2GDS_PUBLIC_HOST", str(payload.get("public_host", "auto")))
    value = configured.strip()
    if value.lower() == "auto":
        value = _primary_ipv4()
    if not value or "://" in value or "/" in value:
        raise ValueError("public_host must be auto, an IP address, or a hostname.")
    return value


def _primary_ipv4() -> str:
    """Discover the preferred outbound LAN address without sending network data."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            return str(probe.getsockname()[0])
    except OSError:
        return socket.gethostname()

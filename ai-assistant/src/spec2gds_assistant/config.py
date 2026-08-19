"""Resolve Assistant settings from the shared registry and environment.

Treat ``config/services.json`` as the default source of cross-service
addresses. Environment variables are deployment overrides, not a second
independent configuration system.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path

from spec2gds_runtime import LogSettings, load_log_settings

_DEFAULT_PUBLIC_HOST = socket.gethostname()


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    host: str
    port: int
    database_path: Path
    openai_api_key: str | None
    openai_model: str
    web_dist_path: Path
    circuit_request_timeout_seconds: float
    spec_request_timeout_seconds: float = 30.0
    spec_service_allowlist: tuple[str, ...] = (
        f"http://{_DEFAULT_PUBLIC_HOST}:6010",
        "http://127.0.0.1:6010",
        "http://localhost:6010",
    )
    circuit_service_allowlist: tuple[str, ...] = (
        f"http://{_DEFAULT_PUBLIC_HOST}:6011/api/circuit-designer/v1",
        "http://127.0.0.1:6011/api/circuit-designer/v1",
    )
    spec_editor_service_url: str = f"http://{_DEFAULT_PUBLIC_HOST}:6010"
    spec_editor_ui_url: str = f"http://{_DEFAULT_PUBLIC_HOST}:6010/editor"
    circuit_designer_service_url: str = (
        f"http://{_DEFAULT_PUBLIC_HOST}:6011/api/circuit-designer/v1"
    )
    circuit_designer_ui_url: str = f"http://{_DEFAULT_PUBLIC_HOST}:6012"
    ai_assistant_service_url: str = f"http://{_DEFAULT_PUBLIC_HOST}:6013"
    ai_assistant_ui_url: str = f"http://{_DEFAULT_PUBLIC_HOST}:6013"
    logging: LogSettings | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        """Build one immutable settings snapshot for application startup."""
        project_root = Path(__file__).resolve().parents[2]
        config_path = _service_config_path(project_root)
        services = _service_urls(config_path)
        database_path = Path(
            os.environ.get(
                "ASSISTANT_DATABASE_PATH",
                str(project_root / "data" / "assistant.db"),
            )
        ).expanduser()
        web_dist_path = Path(
            os.environ.get(
                "ASSISTANT_WEB_DIST_PATH",
                str(project_root / "web" / "dist"),
            )
        ).expanduser()
        return cls(
            host=os.environ.get("ASSISTANT_HOST", str(services["ai_assistant"]["host"])),
            port=int(os.environ.get("ASSISTANT_PORT", str(services["ai_assistant"]["port"]))),
            database_path=database_path,
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            web_dist_path=web_dist_path,
            circuit_request_timeout_seconds=float(
                os.environ.get("CIRCUIT_REQUEST_TIMEOUT_SECONDS", "30")
            ),
            spec_request_timeout_seconds=float(
                os.environ.get("SPEC_REQUEST_TIMEOUT_SECONDS", "30")
            ),
            spec_service_allowlist=tuple(
                value.strip().rstrip("/")
                for value in os.environ.get(
                    "SPEC_SERVICE_ALLOWLIST",
                    str(services["spec_editor"]["service_url"]),
                ).split(",")
                if value.strip()
            ),
            circuit_service_allowlist=tuple(
                value.strip().rstrip("/")
                for value in os.environ.get(
                    "CIRCUIT_SERVICE_ALLOWLIST",
                    str(services["circuit_designer"]["service_url"]),
                ).split(",")
                if value.strip()
            ),
            spec_editor_service_url=str(services["spec_editor"]["service_url"]),
            spec_editor_ui_url=str(services["spec_editor"]["ui_url"]),
            circuit_designer_service_url=str(services["circuit_designer"]["service_url"]),
            circuit_designer_ui_url=str(services["circuit_designer"]["ui_url"]),
            ai_assistant_service_url=str(services["ai_assistant"]["service_url"]),
            ai_assistant_ui_url=str(services["ai_assistant"]["ui_url"]),
            logging=load_log_settings(config_path),
        )


def _service_config_path(project_root: Path) -> Path:
    """Resolve the one shared registry without defining per-app fallbacks."""
    return Path(
        os.environ.get(
            "SPEC2GDS_SERVICE_CONFIG",
            str(project_root.parent / "config" / "services.json"),
        )
    ).expanduser().resolve()


def _service_urls(path: Path) -> dict[str, dict[str, str | int]]:
    """Read hosted endpoints used by the Assistant and its browser chooser."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 2:
        raise ValueError("Service registry schema_version must be 2.")
    public_host = _public_host(payload)

    result: dict[str, dict[str, str | int]] = {}
    for name in ("spec_editor", "circuit_designer", "ai_assistant"):
        service = payload[name]["service"]
        ui = payload[name]["ui"]
        result[name] = {
            "host": service["host"],
            "port": service["port"],
            "service_url": _endpoint_url(service, public_host),
            "ui_url": _endpoint_url(ui, public_host),
        }

    result["spec_editor"]["service_url"] = os.environ.get(
        "SPEC_EDITOR_SERVICE_URL", str(result["spec_editor"]["service_url"])
    ).rstrip("/")
    result["circuit_designer"]["service_url"] = os.environ.get(
        "CIRCUIT_DESIGNER_SERVICE_URL",
        str(result["circuit_designer"]["service_url"]),
    ).rstrip("/")
    result["circuit_designer"]["ui_url"] = os.environ.get(
        "CIRCUIT_DESIGNER_UI_URL", str(result["circuit_designer"]["ui_url"])
    ).rstrip("/")
    assistant_override = os.environ.get("AI_ASSISTANT_URL")
    if assistant_override:
        assistant = assistant_override.rstrip("/")
        result["ai_assistant"]["service_url"] = assistant
        result["ai_assistant"]["ui_url"] = assistant
    return result


def _endpoint_url(value: dict[str, object], public_host: str) -> str:
    path = str(value.get("base_path", "")).strip("/")
    suffix = f"/{path}" if path else ""
    authority = f"[{public_host}]" if ":" in public_host else public_host
    return f"{value['scheme']}://{authority}:{value['port']}{suffix}"


def _public_host(payload: dict[str, object]) -> str:
    """Resolve the browser-reachable host independently from wildcard binds."""
    configured = os.environ.get("SPEC2GDS_PUBLIC_HOST", str(payload.get("public_host", "auto")))
    value = configured.strip()
    if value.lower() == "auto":
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect(("192.0.2.1", 9))
                value = str(probe.getsockname()[0])
        except OSError:
            value = socket.gethostname()
    if not value or "://" in value or "/" in value:
        raise ValueError("public_host must be auto, an IP address, or a hostname.")
    return value

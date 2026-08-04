from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


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
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    )
    circuit_service_allowlist: tuple[str, ...] = (
        "http://127.0.0.1:4100/api/circuit-designer/v1",
    )
    spec_editor_service_url: str = "http://127.0.0.1:8000"
    spec_editor_ui_url: str = "http://127.0.0.1:8000/editor"
    circuit_designer_service_url: str = "http://127.0.0.1:4100/api/circuit-designer/v1"
    circuit_designer_ui_url: str = "http://127.0.0.1:4180"
    ai_assistant_service_url: str = "http://127.0.0.1:4200"
    ai_assistant_ui_url: str = "http://127.0.0.1:4200"

    @classmethod
    def from_env(cls) -> "Settings":
        project_root = Path(__file__).resolve().parents[2]
        services = _service_urls(project_root)
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
        )


def _service_urls(project_root: Path) -> dict[str, dict[str, str | int]]:
    path = Path(
        os.environ.get(
            "SPEC2GDS_SERVICE_CONFIG",
            str(project_root.parent / "config" / "services.json"),
        )
    ).expanduser()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Service registry schema_version must be 1.")

    result: dict[str, dict[str, str | int]] = {}
    for name in ("spec_editor", "circuit_designer", "ai_assistant"):
        service = payload[name]["service"]
        ui = payload[name]["ui"]
        result[name] = {
            "host": service["host"],
            "port": service["port"],
            "service_url": _endpoint_url(service),
            "ui_url": _endpoint_url(ui),
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
    assistant_override = os.environ.get("AI_ASSISTANT_URL") or os.environ.get(
        "EXTERNAL_ASSISTANT_URL"
    )
    if assistant_override:
        assistant = assistant_override.rstrip("/")
        result["ai_assistant"]["service_url"] = assistant
        result["ai_assistant"]["ui_url"] = assistant
    return result


def _endpoint_url(value: dict[str, object]) -> str:
    path = str(value.get("base_path", "")).strip("/")
    suffix = f"/{path}" if path else ""
    return f"{value['scheme']}://{value['host']}:{value['port']}{suffix}"

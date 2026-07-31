from __future__ import annotations

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

    @classmethod
    def from_env(cls) -> "Settings":
        project_root = Path(__file__).resolve().parents[2]
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
            host=os.environ.get("ASSISTANT_HOST", "127.0.0.1"),
            port=int(os.environ.get("ASSISTANT_PORT", "4200")),
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
                    "http://127.0.0.1:8000,http://localhost:8000",
                ).split(",")
                if value.strip()
            ),
        )

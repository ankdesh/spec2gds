from __future__ import annotations

import uvicorn
from spec2gds_runtime import StructuredLogger

from .config import Settings


def main() -> None:
    settings = Settings.from_env()
    logger = StructuredLogger("ai-assistant", settings.logging) if settings.logging else None
    if logger:
        logger.event(
            "process",
            "starting",
            "Starting AI Assistant",
            details={"host": settings.host, "port": settings.port},
        )
    uvicorn.run(
        "spec2gds_assistant.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=False,
        access_log=False,
    )
    if logger:
        logger.event("process", "stopped", "Stopped AI Assistant")


if __name__ == "__main__":
    main()

"""Structured JSON logging facility for Testplan Service."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any


class StructuredLogger:
    """Emits structured log records with correlation IDs and execution metrics."""

    def __init__(self, component: str = "testplan-service", stream: Any = None) -> None:
        self.component = component
        self.stream = stream or sys.stderr

    def event(
        self,
        category: str,
        action: str,
        message: str,
        *,
        severity: str = "info",
        correlation_id: str | None = None,
        duration_ms: float | None = None,
        status: int | None = None,
        details: dict[str, Any] | None = None,
        exception: Exception | None = None,
    ) -> None:
        """Write one structured JSON log line."""
        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": self.component,
            "category": category,
            "action": action,
            "severity": severity,
            "message": message,
        }
        if correlation_id:
            record["correlation_id"] = correlation_id
        if duration_ms is not None:
            record["duration_ms"] = round(duration_ms, 2)
        if status is not None:
            record["status"] = status
        if details:
            record["details"] = details
        if exception:
            record["exception"] = {
                "type": type(exception).__name__,
                "message": str(exception),
            }

        line = json.dumps(record, default=str)
        self.stream.write(line + "\n")
        self.stream.flush()

    def info(self, message: str, **kwargs: Any) -> None:
        self.event("general", "info", message, severity="info", **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self.event("general", "warning", message, severity="warning", **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self.event("general", "error", message, severity="error", **kwargs)

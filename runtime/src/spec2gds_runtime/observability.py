"""Process-safe JSON-lines logging shared by the Python applications.

The three applications are intentionally separate processes.  This module uses a
small lock-file protocol instead of a process-local logging handler so every
runtime can safely append to the same file.  When the configured size is reached,
the active file is compacted in place to keep only its newest complete records.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Literal, Mapping
from uuid import uuid4

LogLevel = Literal["info", "debug"]
Severity = Literal["debug", "info", "warning", "error"]

_SECRET_KEYS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
)
_PROCESS_LOCK = threading.Lock()


@dataclasses.dataclass(frozen=True, slots=True)
class LogSettings:
    """Validated observability settings resolved from the shared registry."""

    enabled: bool
    level: LogLevel
    file: Path
    max_bytes: int
    viewer_host: str
    viewer_port: int


def load_log_settings(config_path: Path) -> LogSettings:
    """Load logging settings, allowing only the two documented env overrides."""
    source = config_path.expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 2:
        raise ValueError("Service registry schema_version must be 2.")
    value = payload.get("logging")
    if not isinstance(value, dict):
        raise ValueError("Service registry logging settings are required.")

    enabled_override = os.environ.get("SPEC2GDS_LOGGING")
    enabled = _environment_boolean(enabled_override) if enabled_override is not None else value.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError("logging.enabled must be a boolean.")
    level = str(os.environ.get("SPEC2GDS_LOG_LEVEL", value.get("level", "info"))).lower()
    if level not in {"info", "debug"}:
        raise ValueError("SPEC2GDS_LOG_LEVEL must be info or debug.")
    configured_file = value.get("file")
    if not isinstance(configured_file, str) or not configured_file.strip():
        raise ValueError("logging.file is required.")
    log_file = Path(configured_file).expanduser()
    if not log_file.is_absolute():
        log_file = source.parent / log_file
    max_bytes = value.get("max_bytes")
    if not isinstance(max_bytes, int) or max_bytes < 1024:
        raise ValueError("logging.max_bytes must be an integer of at least 1024.")
    viewer = value.get("viewer")
    if not isinstance(viewer, dict):
        raise ValueError("logging.viewer is required.")
    host = str(viewer.get("host", ""))
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("The log viewer must use a loopback host.")
    port = viewer.get("port")
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("logging.viewer.port must be between 1 and 65535.")
    return LogSettings(enabled, level, log_file.resolve(), max_bytes, host, port)


def _environment_boolean(value: str) -> bool:
    """Parse the deliberately narrow public logging switch."""
    normalized = str(value).strip().lower()
    if normalized == "on":
        return True
    if normalized == "off":
        return False
    raise ValueError("SPEC2GDS_LOGGING must be ON or OFF.")


def redact(value: Any, *, key: str = "") -> Any:
    """Convert arbitrary runtime values into JSON-safe, secret-free data."""
    lowered = key.lower()
    if any(candidate in lowered for candidate in _SECRET_KEYS):
        return "[REDACTED]"
    if isinstance(value, str) and ("base64" in lowered or value.startswith("data:") and ";base64," in value):
        encoded = value.encode("utf-8")
        return {
            "omitted": "base64",
            "characters": len(value),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {
            "omitted": "binary",
            "bytes": len(value),
            "sha256": hashlib.sha256(value).hexdigest(),
        }
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return redact(dataclasses.asdict(value))
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return redact(model_dump(mode="json"))
    if isinstance(value, Mapping):
        return {str(item_key): redact(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [redact(item) for item in value]
    if isinstance(value, BaseException):
        return {"type": type(value).__name__, "message": str(value)}
    return repr(value)


class StructuredLogger:
    """Write one compact JSON object per event without affecting app behavior."""

    def __init__(self, application: str, settings: LogSettings) -> None:
        self.application = application
        self.settings = settings
        self._reported_failure = False

    def event(
        self,
        component: str,
        event: str,
        message: str,
        *,
        severity: Severity = "info",
        origin: Literal["backend", "browser"] = "backend",
        details: Any = None,
        correlation_id: str | None = None,
        session_id: str | None = None,
        duration_ms: float | None = None,
        status: int | str | None = None,
        exception: BaseException | None = None,
        timestamp: str | None = None,
    ) -> None:
        if not self.settings.enabled or (severity == "debug" and self.settings.level != "debug"):
            return
        record: dict[str, Any] = {
            "schema_version": 1,
            "timestamp": timestamp or _utc_timestamp(),
            "severity": severity,
            "detail_level": self.settings.level,
            "application": self.application,
            "origin": origin,
            "component": component,
            "event": event,
            "message": message,
            "event_id": uuid4().hex,
        }
        for field, value in (
            ("correlation_id", correlation_id),
            ("session_id", session_id),
            ("duration_ms", round(duration_ms, 3) if duration_ms is not None else None),
            ("status", status),
        ):
            if value is not None:
                record[field] = value
        # Diagnostic payloads appear only in Debug mode, keeping Info records concise.
        if self.settings.level == "debug" and details is not None:
            record["details"] = redact(details)
        if exception is not None:
            record["exception"] = redact(exception)
            if self.settings.level == "debug":
                record["traceback"] = "".join(
                    traceback.format_exception(type(exception), exception, exception.__traceback__)
                )
        try:
            self._write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        except Exception as reason:  # Logging must never take down a user workflow.
            if not self._reported_failure:
                self._reported_failure = True
                print(f"spec2gds logging disabled after write failure: {reason}", file=os.sys.stderr)

    def browser_events(self, session_id: str, events: list[dict[str, Any]]) -> None:
        """Accept a validated browser batch and reapply server-side redaction."""
        for value in events:
            severity = str(value.get("severity", "info"))
            if severity not in {"debug", "info", "warning", "error"}:
                severity = "warning"
            self.event(
                str(value.get("component", "ui")),
                str(value.get("event", "browser_event")),
                str(value.get("message", "Browser event")),
                severity=severity,  # type: ignore[arg-type]
                origin="browser",
                details=value.get("details"),
                correlation_id=value.get("correlation_id"),
                session_id=session_id,
                timestamp=value.get("timestamp"),
            )

    def _write(self, line: str) -> None:
        encoded = line.encode("utf-8")
        path = self.settings.file
        path.parent.mkdir(parents=True, exist_ok=True)
        with _PROCESS_LOCK:
            lock_path = path.with_name(path.name + ".lock")
            _acquire_lock(lock_path)
            try:
                current_size = path.stat().st_size if path.exists() else 0
                if current_size + len(encoded) > self.settings.max_bytes:
                    _compact_to_newest(path, encoded, self.settings.max_bytes)
                else:
                    with path.open("ab") as stream:
                        stream.write(encoded)
                        stream.flush()
                        os.fsync(stream.fileno())
            finally:
                lock_path.unlink(missing_ok=True)


def _acquire_lock(path: Path, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w", encoding="ascii") as stream:
                stream.write(f"{os.getpid()} {time.time()}\n")
            return
        except FileExistsError:
            # A crashed writer may leave the tiny coordination file behind.
            try:
                if time.time() - path.stat().st_mtime > 30:
                    path.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for log lock {path}.")
            time.sleep(0.01)


def _compact_to_newest(path: Path, incoming: bytes, max_bytes: int) -> None:
    existing = path.read_bytes() if path.exists() else b""
    # A process crash can leave a final partial record.  Never preserve it as if
    # it were valid merely because a later process triggered compaction.
    if existing and not existing.endswith(b"\n"):
        existing = existing.rsplit(b"\n", 1)[0] + b"\n" if b"\n" in existing else b""
    complete = [line + b"\n" for line in existing.splitlines() if line]
    complete.append(incoming)
    kept: list[bytes] = []
    total = 0
    for line in reversed(complete):
        if kept and total + len(line) > max_bytes:
            break
        kept.append(line)
        total += len(line)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(b"".join(reversed(kept)))
    os.replace(temporary, path)


def _utc_timestamp() -> str:
    seconds = time.time()
    whole = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(seconds))
    return f"{whole}.{int(seconds % 1 * 1_000_000):06d}Z"

"""Read-only browser viewer for the combined spec2gds JSONL log."""

from __future__ import annotations

import argparse
import asyncio
import json
import webbrowser
from pathlib import Path
from threading import Timer
from typing import Any, AsyncIterator

from spec2gds_runtime import StructuredLogger

from spec2gds.service_registry import load_service_registry


def create_app() -> Any:
    """Create the configured read-only viewer API and static web application."""
    from fastapi import FastAPI, Query
    from fastapi.responses import FileResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles

    settings = load_service_registry().logging
    assets = Path(__file__).with_name("log_viewer_static")
    app = FastAPI(title="spec2gds Log Viewer", docs_url=None, redoc_url=None)
    app.mount("/assets", StaticFiles(directory=assets), name="log-viewer-assets")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "logging_enabled": settings.enabled,
            "level": settings.level,
        }

    @app.get("/api/logs")
    def logs(
        limit: int = Query(1000, ge=1, le=5000),
        application: str | None = None,
        component: str | None = None,
        severity: str | None = None,
        correlation_id: str | None = None,
        query: str | None = None,
    ) -> dict[str, Any]:
        records, malformed = _read_records(settings.file)
        filtered = [
            record
            for record in records
            if _matches(record, application, component, severity, correlation_id, query)
        ]
        return {
            "logging_enabled": settings.enabled,
            "level": settings.level,
            "records": filtered[-limit:],
            "malformed_lines": malformed,
        }

    @app.get("/api/logs/stream")
    async def stream() -> StreamingResponse:
        return StreamingResponse(
            _tail(settings.file),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(assets / "index.html")

    return app


def _read_records(path: Path) -> tuple[list[dict[str, Any]], int]:
    if not path.exists():
        return [], 0
    records: list[dict[str, Any]] = []
    malformed = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(value, dict):
            records.append(value)
        else:
            malformed += 1
    return records, malformed


def _matches(
    record: dict[str, Any],
    application: str | None,
    component: str | None,
    severity: str | None,
    correlation_id: str | None,
    query: str | None,
) -> bool:
    exact = (
        (application, "application"),
        (component, "component"),
        (severity, "severity"),
        (correlation_id, "correlation_id"),
    )
    if any(expected and str(record.get(field, "")) != expected for expected, field in exact):
        return False
    return not query or query.lower() in json.dumps(record, ensure_ascii=False).lower()


async def _tail(path: Path) -> AsyncIterator[str]:
    """Follow an append-only file and recover when newest-entry compaction shrinks it."""
    position = path.stat().st_size if path.exists() else 0
    while True:
        await asyncio.sleep(0.5)
        if not path.exists():
            position = 0
            continue
        size = path.stat().st_size
        if size < position:
            position = 0
        if size == position:
            yield ": keepalive\n\n"
            continue
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            stream.seek(position)
            for line in stream:
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield f"data: {json.dumps(value, ensure_ascii=False)}\n\n"
            position = stream.tell()


def main() -> None:
    """Start the configured viewer and open it in the user's default browser."""
    parser = argparse.ArgumentParser(description="View combined spec2gds logs.")
    parser.add_argument("--no-open", action="store_true", help="do not open a browser")
    args = parser.parse_args()
    settings = load_service_registry().logging
    public_host = settings.viewer_public_host or settings.viewer_host
    url = f"http://{public_host}:{settings.viewer_port}"
    logger = StructuredLogger("log-viewer", settings)
    logger.event(
        "process", "starting", "Starting spec2gds Log Viewer",
        details={"host": settings.viewer_host, "port": settings.viewer_port},
    )
    print(f"spec2gds log viewer: {url}")
    if not args.no_open:
        # Give uvicorn a moment to bind before the browser performs its first request.
        timer = Timer(0.5, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    import uvicorn

    uvicorn.run(create_app(), host=settings.viewer_host, port=settings.viewer_port, access_log=False)
    logger.event("process", "stopped", "Stopped spec2gds Log Viewer")

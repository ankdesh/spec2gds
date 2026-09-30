"""Command-line entry points for the V1 API and bundled browser editor."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from spec2gds_runtime import StructuredLogger

from spec2gds.service_registry import load_service_registry

_APP_FACTORY = "spec2gds.agent_spec.spec_format.v1_api:create_app"


def _port(value: str) -> int:
    """Parse a TCP port and reject values uvicorn cannot bind."""
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _parser(command: str) -> argparse.ArgumentParser:
    """Build the shared server/editor argument parser."""
    configured = load_service_registry().spec_editor.service
    parser = argparse.ArgumentParser(
        prog=f"spec2gds-{command}",
        description="Run the V1 API and its bundled React/A2UI browser editor.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("AGENT_SPEC_HOST", configured.host),
        help="bind address (default: AGENT_SPEC_HOST or config/services.json)",
    )
    parser.add_argument(
        "--port",
        type=_port,
        default=_port(os.environ.get("AGENT_SPEC_PORT", str(configured.port))),
        help="bind port (default: AGENT_SPEC_PORT or config/services.json)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="restart the service when Python source files change",
    )
    parser.add_argument(
        "--require-human-approval",
        action="store_true",
        help="require explicit approval before assistant changes are saved",
    )
    return parser


def _run(command: str, argv: Sequence[str] | None = None) -> None:
    """Parse one public command and run the shared FastAPI application."""
    args = _parser(command).parse_args(argv)
    # The import-string factory is recreated in uvicorn's reload subprocess.
    os.environ["SPEC2GDS_REQUIRE_HUMAN_APPROVAL"] = "1" if args.require_human_approval else "0"
    registry = load_service_registry()
    logger = StructuredLogger("spec-editor", registry.logging)
    logger.event(
        "process",
        "starting",
        f"Starting spec2gds {command}",
        details={"host": args.host, "port": args.port, "reload": args.reload},
    )
    public_host = registry.public_host if args.host in {"0.0.0.0", "::"} else args.host
    editor_url = f"http://{public_host}:{args.port}/editor"
    if command == "editor":
        print(f"spec2gds editor: {editor_url}")
    else:
        print(f"spec2gds server: http://{public_host}:{args.port}")

    import uvicorn

    # An import-string factory lets uvicorn's reload supervisor recreate the
    # application cleanly instead of retaining an in-memory session object.
    uvicorn.run(
        _APP_FACTORY,
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        access_log=False,
    )
    logger.event("process", "stopped", f"Stopped spec2gds {command}")


def server_main(argv: Sequence[str] | None = None) -> None:
    """Run the local API; the editor remains available at ``/editor``."""
    _run("server", argv)


def editor_main(argv: Sequence[str] | None = None) -> None:
    """Run the local API and print the bundled editor's browser URL."""
    _run("editor", argv)


def main() -> None:
    """Preserve ``python -m spec2gds.agent_spec.api`` as the server command."""
    server_main()


if __name__ == "__main__":
    main()

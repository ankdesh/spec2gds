"""Command-line entry points for the V1 API and bundled browser editor."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from spec2gds_runtime import StructuredLogger
from spec2gds_runtime.launch import factory_bootstrap
from spec2gds_runtime.service_config import listener_overrides

from spec2gds.service_registry import load_service_registry


def _port(value: str) -> int:
    """Parse a TCP port and reject values uvicorn cannot bind."""
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _parser(command: str) -> argparse.ArgumentParser:
    """Build the shared server/editor argument parser."""
    parser = argparse.ArgumentParser(
        prog="spec2gds-spec-editor" if command == "editor" else "spec2gds-spec-service",
        description="Run the Spec service API and bundled Spec Editor.",
    )
    parser.add_argument("--service-config", type=Path,
                        help="service configuration file (CLI > file > defaults)")
    parser.add_argument("--spec-root", type=Path, help="allowed Spec directory")
    parser.add_argument("--public-host", help="host advertised for wildcard listeners; accepts auto")
    parser.add_argument("--host", help="listener bind address")
    parser.add_argument("--port", type=_port, help="listener port")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="restart the service when Python source files change",
    )
    parser.add_argument(
        "--require-designer-approval", "--require-human-approval",
        dest="require_designer_approval",
        action="store_true",
        help="require explicit approval before assistant changes are saved",
    )
    return parser


def _run(command: str, argv: Sequence[str] | None = None) -> None:
    """Parse one public command and run the shared FastAPI application."""
    args = _parser(command).parse_args(argv)
    overrides = listener_overrides("spec_editor", host=args.host, port=args.port)
    if args.public_host is not None:
        overrides["public_host"] = args.public_host
    if args.spec_root is not None and not args.spec_root.expanduser().is_dir():
        raise ValueError("Spec root must be an existing directory.")
    if args.spec_root is not None:
        overrides.setdefault("spec_editor", {})["spec_root"] = str(args.spec_root.expanduser().resolve())
    registry = load_service_registry(args.service_config, overrides=overrides)
    print(f"Spec root: {registry.config['spec_editor']['spec_root']}")
    args.host, args.port = registry.spec_editor.service.host, registry.spec_editor.service.port
    logger = StructuredLogger("spec-editor", registry.logging)
    logger.event(
        "process",
        "starting",
        f"Starting spec2gds {command}",
        details={"host": args.host, "port": args.port, "reload": args.reload},
    )
    if command == "editor":
        print(f"spec2gds Spec Editor: {registry.spec_editor.ui.url}")
    else:
        print(f"spec2gds Spec service: {registry.spec_editor.service.url}")

    import uvicorn

    # An import-string factory lets uvicorn's reload supervisor recreate the
    # application cleanly instead of retaining an in-memory session object.
    uvicorn.run(
        factory_bootstrap(
            "def create_app():\n"
            "    from spec2gds.spec.spec_format.v1_api import create_app as build\n"
            f"    return build(service_config=SERVICE_CONFIG, require_designer_approval={args.require_designer_approval!r})\n",
            registry.config,
        ),
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
    """Preserve ``python -m spec2gds.spec.api`` as the server command."""
    server_main()


if __name__ == "__main__":
    main()

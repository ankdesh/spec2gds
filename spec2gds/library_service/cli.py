"""Command-line entry point for running the standalone library service."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

from spec2gds.library_service.service import create_app


def main(argv: list[str] | None = None) -> int:
    """Entry point for spec2gds-library-service."""
    parser = argparse.ArgumentParser(
        prog="spec2gds-library-service",
        description="Run the standalone Spec2GDS Component Library service",
    )
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Bind host address")
    parser.add_argument("--port", type=int, default=6017, help="Bind port number")
    parser.add_argument("--library-root", type=Path, default=Path("spec_library"), help="Library root directory")
    parser.add_argument("--state-dir", type=Path, default=Path("spec_library/.state"), help="State directory")

    args = parser.parse_args(argv)

    app = create_app(library_root=args.library_root, state_dir=args.state_dir)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())

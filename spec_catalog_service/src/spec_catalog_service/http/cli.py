"""Command-line entry point for running the standalone library service."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn
from spec2gds_runtime.service_config import listener_overrides, resolve_config

from spec_catalog_service.http.service import create_app


def main(argv: list[str] | None = None) -> int:
    """Entry point for spec2gds-catalog-service."""
    parser = argparse.ArgumentParser(
        prog="spec2gds-catalog-service",
        description="Run the standalone Spec Catalog service",
    )
    parser.add_argument("--service-config", type=Path)
    parser.add_argument("--public-host")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--catalog-root", type=Path)
    parser.add_argument("--state-dir", type=Path)

    args = parser.parse_args(argv)

    overrides = listener_overrides("spec_catalog", host=args.host, port=args.port)
    if args.public_host:
        overrides["public_host"] = args.public_host
    for field in ("catalog_root", "state_dir"):
        value = getattr(args, field)
        if value is not None:
            overrides["spec_catalog"][field] = str(value.resolve())
    config = resolve_config(args.service_config, overrides=overrides)["spec_catalog"]
    app = create_app(library_root=Path(config["catalog_root"]), state_dir=Path(config["state_dir"]))
    uvicorn.run(app, host=config["service"]["host"], port=config["service"]["port"], log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())

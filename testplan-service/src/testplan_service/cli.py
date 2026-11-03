"""Command-line entry point for Verification Planner service."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

import uvicorn
from spec2gds_runtime.launch import factory_bootstrap
from spec2gds_runtime.service_config import endpoint_url, listener_overrides, resolve_config

from testplan_service.constants import (
    DEFAULT_PRODUCT_TITLE,
    DEFAULT_STORAGE_DIR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("testplan-service")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verification-planner",
        description=f"{DEFAULT_PRODUCT_TITLE} Service and Interactive Web Editor",
    )
    parser.add_argument("--service-config", type=Path)
    parser.add_argument("--public-host")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument(
        "--storage-dir",
        default=DEFAULT_STORAGE_DIR,
        help=f"Directory for SQLite verification data storage (default: {DEFAULT_STORAGE_DIR})",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for local development",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    overrides = listener_overrides("verification_planner", host=args.host, port=args.port)
    if args.public_host is not None:
        overrides["public_host"] = args.public_host
    config = resolve_config(args.service_config, overrides=overrides)
    endpoint = config["verification_planner"]["service"]
    args.host, args.port = endpoint["host"], endpoint["port"]
    print(f"Verification Planner: {endpoint_url(config['verification_planner']['ui'], config['public_host'])}")
    storage_path = Path(args.storage_dir).resolve()

    logger.info(
        "Starting %s on http://%s:%s (storage: %s)",
        DEFAULT_PRODUCT_TITLE,
        args.host,
        args.port,
        storage_path,
    )

    app = factory_bootstrap(
        "def create_app():\n"
        "    from testplan_service.api.app import create_app as build\n"
        f"    return build(storage_dir=Path({str(storage_path)!r}))\n",
        config,
    )

    uvicorn.run(
        app,
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        access_log=False,
    )


if __name__ == "__main__":
    main()

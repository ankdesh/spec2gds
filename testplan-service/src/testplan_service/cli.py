"""Command-line entry point for Verification Planner service."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

import uvicorn

from testplan_service.api.app import create_app
from testplan_service.constants import (
    DEFAULT_PRODUCT_TITLE,
    DEFAULT_SERVICE_HOST,
    DEFAULT_SERVICE_PORT,
    DEFAULT_STORAGE_DIR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("testplan-service")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verification-planner",
        description=f"{DEFAULT_PRODUCT_TITLE} Service and Interactive Web Editor",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_SERVICE_HOST,
        help=f"Bind host address (default: {DEFAULT_SERVICE_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_SERVICE_PORT,
        help=f"Bind port (default: {DEFAULT_SERVICE_PORT})",
    )
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
    storage_path = Path(args.storage_dir).resolve()

    logger.info(
        "Starting %s on http://%s:%s (storage: %s)",
        DEFAULT_PRODUCT_TITLE,
        args.host,
        args.port,
        storage_path,
    )

    app = create_app(storage_dir=storage_path)

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        access_log=False,
    )


if __name__ == "__main__":
    main()

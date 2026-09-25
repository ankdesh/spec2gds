"""Command-line entry point for Testplan Service."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import uvicorn

from testplan_service.api.app import create_app
from testplan_service.constants import (
    DEFAULT_SERVICE_HOST,
    DEFAULT_SERVICE_PORT,
    DEFAULT_STORAGE_DIR,
)
from testplan_service.logging import StructuredLogger
from testplan_service.storage.file_repository import FileTestPlanRepository


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="testplan-service",
        description="Hierarchical Testplan Management Service and Interactive Editor",
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
        help=f"Directory for JSON testplan storage (default: {DEFAULT_STORAGE_DIR})",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Pre-seed storage with realistic sample testplans (ALU, UART, FIFO, Crossbar)",
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
    logger = StructuredLogger("testplan-service")

    logger.info(
        f"Starting testplan-service on http://{args.host}:{args.port}",
        details={"storage_dir": str(storage_path), "reload": args.reload},
    )

    repo = FileTestPlanRepository(storage_path)

    # Pre-seed if explicitly requested or if storage directory contains no testplans
    existing_plans = repo.list_all()
    if args.seed or len(existing_plans) == 0:
        from testplan_service.samples.seed import seed_repository

        seeded = seed_repository(repo)
        logger.info(
            f"Seeded {len(seeded)} sample testplan(s) into {storage_path}",
            details={"plan_ids": [p.id for p in seeded]},
        )

    app = create_app(repository=repo, logger=logger)

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        access_log=False,
    )


if __name__ == "__main__":
    main()

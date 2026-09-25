"""Utility to seed storage repositories with realistic sample testplans."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from testplan_service.constants import DEFAULT_STORAGE_DIR
from testplan_service.logging import StructuredLogger
from testplan_service.models.testplan import TestPlanDocument
from testplan_service.samples import build_all_sample_plans
from testplan_service.storage.file_repository import FileTestPlanRepository
from testplan_service.storage.interface import TestPlanRepository


def seed_repository(repository: TestPlanRepository) -> list[TestPlanDocument]:
    """Populate a repository with all standard domain sample testplans."""
    plans = build_all_sample_plans()
    for plan in plans:
        repository.save(plan)
    return plans


def main(argv: Sequence[str] | None = None) -> None:
    """Command-line entrypoint to seed the on-disk storage directory."""
    parser = argparse.ArgumentParser(
        prog="testplan-seed",
        description="Seed testplan-service storage with diverse domain testplans",
    )
    parser.add_argument(
        "--storage-dir",
        default=DEFAULT_STORAGE_DIR,
        help=f"Target storage directory (default: {DEFAULT_STORAGE_DIR})",
    )
    args = parser.parse_args(argv)

    storage_path = Path(args.storage_dir).resolve()
    repo = FileTestPlanRepository(storage_path)
    logger = StructuredLogger("testplan-seed")

    plans = seed_repository(repo)
    logger.info(
        f"Successfully seeded {len(plans)} sample testplan(s) into {storage_path}",
        details={"plan_ids": [p.id for p in plans]},
    )
    for p in plans:
        print(f"  • {p.name} [{p.id}] -> {len(p.nodes)} nodes")


if __name__ == "__main__":
    main()

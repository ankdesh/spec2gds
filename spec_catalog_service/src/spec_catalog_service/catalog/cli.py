"""Command-line interface for spec2gds-catalog."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spec_catalog_service.catalog.checker import LibraryChecker, is_temp_directory
from spec_catalog_service.catalog.indexer import LibraryIndexer
from spec_catalog_service.catalog.publisher import LibraryPublisher
from spec_catalog_service.catalog.verifier import LibraryVerifier


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="spec2gds-catalog",
        description="Spec Catalog management and verification utility",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # check
    check_p = subparsers.add_parser("check", help="Validate inventory, DAG, packages, and evidence")
    check_p.add_argument("--phase", type=int, required=True, choices=[1, 2, 3, 4], help="Catalog rollout phase")
    check_p.add_argument("--output", type=Path, required=True, help="Directory inside temp/TEMP_* for report")
    check_p.add_argument("--candidates", type=Path, default=None, help="Optional candidate tree root")
    check_p.add_argument("--catalog-root", type=Path, default=Path("spec_catalog_service/catalog"), help="Canonical catalog root")

    # verify
    verify_p = subparsers.add_parser("verify", help="Run hardware verification across presets")
    verify_p.add_argument("--phase", type=int, required=True, choices=[1, 2, 3, 4], help="Catalog rollout phase")
    verify_p.add_argument("--output", type=Path, required=True, help="Directory inside temp/TEMP_* for evidence and report")
    verify_p.add_argument("--candidates", type=Path, default=None, help="Optional candidate tree root")
    verify_p.add_argument("--catalog-root", type=Path, default=Path("spec_catalog_service/catalog"), help="Canonical catalog root")

    # publish
    pub_p = subparsers.add_parser("publish", help="Publish verified candidate releases into canonical library")
    pub_p.add_argument("--phase", type=int, required=True, choices=[1, 2, 3, 4], help="Catalog rollout phase")
    pub_p.add_argument("--candidates", type=Path, required=True, help="Candidate tree root")
    pub_p.add_argument("--evidence", type=Path, required=True, help="Verification evidence directory")
    pub_p.add_argument("--output", type=Path, required=True, help="Directory inside temp/TEMP_* for publication report")
    pub_p.add_argument("--catalog-root", type=Path, default=Path("spec_catalog_service/catalog"), help="Canonical catalog root")

    # index
    idx_p = subparsers.add_parser("index", help="Rebuild SQLite catalogue index")
    idx_p.add_argument("--catalog-root", type=Path, default=Path("spec_catalog_service/catalog"), help="Canonical catalog root")
    idx_p.add_argument("--state-dir", type=Path, default=Path("spec_catalog_service/.state"), help="State directory")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for spec2gds-catalog CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand in {"check", "verify", "publish"}:
        if not is_temp_directory(args.output):
            print(f"Error: --output directory {args.output} must be inside an ignored temp/TEMP_* directory.", file=sys.stderr)
            return 2

    if args.subcommand == "check":
        checker = LibraryChecker(
            phase=args.phase,
            library_root=args.catalog_root,
            candidates=args.candidates,
            output=args.output,
        )
        code, report = checker.check()
        print(f"Check completed with status '{report.get('overall_status')}': {len(report.get('errors', []))} error(s)")
        return code

    elif args.subcommand == "verify":
        verifier = LibraryVerifier(
            phase=args.phase,
            library_root=args.catalog_root,
            candidates=args.candidates,
            output=args.output,
        )
        code, report = verifier.verify()
        print(f"Verify completed with status '{report.get('overall_status')}'")
        return code

    elif args.subcommand == "publish":
        publisher = LibraryPublisher(
            phase=args.phase,
            candidates=args.candidates,
            evidence=args.evidence,
            output=args.output,
            library_root=args.catalog_root,
        )
        code, report = publisher.publish()
        print(f"Publish completed with status '{report.get('overall_status')}': {len(report.get('published', []))} published")
        return code

    elif args.subcommand == "index":
        indexer = LibraryIndexer(
            library_root=args.catalog_root,
            state_dir=args.state_dir,
        )
        stats = indexer.rebuild()
        print(f"Index rebuild completed: {stats['components_indexed']} components, {stats['releases_indexed']} releases.")
        if stats["errors"]:
            print(f"Warnings/Errors encountered: {len(stats['errors'])}", file=sys.stderr)
            return 1
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())

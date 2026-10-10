"""CLI for the custom IP-XACT-centered V1 `.spec` package."""

import argparse
import json
import pathlib
import sys

from spec2gds.spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.naming import (
    document_name,
    entity_name,
    normalize_package_names,
    readable_name,
)
from spec2gds.spec.spec_format.review_store import review_bridge
from spec2gds.spec.spec_format.proposal_service import reconcile_assistant_receipts
from spec2gds.spec.spec_format.spec_service_store import document_key
from spec2gds.spec.spec_format.v1_api import V1Session
from spec2gds.spec.spec_format.workspace_target import (
    assistant_state_root,
    resolve_spec_target,
)


def _parser() -> argparse.ArgumentParser:
    """Build the V1 source-package command line parser."""
    parser = argparse.ArgumentParser(prog="spec2gds-spec", description="IP-XACT-centered spec2gds V1 package tool")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Create an empty V1 .spec package.")
    create.add_argument("--output", required=True)
    create.add_argument("--name", help="Readable specification name")
    create.add_argument("--document-id", help=argparse.SUPPRESS)

    validate = commands.add_parser("validate", help="Validate a V1 .spec package.")
    validate.add_argument("--container", required=True)

    inspect = commands.add_parser("inspect", help="Inspect a V1 .spec package.")
    inspect.add_argument("--container", required=True)
    inspect.add_argument("--format", choices=["json", "text"], default="text")

    unpack = commands.add_parser("unpack", help="Unpack a V1 .spec package.")
    unpack.add_argument("--container", required=True)
    unpack.add_argument("--output", required=True)

    pack = commands.add_parser("pack", help="Pack an unpacked V1 .spec directory.")
    pack.add_argument("--input", required=True)
    pack.add_argument("--output", required=True)
    for command in (create, validate, unpack, pack):
        command.add_argument("--json", action="store_true", help="Include exact technical identifiers")
    for action in ("architecture-reviews",):
        review = commands.add_parser(action, help="Inspect stored architecture reviews.")
        review.add_argument("target", help="Workspace directory or exact .spec path")
        review.add_argument("--json", action="store_true", help="Include exact technical identifiers")
    for action in ("reviews", "history"):
        review = commands.add_parser(action, help=f"{action.capitalize()} assistant proposals for one specification.")
        review.add_argument("target", help="Workspace directory or exact .spec path")
        review.add_argument("--json", action="store_true", help="Include exact technical identifiers")
        if action == "history":
            review.add_argument("--before", type=int)
            review.add_argument("--limit", type=int, default=50)
    return parser


def _review_command(target: str, technical: bool = False) -> int:
    """Inspect the Spec service journal without changing decisions or host state."""
    path = resolve_spec_target(target)
    session = V1Session(str(path))
    reconcile_assistant_receipts(session)
    items = []
    cursor = None
    while True:
        page = session.journal.history(cursor)
        items.extend(page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    if technical:
        print(json.dumps({"spec_path": str(path), "reviews": items}, indent=2))
    else:
        print(document_name(session.revision))
        for item in items:
            print(f"Review {item['ordinal']}: {item['title']} · {item['state']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Execute one V1 package command and return a shell-compatible status."""
    args = _parser().parse_args(argv)
    try:
        if args.command == "architecture-reviews":
            path = resolve_spec_target(args.target)
            root = assistant_state_root(path)
            listing = review_bridge(root, "architecture-list")["architecture_reviews"]
            document_id = SpecPackage.load(str(path)).manifest.document_id
            owner_key = document_key(str(path), document_id)
            available = [item for item in listing if ((item.get("serviceDocumentKey") == owner_key and item.get("documentId") == document_id) or (item.get("destinationServiceDocumentKey") == owner_key and item.get("destinationDocumentId") == document_id))]
            for number, item in enumerate(available, 1):
                item.setdefault("reviewNumber", number)
            if args.command == "architecture-reviews":
                if args.json:
                    print(json.dumps({"architecture_reviews": available}, indent=2))
                else:
                    for item in available:
                        print(f"Architecture review {item['reviewNumber']}: {item.get('plan', {}).get('title', 'Architecture')} · {item['status']}")
                return 0
        if args.command == "reviews":
            return _review_command(args.target, args.json)
        if args.command == "history":
            path = resolve_spec_target(args.target)
            session = V1Session(str(path))
            reconcile_assistant_receipts(session)
            history = session.journal.history(args.before, args.limit)
            if args.json:
                print(json.dumps(history, indent=2))
            else:
                for item in history["items"]:
                    print(f"Review {item['ordinal']}: {item['title']} · {item['state']}")
            return 0
        if args.command == "create":
            output = pathlib.Path(args.output)
            if output.exists():
                raise ValueError(f"Refusing to overwrite existing package: {output}")
            package = SpecPackage.create(document_id=args.document_id, title=args.name or readable_name(output.stem))
            normalize_package_names(package)
            package.save(str(output))
            print(json.dumps({"container": str(output), "document_id": package.manifest.document_id}, sort_keys=True) if args.json else f"Created {package.narrative.title}: {output}")
            return 0
        if args.command == "validate":
            package = SpecPackage.load(args.container)
            print(json.dumps({"container": args.container, "source_hash": package.source_hash(), "valid": True}, sort_keys=True) if args.json else f"Valid: {package.narrative.title or readable_name(pathlib.Path(args.container).stem)}")
            return 0
        if args.command == "inspect":
            package = SpecPackage.load(args.container)
            report = {
                "manifest": package.manifest.model_dump(mode="json"),
                "source_hash": package.source_hash(),
                "paths": sorted(package.files),
            }
            if args.format == "text":
                revision = SpecRevision.from_package(package)
                print(document_name(revision))
                print("documents:")
                for entity in (*revision.components, *revision.designs, *revision.bus_definitions, *revision.abstraction_definitions):
                    print(f"  - {entity.ref.entity_kind}: {entity_name(entity)}")
            else:
                print(json.dumps(report, indent=2, sort_keys=True))
            return 0
        if args.command == "unpack":
            package = SpecPackage.load(args.container)
            package.unpack(args.output)
            print(json.dumps({"container": args.container, "output": args.output}, sort_keys=True) if args.json else f"Unpacked {package.narrative.title}: {args.output}")
            return 0
        if args.command == "pack":
            output = pathlib.Path(args.output)
            if output.exists():
                raise ValueError(f"Refusing to overwrite existing package: {output}")
            package = SpecPackage.from_directory(args.input)
            package.save(str(output))
            print(json.dumps({"input": args.input, "container": str(output)}, sort_keys=True) if args.json else f"Packed {package.narrative.title}: {output}")
            return 0
    except (OSError, ValueError, SpecValidationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

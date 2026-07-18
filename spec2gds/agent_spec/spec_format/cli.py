"""CLI for the custom IP-XACT-centered V1 `.spec` package."""

import argparse
import json
import pathlib
import sys

from spec2gds.agent_spec.spec_format.archive import SpecPackage, SpecValidationError


def _parser() -> argparse.ArgumentParser:
    """Build the V1 source-package command line parser."""
    parser = argparse.ArgumentParser(description="IP-XACT-centered spec2gds V1 package tool")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Create an empty V1 .spec package.")
    create.add_argument("--output", required=True)
    create.add_argument("--document-id")

    validate = commands.add_parser("validate", help="Validate a V1 .spec package.")
    validate.add_argument("--container", required=True)

    inspect = commands.add_parser("inspect", help="Inspect a V1 .spec package.")
    inspect.add_argument("--container", required=True)
    inspect.add_argument("--format", choices=["json", "text"], default="json")

    unpack = commands.add_parser("unpack", help="Unpack a V1 .spec package.")
    unpack.add_argument("--container", required=True)
    unpack.add_argument("--output", required=True)

    pack = commands.add_parser("pack", help="Pack an unpacked V1 .spec directory.")
    pack.add_argument("--input", required=True)
    pack.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute one V1 package command and return a shell-compatible status."""
    args = _parser().parse_args(argv)
    try:
        if args.command == "create":
            output = pathlib.Path(args.output)
            if output.exists():
                raise ValueError(f"Refusing to overwrite existing package: {output}")
            package = SpecPackage.create(document_id=args.document_id)
            package.save(str(output))
            print(json.dumps({"container": str(output), "document_id": package.manifest.document_id}, sort_keys=True))
            return 0
        if args.command == "validate":
            package = SpecPackage.load(args.container)
            print(json.dumps({"container": args.container, "source_hash": package.source_hash(), "valid": True}, sort_keys=True))
            return 0
        if args.command == "inspect":
            package = SpecPackage.load(args.container)
            report = {
                "manifest": package.manifest.model_dump(mode="json"),
                "source_hash": package.source_hash(),
                "paths": sorted(package.files),
            }
            if args.format == "text":
                print(f"document_id: {package.manifest.document_id}")
                print(f"source_hash: {report['source_hash']}")
                print("documents:")
                for entry in package.manifest.documents:
                    print(f"  - {entry.kind}: {entry.vlnv} ({entry.path})")
            else:
                print(json.dumps(report, indent=2, sort_keys=True))
            return 0
        if args.command == "unpack":
            package = SpecPackage.load(args.container)
            package.unpack(args.output)
            print(json.dumps({"container": args.container, "output": args.output}, sort_keys=True))
            return 0
        if args.command == "pack":
            output = pathlib.Path(args.output)
            if output.exists():
                raise ValueError(f"Refusing to overwrite existing package: {output}")
            package = SpecPackage.from_directory(args.input)
            package.save(str(output))
            print(json.dumps({"input": args.input, "container": str(output)}, sort_keys=True))
            return 0
    except (OSError, ValueError, SpecValidationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate a selected component/design by its readable name."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from spec2gds.agent_spec.activities import (
    ActivitySnapshot,
    LocalActivityWorkspace,
    SpecExtensionRegistry,
    activity_availability,
    invoke_activity,
)
from spec2gds.agent_spec.activities.rtl import register_extensions
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.naming import entity_name, select_entity


def select_target(revision: SpecRevision, selection: str | None):
    """Reject ambiguous defaults and fuzzy names before any workspace mutation."""
    if selection is None:
        candidates = revision.entry_designs()
        if len(candidates) != 1:
            raise ValueError("Use --target with a component or design name; no unique entry design exists.")
        return candidates[0]
    return select_entity(revision, selection)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec_path", type=Path)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--target", help="Readable component/design name (technical IDs and VLNVs also accepted)")
    parser.add_argument("--json", action="store_true", help="Print the machine-readable report including provenance IDs")
    args = parser.parse_args()
    revision = SpecRevision.load(str(args.spec_path.resolve()))
    try:
        target = select_target(revision, args.target)
    except ValueError as exc:
        parser.error(str(exc))
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    snapshot = ActivitySnapshot.create(revision, target.ref)
    availability = activity_availability(registry, "rtl.generate", snapshot)
    if not args.json:
        print("Target:", entity_name(target))
    if not args.json:
        for diagnostic in availability.diagnostics:
            print(diagnostic)
    if not availability.available:
        return 2
    result = invoke_activity(registry, "rtl.generate", snapshot, LocalActivityWorkspace(args.workspace.resolve()))
    if args.json:
        print(json.dumps(result.report, indent=2))
    else:
        print(result.summary)
    if not args.json:
        print("Generated:", args.workspace.resolve() / result.report["output_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

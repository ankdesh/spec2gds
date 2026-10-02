"""Generate a selected component/design by exact entity ID or full VLNV."""
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


def select_target(revision: SpecRevision, selection: str | None):
    """Reject ambiguous defaults and fuzzy names before any workspace mutation."""
    if selection is None:
        candidates = revision.entry_designs()
        if len(candidates) != 1:
            raise ValueError("Use --target with an exact component/design entity ID or full VLNV; no unique entry design exists.")
        return candidates[0]
    candidates = [item for item in (*revision.components, *revision.designs)
                  if item.ref.entity_id == selection or item.vlnv == selection]
    if len(candidates) != 1:
        raise ValueError(f"Unknown or ambiguous RTL target {selection!r}; use an exact entity ID or full VLNV.")
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec_path", type=Path)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--target", help="Exact entity ID or vendor:library:name:version")
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
    print("Target:", target.vlnv)
    for diagnostic in availability.diagnostics:
        print(diagnostic)
    if not availability.available:
        return 2
    result = invoke_activity(registry, "rtl.generate", snapshot, LocalActivityWorkspace(args.workspace.resolve()))
    print(json.dumps(result.report, indent=2))
    print("Generated:", args.workspace.resolve() / result.report["output_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Generate RTL from spec without using the UI

from __future__ import annotations

import json
import sys
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

# Get spec and workspace
spec_path = Path(sys.argv[1]).resolve()
workspace = Path(sys.argv[2]).resolve()

revision = SpecRevision.load(str(spec_path))

requested_target = sys.argv[3] if len(sys.argv) > 3 else None
target = None

if requested_target:
    target = next((c for c in revision.components if c.ref.entity_id == requested_target or requested_target in c.vlnv or requested_target in c.ref.entity_id), None)
    if target is None and revision.designs:
        target = next((d for d in revision.designs if d.ref.entity_id == requested_target or requested_target in d.vlnv or requested_target in d.ref.entity_id), None)

if target is None:
    if revision.entry_designs():
        target = revision.entry_designs()[0]
    elif revision.components:
        target = revision.components[-1]
    else:
        raise SystemExit("The package has no entry designs or components.")

registry = SpecExtensionRegistry()
register_extensions(registry)

snapshot = ActivitySnapshot.create(revision, target.ref)
availability = activity_availability(registry, "rtl.generate", snapshot)

print("Target:", target.vlnv)
print("Available:", availability.available)
for diagnostic in availability.diagnostics:
    print(diagnostic)

if not availability.available:
    raise SystemExit(2)

result = invoke_activity(
    registry,
    "rtl.generate",
    snapshot,
    LocalActivityWorkspace(workspace),
)

print(json.dumps(result.report, indent=2))
print("Generated:", workspace / result.report["output_path"])

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

if not revision.entry_designs():
    raise SystemExit("The package has no entry design.")

target = revision.entry_designs()[0]

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

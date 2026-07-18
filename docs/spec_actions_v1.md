# V1.3 Actions, Artifacts, and Reviewed Proposals

V1.3 adds the generic execution platform above V1.2's immutable `SpecRevision`.
An action targets a component or design through `EntityRef`; it receives a
read-only dependency snapshot, never a writable live `.spec` package.

## Execute a Reference Action

```python
from pathlib import Path

from spec2gds.agent_spec.spec_format import (
    ActionService,
    ActivityStore,
    ArtifactSidecar,
    SpecRevision,
    create_reference_registry,
)

revision = SpecRevision.load("design.spec")
package = revision.to_package()
sidecar = ArtifactSidecar(Path(".spec-artifacts"))
activity = ActivityStore(package, sidecar)
service = ActionService(create_reference_registry(), sidecar)

execution = service.execute(
    revision,
    activity,
    "reference.snapshot_summary",
    revision.entry_designs()[0].ref,
)
assert execution.status == "succeeded"
package.save("design-with-activity.spec")
```

The action service creates isolated input/output directories, writes a
language-neutral snapshot bundle, invokes the configured local command, and
requires `completion.json` in the output directory. It records an action
execution, report, artifact metadata, and any proposal under `activity/`.
That metadata is excluded from `source_revision_hash`.

Artifact bytes are stored in the content-addressed sidecar, not in `.spec`.
Use `ActivityStore.artifact_diagnostics()` to report a missing or corrupt
sidecar object without corrupting source state.

## Reference Actions

- `reference.snapshot_summary` creates a JSON summary artifact from a component
  or design snapshot.
- `reference.artifact_transform` consumes one selected text/JSON artifact and
  creates an immutable upper-case child artifact with lineage.
- `reference.narrative_proposal` produces a harmless pending narrative edit.

## Review a Proposal

```python
proposal = activity.state.proposals[0]
preview = service.preview_proposal(revision, activity, proposal.proposal_id)
if preview.succeeded:
    accepted = service.accept_proposal(revision, activity, proposal.proposal_id)
    next_revision = accepted.revision
```

Actions cannot change source directly. Acceptance rechecks the proposal's base
source hash and applies its operations through the V1.2 transaction validator.
Reject with `service.reject_proposal(activity, proposal_id)`; the execution
record remains while source is unchanged.

Run all V1 package, SpecIR, and action-platform tests with:

```bash
uv run python -m pytest tests/agent_spec/spec_format -q
```

See [V1.3 — Actions, Artifacts, and Reviewed Change Proposals](pivot/v1_03_actions_artifacts_and_change_proposals.md)
for the full contract and exit gate.

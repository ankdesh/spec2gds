# Post-Pivot V1 Code Map

The production implementation is intentionally concentrated in
`spec2gds/agent_spec/spec_format/`. No compatibility adapter loads the removed
ODT/heading prototype.

| Module | Responsibility |
| --- | --- |
| `models.py` | Strict source-package contracts and cross-field invariants. |
| `archive.py` | Deterministic ZIP I/O, package validation, and source hashing. |
| `ipxact.py` | IP-XACT 1685-2022 parsing and profile validation. |
| `ir.py` | Immutable editor/action projection, queries, and dependency closure. |
| `transactions.py` | Atomic, revision-guarded source edits. |
| `actions.py` | Action contracts, snapshots, executions, artifacts, and proposals. |
| `reference_actions.py` | Small trusted subprocess actions used for V1 acceptance. |
| `v1_api.py` | The single HTTP composition root and session boundary. |
| `editor/` | A no-build browser client that owns presentation state only. |
| `samples.py` | Deterministic, visually rich V1 acceptance fixture. |

## Runtime Flow

1. `V1Session` validates a package and constructs an immutable `SpecRevision`.
2. The editor renders the snapshot returned by the API; it never mutates a
   `SpecPackage` directly.
3. Source changes become typed `SpecEditTransaction` operations guarded by the
   current source revision hash.
4. Actions execute against immutable dependency snapshots. Generated content
   is stored in a content-addressed sidecar and recorded in package activity.
5. A proposal changes source only after explicit review and revalidation.

## Maintenance Rules

- Add source semantics to the models and IR first, then expose them through
  transactions and the API.
- Keep derived UI views out of the package; recompute them from SpecIR.
- Keep action activity out of the source revision hash.
- Preserve stable entity and narrative block IDs across edits.
- Extend `build_v1_sample()` whenever a new editor-visible V1 feature lands.

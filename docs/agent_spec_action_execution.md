# Agent-Spec V1 Action Execution Contract

Actions are trusted local tools that read immutable source snapshots and return
reports, generated artifacts, and optional reviewed source proposals. They
target a component or design by stable `EntityRef`; there is no heading/block
execution model.

## Action Definition

An `ActionDefinition` declares:

- stable `action_id`, semantic `version`, and user-facing `title`;
- accepted target entity kinds;
- JSON Schema for normalized inputs and reports;
- required capabilities and optional preconditions/postconditions;
- consumed and produced artifact roles;
- local executor command and timeout;
- whether change proposals are permitted.

Definitions are registered explicitly in `ActionRegistry`. Duplicate action IDs
are rejected rather than replaced.

## Execution Sequence

1. Resolve the target from the current immutable `SpecRevision`.
2. Validate target kind, JSON inputs, selected input artifact roles, and action
   preconditions.
3. Compute the target dependency closure and linked narrative blocks.
4. Capture a deterministic `ActionSnapshot` identified by its source revision,
   target, action version, closure, normalized inputs, and input artifacts.
5. Write a language-neutral snapshot bundle to an isolated temporary input
   directory.
6. Invoke the trusted command with `--input <dir> --output <dir>` and a bounded
   timeout.
7. Validate `completion.json`, report schema, artifact declarations, hashes,
   sizes, provenance, parent lineage, proposal permission, and postconditions.
8. Ingest artifact bytes into the content-addressed sidecar and append durable
   activity records.

Timeouts, non-zero exits, malformed completion data, and failed contracts
produce a durable failed execution with diagnostics. Partial outputs are not
accepted.

## Snapshot Bundle

```text
input/
├── snapshot.json
├── source/
│   ├── manifest.json
│   ├── document.json
│   └── ipxact/... selected dependency documents
├── assets/...
├── annotations/...
└── input-artifacts/...
```

`snapshot.json` records the snapshot ID, source revision hash, target,
dependency closure, selected source documents, linked narrative, accepted
annotations, normalized inputs, and input artifact metadata. The executor has
no writable handle to the live package.

## Completion Manifest

The executor writes `output/completion.json` with:

```json
{
  "status": "succeeded",
  "toolchain_identity": "tool/name@version",
  "report": {"summary": "Human-readable result"},
  "artifacts": [],
  "proposals": []
}
```

Every declared artifact names a role, kind, media type, output-relative path,
and optionally explicit size/hash, source entities, and selected parent
artifact IDs. Paths must remain below the output directory.

## Provenance

`ArtifactRef` binds immutable bytes to:

- the producing execution and action;
- the source revision and stable source entities;
- normalized action inputs and selected input artifacts;
- parent artifact IDs;
- toolchain identity, media type, size, and SHA-256 locator.

The sidecar verifies content hashes on both ingest and read. Missing or corrupt
content appears as artifact diagnostics; it does not invalidate source.

## Change Proposals

Actions never mutate source directly. A permitted action may declare operations
in a `ChangeProposal` with a base source revision and rationale.

- **Preview** decodes operations and applies them to a private revision copy.
- **Accept** requires a pending proposal at the current source revision, runs
  the same transaction validation, records review state, and returns a new
  revision with earlier activity retained.
- **Reject** changes only proposal review state.

V1 proposal operations deliberately support the safe narrative writeback
subset. Broader source changes should be added only with typed operations and
reviewable diffs.

## HTTP Surface

| Route | Purpose |
| --- | --- |
| `GET /entities/{kind}/{entity_id}/actions` | List compatible definitions. |
| `POST /entities/{kind}/{entity_id}/actions/{action_id}/preconditions` | Validate inputs and snapshot readiness. |
| `POST /entities/{kind}/{entity_id}/actions/{action_id}/executions` | Execute synchronously and record activity. |
| `GET /executions` | List durable execution records. |
| `GET /executions/{execution_id}` | Read one execution and report. |
| `GET /artifacts` | List artifacts, optionally filtered by source entity. |
| `GET /artifacts/{artifact_id}/lineage` | Traverse immutable parent lineage. |
| `GET /artifacts/{artifact_id}/content` | Read verified artifact bytes. |
| `GET /proposals` | List proposal review state. |
| `POST /proposals/{proposal_id}/preview` | Validate without mutation. |
| `POST /proposals/{proposal_id}/accept` | Apply through the transaction boundary. |
| `POST /proposals/{proposal_id}/reject` | Record rejection without source change. |

## Reference Actions

The checked-in registry supplies snapshot summary, artifact transform, and
narrative proposal actions. They are acceptance fixtures for the generic
platform, not downstream hardware generators.

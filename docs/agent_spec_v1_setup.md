# Agent-Spec V1 Setup

This document captures the agreed v1 setup after the architecture question pass.
It should be treated as the near-term build target for the first implementation.

The first backend slice is implemented under:

```text
spec2gds/agent_spec/
```

Focused tests live under:

```text
tests/agent_spec/test_v1_setup.py
```

The local API can be started with:

```bash
uv run python -m spec2gds.agent_spec.api
```

The implemented v1 slice opens `.spec` documents. Import adapters
from Word, PDF, Markdown, SystemRDL, CSV, and custom tables remain future work.

## V1 Decisions

| Area | Decision |
| --- | --- |
| Document source | A human-written hardware spec may start as Word, PDF, Markdown, agent-spec, or another format. It is converted into an `.spec` document. |
| Block model | Every .spec heading or subheading creates a block. A block can also be called a section or subsection. |
| Block version | A version snapshots the prose under the heading plus linked artifacts together. |
| Action input | When an action is triggered, the server captures the currently selected block version into an immutable input snapshot. Later UI version changes do not affect that run. |
| Tags | V1 tags are `systemc-perf`, `systemc-bitaccurate`, `rtl`, `ip`, `interface`, and `configuration`. A block may have multiple tags. |
| .spec writes | The server owns all writes to the agent-spec during an agent-spec session. LibreOffice or other external editors should not write the active file while the server session is open. |
| Sidecar | The server maintains a sidecar working directory for speed, temporary files, run outputs, and external artifacts. |
| Checkpoint | The final stage of a pipeline extracts agent-spec-facing artifact references, summaries, hashes, diagnostics, and checkpoint metadata back into the agent-spec. |
| Large artifacts | Large artifacts live externally. The agent-spec stores summaries, hashes, types, provenance, and stable retrieval metadata. |
| First pipelines | V1 demos use pseudo SystemC performance and SystemC bit-accurate pipelines. They wait a few seconds, return fixed artifacts, and trigger automatic agent-spec metadata updates. |
| Pipeline interface | Pipeline implementations may internally be a mix of Python, shell tools, EDA tools, or agent workflows. The public server interface is always Python functions. |
| Remote workers | Remote workers are assumed in the contract. Workers receive an input snapshot derived from agent-spec data only, not arbitrary prior artifacts from the artifact store. |
| Action workflows | Internal action/pipeline workflow design is out of scope. This project defines the external contracts. |
| Run states | V1 only needs `queued`, `running`, `completed`, and `failed`. Cancellation, pause/resume, and retry can come later. |
| Writeback | Valid artifact metadata auto-applies after sanity checks. Malformed or uncertain outputs are captured with `needs_human_feedback`. |
| Rerun behavior | A rerun attaches a new artifact attachment with metadata. Existing attachments are preserved. |
| Attachment owner | The agent-spec server owns attachments once valid data arrives from a human interaction or pipeline. |
| Source updates | Pipelines cannot directly update source block content. A future source-update artifact may be reviewed by a human before the server applies it. |
| Traceability | V1 requires artifact/reference traceability: outputs record source block versions and applicable artifact or `spec://` references. |
| Action registration | Actions are registered by Python modules in the repo plus YAML config. |
| Action visibility | Actions declare tag/context rules; the UI shows only relevant actions near matching blocks. |
| Action parameters | V1 parameters support strings, enums, paths, booleans, numbers, block selectors, and version selectors. |
| Enablement | Action enable/disable is controlled per server deployment by config. |
| Server mode | V1 is local single-user. |
| Identity | V1 has no authentication. User identity comes from server config. |
| Events | Events are durable enough to audit completed runs, not to replay an entire interactive session. |
| Native schema | V1 includes a minimal native `agent-spec` schema beside IP-XACT, designed to be extended. |
| Register maps | V1 register maps use IP-XACT only. Later imports can convert SystemRDL, CSV, tables, or other sources. |
| Pipeline inputs | Each action defines the block versions and artifacts it needs. Pipelines do not have to consume one universal model. |
| Safety invariants | V1 must prevent stale pipeline input, silent overwrite, untraceable artifacts, and malformed artifact metadata being applied. |

## Minimal Native Schema

The native schema should be small but deliberately extensible. Suggested
Pydantic model families:

```text
AgentSpecManifest
  document_id
  schema_version
  created_at
  updated_at
  user_identity
  sidecar_root

SpecGraph
  blocks
  active_versions
  artifact_refs
  attachments

BlockRecord
  block_id
  heading_id
  title
  level
  tags
  versions

BlockVersionRecord
  version_id
  block_id
  content_hash
  artifact_ref_ids
  created_at

ArtifactRef
  artifact_id
  artifact_kind
  media_type
  summary
  sha256
  external_uri
  producer
  source_trace
  created_at

RunRecord
  run_id
  action_id
  status
  input_snapshot_id
  read_set
  produced_artifact_ids
  diagnostics
  started_at
  completed_at
```

.spec paths:

```text
spec_data/agent-spec/manifest.json
spec_data/agent-spec/graph.json
spec_data/agent-spec/versions/<block_id>/<version_id>.json
spec_data/agent-spec/artifacts/<artifact_id>.json
spec_data/agent-spec/runs/<run_id>/run.json
spec_data/agent-spec/runs/<run_id>/events.ndjson
spec_data/agent-spec/checkpoints/<checkpoint_id>.json
```

## Pseudo Pipeline Demo

The first demo should prove the architecture without requiring real SystemC
generators.

1. User opens an agent-spec document in the local server UI.
2. Server projects headings/subheadings into blocks.
3. User applies tags such as `systemc-perf` or `systemc-bitaccurate`.
4. UI shows only actions whose tag/context rules match the selected block.
5. User triggers `systemc.perf.pseudo` or `systemc.bitaccurate.pseudo`.
6. Server captures the current block version and artifact references into an
   immutable input snapshot.
7. Worker receives only the snapshot derived from agent-spec data.
8. Worker waits a few seconds and returns fixed artifact metadata.
9. Server sanity-checks artifact metadata.
10. Server writes artifact reference, attachment, run record, audit events, and
    checkpoint metadata into the agent-spec.
11. UI receives run/document events and shows the new artifact attachment.

## Sanity Checks

The server should reject or mark `needs_human_feedback` when:

- Required artifact fields are missing.
- Artifact hash is malformed or missing.
- Artifact metadata points at an unsupported external URI scheme.
- Artifact references a block version that was not in the run input snapshot.
- Artifact references a missing source block, version, or `spec://` node.
- Artifact role is not allowed by the action output contract.
- The writeback would replace or silently overwrite an existing attachment.
- The agent-spec document hash changed in a way that invalidates the input snapshot.

## Test Plan

The v1 implementation should include unit and integration tests for:

- .spec heading projection into blocks and subsections.
- Multiple tags per block.
- Action discovery from Python modules plus YAML config.
- Action visibility by tag/context rule.
- Action parameter schemas for strings, enums, paths, booleans, numbers, block
  selectors, and version selectors.
- Immutable input snapshot capture at trigger time.
- Existing runs remaining unchanged after the user switches active versions.
- Remote worker snapshot content containing only agent-spec-derived data.
- Pseudo SystemC performance pipeline success path.
- Pseudo SystemC bit-accurate pipeline success path.
- Automatic artifact attachment after sanity checks pass.
- `needs_human_feedback` status when artifact metadata is malformed.
- Rerun appending a new attachment instead of replacing an old one.
- Audit event persistence for completed runs.
- .spec reload preserving graph, block versions, artifact references, attachments,
  run records, and checkpoints.
- Server-owned write guard rejecting out-of-band writes during a session.

## Deferred Design Topics

- Git diff friendliness for .spec internals.
- Exact external artifact storage mechanism.
- Source-block update artifacts and human review flow.
- Real SystemC performance and bit-accurate generator contracts.
- Import adapters from Word, PDF, Markdown, SystemRDL, CSV, custom tables, and
  other source formats.
- Authentication and multi-user collaboration.
- Cancellation, retry, and pause/resume.

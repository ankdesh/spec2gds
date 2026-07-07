# Agent-Spec Roadmap and Design Questions

## Roadmap

### Phase 0: Freeze the Architecture Vocabulary

- Agree on what a block is and which tags exist first.
- Agree on where version boundaries live: section, table, IP block, register
  map, interface, requirement, or a mix.
- Design the external artifact storage mechanism.
- Pick the first real pipeline target.

### Phase 1: Core Models and agent-spec Persistence

- Add `spec2gds/agent_spec/` Pydantic models.
- Persist `spec_data/agent-spec/manifest.json` and `graph.json`.
- Map existing .spec headings and relation metadata into block IDs.
- Add immutable block version records.
- Add graph validation tests and .spec reload tests.

### Phase 2: Action Registry and Event Bus

- Implement Python action provider protocol.
- Add API endpoints for action discovery and run creation.
- Implement in-process pub-sub with a durable event envelope.
- Add a generic local worker runtime.
- Add pseudo SystemC performance and bit-accurate actions.

### Phase 3: UI Integration

- Fetch available actions from the server by document/block context.
- Render generic action buttons and parameter forms.
- Subscribe to run events through WebSocket or SSE.
- Show run logs, artifacts, diagnostics, and feedback-needed items.
- Show automatically applied artifact attachments in document context.

### Phase 4: First Real Pipeline

- Implement one real generator, preferably the shortest path that proves value.
- Candidate options: SystemC stub generator, RTL stub generator, UVM register
  model stub generator, or synthesis wrapper around an existing RTL artifact.
- Store generated artifact hashes, summaries, and references in agent-spec.
- Record tool versions, parameters, and source block versions.

### Phase 5: Hardening

- Add document locks and optimistic conflict checks.
- Add action capability restrictions, timeouts, and subprocess isolation.
- Harden the external artifact storage mechanism.
- Add multi-user or remote-worker support only after local single-writer flow is
  reliable.

## Decision Ledger

These decisions are captured in more detail in
[`agent_spec_v1_setup.md`](agent_spec_v1_setup.md).

| Area | V1 decision |
| --- | --- |
| Blocks | Every .spec heading/subheading creates a block, also called a section/subsection. |
| Block versions | A version snapshots prose and linked artifacts together. |
| Action inputs | An action captures the currently selected block version at trigger time. |
| Generated output | Pipeline outputs are artifacts attached to existing blocks, not new sections or blocks. |
| Tags | V1 tags are `systemc-perf`, `systemc-bitaccurate`, `rtl`, `ip`, `interface`, and `configuration`. |
| Artifact storage | Large artifacts live externally; agent-spec stores hashes, summaries, and artifact references. |
| Server writes | The server owns all .spec writes during a session. |
| Sidecar | The server uses a sidecar working directory and checkpoints agent-spec-facing metadata back into agent-spec. |
| First pipelines | V1 demo pipelines are pseudo SystemC performance and SystemC bit-accurate pipelines. |
| Pipeline interface | Public pipeline interface is Python functions, even if internals use mixed tools. |
| Remote workers | Remote workers receive input snapshots derived from agent-spec data only. |
| Run lifecycle | V1 requires `queued`, `running`, `completed`, and `failed`. |
| Writeback | Valid artifact metadata auto-applies after sanity checks. Bad output becomes `needs_human_feedback`. |
| Reruns | Reruns append new attachments with metadata. Existing attachments remain. |
| Attachment ownership | The agent-spec server owns attachments after receiving valid data. |
| Source content | Pipelines cannot directly update source block content. A future reviewed source-update artifact may handle that. |
| Traceability | V1 requires source block version plus artifact/reference traceability. |
| Action registration | Repo Python modules plus YAML config. |
| Action visibility | Actions declare tag/context rules. |
| Parameters | Strings, enums, paths, booleans, numbers, block selectors, and version selectors. |
| Enablement | Per server deployment config. |
| Server mode | Local single-user first. |
| Identity | No auth in v1; user identity comes from config. |
| Events | Durable enough to audit completed runs, not replay whole sessions. |
| Schema | Minimal extensible native agent-spec schema beside IP-XACT. |
| Register maps | IP-XACT only in v1. Other sources arrive later through import functionality. |
| Pipeline models | Each action defines the inputs it needs; no single universal pipeline model is required. |
| Acceptance demo | Pseudo SystemC actions return fixed artifacts after a few seconds and update the document. |
| Safety | Prevent stale pipeline input, silent overwrite, untraceable artifacts, and malformed artifact metadata application. |

## Remaining Design Topics

- Git diff friendliness for .spec internals.
- Exact external artifact storage and retrieval mechanism.
- Real SystemC performance and bit-accurate pipeline contracts.
- Source-block update artifact review flow.
- Future import actions for SystemRDL, CSV, custom tables, and other formats.
- Later remote-worker deployment details beyond the snapshot contract.

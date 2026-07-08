# Agent-Spec Roadmap And Open Questions

This document is for future work and unresolved design choices. Current
architecture and setup details live in:

- [`agent_spec_architecture.md`](agent_spec_architecture.md)
- [`agent_spec_v1_setup.md`](agent_spec_v1_setup.md)
- [`agent_spec_action_contract.md`](agent_spec_action_contract.md)

## Current Baseline

The repository already has a local `.spec` document workflow:

- office-compatible `.spec` archive load/save
- `spec_data/` preservation and package validation
- semantic document projection for the editor
- section version and IP-XACT attachment metadata
- React/Vite local editor shell
- local FastAPI editor API
- mounted action/run API
- graph projection from headings into blocks and block versions
- built-in pseudo actions
- run snapshots, run records, events, writebacks, checkpoints, and artifact
  attachment metadata
- hardware-document benchmark fixtures

The next roadmap items should build from that baseline rather than re-planning
the package split or migration that has already happened.

## Near-Term Priorities

1. Stabilize the current local editor/action loop.
2. Improve diagnostics so users can fix blocking save issues quickly.
3. Make action parameter validation stricter and clearer.
4. Decide the first real hardware pipeline target.
5. Add focused tests when changing graph projection, action contracts, package
   persistence, or editor save behavior.

## Candidate Pipeline Targets

| Candidate | Why it may be useful | Main unknown |
| --- | --- | --- |
| SystemC stub generator | Builds directly on the pseudo SystemC actions. | Minimum useful generated model shape. |
| RTL stub generator | Helps connect specs to implementation skeletons. | Required input schema beyond current prose/IP-XACT. |
| UVM register model stub | Good fit if IP-XACT register maps become reliable. | Current benchmark XML is schema-clean but still lacks rich register maps. |
| Validation/report action | Lower risk than generation and useful for users immediately. | Which checks should be project-owned versus plugin-owned. |

## Open Design Questions

| Topic | Question |
| --- | --- |
| Artifact storage | Should sidecar files remain the default, or should artifacts move to a content-addressed store? |
| Imports | Which source format should be productized first: PDF/HTML benchmark conversion, Markdown, SystemRDL, CSV/register tables, or office documents? |
| Native schema | What project-owned schema is needed beside IP-XACT for requirements, assumptions, interfaces, and generated reports? |
| Action parameters | Should parameter metadata remain the current simple model or move to JSON Schema? |
| Event delivery | Is polling `/agent-spec/events` enough for now, or should the UI use SSE/WebSocket updates? |
| Source updates | What reviewed workflow is acceptable before an action can update source prose? |
| Concurrency | Is the current file-hash write guard enough, or do we need document locks and finer conflict reports? |
| Security | What restrictions are needed before actions can invoke external tools or user-provided scripts? |
| Naming | Should user-facing text say `agent-spec document`, `.spec document`, or a more domain-specific term? |

## Deferred Work

- remote workers, leases, and queues
- authentication and multi-user editing
- exact office rendering in the browser
- rich table editing
- full IP-XACT schema normalization
- real EDA tool integration
- cancellation, retry, pause, and resume
- PR/CI packaging for frontend browser dependencies

## Decision Ledger

| Area | Decision |
| --- | --- |
| Active package path | Active code lives under `spec2gds/agent_spec/`. |
| Active document extension | `.spec`. |
| Current server mode | Local single-user. |
| Current action execution | Synchronous in-process runs. |
| Current generated artifacts | Sidecar files plus metadata in `.spec`. |
| Current writeback policy | Auto-attach valid artifact metadata; record diagnostics for invalid output. |
| Current block model | Every heading becomes a block in the action graph. |
| Current tags | `systemc-perf`, `systemc-bitaccurate`, `rtl`, `ip`, `interface`, `configuration`. |

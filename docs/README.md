# spec2gds Documentation

The documents in this directory describe the current IP-XACT-centered
specification system, the independent Circuit Designer, their development
methods, and completed migration history.

## Start Here

- [Architecture](agent_spec_architecture.md): system boundaries, dependency
  direction, runtime flows, and invariants.
- [Development Methodology](development_methodology.md): source-first vertical
  slices and definition of done.
- [Code Map](post_pivot_code_map.md): concise path-to-responsibility index.
- [Vocabulary](agent_spec_vocabulary.md): canonical terms and retired language.

## Current Contracts

- [Document Schema and Interfaces](agent_spec_document_schema.md): package,
  manifest, narrative, assets, activity, and validation layers.
- [Document Import Utility](document_import.md): Docling PDF/Word/ODT parsing,
  narrative projection, source provenance, and optional OpenAI table-to-IP-XACT
  extraction.
- [Simple SystemC ODT Import Benchmark](simple_spec_systemc_benchmark.md):
  reproducible conversion and integrity checks for four ODT hardware
  specifications.
- [IP-XACT Protocol Rules](ipxact_protocol.md): IEEE 1685-2022 semantics and V1
  profile.
- [IP-XACT to Circuit Designer Adapter v1](ipxact_circuit_adapter_v1.md): run
  the editor-to-circuit flow and understand the initial direct-port boundary.
- [SpecIR and Atomic Edits](spec_ir_v1.md): immutable semantic reads and
  revision-guarded writes.
- [Action Execution Contract](agent_spec_action_execution.md): snapshots,
  executors, reports, artifacts, provenance, and proposals.
- [Local API and Editor](spec_editor_v1.md): run commands, routes, and browser
  interaction model.
- [Spec Assistant Integration](spec-assistant-integration.md): optional
  external Assistant UI, entity ownership, typed proposal preview/apply, and
  refresh events.
- [A2UI Stage 1 Editor](spec_editor_a2ui_stage1.md): unified read-only document
  projection, semantic catalog, React boundary, and Stage 2 seam.
- [Diagnostics](agent_spec_diagnostics.md): validation domains and operational
  troubleshooting.

## Independent Circuit Designer

Circuit Designer is a separate REST-based subsystem. It does not persist
SpecIR, IP-XACT, or circuit sessions.

- [Design and Architecture](circuit_designer_architecture_v1.md): start here for
  ownership, components, runtime flows, REST surface, concurrency, and v1
  boundaries.
- [Protocol](circuit_designer_protocol_v1.md): canonical document,
  construction, operations, drafts, diagnostics, and transport outcomes.
- [Provider Boundary](circuit_designer_provider_v1.md): independent hierarchy,
  HTTP callbacks, and provider-owned persistence.
- [Agent Tools and Proposals](circuit_designer_tools_v1.md): structured
  queries, previews, exports, and immutable proposals.
- [Run Guide](circuit_designer_run_v1.md): browser, service-only, file, test,
  and production commands.
- [External Assistant](../external-assistant/docs/architecture.md): optional
  assistant-ui, A2A agent, Circuit and Spec proposal preview, and review
  architecture.

## Engineering Practice

- [Code Organization](agent_spec_code_organization.md)
- [Coding Guidelines](coding_guidelines.md)
- [UI Testing](agent_spec_ui_testing.md)
- [Samples and Benchmark Material](agent_spec_benchmarks.md)
- [Architecture Boundary Assessment](mvc_architecture_assessment.md)

## Roadmap and History

- [Roadmap and Open Decisions](agent_spec_roadmap_questions.md)
- [Completed V1 Pivot Plans](pivot/README.md)
- [Future V2–V4 Roadmap](pivot/future_v2_v3_v4_roadmap.md)

The four V1 pivot plans are retained as completed decision/acceptance history.
References to removed ODT or heading-based behavior inside those plans describe
the migration target that was eliminated, not current runtime behavior.
Earlier Circuit Designer phase documents are indexed in
[`docs/archive/README.md`](archive/README.md). They describe removed
SpecIR/FastAPI, local-backend, and earlier canvas designs and are not active
contracts.

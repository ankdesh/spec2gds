# spec2gds Documentation

The documents in this directory describe the current IP-XACT-centered V1
product, its development method, and the completed pivot history.

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
- [IP-XACT Protocol Rules](ipxact_protocol.md): IEEE 1685-2022 semantics and V1
  profile.
- [SpecIR and Atomic Edits](spec_ir_v1.md): immutable semantic reads and
  revision-guarded writes.
- [Action Execution Contract](agent_spec_action_execution.md): snapshots,
  executors, reports, artifacts, provenance, and proposals.
- [Local API and Editor](spec_editor_v1.md): run commands, routes, and browser
  interaction model.
- [A2UI Stage 1 Editor](spec_editor_a2ui_stage1.md): unified read-only document
  projection, semantic catalog, React boundary, and Stage 2 seam.
- [Circuit Designer Phase 0](circuit_designer_phase0.md): renderer-neutral
  contracts, SpecIR projection, deterministic layout, and standalone React mock app.
- [Circuit Designer Phase 1](circuit_designer_phase1.md): live read-only SpecIR
  catalog/graph API, reusable HTTP client, and server-backed canvas workflow.
- [Circuit Designer Complete Roadmap](circuit_designer_complete.md): mutation,
  locking, history, agent proposals, hierarchy, hosting, and final workflows.
- [Standalone Circuit Designer](circuit_designer_standalone.md): independent
  examples, local command engine, and the SpecIR isolation boundary.
- [Diagnostics](agent_spec_diagnostics.md): validation domains and operational
  troubleshooting.

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

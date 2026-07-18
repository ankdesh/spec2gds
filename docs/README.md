# spec2gds Documentation

This directory contains durable project documentation. Each document has a
specific purpose so current architecture, future ideas, and contributor rules do
not blur together.

## V1 Active Docs

- [V1 Source Package](spec_format_v1.md): deterministic IP-XACT-centered
  package foundation and standalone CLI.
- [V1.2 SpecIR and Atomic Edits](spec_ir_v1.md): immutable semantic source
  snapshots, graph queries, and validated optimistic edit transactions.
- [V1.3 Actions, Artifacts, and Proposals](spec_actions_v1.md): entity-targeted
  external actions, sidecar artifacts, activity provenance, and review-gated
  source edits.
- [V1.4 Local API and Editor](spec_editor_v1.md): production API/editor shell,
  source revision checks, action executions, and proposal review.

## Archived ODT-Agent-Spec Docs

The following documents describe the pre-cutover ODT/heading-based prototype.
They are retained as historical rationale and are not production contracts.

- [Architecture](agent_spec_architecture.md): current components, runtime
  flows, storage layout, and pointers from concepts to code.
- [MVC Architecture Assessment](mvc_architecture_assessment.md): evidence-based
  review of MVC boundaries, good design patterns, architectural pressure points,
  and a prioritized refactoring path.
- [Document Schema and Interfaces](agent_spec_document_schema.md): `.spec`
  archive layout, schema-bearing package parts, `spec://` links, and
  document-facing code/API interfaces.
- [Vocabulary](agent_spec_vocabulary.md): shared terms for `.spec` documents,
  blocks, sections, actions, runs, artifacts, and editor concepts.
- [Action Execution Contract](agent_spec_action_execution.md): action input,
  executor callbacks, reports, artifacts, and A2UI report surfaces.
- [IP-XACT Protocol Rules](ipxact_protocol.md): protocol fidelity rules for
  embedded IP-XACT payloads, bus interfaces, editor behavior, and benchmarks.
- [Diagnostics and Sanitization](agent_spec_diagnostics.md): CLI commands for
  inspecting full `.spec` package anatomy and applying conservative structural
  repairs.
- [Code Organization](agent_spec_code_organization.md): current package layout,
  naming guidelines, and where new code should go.
- [Roadmap and Open Questions](agent_spec_roadmap_questions.md): future work and
  unresolved design topics.
- [Benchmarks](agent_spec_benchmarks.md): hardware-document benchmark inputs,
  generated artifacts, and rebuild/test commands.
- [UI Testing](agent_spec_ui_testing.md): Playwright setup and restricted
  environment notes.
- [Coding Guidelines](coding_guidelines.md): repository-specific development,
  testing, and documentation practices.

## IP-XACT Pivot Plans

The approved implementation sequence for replacing the ODT-centered format is
kept in [Pivot Plans](pivot/README.md). Apply its four V1 plans in order;
the [future roadmap](pivot/future_v2_v3_v4_roadmap.md) records the V2–V4
direction without authorizing implementation work.

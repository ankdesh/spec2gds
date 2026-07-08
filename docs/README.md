# spec2gds Documentation

This directory contains durable project documentation. Each document has a
specific purpose so current architecture, future ideas, and contributor rules do
not blur together.

## Agent-Spec Docs

- [Architecture](agent_spec_architecture.md): current components, runtime
  flows, storage layout, and pointers from concepts to code.
- [Document Schema and Interfaces](agent_spec_document_schema.md): `.spec`
  archive layout, schema-bearing package parts, `spec://` links, and
  document-facing code/API interfaces.
- [Vocabulary](agent_spec_vocabulary.md): shared terms for `.spec` documents,
  blocks, sections, actions, runs, artifacts, and editor concepts.
- [Action and Pipeline Contract](agent_spec_action_contract.md): implemented
  action metadata, input snapshots, run events, artifact validation, and
  writeback records.
- [Pipeline API](agent_spec_pipeline_api.md): read-only pipeline context
  endpoints and explicit artifact writeback endpoints.
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

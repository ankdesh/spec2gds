# spec2gds Documentation

This directory contains durable project documentation. Each document has a
specific purpose so current architecture, future ideas, and contributor rules do
not blur together.

## Agent-Spec Docs

- [Architecture](agent_spec_architecture.md): current components, runtime
  flows, storage layout, and pointers from concepts to code.
- [Vocabulary](agent_spec_vocabulary.md): shared terms for `.spec` documents,
  blocks, sections, actions, runs, artifacts, and editor concepts.
- [Action and Pipeline Contract](agent_spec_action_contract.md): implemented
  action metadata, input snapshots, run events, artifact validation, and
  writeback records.
- [V1 Setup](agent_spec_v1_setup.md): environment, run commands, tests, current
  v1 decisions, and non-goals.
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

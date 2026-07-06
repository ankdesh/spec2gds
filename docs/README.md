# spec2gds Architecture Docs

This directory captures project-level architecture notes that should survive
individual coding sessions.

## Agent-Spec Architecture

- [Agent-Spec Architecture Plan](agent_spec_architecture.md): central server,
  ODT-backed source of truth, event flow, versioning, UI responsibilities, and
  pipeline writeback model.
- [Agent-Spec Vocabulary](agent_spec_vocabulary.md): shared concept glossary
  for hardware specs, agent-spec documents, blocks, tags, versions, actions,
  runs, artifacts, attachments, and writebacks.
- [Action and Pipeline Contract](agent_spec_action_contract.md): configurable
  Python action schema, immutable input snapshots, event envelope, run lifecycle,
  and writeback record format.
- [Agent-Spec V1 Setup](agent_spec_v1_setup.md): agreed v1 decisions, native
  schema outline, pseudo pipeline demo, sanity checks, and test plan.
- [Roadmap and Design Decisions](agent_spec_roadmap_questions.md): staged build
  plan, v1 decision ledger, and remaining design topics.

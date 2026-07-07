# Agent-Spec Code Organization

This document explains the current code layout and naming expectations. It
replaces the old refactor plan that described moving from a previous package
shape.

## Current Layout

```text
spec2gds/agent_spec/
  api/        local FastAPI apps
  document/   semantic document parsing, editor session, relations, UI frontend
  package/    .spec archive mechanics, CLI, verifier
  plugins/    modality handlers for payloads such as JSON and IP-XACT
  storage/    graph projection and .spec metadata persistence
  actions/    action registry and built-in actions
  runs/       run coordination and writeback checks
  samples/    sample document builders and generated fixtures
  models.py   shared Pydantic contracts
```

Tests follow the same top-level concept:

```text
tests/agent_spec/
  package/
  test_v1_setup.py
  test_hw_docs_benchmark.py
```

## Naming Guidelines

- Use `.spec` for the project document package extension.
- Use `agent_spec` for Python package/module paths.
- Use `AgentSpecArchive` for the current archive wrapper unless a real rename is
  implemented across code and tests.
- Use "block" for action graph units and "section" for user-facing document
  discussions when that reads more naturally.
- Use "artifact" for generated or embedded payloads with metadata.
- Keep "ODF" or "office-compatible" wording only when discussing the package
  mechanics in `package/archive.py` or file compatibility.

## Where New Code Usually Goes

| Need | Location |
| --- | --- |
| New API route for editor snapshots, saves, file browsing, or IP-XACT editing | `spec2gds/agent_spec/api/document_app.py` |
| New API route for blocks, tags, actions, runs, or run events | `spec2gds/agent_spec/api/app.py` |
| New document parsing or edit behavior | `spec2gds/agent_spec/document/semantic.py` |
| New editor save/session behavior | `spec2gds/agent_spec/document/session.py` |
| New relation metadata | `spec2gds/agent_spec/document/relations.py` |
| New payload type | `spec2gds/agent_spec/plugins/` |
| New package-level validation | `spec2gds/agent_spec/package/verifier.py` |
| New graph persistence behavior | `spec2gds/agent_spec/storage/repository.py` |
| New built-in action | `spec2gds/agent_spec/actions/builtin.py` |
| New run/writeback behavior | `spec2gds/agent_spec/runs/runner.py` |
| New shared contract | `spec2gds/agent_spec/models.py` |

## Documentation Expectations

When behavior changes, update the document that owns that purpose:

| Change | Update |
| --- | --- |
| Component boundaries or flow | `docs/agent_spec_architecture.md` |
| Data contract for actions/runs/writebacks | `docs/agent_spec_action_contract.md` |
| Terms or naming | `docs/agent_spec_vocabulary.md` |
| Setup commands or test commands | `README.md` and `docs/agent_spec_v1_setup.md` |
| Open design choices | `docs/agent_spec_roadmap_questions.md` |
| Benchmarks | `docs/agent_spec_benchmarks.md` |
| Contributor rules | `docs/coding_guidelines.md` |

Avoid keeping outdated migration plans in active docs. If historical context is
needed, label it as historical and keep it out of the architecture path.

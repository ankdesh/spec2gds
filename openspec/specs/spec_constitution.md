# Submodule Specification: agent-spec

`agent-spec` is the active specification-document layer in `spec2gds`. It owns
the document package, semantic section model, versioned graph, action registry,
pipeline run records, artifact references, writebacks, and audit trail used by
agents and downstream hardware-design flows.

The older `spec` naming should not remain as a separate implementation boundary
in this repository. Historical documents may mention that `.spec` evolved from
ODT/ODF-compatible package mechanics, but active code and user-facing behavior
should use agent-spec terminology.

---

## 1. Submodule Role and Boundaries

The `agent-spec` submodule is responsible for:

1. **Document Package Management**: Loading, saving, validating, and preserving
   `.spec` documents with embedded machine-readable metadata.
2. **Semantic Document Projection**: Mapping headings, sections, tables,
   figures, links, and attachments into typed document blocks.
3. **Versioned Graph Storage**: Maintaining block versions, active-version
   pointers, tags, artifact references, attachments, and provenance.
4. **Action Orchestration**: Discovering configured actions, capturing
   immutable input snapshots, running local or remote workers, and recording
   results.
5. **Writeback and Audit**: Validating pipeline outputs, applying safe artifact
   metadata updates, routing ambiguous outputs to human feedback, and recording
   durable audit events.

It does **not** own physical synthesis, simulation semantics, place-and-route,
or GDS generation. Those remain downstream tools or actions that consume
agent-spec snapshots and return traceable artifacts.

---

## 2. Document Format Policy

### Active Extension

The active document extension is `.spec`.

### Compatibility

`.spec` should remain office-compatible for now so the human-readable document
body can continue to benefit from mature office-document tooling. This
compatibility is an implementation strategy, not the public architecture name.
If preserving office compatibility materially complicates the agent/pipeline
design, the project may drop that compatibility in a later design revision.

### Naming

Active package names, class names, function names, CLI text, UI labels, tests,
and examples should use agent-spec terminology. Avoid ODT-centered names in new
code. Historical docs may describe the ODT/ODF origin when useful for context.

---

## 3. Technical Requirements and Design Patterns

- **Typed Contracts**: Public data exchanged between services, actions, tests,
  and APIs should use strictly typed Python models.
- **Stable Versions**: Pipeline actions must consume immutable block versions
  and record their read set.
- **Traceable Artifacts**: Generated outputs must include source trace,
  producer, hash, media type, summary, and role metadata.
- **Server-Owned Writes**: Pipelines should not directly mutate source document
  content. They return artifacts, diagnostics, and writeback requests for the
  agent-spec server to validate and apply.
- **Loose Coupling**: Actions should be discoverable from Python/config
  contracts and should not require custom UI code for each new action.
- **Readable Code**: Public modules, classes, methods, Pydantic models, action
  contracts, and non-obvious internal logic must include useful docstrings or
  comments. Comments should explain intent, constraints, or invariants rather
  than restating individual lines of code.
- **Focused Tests**: Package save/load, metadata preservation, graph projection,
  action dispatch, writeback validation, and API behavior should stay covered by
  focused tests.

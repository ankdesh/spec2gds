# Agent-Spec Refactor Goals

## Confirmed Direction

`agent-spec` is the single active specification-document architecture in
`spec2gds`. The earlier `spec` term referred to the broader hardware-spec
concept and should not remain as a separate code hierarchy in this repository.

The refactor should use a hard cutover:

- Move the existing package/container/editor implementation into
  `spec2gds/agent_spec/`.
- Remove active `spec2gds.spec` imports, modules, tests, and user-facing
  commands instead of keeping compatibility shims.
- Treat `.spec` as the agent-spec document extension everywhere in active code,
  examples, tests, and user-facing instructions.
- Rename existing `.odt` sample documents used by active tests to `.spec`.
- Keep the `.spec` package office-compatible for now. The implementation may
  continue to preserve the office-document structure internally, but active code
  names should describe agent-spec concepts rather than the source file type.
- Keep historical documentation that explains `.spec` was derived from ODT/ODF,
  but avoid ODT naming in public APIs, package names, CLI names, UI labels,
  test names, and new code symbols.
- Revisit office compatibility if preserving it starts to make the design
  materially more complex than the agent/pipeline workflow needs.

## Refactor Goals

1. Collapse the active specification code under `spec2gds/agent_spec/`.
2. Rename the old container layer around the `.spec` document abstraction.
3. Organize code by responsibility instead of by the old file-type boundary.
4. Make `.spec` the only active extension used by fixtures, examples, tests,
   APIs, UI file browsers, and documentation snippets.
5. Remove `spec2gds.spec` as an active package path.
6. Replace ODT-centered names such as `odt_container`, `HybridODTContainer`, and
   "ODT editor" with agent-spec names.
7. Keep low-level office compatibility behavior covered by tests so the `.spec`
   file remains readable by office tooling while that remains useful.
8. Update the constitution so future code must include useful docstrings and
   comments for public contracts and non-obvious logic.
9. Add or improve docstrings while files are moved, especially for public
   modules, classes, models, service methods, and action contracts.
10. Update README and architecture docs after the move so users see one
    coherent agent-spec flow.

## Target Code Shape

```text
spec2gds/
  agent_spec/
    package/          .spec archive loading, saving, manifest, embedded files
    document/         semantic content model, headings, sections, relations
    storage/          repository, graph persistence, sidecar/checkpoints
    actions/          action registry, built-in providers, config loading
    runs/             run coordinator, snapshots, audit events
    api/              FastAPI routes for documents, actions, runs, UI support
    plugins/          payload handlers such as JSON and IP-XACT
    samples/          .spec sample builders and fixtures
```

The exact names can change during implementation if the code suggests a cleaner
boundary, but the final tree should make the agent-spec document and pipeline
workflow obvious without needing the old `spec` or ODT terminology.

## Suggested Implementation Phases

### Phase 1: Inventory and Rename Plan

- List every active import, file path, CLI command, UI string, fixture, and test
  that still uses `spec2gds.spec`, `odt_container`, `ODT`, or `.odt`.
- Decide final names for the package abstraction, semantic document layer, and
  editor/API routes.
- Identify historical docs that should be preserved without changing their
  archived meaning.

### Phase 2: Move Code and Tests

- Move implementation from `spec2gds/spec/odt_container/` into the new
  `spec2gds/agent_spec/` hierarchy.
- Move tests from `tests/spec/odt_container/` into `tests/agent_spec/`.
- Update imports directly to the new paths.
- Delete the old active package path once tests are green.

### Phase 3: Rename Extension and User Surface

- Rename active sample files from `.odt` to `.spec`.
- Update file filters, API payload names, CLI help, web UI labels, test names,
  and README commands to use `.spec`.
- Keep office-compatible package behavior underneath `.spec`.

### Phase 4: Documentation and Constitution

- Update README, docs index, architecture plan, setup guide, vocabulary, and
  action contract to describe `.spec` and the unified `agent-spec` hierarchy.
- Keep historical ODT/ODF explanation only where it helps explain compatibility
  or project history.
- Ensure the constitution requires useful docstrings/comments for public code
  and complex internal logic.

### Phase 5: Validation

- Run the Python test suite with `uv run python -m pytest -q`.
- Add focused tests for `.spec` load/save, embedded metadata preservation,
  graph projection, action runs, writebacks, and API file browsing.
- Confirm no active code imports `spec2gds.spec`.
- Confirm no active user-facing text refers to an ODT container/editor.

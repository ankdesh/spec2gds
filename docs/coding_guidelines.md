# Coding Guidelines

These rules apply to the current IP-XACT-centered V1 implementation and future
capability packs.

## Environment and Commands

- Use `uv` and the repository virtual environment.
- Add dependencies through `pyproject.toml` and keep `uv.lock` synchronized.
- Keep run commands in `README.md` and the owning document current.

```bash
uv sync
uv run python -m pytest -q
uv run spec2gds-server
```

## Source Authority

- Treat the manifest, narrative AST, IP-XACT documents, source assets, and
  accepted annotations as canonical source.
- Do not persist derived topology, UI cards, or generated downstream content as
  duplicate source.
- Keep activity outside the source revision hash.
- Require reviewed proposals for action-generated source changes.

## Contracts and Types

- Target Python 3.12 or newer and annotate all function boundaries.
- Use frozen strict Pydantic models for persisted/API contracts and frozen
  dataclasses for immutable internal projections.
- Reject unknown persisted fields and unsupported protocol content.
- Use stable IDs and `EntityRef` for identity; use VLNV for IP-XACT-native
  document references.
- Keep mutable construction objects behind explicit package/transaction
  boundaries.

## Module Boundaries

- Core package, protocol, IR, transaction, and action code must not depend on
  FastAPI or browser code.
- Route handlers translate transport values into typed core operations.
- The browser owns presentation state only and sends all writes through the
  revision-guarded API.
- Avoid eager imports from package initializers.
- Extend the current boundaries described in
  [`agent_spec_code_organization.md`](agent_spec_code_organization.md); do not
  recreate deleted pre-pivot compatibility layers.

## Protocol Fidelity

- Validate IP-XACT using the bundled IEEE 1685-2022 schemas and the V1 profile.
- Keep physical ports under `model/ports` and formal interfaces under
  `busInterfaces/busInterface`.
- Never infer a bus interface solely from a port.
- Parse XML with external entity, DTD, and network access disabled.
- Preserve deterministic normalization and package paths.

## Writes and Errors

- Apply source edits to a private copy and validate the complete candidate.
- Require expected source revision hashes at public write boundaries.
- Return explicit diagnostics; do not silently repair or guess hardware intent.
- Validate archive paths before filesystem or ZIP access.
- Verify artifact hashes on both ingest and read.
- Do not broaden exception handling until failure modes and diagnostics remain
  distinguishable.

## Documentation and Comments

- Keep durable project knowledge under `docs/`.
- Give every Python module, class, and function a useful docstring.
- Comment invariants, security boundaries, determinism requirements, and
  non-obvious protocol order—not obvious syntax.
- Update architecture, schema, vocabulary, methodology, and usage docs in the
  same change that alters those contracts.
- Mark historical plans as completed history; do not describe removed systems
  as current.

## Tests and Samples

- Mirror source boundaries under `tests/agent_spec/spec_format/`.
- Test happy paths and validation failures at the narrowest useful layer.
- Add end-to-end API coverage for cross-layer behavior.
- Extend `build_v1_sample()` for every editor-visible capability and regenerate
  the checked-in package.
- Require deterministic save/repack bytes and source hashes.
- Validate real protocol content rather than project-specific summaries.

## Change Completion Checklist

- Persisted and API contracts are typed and documented.
- Source/activity boundaries and revision behavior remain correct.
- Invalid input fails without partial mutation.
- Unit, integration, deterministic sample, and relevant UI acceptance tests
  pass.
- README commands and owning docs match executable entry points.
- `git diff --check` is clean and documentation links resolve.

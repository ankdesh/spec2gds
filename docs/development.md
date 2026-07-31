# Development guide

## Repository map

```text
spec2gds/agent_spec/spec_format/   .spec model, SpecIR, transactions, actions, API
spec2gds/agent_spec/importers/     PDF, Word, and ODT import
circuit-designer/schema/           canonical Circuit Designer JSON Schema
circuit-designer/packages/core/    contracts, validation, operations, drafts, export
circuit-designer/packages/service/ REST sessions, leases, proposals, providers
circuit-designer/packages/layout/  placement and orthogonal routing
circuit-designer/packages/react/   canvas rendering and gestures
circuit-designer/apps/editor/      specification editor frontend
circuit-designer/apps/standalone/  independent Circuit Designer frontend
external-assistant/                optional assistant service and web client
tests/                             Python contract and integration tests
docs/                              current architecture and workflows
```

## Python environment

Use `uv`; do not install project packages into the system interpreter.

```bash
uv sync
uv run python -m pytest -q
```

For document import:

```bash
uv sync --extra document-import
uv run spec2gds-import-document input.pdf -o output.spec
```

Focused checks:

```bash
uv run python -m pytest tests/agent_spec/spec_format -q
uv run python -m pytest tests/agent_spec/importers -q
uv run python -m py_compile spec2gds/agent_spec/spec_format/*.py
```

## TypeScript environment

Use Node.js 24 or newer.

```bash
cd circuit-designer
npm install
npm run generate:check
npm test
npm run build
```

`schema/circuit-designer.v1.schema.json` is authoritative. After a schema
change, run `npm run generate`, inspect the generated types and protocol copy,
then run `npm run generate:check`.

Browser acceptance tests use:

```bash
cd circuit-designer
npm run test:e2e
```

## Optional assistant

The assistant is a separate Python project with its own `uv` environment.

```bash
cd external-assistant
uv sync
uv run python -m pytest -q
cd web
npm install
npm run build
```

## Change rules

- Change the owner of a contract first, then update adapters and views.
- Keep immutable reads separate from validated writes.
- Use revision guards for all saved edits.
- Keep connectivity separate from layout geometry.
- Keep generated artifacts out of source control unless they are required
  runtime assets, such as the packaged editor bundle.
- Put reusable regression data in small programmatic test fixtures.
- Add or update a document in `docs/` when architecture, a public workflow, or
  run instructions change.
- Remove stale documents rather than preserving an in-repository archive.

## Completion checklist

Before handing off a change:

1. Run focused tests for the changed owner.
2. Run the full Python and TypeScript suites when a shared contract changed.
3. Build any affected frontend.
4. Search for references to removed routes, files, demos, or commands.
5. Update the root README and the smallest relevant living document.

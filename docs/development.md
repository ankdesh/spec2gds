# Development guide

## Repository map

```text
spec2gds/agent_spec/spec_format/   .spec model, SpecIR, transactions, actions, API
spec2gds/agent_spec/activities/    Activity snapshots, read SDK, contracts, registry
spec2gds/agent_spec/importers/     PDF, Word, and ODT import
circuit-designer/schema/           canonical Circuit Designer JSON Schema
circuit-designer/packages/core/    contracts, validation, operations, drafts, export
circuit-designer/packages/service/ REST sessions, leases, proposals, providers
circuit-designer/packages/layout/  placement and orthogonal routing
circuit-designer/packages/react/   canvas rendering and gestures
circuit-designer/apps/editor/      specification editor frontend
circuit-designer/apps/standalone/  independent Circuit Designer frontend
ai-assistant/                      optional AI Assistant service and web client
config/services.json               shared hosted-service IP/port registry
tests/                             Python contract and integration tests
docs/                              current architecture and workflows
```

## Python environment

Service processes and frontend dev proxies read `config/services.json` at
startup. Use `SPEC2GDS_SERVICE_CONFIG=/absolute/path/services.json` for an
untracked machine-specific registry.

Use `uv`; do not install project packages into the system interpreter.

The deterministic RTL Activity tests also require GNU Make and Verilator 5.x
on `PATH`. This is a required external toolchain check, not an optional test.

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
uv run python -m pytest tests/agent_spec/activities -q
uv run python -m pytest tests/agent_spec/activities/rtl -q
uv run python -m pytest tests/agent_spec/importers -q
uv run python -m py_compile spec2gds/agent_spec/spec_format/*.py spec2gds/agent_spec/activities/*.py
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

Circuit Designer browser acceptance tests use:

```bash
cd circuit-designer
npm run test:e2e
```

The specification editor owns a separate browser-test configuration and dev
server lifecycle:

```bash
cd circuit-designer
npm run test:e2e:editor
```

The two commands deliberately do not start each other's applications. A future
combined workflow should be owned by the specification editor and delegate to
the existing Circuit Designer command rather than expanding Circuit Designer's
default startup.

## Optional AI Assistant

The AI Assistant is a separate Python project with its own `uv` environment.

```bash
cd ai-assistant
uv sync
uv run python -m pytest -q
cd web
npm install
npm run build
```

## Combined local launcher

Once the root, Circuit Designer, and AI Assistant dependencies are installed,
run all three development services with their default settings from the
repository root:

```bash
scripts/serve-all.sh start
scripts/serve-all.sh stop
```

The script tracks process groups with PID files in `logs/serve-all/`. Each
service writes to a separate log in the same directory. The `stop` command also
uses `lsof` to terminate untracked listeners on the default service ports
`8000`, `4100`, `4180`, and `4200`. The script deliberately does not install
dependencies or own the longer-term service monitoring mechanism.

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

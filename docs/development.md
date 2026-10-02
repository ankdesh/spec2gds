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
circuit-designer/packages/app-react/ reusable application shell and host adapters
circuit-designer/apps/editor/      specification editor frontend
circuit-designer/apps/standalone/  independent Circuit Designer frontend
ai-assistant/                      DeepSeek Harness assistant product and web client
testplan-service/                   snapshot-bound planning, evidence, reference generation
config/services.json               shared hosted-service IP/port registry
tests/                             Python contract and integration tests
docs/                              current architecture and workflows
```

## Python environment

The combined launcher exports `config/services.json` to participating services.
Use `SPEC2GDS_SERVICE_CONFIG=/absolute/path/services.json` for an untracked
machine-specific registry. Circuit Designer's service and Vite UI also have
independent defaults and do not require that shared registry.

Use `uv`; do not install project packages into the system interpreter.
Running `uv sync` creates the repository-local `.venv`. The AI Assistant is a
Node product and does not use Python or `uv`.

The deterministic RTL Activity tests also require GNU Make and Verilator 5.x
on `PATH`. This is a required external toolchain check, not an optional test.

```bash
uv sync
uv run python -m pytest -q tests testplan-service/tests
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

Use Node.js 24.2 or newer for the combined workspaces. Circuit Designer alone
declares Node 24+; the Assistant also accepts 22.19+ in the 22.x line. The
pinned Harness CLI uses `import.meta.main`, which is absent in Node 24.0/24.1.

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

The AI Assistant is a separate DeepSeek Harness Node workspace.

```bash
scripts/setup-all.sh
npm --prefix ai-assistant run typecheck
npm --prefix ai-assistant test
npm --prefix ai-assistant run build
npm --prefix ai-assistant run test:harness
```

Native event packages are linked from the Harness source; they are not
currently installed from published npm artifacts. `HARNESS_SOURCE` selects the
checkout. The unified setup follows `DSH_BRANCH`; it does not enforce the
`harness.lock.json` pin or offer `--update-harness`. Check the source revision
against the lock before testing; packaging requires it to be clean and matching.

See [Assistant acceptance](assistant-acceptance-tests.md) for owner refinement
and isolated browser scenarios. [The event tutorial](event-driven-assistant-tutorial.md)
explains `test:ui` browser dependencies and optional screenshot capture. The
three product browser tests use a minimal adapter shell with real React/native
services and deterministic owner/model fixtures; full Harness-shell acceptance
is a separate scope.

## Verification Planner

```bash
uv sync
uv run testplan-service --host 127.0.0.1 --port 6016 --storage-dir verification-data
uv run python -m pytest testplan-service/tests -q
```

The service can also use its own `uv sync` environment from `testplan-service/`.
Its UI is shipped static JavaScript; no Node build is needed. It is not part of
the combined launcher's process list. See [service operation](verification-service-overall.md).

## Combined local launcher

For a first-time setup from the repository root, install every runtime and
build the Harness Assistant:

```bash
scripts/setup-all.sh
```

Then run all three services with their default settings from the repository
root:

```bash
scripts/serve-all.sh start
scripts/serve-all.sh restart  # replace a running stack after source changes
scripts/serve-all.sh stop
```

Set `OPENAI_API_KEY` before `start` to enable Assistant proposal generation; it
is not required for the other two applications. The script tracks process
groups with PID files in `logs/serve-all/`. Each
service writes to a separate log in the same directory. The `stop` command also
uses `lsof` to terminate untracked listeners on the default service ports
`6010` through `6014`. Services read their bind configuration from
`config/services.json`, while the displayed URLs and cleanup list describe the
tracked defaults. `start` refuses partial and untracked stacks on those ports;
use `restart` after rebuilding so an older browser bundle cannot remain active.
The script deliberately does not install dependencies or own
the longer-term service monitoring mechanism.

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

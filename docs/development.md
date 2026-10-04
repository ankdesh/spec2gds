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

## Test tiers

After `scripts/setup-all.sh`, run these commands from the repository root:

```bash
scripts/test-all.sh                   # fundamental is the default
scripts/test-all.sh fundamental
scripts/test-all.sh extensive
scripts/test-all.sh all
```

| Tier | Coverage | Use |
| --- | --- | --- |
| Fundamental | Fast Python model, package, validation, transaction, projection, owner/API, Activity preflight, importer, runtime and Verification Planner tests; all Circuit Designer and Assistant unit tests | During development and for ordinary pull requests |
| Extensive | Remaining Python RTL lint/compilation/simulation, SystemC/CIRCT compilation and Assistant CLI workflows; Harness integration; Circuit Designer, Spec Editor and Assistant browser suites | Before merging workflow, generator or UI changes, and for complete regression runs |

The tiers are disjoint. `all` runs both without repeating fundamental tests.
Existing `npm test` and unfiltered Python test commands retain their full
selection. Nothing is removed from the suites.

Preview commands with `scripts/test-all.sh all --dry-run`. Use
`scripts/test-all.sh extensive --no-browser` when browser checks are being run
through their dedicated commands below. The runner reports every failed check,
continues independent suites, skips consumers of failed builds and exits nonzero
if any check fails. It prints the total elapsed time after a successful run.

Fundamental needs the installed root uv environment, Circuit Designer npm
dependencies and linked Assistant/DSH dependencies. It does not rebuild products
or run hardware simulations. Extensive builds the Assistant before CLI/Harness
checks and the frontends before browser checks. It needs Verilator 5.x, GNU Make
and a C++ compiler; `SYSTEMC_PREFIX` and `CIRCT_PREFIX` enable their existing
optional compiler checks. Both tiers use deterministic model fixtures and need
no model API keys. Local HTTP fixtures need permission to bind loopback sockets.

The Assistant browser tests reuse Circuit Designer's Playwright and React
dependencies and the Chromium installed by setup. `ASSISTANT_UI_TEST_DEPS` and
`PLAYWRIGHT_BROWSERS_PATH` can override those defaults. The independent Circuit
and Spec browser runners retain their own browser-path settings.

Python selection uses the registered `extensive` marker:

```bash
uv run python -m pytest -q --strict-markers tests testplan-service/tests -m 'not extensive'
uv run python -m pytest -q --strict-markers tests testplan-service/tests -m extensive
```

New fast tests enter fundamental automatically. Mark a test
`@pytest.mark.extensive` when it compiles/simulates hardware or launches a complete
Assistant workflow; use `pytestmark = pytest.mark.extensive` only for modules
whose tests belong together. Keep fast structural/preflight tests fundamental
even when they share a file with compiler tests. Marker names are checked by the
runner. All current JavaScript unit tests remain fundamental; native Harness and
browser integration retain their separate existing commands in extensive.

The named owner/editor scenarios under `tests/ui-scenarios`, Assistant evaluation
reports and live-provider/generalization runs remain separately invoked. They
have their own service lifecycle, artifacts or model-key requirements; see
[Assistant acceptance](assistant-acceptance-tests.md). Lint, typechecking and
schema generation checks also retain their existing commands below.

## Python environment

The combined launcher exports `config/services.json` to participating services.
Use `SPEC2GDS_SERVICE_CONFIG=/absolute/path/services.json` for an untracked
machine-specific registry. Circuit Designer's service and Vite UI also have
independent defaults and do not require that shared registry.

Use `uv`; do not install project packages into the system interpreter.
Running `uv sync` creates the repository-local `.venv`. The AI Assistant is a
Node product and does not use Python or `uv`.

The extensive RTL Activity tests require GNU Make and Verilator 5.x on `PATH`.
This requirement also applies to the unfiltered full Python command below.

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

Setup refreshes the local package, type and executable links and writes the
canonical checkout path to `ai-assistant/.env`, preserving other developer
settings. Relative `HARNESS_SOURCE` destinations are resolved from the repository
root. Rerun setup after replacing or moving Harness. See
[Harness setup troubleshooting](harness-setup-troubleshooting.md) for the five
issue resolutions and isolated setup regressions.

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

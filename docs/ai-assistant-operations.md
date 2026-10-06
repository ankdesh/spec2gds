# AI Assistant operations and tests

Use the [system contract](ai-assistant.md) for required behavior. Check
[TEMP implementation gaps](TEMP-ai-assistant-implementation-gaps.md) before
assuming that a required flow is fully supported. This guide collects run
commands, configuration, diagnostics, and verification. It does not redefine
product behavior.

## Setup and source pin

Use the root uv-managed Python environment. Use Node.js 24.2+ for the combined
stack. Assistant alone also supports Node.js 22.19+ in the 22.x line. Node.js
24.0/24.1 cannot launch the pinned Harness CLI. The launcher checks this before
runtime state is created. Circuit Designer declares Node.js 24+.

From the repository root:

```bash
uv sync
scripts/setup-all.sh
npm --prefix circuit-designer run build:editor
```

Setup prepares the selected Harness source, links its unpublished native `.spec` files
and toolchain, and builds the Assistant. Do not use a separate `npm ci` in
`ai-assistant` for this source-linked dependency composition. Network access is
needed for clone/fetch/install. There is no `setup:harness` npm script or
`--update-harness` option.

`HARNESS_SOURCE` selects a checkout. Relative values resolve from the repository
root. The default is the sibling `deepseek-harness` directory. Setup follows
`DSH_BRANCH`, currently `spec2gds/integration`. It records the physical checkout
path in `ai-assistant/.env` and preserves other settings, comments, and permissions.
It refreshes native `.spec` file/type links and the actual `tsc`/`tsx` executable links.
Replaced installed entries remain in `node_modules/.harness-links-*`.

Verify that the selected checkout matches [harness.lock.json](../ai-assistant/harness.lock.json).
The setup script does not enforce the pin or a clean checkout. Packaging does.
Stricter bootstrap enforcement is proposed in future work. Do not use setup to change another
person's dirty checkout without first resolving its state.

```bash
# Set this to the exact checkout selected by setup.
ASSISTANT_HARNESS_CHECKOUT=/absolute/path/to/deepseek-harness
git -C "$ASSISTANT_HARNESS_CHECKOUT" rev-parse HEAD
git -C "$ASSISTANT_HARNESS_CHECKOUT" status --short
```

Compare the commit with the lock file. For a moved/deleted Harness checkout,
rerun setup with an explicit destination:

```bash
HARNESS_SOURCE=/absolute/path/to/deepseek-harness scripts/setup-all.sh
```

If toolchain links are missing, inspect the setup diagnostic. Install the Harness
checkout's dependencies before relinking. Do not copy pnpm shell wrappers as
standalone executables. Focused setup tests use disposable fixtures; they do not
replace a real source build.

## Start and use the browser

Set the provider key in the environment, then start from the repository root:

```bash
scripts/serve-all.sh start
```

For restricted Spec content saves:

```bash
scripts/serve-all.sh start --require-human-approval
```

The launcher prints service URLs. It does not open a browser. After rebuilding
product or Harness code, use `scripts/serve-all.sh restart`. `start` refuses a
stale or partial stack on the default ports. Do not restart a shared stack merely
to run an isolated test.

To run the Assistant alone, with its services already available:

```bash
cd ai-assistant
npm run dev
```

Open the printed Assistant URL. The global new-conversation chooser can select configured
Spec/Circuit services, connect another service for this process, or create an empty
source. A Workspace-row chooser stays within its logical design source. Select the
execution preset before starting. Editor launches already identify an exact target.
A browser launch passes a binding reservation through Harness's one-time authentication
exchange in a URL fragment. The client removes the fragment before activation.

For a contentful new document, use this required sequence:

1. Send the design request. Inspect the architecture, name, service, and assumptions.
2. Approve, revise, or cancel the architecture in the Assistant.
3. After approval, allow creation and continuation in the separate document conversation.
4. Inspect the service result. An automatic save must show the saved receipt. A restricted
   proposal must remain pending until approved in Spec Editor.
5. In Spec Editor, open the exact saved path if another document is visible. Open
   **AI Assistant submission history**, inspect **Details and diff**, then approve the
   stored proposal. Refresh Assistant status if needed. Do not infer the target from
   the service's active document.

Use **File → Open Spec** for a server-local `.spec` path. There is no
`/specs/<document-id>` editor route. Use **Edit text…** for explanations. For RTL
output, use the component/design **Options → Launch activity… → rtl.generate → Run**.
The [generator reference](rtl-generation-activity.md) defines targets and reports.

The required Assistant UI has no Spec content-save approval button and no extra
creation confirmation after architecture approval. The TEMP list records the controls
that still differ. Tests of the current code can pass while those gaps remain open.

## Configuration and limits

This section is the single assistant-defaults reference. Other guides must link here.
The deployment profile is [cordis.patch.yml](../ai-assistant/profile/cordis.patch.yml).

| Variable | Default / role |
| --- | --- |
| `ASSISTANT_HOST` / `ASSISTANT_PORT` | `0.0.0.0` / `6013`. |
| `ASSISTANT_STATE` | `ai-assistant/.dev` in development. Back up the complete root. |
| `ASSISTANT_PROFILE` | `spec2gds-web`; `spec2gds-headless` omits the web UI. |
| `SPEC2GDS_SCRATCH_ROOT` | `<state>/workspaces`; private logical-source grouping paths. |
| `SPEC_DOCUMENT_ROOT` | `<state>/spec-documents`; service-reserved named `.spec` destinations. |
| `SPEC2GDS_CATALOG_ROOT` | Product `profile/catalog`, set by launch scripts. |
| `OPENAI_MODEL` | `gpt-4o-mini`; configured default model. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1`. |
| `OPENAI_API_KEY` | No default credential. Required for provider model calls. |
| `SPEC_SERVICE_ALLOWLIST` | `http://127.0.0.1:6010`; comma-separated exact service URLs. |
| `CIRCUIT_SERVICE_ALLOWLIST` | `http://127.0.0.1:6011/api/circuit-designer/v1`; comma-separated exact service URLs. |
| `ASSISTANT_OWNER_TIMEOUT_MS` | `30000`; service request deadline. |
| `ASSISTANT_MAX_OUTPUT_TOKENS` | `16384` (16,384); cap for each model response and configured compaction. Product range: 128–32,768. |
| `ASSISTANT_MAX_STEPS_PER_TURN` | `3`; focused base model-request steps. Product range: 1–20. |
| `ASSISTANT_HTTP_MONITOR_ORIGINS` | Configured service allowlists when unset; comma-separated exact monitoring origins. |

The focused step limit gets one extra step after a visible structured-question
call in that turn. Goal/orchestrated turns currently allow eight model steps.
Changing the focused environment variable does not change that fixed nonfocused
limit. All model calls still use the deployment output limit. A provider can also
have its own cap. Reasoning tokens can consume output allowance even when no final
text appears. Output tokens, model steps, and goal rounds are different limits.
Record the effective values when investigating a stopped turn.

The OpenAI route offers `gpt-5.6-luna` as well as the configured model. The endpoint
and key must have access to the selected model. Generic Harness Models onboarding
is omitted. Exact prompt/event definitions are pinned to the conversation; model
selection must remain within approved routes.

Service allowlists are rechecked on service calls. Product browser routes use same-origin
checks. This is a trusted single-user deployment, not an authenticated public
multi-user service. Run one Assistant process per state root.

Aggregate allocations below come from the shared profile. Trusted deployment
configuration can change them within `execution-policy.ts` ceilings. Reviewed
templates can lower an allocation, not exceed deployment.

| Aggregate bound | Goal | Orchestrated |
| --- | --- | --- |
| Rounds / requests | 8 / 32 | 8 / 48 |
| Tokens / active time | 300,000 / 30 minutes | 500,000 / 45 minutes |
| Members / concurrency | 1 / 1 | 7 / 3 |
| Pending deliveries / ledger events | 100 / 256 | 1,000 / 1,000 |
| Payload bytes / causal depth | 131,072 / 16 | 131,072 / 16 |

HTTP monitoring has separate transport bounds:

| Bound | Value |
| --- | --- |
| Scheduler tick | 1 second. |
| Check interval | 5 seconds to 1 hour; UI suggests 60 seconds. |
| Debounce | 5 seconds. |
| Request deadline / body | 5 seconds / 64 KiB. |
| Sources per conversation / process | 2 / 100. |
| Concurrent checks / disable threshold | 2 / 5 consecutive HTTP failures. |

## CLI flows

The root Python entry points are `spec2gds-assistant` and `spec2gds-spec`.
The Assistant command supports `focused` only. It starts a private loopback Spec
service, binds one headless turn, prints the answer/IDs, then exits. The Spec command
inspects or decides stored records; it never calls a model.

```bash
uv run spec2gds-assistant ./work/timer --preset focused -- "Propose a timer component."
uv run spec2gds-spec architecture-reviews ./work/timer
uv run spec2gds-spec approve-architecture ./work/timer REVIEW_ID
uv run spec2gds-assistant ./work/timer --architecture-review-id REVIEW_ID -- "Implement the approved architecture."
```

Use the returned review ID. `revise-architecture` and `cancel-architecture` also
operate on that durable record. An approved review must match the exact document,
scope, and relevant revision. Headless mode does not receive browser creation or
question cards. Report unresolved input instead of assuming a browser action occurred.

For a restricted content save:

```bash
uv run spec2gds-assistant ./work/timer --require-human-approval -- "Improve the timer explanation only."
uv run spec2gds-spec reviews ./work/timer
uv run spec2gds-spec approve ./work/timer PROPOSAL_ID
uv run spec2gds-spec history ./work/timer --limit 25
```

`reject` rejects a pending content proposal. Approval reopens and revalidates the
stored artifact; it does not accept new operations from the command line. Pass an
ID when several proposals are pending. `history --limit N --before CURSOR` paginates.
These explicit CLI decisions are the approved exception to browser approval location.

A directory target uses its sole direct-child `.spec` file. With none, the Assistant
command creates an empty `<directory-name>.spec` before requesting content. With
several, it reports candidates. An explicit `.spec` path selects that file and can
create it if absent. Spec decision commands require an existing document. Browser
and CLI writers keep disk conflict/revision checks and reconcile interrupted saves.

Each document's CLI records are under
`<workspace>/.spec2gds/assistant/<package-path-hash>/`:

| Record | Contents |
| --- | --- |
| `last-run.json` | Latest run schema, path, document/conversation ID, preset, policy, exit code, answer, proposal IDs/states, and event path. |
| `runs/<session-id>.json` | Run metadata. |
| `runs/<session-id>.jsonl` | Raw exported events for that invocation. |
| `spec2gds-spec reviews` output | Exact stored artifacts, preview, service diagnostics, and receipts. |

The path hash distinguishes explicit files in one workspace. Do not interpret
exit code or model answer alone as a saved-state result.

Lower-level Harness requests can bind by service-resolved names or technical IDs:

```bash
cd ai-assistant
npm run request -- --domain circuit --service-url http://127.0.0.1:6011/api/circuit-designer/v1 --document-name "My circuit" -- "Explain the clock and reset topology."
```

`--session-id ID` resumes an existing binding. Spec names can select documents,
targets, or qualified narrative sections such as `Operation › Cycle timing`.
Unknown/ambiguous names return choices. Technical `--document-id`,
`--owner-document-key`, and `--entity-id` options remain available. Native releases
use `node deployment/request.mjs` with the same interface.

## Event configuration, monitoring, and recovery

Start a bound goal/orchestrated conversation. In the new-conversation chooser, select an event
template. **Configure event template** opens visual fields and their canonical
JSON text. JSON is a YAML subset. Inspect the primary, analyst, reviewer, permitted
routes/tools, typed events, and subscriptions. Keep the required causal review chain.

Change a prompt, apply text to the visual editor if needed, then select **Validate
and preview**. Inspect warnings and the exact diff. **Save reviewed template** saves
that exact revision. Built-in edits create a separate named template. Start the conversation
to pin it. Later edits do not change the conversation's prompts, tools, or budget.

Use **Inspect configuration and execution** to inspect configuration digest, causal
event ancestry, delivery/activation attempts, waits, request charges, sources, and
native member transcripts. Historic charge records may lack per-request member
attribution; do not infer it.

In **Monitor service endpoint**, keep the bound-service URL and revision pointer.
Select changed/equality, supply a JSON value for equality, and choose an interval.
**Start monitoring** adds an immutable source. Unchanged checks use no model calls.
A stable change wakes the permitted event chain using the remaining budget.
Disable/re-enable retains the cursor. Repeated HTTP failures disable the source;
correct the endpoint before enabling it again. Source editing/deletion is not
supported. Adding a service outside the startup monitoring allowlist needs a policy
update and restart.

Trusted host/API configuration can name a bearer-credential environment variable
with `authorizationEnv`. Persist only that variable name. The UI does not accept
credential values. Startup rechecks origins and credential availability.

`wait_for_event` can await a human answer, a declared event, or an exact service
review. Use **Answer** for the current wait identity and observed execution revision.
Stale answers cannot wake another activation. Waiting consumes no member model
rounds; another permitted member may still work.

Pause blocks checks and new admissions. Stop is terminal and cancels execution
waits. Neither action undoes a saved document or discards a service proposal.
Restart needs human Resume for persistent execution. Resume retains spent budget.
A replay-safe read-only delivery has at most three transport attempts, with
one-second initial and ten-second maximum backoff. Interrupted/uncertain attempts
need **Acknowledge uncertainty and retry**. These transport retries must not repair
a stopped model validation request.

Back up the whole Assistant state root and the `.spec` file with its service records.
Native JSONL, product SQLite, and native event/source storage are different records.
Spec state includes durable submissions and `.spec` file decisions. Circuit documents and
pending proposals are process-local; reopen them after a Circuit restart. Older
unsupported goal/orchestrated conversations stay readable but require a new conversation for work.
The preserved legacy Python assistant database is not loaded by this runtime.

## Instruction releases and service extensions

Static model guidance is in `ai-assistant/profile/catalog`. The release manifest
is `release.json`. Native tool contracts are in `tools/*.json`. General instruction
text is in `instructions.json`; domain and event-member files remain in the same
catalogue. TypeScript handlers perform validation and service calls.

To add or change a tool:

1. Edit its JSON contract and catalogue instructions. Keep service operation
   vocabularies in the relevant service.
2. Add the execution module and register it through the native adapter. Declare
   its availability rule and handler compatibility. Instructions grant no authority.
3. Run `npm --prefix ai-assistant run generate:tools`. Commit generated argument
   types. CI/build checks use `npm --prefix ai-assistant run check:tools`.
4. Add deterministic admission, permission, state, and service-call checks.
5. Increment the release semantic version. Use a major version for incompatible
   static contracts, a minor version for compatible additions, and a patch version
   for compatible guidance corrections. Increment the handler compatibility version
   when installed handlers cannot safely execute old contracts. Released content
   is immutable. Keep old snapshots; require fresh conversations for incompatible
   execution.

To extend a service, update that service's metadata and route declarations together.
Update only its Assistant adapter and tests. Verify metadata without an open
document and with the other service unavailable. Keep every action within the
selected service base. Interface version `1.0.0` requires the declared action set;
changes to this interface require an explicit adapter compatibility update.

To add an adapter for a new service kind, first accept its domain, target, scope,
permission, and save rules. Add its metadata declaration and an explicit Assistant
adapter. Register the kind in binding validation and the capability boundary.
Add checks for exact targets, permissions, receipts, and operation with other
services unavailable. Metadata alone must not enable a new domain. New domain
support remains separate accepted work.

SQLite stores releases in `instruction_releases` and conversation pins in
`instruction_snapshots`. These pins have no binding foreign key. Event template
pins remain in `binding_event_configuration`. Native identifiers such as
`session_id` and `owner_document_key` remain code identifiers.

After TD-05, old conversations without snapshots are readable history. Start a
fresh conversation for model execution. Do not delete design data or receipts to
resolve a missing pin. A release hash conflict requires a new release version;
never replace stored snapshots to hide it.

## Investigate an error

First capture the visible error and **Technical details**. Record the exact conversation,
binding, user request, failure stage, tool call, proposal/review/creation ID, source
revision, operation-schema digest, and effective model limits. Preserve the last
confirmed receipt. Do not reproduce by editing a developer's live document.

Follow the failed request in this order:

1. Check the exact target and scope. Compare the conversation binding with the service record,
   not just the editor's visible title.
2. Find the native tool call and result. A native schema rejection can occur before
   product code executes. Absence of a service request does not prove a service bug.
3. Check the prompt actually supplied to the model, its version, and the published
   tool fields. A complete prompt can suppress separately registered sections.
4. Compare admitted formatting, the stored artifact, and the service preview. Check
   local aliases, typed references, component descriptions, and authored revision.
5. If a write started, inspect its exact service receipt. Keep unknown outcomes
   uncertain. Do not create a new document/proposal as recovery.
6. If the turn stopped, inspect provider finish reason, token usage, model-step
   count, and last confirmed phase. A token cap can stop the answer after a context
   read while the document remains empty.

Service output is under `logs/serve-all` for the combined launcher. Durable conversations
are under the configured Assistant runtime state; development snapshots commonly
use `session.v3.jsonl.zstd`. Locate them with:

```bash
rg --files --hidden ai-assistant/.dev | rg 'session\.v3\.jsonl(\.zstd)?$'
# Substitute the exact file found above.
zstd -dc /absolute/path/to/session.v3.jsonl.zstd > /tmp/assistant-session.jsonl
rg -n 'tool/call|tool/result|turn/end|assistant/message|max-tokens' /tmp/assistant-session.jsonl
```

For an uncompressed snapshot, read it directly. Keep exports local to the project;
they can contain design text. Product `assistant.sqlite3` stores architecture,
creation, binding, and proposal records. Use read-only SQLite inspection or the
existing product/service APIs. Never edit a database row to force approval or completion.

Unified structured logging is off by default. Follow [logging](logging.md) to enable
`SPEC2GDS_LOGGING=ON` and choose `SPEC2GDS_LOG_LEVEL`. The common service registry
selects the log path. Debug data is redacted, but still contains design/conversation
text. An absent unified log is not evidence that a tool never ran; inspect JSONL
and service receipts.

| Symptom | Check first |
| --- | --- |
| Missing architecture field | Native tool schema and field path; distinguish `name` from `component`/`design`. |
| “New component … needs description” | Same-batch metadata, alias, document ID, and component kind. |
| Proposal rejected after a rename | Stable target reference in the service transaction; never find a new RTL service by display name. |
| Content marked complete after creation | Creation receipt versus admitted continuation versus applied content receipt. |
| Wrong document edited | Binding, explicit target intent, scope, and keyed service request. |
| Stale proposal/review | Model-read revision and review dependency; no restamping. |
| Repeated invalid calls | First-failure stop guard and prompt instructions. |
| Circuit sent but source unchanged | Draft/accept/save phase; `sent` is only handoff. |

Assign the fault only after locating its stage. Useful investigation groups are
prompt wording, native schema, Assistant formatting/guard, service schema/semantics,
UI status, transport, and execution limits. Add a deterministic regression at the
failed boundary. Add a browser case for a visible control or state problem.

## Source map for investigation

Read the code at the failed boundary. Do not infer service validity from a model
answer or a UI card.

| Boundary | Main entry points |
| --- | --- |
| Host composition, launch, review actions, and native hooks | [index.ts](../ai-assistant/src/index.ts). |
| Prompts and exact context | [Catalogue](../ai-assistant/profile/catalog), [domain-context.ts](../ai-assistant/src/domain-context.ts), and [service-clients.ts](../ai-assistant/src/service-clients.ts). |
| Tool admission and proposal preparation | [tools.ts](../ai-assistant/src/tools.ts), [service-operation-schema.ts](../ai-assistant/src/service-operation-schema.ts), and [proposal-pipeline.ts](../ai-assistant/src/proposal-pipeline.ts). |
| Formatting, aliases, and persistent IDs | [normalize.ts](../ai-assistant/src/normalize.ts). |
| Architecture and document creation | [architecture-review.ts](../ai-assistant/src/architecture-review.ts) and [source-creation.ts](../ai-assistant/src/source-creation.ts). |
| Product records, execution, and configuration | [state.ts](../ai-assistant/src/state.ts), [execution-policy.ts](../ai-assistant/src/execution-policy.ts), and [event-configuration.ts](../ai-assistant/src/event-configuration.ts). |
| Cards, diagnostics, and metrics | [Client](../ai-assistant/client/index.js), [proposal-presentation.ts](../ai-assistant/src/proposal-presentation.ts), and [eval-metrics.ts](../ai-assistant/src/eval-metrics.ts). |
| Spec service semantics and saved receipts | [Spec format source](../spec2gds/spec/spec_format). |
| Restricted browser approval | [Spec Editor](../circuit-designer/apps/editor/src/App.tsx). |
| Circuit proposals, drafts, and source saves | [Circuit service](../circuit-designer/packages/service/src) and [standalone editor](../circuit-designer/apps/standalone/src). |

## Verification commands

Run source checks with a supported Node runtime. From the repository root:

```bash
uv sync
npm --prefix ai-assistant run build
uv run python -m pytest tests/spec/spec_format -q
npm --prefix circuit-designer run build:editor
```

Then from `ai-assistant`:

```bash
npm run typecheck
npm test
npm run test:harness
npm run build
```

Run Assistant tests from its directory to avoid nvm-related setup-fixture path
issues with `npm --prefix`. CLI service fixtures need the compiled Assistant first.
Setup runs the real source linker; there is no separate bootstrap test script.
Use `node --import tsx --test tests/setup.test.ts` for focused setup fixtures.

### Browser checks

From the repository root, build the Assistant and editor. Install isolated scenario
dependencies and the
Circuit workspace's Chromium cache:

```bash
npm ci --prefix tests/ui-scenarios
cd circuit-designer
PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright-browsers" npm exec -- playwright install chromium
cd ..
bash tests/ui-scenarios/run-test.sh --scenario architecture --output /tmp/assistant-ui-architecture
bash tests/ui-scenarios/run-test.sh --scenario automatic --output /tmp/assistant-ui-automatic
bash tests/ui-scenarios/run-test.sh --scenario restricted --approval-mode review --output /tmp/assistant-ui-restricted
bash tests/ui-scenarios/run-test.sh --scenario live --output /tmp/assistant-ui-draft
bash tests/ui-scenarios/run-test.sh --scenario binding --output /tmp/assistant-ui-binding
bash tests/ui-scenarios/run-test.sh --scenario repeated --output /tmp/assistant-ui-repeated
npm --prefix circuit-designer run test:e2e:editor
```

`live` tests editor refresh and draft retention; it does not use a live provider.
`--headed` shows the browser. The runner uses temporary documents/state, dedicated
ports, and only its own processes. It captures screenshots, traces, service logs,
console/network failures, model requests, receipts/revisions, and `.spec` file copies.
Assertions check service state, disk contents, and rendered editor data. The automatic
scenario requires architecture decisions, with no final-save confirmation. The
restricted scenario must be updated for Editor-only approval; see TEMP.

Event-preset UI tests use real React/native services with a minimal Harness shell
adapter and deterministic services/models. They do not prove every full-shell panel.
Install browser tools separately from the unpublished runtime composition:

```bash
cd ai-assistant
npm install --prefix .ui-test-tools --no-audit --no-fund @playwright/test@1.61.1 react@18.3.1 react-dom@18.3.1
PLAYWRIGHT_BROWSERS_PATH="$PWD/.ui-test-tools/browsers" .ui-test-tools/node_modules/.bin/playwright install chromium
ASSISTANT_UI_TEST_DEPS="$PWD/.ui-test-tools" PLAYWRIGHT_BROWSERS_PATH="$PWD/.ui-test-tools/browsers" npm run test:ui
```

Optionally set `ASSISTANT_UI_SCREENSHOT_DIR` to an absolute artifact directory.
The UI tests cover configuration, causal routing, review waits, controls,
permissions, and exact pins. Keep this proof scope separate from the isolated
service/editor browser scenarios and native headless transport tests.

### Evaluation and RTL evidence

```bash
cd ai-assistant
npm run eval -- --output /tmp/spec2gds-assistant-eval
```

This command validates the versioned `evals` catalogue and fixture existence.
It writes `catalogued` results; it does not run the case requests or assert their
semantic outcomes. `--session /path/to/session.jsonl` adds measurements from an
uncompressed native snapshot. The native Harness integration separately records
and keylessly replays a deterministic model trajectory.

Metrics currently measure proposal calls, structured results, first ready preview,
operation counts, clarifications, retries, latency, and native token usage. An
applied/sent count is a stage measurement, not a generic completion score.
False-completion violations require explicit failed evaluation assertion events;
zero events do not prove absence of false claims. No release quality threshold is
approved. The TEMP list records metric and corpus gaps.

RTL functional checks need Verilator 5.x, Make, and a C++ compiler. Run from the
repository root:

```bash
uv run --no-sync python -m pytest tests/spec/activities/rtl -q
uv run --no-sync python scripts/rtl_evaluation.py --project /absolute/published/project --case adder_8 --source-revision sha256:SOURCE_REVISION --output /tmp/adder-check
```

The project check verifies inventory/revision before separate generation, lint,
compilation, and simulation outcomes. Explicit `--spec PACKAGE --target ID_OR_VLNV`
generates a separate CLI project; it is not evidence of UI activity execution.
Portable cases cover concrete adders, counters, asynchronous FIFOs, a priority
encoder, and a registered pipeline. Negative controls must compile and then fail
simulation. Full original parameterized RTLLM compatibility remains unverified.

Live-model smoke is separate. Run from the repository root:

```bash
bash tests/ui-scenarios/run-test.sh --scenario automatic --live-model --output /tmp/assistant-live-smoke
cd tests/ui-scenarios
node --import tsx runner/run_generalization.ts --output /tmp/assistant-generalization
node --import tsx runner/run_generalization.ts --case registered_pipeline --repeats 3 --output /tmp/assistant-pipeline-live --benchmark-root /path/to/RTLLM
```

These commands need `OPENAI_API_KEY`. The generalization runner defaults to three
runs per case with short requests and no supplied RTL/tool instructions. The runner
currently overrides deployment limits: live runs use 8,192 output tokens and 12
steps; deterministic UI scenarios use 1,200 and five. These are test settings,
not application defaults. Environment overrides are recorded in run artifacts.
Record model, endpoint, actual limits, prompt/template versions, reviewed architecture,
authored document, UI-generated artifacts, simulation, and manual document-quality
review. Missing credentials/tools mean unverified; do not substitute canned RTL.

Preserved [implementation evidence](evidence/hierarchical-spec-implementation.json)
and [live-evaluation status](evidence/hierarchical-spec-live-evaluation.json) are dated
records. They do not prove the new contract. Their raw content is retained unchanged.

## Acceptance matrix

Requirement IDs refer to the system contract. Existing fixtures are evidence of
specific boundaries, not full compliance. Open rows identify the needed extension
in TEMP. New acceptance tests must fail if they violate a required result.

| Requirement | Required assertion | Existing evidence / open gap |
| --- | --- | --- |
| [AS-01](ai-assistant.md#as-01) | One behavior contract; valid local links; stable IDs. | Documentation link/ID audit. |
| [AS-02](ai-assistant.md#as-02) | Model cannot approve/save directly; specialists remain read-only. | `domain-contracts`, `execution-policy`, `event-configuration` Assistant tests. |
| [AS-03](ai-assistant.md#as-03) | A conversation remains bound to A while B is visible; equal IDs have distinct keys; restart reopens A. | Service `test_iterative_refinement.py`, Assistant state/service-client/workspace tests, `binding` browser case. |
| [AS-04](ai-assistant.md#as-04) | Unqualified creation uses current document; explicit B stops before authoring any A edit. | Binding tests are partial. [GAP-10](TEMP-ai-assistant-implementation-gaps.md#gap-10) needs language-intent and native/browser cases. |
| [AS-05](ai-assistant.md#as-05) | Component or Design scope cannot create top-level or edit read-only neighbors; unavailable targets never fall back. | Service `test_v1_api.py`, operation-schema/service-client tests; [GAP-09](TEMP-ai-assistant-implementation-gaps.md#gap-09) for service selection. |
| [AS-06](ai-assistant.md#as-06) | Complete paged values, fresh revision, stable selection; malformed/stale cursor fails. | Service `test_unified_assistant.py`, Assistant domain/service-client tests. |
| [AS-07](ai-assistant.md#as-07) | Live schema governs proposals; unknown constructs fail; digest change refreshes in the same conversation. | Assistant domain-contract/iterative-refinement/service-client tests; service API tests. |
| [AS-08](ai-assistant.md#as-08) | Safe new defaults are visible; unresolved existing semantics asks; no redundant details confirmation. | Assistant `iterative-refinement.test.ts` and `domain-contracts.test.ts` question/default cases are partial; [GAP-12](TEMP-ai-assistant-implementation-gaps.md#gap-12). |
| [AS-09](ai-assistant.md#as-09) | Every new hardware, structural, or RTL edit has approved architecture; text-only does not rewrite RTL. | Architecture/service tests cover creation and text stability; [GAP-01](TEMP-ai-assistant-implementation-gaps.md#gap-01) adds RTL and other uncovered edits. |
| [AS-10](ai-assistant.md#as-10) | Approved names, ports, hierarchy, edits, service/scope, and dependent revision match; questions block approval. | Assistant architecture-review tests are partial; [GAP-05](TEMP-ai-assistant-implementation-gaps.md#gap-05) and [GAP-08](TEMP-ai-assistant-implementation-gaps.md#gap-08). |
| [AS-11](ai-assistant.md#as-11) | One creation after approval under both policies; empty request skips review; no extra confirmation. | Source-creation unit/host/client tests; [GAP-03](TEMP-ai-assistant-implementation-gaps.md#gap-03). |
| [AS-12](ai-assistant.md#as-12) | Saved document, active conversation, admitted request, and saved content stay distinct; failed content resumes only that document. | Source-creation recovery tests; [GAP-07](TEMP-ai-assistant-implementation-gaps.md#gap-07) and [GAP-08](TEMP-ai-assistant-implementation-gaps.md#gap-08). |
| [AS-13](ai-assistant.md#as-13) | Automatic saves once; restricted source is unchanged until Editor approval; Assistant cannot approve Spec content. | Service policy/refinement tests; [GAP-02](TEMP-ai-assistant-implementation-gaps.md#gap-02) extends restricted browser/host cases. |
| [AS-14](ai-assistant.md#as-14) | Alias/reference remapping is deterministic; descriptions are same-batch; invalid batch rolls back. | Assistant normalize/pipeline/iterative tests; service unified/atomic tests; native Harness fixture. |
| [AS-15](ai-assistant.md#as-15) | Stale content is not restamped; changed ID replay fails; interrupted save recovers exact receipt once. | Service iterative/CLI tests and Assistant state/pipeline/creation tests. |
| [AS-16](ai-assistant.md#as-16) | Requested hierarchy is preserved; text-only keeps SV bytes; renamed creation validates by stable ID. | Service unified/refinement tests; [GAP-12](TEMP-ai-assistant-implementation-gaps.md#gap-12) for prompt intent. |
| [AS-17](ai-assistant.md#as-17) | Reachable hierarchy, reuse, concrete slices, targets, warnings, and old report compatibility are correct. | RTL activity suite and service unified tests. Unsupported cases must reject. |
| [AS-18](ai-assistant.md#as-18) | Effective prompt, native schema, and guards agree; complete unbound prompt includes creation/architecture rules. | Native architecture-runtime and host/domain tests; [GAP-01](TEMP-ai-assistant-implementation-gaps.md#gap-01) / [GAP-04](TEMP-ai-assistant-implementation-gaps.md#gap-04) / [GAP-12](TEMP-ai-assistant-implementation-gaps.md#gap-12). |
| [AS-19](ai-assistant.md#as-19) | One validation failure stops authoring and continuation in every preset. User retry is explicit. | Current native test permits correction; [GAP-04](TEMP-ai-assistant-implementation-gaps.md#gap-04) replaces this expectation. |
| [AS-20](ai-assistant.md#as-20) | Every failure path retains stage, field/operation, request identity, and known mutation outcome. | Proposal-presentation/client tests are partial; [GAP-06](TEMP-ai-assistant-implementation-gaps.md#gap-06). |
| [AS-21](ai-assistant.md#as-21) | Output/step/aggregate limits are distinct and enforced; waiting/restart does not refill them. | Launch/native Harness/execution tests. Test budgets differ; [GAP-13](TEMP-ai-assistant-implementation-gaps.md#gap-13). |
| [AS-22](ai-assistant.md#as-22) | Only latest causal review permits proposal; waits match exact decisions; failures do not resume repair. | Native event/execution/goal tests are partial; [GAP-02](TEMP-ai-assistant-implementation-gaps.md#gap-02) / [GAP-04](TEMP-ai-assistant-implementation-gaps.md#gap-04). |
| [AS-23](ai-assistant.md#as-23) | Reviewed template pins, service-only monitoring, unchanged checks, outbox dedupe, and source failure bounds hold. | Event-configuration/runtime/preset UI tests and pinned Harness native checks. |
| [AS-24](ai-assistant.md#as-24) | Restart retains bindings, records, spending, and uncertainty; no automatic persistent work before Resume. | State/source-creation/event runtime tests; [GAP-07](TEMP-ai-assistant-implementation-gaps.md#gap-07) end-to-end recovery. |
| [AS-25](ai-assistant.md#as-25) | Close/archive do not approve/discard/stop; cancellation/Stop do not undo saved content. | Card/control tests are partial; [GAP-11](TEMP-ai-assistant-implementation-gaps.md#gap-11) needs native browser close/reopen. |
| [AS-26](ai-assistant.md#as-26) | Source-bound Circuit accept stages only; failed save keeps draft; source save requires Spec receipt. | Circuit service/client source-save tests; optional enhancements remain in future work. |
| [AS-27](ai-assistant.md#as-27) | Completion matches requested stage; empty/continued/sent never imply saved content; functional claims need tests. | Receipt fixtures, service browser and RTL cases are partial; [GAP-07](TEMP-ai-assistant-implementation-gaps.md#gap-07) / [GAP-13](TEMP-ai-assistant-implementation-gaps.md#gap-13). |
| [AS-28](ai-assistant.md#as-28) | Source checkout matches pin; build inputs are clean; setup repairs links without erasing settings. | Setup fixtures, manual pin check, and release packaging checks. Pin-enforcing bootstrap remains future work. |
| [AS-29](ai-assistant.md#as-29) | Scope, pending decisions, failures, and exact diff stay visible after collapse/reload. | Source-creation-client and architecture/browser tests; [GAP-02](TEMP-ai-assistant-implementation-gaps.md#gap-02) / [GAP-06](TEMP-ai-assistant-implementation-gaps.md#gap-06) / [GAP-11](TEMP-ai-assistant-implementation-gaps.md#gap-11). |
| [AS-30](ai-assistant.md#as-30) | Results distinguish catalogue, fixtures, replay, live inference, lint, simulation, and unverified checks. | Evaluation fixtures and RTL runner; [GAP-13](TEMP-ai-assistant-implementation-gaps.md#gap-13). |
| [AS-31](ai-assistant.md#as-31) | JSON contracts, generated arguments, native admission, and one instruction source. | `instruction-snapshots.test.ts`, contract/domain tests, `check:tools`, native integration. |
| [AS-32](ai-assistant.md#as-32) | Independent metadata exports, known actions, no cross-service routing. | Spec `test_assistant_integration_metadata.py`, Circuit service metadata tests, adapter/transport checks. |
| [AS-33](ai-assistant.md#as-33) | Durable pins, release immutability, inheritance, legacy blocking, and incompatible handlers. | `instruction-snapshots.test.ts` and source-creation host tests. |
| [AS-34](ai-assistant.md#as-34) | Extension procedure and deterministic evidence without a model-quality claim. | This procedure, generated-type checks, packaged asset checks, deterministic native/UI tests. |

Fixture files are under [Assistant tests](../ai-assistant/tests),
[service tests](../tests/spec/spec_format), [UI scenarios](../tests/ui-scenarios/runner),
and [RTL tests](../tests/spec/activities/rtl). Read the actual test before
claiming its coverage. Do not use fixed historical pass counts as release gates.

## TD-05 verification record

Verified on 2026-10-06. These are deterministic results, not model-quality scores.

| Check | Result |
| --- | --- |
| Assistant unit and contract checks | 134 passed |
| Native Harness checks with fixed model responses | 5 passed |
| Browser preset and pin checks with installed Chrome | 3 passed |
| Circuit service checks, including metadata and Save to Spec | 24 passed |
| Selected Spec metadata, proposal, and hierarchy checks | 17 passed; 1 skipped because Verilator was unavailable |
| Generated types, Assistant build, and Circuit service build | Passed |
| Release packaging and catalogue assets | Passed with the clean pinned Harness |
| Documentation audit | 333 local links, 120 heading links, 34 mapped requirements, and four JSON examples checked |

Live-model accuracy comparison was not run. The native architecture retry fixtures
characterize existing behavior recorded in GAP-04; they do not accept that behavior
as first-failure compliance. All unrelated TEMP entries remain open. Only the
verified duplicate-instruction-source part of GAP-12 is removed.

The browser checks used the existing Circuit workspace test dependencies through
`ASSISTANT_UI_TEST_DEPS` and the installed Chrome path through
`ASSISTANT_UI_BROWSER_PATH`. These are optional test controls. Release packaging
stages the canonical guides from repository `docs`; it does not restore a second
editable guide set under `ai-assistant/docs`.

## Build and maintain

From `ai-assistant`, after source and test verification:

```bash
npm run package -- /tmp/spec2gds-assistant-release
```

Packaging requires a clean Harness checkout at the exact lock revision. New native
npm packages are source-linked; registry publication and lockfile regeneration are
separate release work. Keep product behavior in spec2gds and generic extension
changes in Harness. Generated bundles, dependencies, samples, and old research
are not authorities for product behavior.

For a contract change, update the stable requirement, its acceptance row, and the
TEMP gap record. Validate JSON examples against native tool admission and service
schemas. Check all local Markdown paths/heading anchors and references to pruned
guides. Remove completed TEMP entries after proof. Remove the TEMP file when its
last entry is closed; keep the contract, operations guide, and future proposals.

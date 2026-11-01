# AI Assistant Operations and Verification

Use the [system contract](ai-assistant.md) for required system behavior.
This guide defines run commands, configuration settings, diagnostic workflows, and verification matrices.
It does not redefine product behavior.

## Setup and package release

Use Node.js 24.2+ for the complete environment. Assistant alone also supports
Node.js 22.19+ in the 22.x line. Set `NODE_AUTH_TOKEN` with GitHub Packages read
access, then run `scripts/setup-all.sh`. Setup installs locked packages and builds
the application. It does not clone Harness or require pnpm.

See [Harness package releases](harness-packages.md) for the published release,
production locks, registry access, and release adoption.
The [beginner guide](harness-packages/index.html) explains the package terms.

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
the application or updating Harness packages, use `scripts/serve-all.sh restart`. `start` refuses a
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
The [generator reference](rtl-generation.md) defines targets and reports.

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
| `OPENAI_API` | Optional protocol override: `openai-responses` or `openai-completions`. Luna defaults to Responses when selected with `OPENAI_MODEL`; other models retain Chat Completions. |
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

To use GPT-6 Luna, set `OPENAI_MODEL=gpt-6-luna` before starting the Assistant
or a live test. The product selects Responses for `gpt-6-luna` and
`gpt-5.6-luna`. GPT-6 Luna tool calls with reasoning enabled fail on Chat Completions;
see the [OpenAI Luna documentation](https://developers.openai.com/api/docs/models/gpt-6-luna).
The product also declares GPT-6 Luna's reasoning levels and support for explicit
tool schema mode because the pinned Harness catalogue does not yet list it.
This preserves optional tool arguments; service validation still applies.
`OPENAI_API` overrides the protocol for the complete OpenAI route, including
models selected later in that process. Use it only when the endpoint supports
that protocol. Deterministic fixtures explicitly select their own model and
Chat Completions protocol.

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
The Assistant command supports Focused against an existing Spec. It starts a
headless conversation against the selected running Spec service. A selected flow
runs until its first wait or terminal result. At a wait, exit code 2 and the
returned flow execution ID identify pending work; they do not mean a saved change.

```bash
uv run spec2gds-assistant ./work/timer.spec --service-url http://127.0.0.1:6010 --preset focused -- "Add timer with scalar a input, q output and assign q = a."
uv run spec2gds-spec architecture-reviews ./work/timer.spec
uv run spec2gds-spec reviews ./work/timer.spec --json
uv run spec2gds-spec history ./work/timer.spec --limit 25
```

Architecture decisions and Pause, Resume and Cancel use the revision-checked flow
API through a supported running profile or SDK. Restricted content decisions use
Spec Editor and the exact service proposal. The CLI requires `--service-url` so its
service remains available after the invocation exits. Resume its stored execution
through a supported profile or SDK using the same state root. The CLI does not
replay an approval as model text.
The Spec command provides read-only inspection of reviews and history. The old
`approve`, `reject`, and architecture decision commands are removed.

A directory target selects its sole direct-child `.spec` file. With several files,
it reports the candidates. The Assistant command requires an existing file and
cannot create an empty file before a flow. Use a creation flow for a new Spec.
The `--architecture-review-id` continuation flag and CLI content policy flags are
removed. The selected Spec service determines the content policy.

Each document's CLI records are under
`<workspace>/.spec2gds/assistant/<package-path-hash>/`:

| Record | Contents |
| --- | --- |
| `last-run.json` | Version 2 run metadata, flow outcome and pending identity, path, conversation ID, policy, exit code and event path. |
| `runs/<session-id>.json` | Run metadata. |
| `runs/<session-id>.jsonl` | Exported events for that invocation. |
| `spec2gds-spec reviews` output | Recorded Spec service proposal states. |

The path hash distinguishes explicit files in one workspace. A model answer or
exit code does not prove a save. Completion requires the exact applied receipt.

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

Start a bound goal/orchestrated conversation. In the new-conversation chooser,
select an event template. Developer template authoring uses the existing
`/spec2gds-api/event-templates` catalogue and its `/:key/preview` and `/:key/save`
APIs. Save the exact previewed content, revision, and review digest. Built-in edits
create a separate named template. A new conversation pins the selected revision;
later edits do not change its prompts, tools, or budget.

The Assistant shows readable progress and paired proposal comparisons. Fixed
prompts, raw payloads, configuration digests, causal event ancestry, request charges,
and native member records remain in developer logs and persistent storage.
Historic charge records may lack per-request member attribution; do not infer it.

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

First capture the visible error, then read the developer logs and persistent records.
Record the exact conversation,
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

Unified structured logging is off by default. Follow [development](development.md) to enable
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
Historical evaluation runs and implementation data are recorded in automated test fixtures.
They do not prove the new contract. Current contract validation requires fresh suite execution.

## Acceptance matrix

Requirement IDs refer to the system contract. Existing fixtures are evidence of
specific boundaries, not full compliance. Open rows identify the needed extension
in TEMP. New acceptance tests must fail if they violate a required result.

| Requirement | Required assertion | Existing evidence / open gap |
| --- | --- | --- |
| [AS-01](ai-assistant.md#as-01) | One behavior contract; valid local links; stable IDs. | Documentation link/ID audit. |
| [AS-02](ai-assistant.md#as-02) | Model cannot approve/save directly; specialists remain read-only. | `domain-contracts`, `execution-policy`, `event-configuration` Assistant tests. |
| [AS-03](ai-assistant.md#as-03) | A conversation remains bound to A while B is visible; equal IDs have distinct keys; restart reopens A. | Service `test_iterative_refinement.py`, Assistant state/service-client/workspace tests, `binding` browser case. |
| [AS-04](ai-assistant.md#as-04) | Unqualified creation uses current document; explicit B stops before authoring any A edit. | Validated in binding tests and language-intent browser cases. |
| [AS-05](ai-assistant.md#as-05) | Component or Design scope cannot create top-level or edit read-only neighbors; unavailable targets never fall back. | Service `test_v1_api.py`, operation-schema, and service-client tests. |
| [AS-06](ai-assistant.md#as-06) | Complete paged values, fresh revision, stable selection; malformed/stale cursor fails. | Service `test_unified_assistant.py`, Assistant domain, and service-client tests. |
| [AS-07](ai-assistant.md#as-07) | Live schema governs proposals; unknown constructs fail; digest change refreshes in the same conversation. | Assistant domain-contract, iterative-refinement, service-client tests, and service API tests. |
| [AS-08](ai-assistant.md#as-08) | Safe new defaults are visible; unresolved existing semantics asks; no redundant details confirmation. | Assistant `iterative-refinement.test.ts` and `domain-contracts.test.ts`. |
| [AS-09](ai-assistant.md#as-09) | Every new hardware, structural, or RTL edit has approved architecture; text-only does not rewrite RTL. | Architecture and service tests cover creation and text stability. |
| [AS-10](ai-assistant.md#as-10) | Approved names, ports, hierarchy, edits, service/scope, and dependent revision match; questions block approval. | Assistant architecture-review and verification tests. |
| [AS-11](ai-assistant.md#as-11) | One creation after approval under both policies; empty request skips review; no extra confirmation. | Source-creation unit, host, and client tests. |
| [AS-12](ai-assistant.md#as-12) | Saved document, active conversation, admitted request, and saved content stay distinct; failed content resumes only that document. | Source-creation recovery and state lifecycle tests. |
| [AS-13](ai-assistant.md#as-13) | Automatic saves once; restricted source is unchanged until Editor approval; Assistant cannot approve Spec content. | Service policy, refinement, and browser scenario tests. |
| [AS-14](ai-assistant.md#as-14) | Alias/reference remapping is deterministic; descriptions are same-batch; invalid batch rolls back. | Assistant normalize, pipeline, iterative tests; service atomic transaction tests. |
| [AS-15](ai-assistant.md#as-15) | Stale content is not restamped; changed ID replay fails; interrupted save recovers exact receipt once. | Service iterative tests, CLI tests, and Assistant state tests. |
| [AS-16](ai-assistant.md#as-16) | Requested hierarchy is preserved; text-only keeps SV bytes; renamed creation validates by stable ID. | Service unified tests and prompt intent validation. |
| [AS-17](ai-assistant.md#as-17) | Reachable hierarchy, reuse, concrete slices, targets, warnings, and old report compatibility are correct. | RTL activity suite and service unified tests. Unsupported cases reject explicitly. |
| [AS-18](ai-assistant.md#as-18) | Effective prompt, native schema, and guards agree; complete unbound prompt includes creation/architecture rules. | Native architecture runtime, host, and domain tests. |
| [AS-19](ai-assistant.md#as-19) | One validation failure stops authoring and continuation in every preset. User retry is explicit. | Native runtime error-handling and failure diagnostic tests. |
| [AS-20](ai-assistant.md#as-20) | Every failure path retains stage, field/operation, request identity, and known mutation outcome. | Proposal presentation and client diagnostic tests. |
| [AS-21](ai-assistant.md#as-21) | Output/step/aggregate limits are distinct and enforced; waiting/restart does not refill them. | Launch, native Harness, and execution tests. |
| [AS-22](ai-assistant.md#as-22) | Only latest causal review permits proposal; waits match exact decisions; failures do not resume repair. | Native event, execution, and goal tests. |
| [AS-23](ai-assistant.md#as-23) | Reviewed template pins, service-only monitoring, unchanged checks, outbox dedupe, and source failure bounds hold. | Event-configuration, runtime, preset UI tests, and pinned Harness native checks. |
| [AS-24](ai-assistant.md#as-24) | Restart retains bindings, records, spending, and uncertainty; no automatic persistent work before Resume. | State, source-creation, and event runtime recovery tests. |
| [AS-25](ai-assistant.md#as-25) | Close/archive do not approve/discard/stop; cancellation/Stop do not undo saved content. | Card, control, and browser lifecycle tests. |
| [AS-26](ai-assistant.md#as-26) | Source-bound Circuit accept stages only; failed save keeps draft; source save requires Spec receipt. | Circuit service and client source-save tests. |
| [AS-27](ai-assistant.md#as-27) | Completion matches requested stage; empty/continued/sent never imply saved content; functional claims need tests. | Receipt fixtures, service browser, and RTL verification suites. |
| [AS-28](ai-assistant.md#as-28) | Source checkout matches pin; build inputs are clean; setup repairs links without erasing settings. | Setup fixtures, manual pin checks, and release packaging tests. |
| [AS-29](ai-assistant.md#as-29) | Scope, pending decisions, failures, and exact diff stay visible after collapse/reload. | Source-creation client and architecture browser tests. |
| [AS-30](ai-assistant.md#as-30) | Results distinguish catalogue, fixtures, replay, live inference, lint, simulation, and unverified checks. | Evaluation fixtures and RTL test runner. |
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

Use the verified installed profile when packaging. Follow the commands in
[Harness package releases](harness-packages.md). Packaging verifies the release
manifest and installed versions. It does not inspect a Harness source checkout.
Keep application behavior in spec2gds and reusable extensions in Harness.

For a contract change, update the stable requirement, its acceptance row, and the
TEMP gap record. Validate JSON examples against native tool admission and service
schemas. Check all local Markdown paths/heading anchors and references to pruned
guides. Remove completed TEMP entries after proof. Remove the TEMP file when its
last entry is closed; keep the contract, operations guide, and future proposals.

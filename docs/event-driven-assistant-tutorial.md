# Try the goal and orchestrated presets

This tutorial uses a disposable Spec document to explore both presets, configure a template, inspect event causation, and monitor changes. Circuit conversations use the same execution controls and editor, with Circuit-specific tools and owner review/save rules. See [the event/plugin reference](event-driven-assistant-system.md) for the underlying components.

## 1. Prepare the workspace and design source

Use Node.js 22.19+ in the 22.x line or 24.2+ and the normal workspace setup, which selects the configured Harness branch:

```bash
scripts/setup-all.sh
export OPENAI_API_KEY="your-key"
bash scripts/serve-all.sh start --require-human-approval
```

Open the Spec Editor using the URL reported by the launcher (normally port 6010), and create or open a disposable V1 `.spec` document. The Assistant normally runs at `http://127.0.0.1:6013`. If you want to observe a pending review wait, start the Spec owner with its `--require-human-approval` option; automatic owner policy may apply valid proposals immediately. Keep one Assistant process per state root. Model calls use your configured provider; polling itself needs no model key.

## 2. Configure an orchestrated template

In the Assistant, choose **New conversation**, select the connected Spec service and document, and choose **Orchestrated · persistent event agents**. The **Event template** selector offers the built-in Spec template and your saved templates.

Choose **Configure event template**. The topology shows event types on the left, agents on the right, and subscription reactions between them. Expand the primary, analyst, and reviewer inspectors. Read the prompts, model route, approved tool checkboxes, and publications. The primary owns proposal preparation; specialists remain read-only.

Name your template `Spec review experiment`. Add this sentence to the analyst prompt: `Include assumptions explicitly in your findings.` Inspect the subscription from `analysis.ready` to `reviewer`. Keep the required review chain. Expand **Text definition (JSON / YAML subset)** and confirm the edited prompt appears in the text. You can paste a complete edited JSON definition and select **Apply text to visual editor** to reload its fields.

Choose **Validate and preview**. Review the before/after lines and warnings. Unsubscribed review events are expected because they can resolve waits or remain audit records. Missing agents/events, incompatible schemas, unauthorized tools/model routes, and excessive limits prevent saving. Choose **Save reviewed template**, confirm the new template is selected, then **Start conversation**. Its exact configuration revision is now pinned.

## 3. Run and inspect orchestrated work

Send a fully specified request such as:

> Propose a timer component named tutorial_timer. Explain any assumptions and show the owner proposal for review.

The primary may first acknowledge the request. The analyst receives `user.requested`, publishes `analysis.ready`, and the reviewer publishes `review.ready`. The primary can then prepare an owner proposal. Model output varies; if details are missing, answer the clarification rather than assuming a proposal must appear immediately.

Expand **Inspect configuration and execution** in the execution dock. Select the `review.ready` event under **Inspect event**. Its causal chain should identify the human input, analyst result, and reviewer result. Inspect the payload, exact matching `prepare` subscription, delivery state, activation identity, attempt and emitted result. **Native session history** opens the corresponding member's Harness transcript. **Model request charges** shows actual settled tokens/time and any outstanding reservation across all members.

Inspect the proposal card. Apply only if you want the owner change, or choose **Discard** for this experiment. Automatic Spec policy may instead show an already applied receipt. Use **Pause** and verify admission stops; **Resume** retains spending and member sessions. Send a second request to observe the same standing agent identities. Editing the saved template now affects future conversations, while this conversation keeps the pinned prompt and permissions shown in its inspector.

## 4. Try goal continuation and waiting

Start another conversation bound to the same disposable document, choose **Goal · bounded long-running work**, and optionally create a named template with a short primary prompt addition. `goal` has one primary with native goal tools and the same aggregate allowance. It has no analyst/reviewer chain.

Send:

> Prepare a timer component named goal_tutorial_timer. Keep the goal open while owner approval is pending. After the decision, summarize the outcome and complete the goal when the requested work is done.

With human approval enabled, the proposal should show an owner review card, the dock should show **waiting**, and inspection should show the native goal is blocked. Waiting uses no continuation requests. Choose **Discard** to avoid changing the document, or apply the exact proposal if desired. The matching review event resolves that proposal's wait and resumes the same eligible native goal revision. A discard can cause the model to revise its plan or ask for guidance; it does not automatically mean success. Completion is shown only when the native goal completes.

To explore a human wait, ask the primary to use its durable `wait_for_event` tool before proceeding with an ambiguous requirement. When the dock shows a human wait, choose **Answer** and provide the requested value. Its exact wait identity and observed execution revision accompany the answer. If another action changed the state, reload and answer the current wait.

## 5. Monitor an owner revision

In either preset's dock, expand **Monitor owner endpoint**. Keep the suggested bound-owner URL and JSON pointer (`/source_revision_hash` for Spec, `/revision` for Circuit). Choose **Value changes** and a check interval, such as five seconds for this experiment. Choose **Start monitoring**.

Wait for the initial observation. An unchanged revision should not add model requests. Make a small deliberate change in the bound owner editor, save it, and allow one interval plus the five-second debounce. A stable change should record `source.changed`: it wakes the analyst/reviewer chain in `orchestrated` or the primary in `goal`, using the remaining conversation budget. Inspect the observation payload and resulting deliveries. Monitoring never approves a proposal or bypasses owner review.

Choose **Disable monitor** when finished. Re-enabling preserves its cursor. Repeated network/JSON errors are visible and eventually disable the source; correct the owner and enable it again. A foreign URL, redirect, oversized response or invalid pointer is rejected or reported. Pause suspends checks; Stop terminates execution and cancels waits. After a process restart, use **Resume** before expecting sources or agents to run.

## 6. Run the three browser tests without model keys

After the source setup and product build, install browser-only test tools in a separate directory so the unpublished runtime package dependencies do not require an npm registry release:

```bash
cd ai-assistant
npm run build
npm install --prefix .ui-test-tools --no-audit --no-fund @playwright/test@1.61.1 react@18.3.1 react-dom@18.3.1
PLAYWRIGHT_BROWSERS_PATH="$PWD/.ui-test-tools/browsers" .ui-test-tools/node_modules/.bin/playwright install chromium
ASSISTANT_UI_TEST_DEPS="$PWD/.ui-test-tools" PLAYWRIGHT_BROWSERS_PATH="$PWD/.ui-test-tools/browsers" npm run test:ui
```

The three Chromium tests cover orchestrated configuration/causal routing, goal review waiting and HTTP controls, and both presets' permission rejection and configuration pinning. They render the shipped product browser plugin with real React and drive native Loader/event/goal services through product HTTP routes. A minimal test shell provides Harness session/workspace/slot adapters; the model and external owner are deterministic test doubles. These are product UI integration tests, not an end-to-end test of every native Harness shell panel or a live model provider.

Set `ASSISTANT_UI_SCREENSHOT_DIR` to an absolute directory to save final browser
states from the same tests, for example:

```bash
ASSISTANT_UI_SCREENSHOT_DIR="$PWD/../docs/images/event-presets-ui" \
ASSISTANT_UI_TEST_DEPS="$PWD/.ui-test-tools" \
PLAYWRIGHT_BROWSERS_PATH="$PWD/.ui-test-tools/browsers" npm run test:ui
```

The captures show the product UI inside its test shell. They do not depict every
native Harness shell panel. Screenshot capture is optional and does not replace
the tests' state/behavior assertions.

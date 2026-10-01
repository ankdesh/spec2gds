# Event driven assistant — Phase 1

This guide records the Phase 1 baseline. [Phase 2](event-driven-assistant-phase2.md) supersedes its trigger, retry, and review-wait behavior. Both `goal` and `orchestrated` use host-owned execution limits. `focused` keeps its existing request behavior. Workflow authoring, external triggers, automatic retry, and general durable waiting remain deferred.

## Use the presets

Run `scripts/setup-all.sh`, start the owners and Assistant with `bash scripts/serve-all.sh start`, then open the Assistant at `http://127.0.0.1:6013`. Create a bound Spec or Circuit conversation and select its preset. A conversation's preset and owner binding remain fixed.

- **orchestrated:** your request wakes the persistent analyst. Its typed `analysis.ready` result wakes the persistent reviewer; `review.ready` returns to the primary, which prepares the owner proposal. Only the primary receives proposal tools. Later requests reuse the same specialist sessions.
- **goal:** the primary uses native goal tools and continuation. Every model request and native turn consumes its conversation's allowance. A proposal requiring owner review pauses the goal and new admissions. Resolve the review card, then press **Resume** to continue. Applying or sending a proposal does not automatically complete a goal.
- **focused:** the existing context/proposal exchange, owner review, and three-step limit remain available.

The execution dock shows status, members, rounds, requests, tokens, settled active model time, pending work, recent events, and failures. **Pause** cancels active work and prevents admission. **Resume** preserves spending. **Stop** is terminal. Failed/interrupted deliveries offer **Acknowledge uncertainty and retry** while active; the dialog explains that prior results may already exist. A retry receives new message and activation identities and retains the old attempt.

## Limits and authority

| Preset | Rounds / requests | Tokens / aggregate active model time | Members / concurrent dispatch |
| --- | --- | --- | --- |
| goal | 8 / 32 | 300,000 / 30 minutes | 1 / 1 |
| orchestrated | 8 / 48 | 500,000 / 45 minutes | up to 7 / 3; supplied roster has 3 members |

The product also validates hard ceilings and explicit queue, event-history, payload-byte, causal-depth, and output bounds in `ai-assistant/profile/cordis.patch.yml`. Output defaults to 1,200 tokens, including configured native compaction. Token reservations use conservative serialized request bytes/native estimation and output capacity; reported disjoint usage settles them. Missing usage retains the reservation. New requests, events, retry, pause/resume, and restart do not refresh budgets. Exhaustion requires a new conversation; this phase provides no budget top-up.

Models can publish only declared event types and cannot edit the roster, subscriptions, limits, or owner binding. Event payloads use the native supported JSON Schema subset. The executor enforces member tool allowlists independently of prompts. Specialist domain compositions expose only context reads. The primary's proposal guard requires reviewer causation for the latest user request in `orchestrated`.

Spec automatic/restricted approval and Circuit approval/save behavior remain owner-controlled. An event is not permission to mutate an owner. Review actions recheck execution state; explicit pause/stop/exhaustion prevents apply/send. The specific goal hold for pending owner review allows the human review action without allowing model continuation.

## Configuration and persistence

Reusable services live in the sibling Harness fork as `dsh-event-system` and `dsh-event-system-yaml`; spec2gds supplies its adapter and trusted catalog. The product examples live in `ai-assistant/profile/catalog/event-systems/`: four exact templates plus Markdown prompts. The generic analyst/reviewer example lives in the Harness package's `examples/analysis-review/` folder and imports no product code.

The YAML loader rejects executable tags, directives, aliases, anchors, merge keys, unknown fields, missing references, unsafe prompt paths, and configured byte-limit violations. Startup validates and seals the catalog. Conversation creation pins resolved prompt text, definitions, model routes, and their digest. Unspecified member models inherit the primary's selected provider/model at creation. Editing a template affects new conversations.

The native SQLite-backed storage domain `event_systems` stores one snapshot per primary Session ID in `harness-dsh-ui/event-systems.sqlite3`, including events, deliveries, retry history, members, spending, and configuration. Native JSONL transcripts record every delivered plugin message and model/tool exchange. The product's `assistant.sqlite3` stores immutable bindings and owner review metadata. Back up the entire Assistant state root; run one process against it.

On restart, formerly active systems become **needs resume**, and dispatches whose outcome is uncertain become **interrupted**. No model runs automatically. Human Resume restarts eligible pending work with the remaining allowance; interrupted work needs a separate acknowledged retry. Native logs, the ledger, and owner persistence are separate, so the system does not claim exactly-once side effects.

Existing goal/orchestrated conversations without an event-system record remain readable history and refuse new model work. Start a new bound conversation for the updated preset. Existing focused chats continue normally. Historical workflow decoding stays available for old transcripts; the updated presets do not start workflows. No conversations are deleted.

## Verify

From `ai-assistant/`:

```bash
npm run typecheck
npm test
npm run build
npm run test:harness
```

`test:harness` includes the real headless focused profile with keyless replay and native Loader/owner compositions for both updated presets. From the Harness root:

```bash
pnpm exec vitest run packages/workflow/event-system/tests packages/workflow/event-system-yaml/tests
```

Those regressions cover routing, reused identities, native goal continuation, restart spending, human controls, uncertain retry history, overlapping active request cancellation, invalid payload/causal references, integrity validation, and strict YAML/Markdown loading. The fixtures script provider responses and use real native execution and persistence. Live-provider quality evaluation and graphical authoring are separate work.

## Verification result — 2026-09-30

The local source checkouts pass product typechecking, the server/client build, all 89 product unit tests, and all three native integration cases (goal, orchestrated, and focused with keyless replay). Harness Host typechecking passes with its configured 4 GB heap. The focused Harness run passes 126 tests, including 36 event-service/provider tests and 90 shared system-prompt tests. Both new packages pass focused lint; their bilingual documentation pairs, model-experience sections, and limitations sections pass their respective gates. A fresh temporary source-link fixture resolves both new packages, Node types, and executable TypeScript/tsx tools. Shell and JavaScript setup syntax checks pass.

The full Harness documentation run is not green. It reports existing prompt/workflow catalog JSDoc and type-analysis issues, older Agent Note wrapping and package summary issues, and a scoped-events generator heap failure. Focused reruns confirm the new package documentation passes. The repository dependency check also reports the existing ui-sidebar development dependency omission. These broader failures are recorded rather than waived; live-provider quality evaluation and browser interaction testing have not been performed.

The development changes span this product and the sibling Harness checkout. Release packaging requires committing that fork, advancing `ai-assistant/harness.lock.json`, and publishing the reviewed fork revision; the source checkout remains usable for local development. The existing npm lockfile describes the older published package baseline; regenerate it after the fork packages are released. Use the source setup/linking path for this implementation, rather than `npm ci`.

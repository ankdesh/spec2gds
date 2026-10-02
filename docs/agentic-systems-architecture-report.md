# Agent execution design rationale

The implemented Assistant uses event-driven standing agents for `orchestrated`
and the native single-agent goal driver for `goal`. The original fixed-workflow
proposal was design input; it is not the current runtime or an accepted loader
format. See [the current event reference](event-driven-assistant-system.md)
and [the tutorial](event-driven-assistant-tutorial.md) for supported behavior.

## Why events and native goals

A preset selects trusted capabilities; it is not a queue or scheduler. Native
Harness sessions supply history, tools, cancellation and model execution.
The reusable Harness event packages add typed publications, exact subscriptions,
durable deliveries, waits, retries and aggregate accounting. Product adapters
retain the Spec/Circuit binding and owner validation boundary.

A standing member keeps its session between activations. Inbox acceptance and
successful completion are separate ledger states. A retry has its own attempt
identity and never silently erases an uncertain outcome. Idle agents and
unchanged HTTP polls use no model requests. Restart restores state but requires
human Resume before execution.

The orchestrated analyst/reviewer chain is a reaction topology. An edge means
“deliver this event to this agent”; it does not enforce arbitrary dependencies,
joins or stage mappings. The proposal guard additionally requires review
causally descended from the latest request or approved source observation.
Native goal continuation is governed by its own driver, including correlated
waiting, rather than routing every round through event subscriptions.

## Boundaries to preserve

- Configuration is human-owned and pinned per conversation. Prompts cannot
  grant tools, change the roster or refill spending.
- Events, deliveries, activations and owner receipts have separate identities.
  Model publication cannot approve an owner mutation.
- Generic execution belongs in Harness; owner semantics and review UI belong
  in the product. Experimental Agent Teams and community plugin designs are
  references, not dependencies of the delivered event service.
- The ledger, native transcripts, product SQLite and owner persistence are
  separate stores. Recovery does not promise exactly-once external side effects.
- Model requests, native continuation, compaction and retries share the same
  conversation allowance. Pause, retry and restart preserve spent resources.

## Future workflow policy

Workflow authoring and execution remain outside the implemented scope. A later
policy can reuse the event/activation contracts, but needs explicit host-owned
stage dependencies, typed input/output mappings, tool-only stages, committed
stage results and restart recovery. A model checklist or the historical
`sWorkflow` lifecycle service does not provide these guarantees.

Before adding that policy, define stage context isolation, conditions/joins,
cycle handling, human gates, cancellation, per-attempt identities and budgets.
Acceptance must include tool → LLM → LLM → tool ordering; refusal to skip or
repeat committed stages; invalid-output rejection before downstream dispatch;
crashes before/after inbox receipt and completion; and owner-mutation
reconciliation. Distributed dispatch, cross-conversation routing, model-created
rosters, webhooks and file watchers require separate design decisions.

## Code reading order

1. `ai-assistant/harness.lock.json` identifies the supported native source pin.
2. `ai-assistant/profile/cordis.patch.yml` registers native services and limits.
3. `ai-assistant/profile/catalog/event-systems/` supplies trusted definitions.
4. `ai-assistant/src/event-configuration.ts` validates human template changes.
5. `ai-assistant/src/execution-policy.ts` guards limits and proposal causation.
6. `ai-assistant/src/index.ts` connects bindings, native agents and owner reviews.
7. `ai-assistant/tests/event-runtime.integration.test.mjs` and
   `event-presets.ui.test.mjs` exercise the delivered presets.

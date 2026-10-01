# Event driven assistant: three-phase implementation plan

Status: Phases 1–3 are implemented in the local source checkouts; native package publication remains separate. Phase 3 configuration and inspection run in the product adapter over the existing native runtime.

Implementation details and operational behavior are captured in
[the Phase 1 guide](event-driven-assistant-phase1.md), [the Phase 2 guide](event-driven-assistant-phase2.md), and [the current event/plugin reference](event-driven-assistant-system.md). [The tutorial](event-driven-assistant-tutorial.md) covers both presets and the three Chromium UI tests.

Date: 2026-09-30.

## Scope and provenance

Replace the current orchestration behavior with event driven agents while
retaining the `orchestrated` preset name. Reconsider `goal` separately, using
the same resource and persistence foundations where appropriate. Keep
`focused` available throughout the change.

Workflow authoring and execution are outside all three phases. The runtime
should expose stable event, delivery, and activation contracts so a workflow
policy can be added later. Do not build a graph scheduler, joins, stage
mappings, or workflow designer for this project.

The referenced “Agent orchestration patterns” conversation and the attached
DSH plugin analysis report are design input. Their recommendations and
conceptual snippets are not implementation instructions or verified APIs.
Any reused plugin code must be checked against the pinned Harness version,
its actual behavior, and its license before adoption.

The current implementation is described in
[Configurable Assistant Architecture](configurable-assistant-architecture.md).
This plan changes the scope recommended by the older
[agentic systems architecture report](agentic-systems-architecture-report.md);
its detailed phase checklists record the agreed delivery scope. The linked implementation guides describe current behavior.

## Delivery split

| Phase | Usable result | Deliberately deferred |
| --- | --- | --- |
| 1. Conversation agents and goals | `orchestrated` uses persistent event agents; `goal` retains native continuation with shared bounds and controls. | External monitors, automatic recovery, durable goal waiting, and broad configuration UI. |
| 2. Triggers, waiting, and recovery | Approved external events can wake agents; both presets support durable waiting and controlled recovery. | Graphical authoring and advanced trace navigation. |
| 3. Visual configuration and inspection | Humans configure agents/subscriptions visually and inspect why an activation ran. | Workflow setup and execution. |

Each phase is independently reviewable and must meet its exit criteria before
the next phase begins. Phase 1 establishes only the contracts that its first
working example needs; later phases extend them after experience with that
example.

## Common rules

These rules describe the delivered configuration and execution policy.

- Put generic execution services in the Harness fork. Let spec2gds supply
  owner context, domain events, and review integration through an adapter.
- Keep agent identity, memory, and routing local to one conversation. Agents
  retain their native DSH sessions between activations and do no model work
  while idle.
- Humans choose the roster, prompts, subscriptions, and capabilities. An
  agent may publish approved events; it cannot grant itself tools, add agents,
  alter subscriptions, or increase its budget.
- Use YAML for configuration and Markdown for prompts. Validate references
  and pin the resolved configuration when the conversation is created.
- Persist an event before scheduling its deliveries. Give events, deliveries,
  and activations distinct IDs, with correlation and causation references.
  Recording delivery acceptance must not imply successful task completion.
- Enforce aggregate host-owned budgets across participating agents, model
  requests, retries, and continuation. Pause, resume, a new event, and a
  process restart must not silently restore spent resources.
- Preserve immutable owner bindings and the owner's approval policy. Event
  publication is not permission to apply a proposal or save a document.
- Recover saved state after a restart, but require human Resume before
  further model execution. Never blindly replay an uncertain mutation.

## Phase 1 — Conversation agents and goals

### Objective

Deliver the smallest useful replacement for one-shot delegation: a human
request wakes a persistent agent, that agent publishes a typed result, and a
second persistent agent reacts to it in the same bound conversation.
Update `goal` in this same phase: preserve its single-agent native goal loop
while giving it the shared resource controls and removing its dependency on
workflow lifecycle/checkpoint tools.

### Implementation

1. **Define the minimum contracts.** Specify agent identity, a typed event
   envelope, subscription matching, durable delivery states, activation
   outcomes, and human controls. Keep host lifecycle events distinct from
   model-published domain events. Payload validation must reject invalid
   input before routing.
2. **Build the runtime using native DSH execution.** Reuse native sessions,
   inbox admission, cancellation, storage, tool enforcement, and context
   compaction where suitable. Add the missing delivery ledger and dispatcher;
   do not replace the model execution loop. Start with exact event type
   matching and fixed subscriptions.
3. **Add a small trusted text configuration.** Provide one generic
   analyst/reviewer example and one spec2gds example. Agent definitions name
   prompts and trusted capability compositions. Treat missing references as
   startup errors. A general template library is deferred.
4. **Bound execution from the first release.** Enforce existing preset limits
   through observed host activity rather than model-reported checkpoints.
   Cap active agents, queue size, payload size, and event chains. Serialize
   activations for each agent. Exhausting a budget pauses admission with a
   visible reason.
5. **Integrate `orchestrated`.** Replace `delegate_workflow_step` and its
   one-shot child assumptions with event delivery to standing members.
   Support direct user requests, approved agent publications, activation
   outcomes, and application review decisions. Restrict domain proposals to
   the designated proposal-owning agent.
6. **Simplify `goal`.** Keep the native goal driver and goal tools. Replace
   workflow-based progress/budget coupling with host-owned accounting,
   native goal status, and pause/resume/stop. Do not make every continuation
   go through the new multi-agent dispatcher. Retain the owner's proposal
   and approval boundary when determining whether work is complete.
7. **Provide basic controls in the existing UI.** Show members, active/pending
   work, budget use, failures, and pause/resume/stop. A compact event list is
   sufficient. Durable state survives restart; interrupted work is clearly
   marked and requires an explicit decision to retry.
8. **Cut over and document.** Decide how old conversations are handled before
   removing their runtime support. Update setup, configuration, and usage
   instructions for both updated presets.

### Keep this phase small

No file monitors, webhooks, HTTP polling, timers, automatic retry scheduler,
cross-conversation routing, visual editor, or durable goal waiting. Core
persistence, budget enforcement, cancellation, and restart visibility belong
in this phase because an event driven replacement is incomplete without them.

### Exit criteria

- A generic analyst/reviewer example runs without importing spec2gds code.
- In spec2gds, a request causes analysis, a typed result, review, and a
  proposal through the existing owner boundary.
- A later request reuses the same agent identities and sessions.
- An invalid payload, unauthorized publication, or cross-conversation target
  is rejected without executing an agent.
- Duplicate delivery admission does not repeat an already recorded receipt;
  uncertain interrupted execution is exposed for human handling.
- Pause/stop prevents new admissions and cancels owned active work. Restart
  preserves pending work and spent budget and does not run models unaided.
- `goal` uses native bounded continuation without workflow checkpoint tools;
  its pause/resume/stop and completion status remain consistent with owner
  review decisions.
- Native Harness integration tests and product regression tests cover both
  updated presets, `focused`, binding isolation, and owner review.

## Phase 2 — External triggers, waiting, and recovery

### Objective

Make both presets useful for work that spans user turns and external changes,
building on the native goal loop and bounded event agents shipped in Phase 1.

### Implementation

1. **Choose the first external source.** Add only the trigger needed by the
   first real use case. Candidate sources are file changes, supported native
   timers, webhooks, and HTTP conditions. Use an adapter contract so other
   sources can follow without changing agent execution.
2. **Harden trigger ingestion.** Persist trigger definitions and cursors;
   validate and authenticate incoming data as appropriate. Specify debounce,
   event identity, duplicate handling, and behavior while paused or offline.
   Read-only monitoring must not continuously invoke a model.
3. **Add controlled recovery and retries.** Distinguish pending work,
   acknowledged input, completed activation, and uncertain side effects.
   Add bounded backoff for explicitly replay-safe work, attempt limits, and
   human handling for failed or uncertain deliveries. Resume uses the same
   budget allocation unless a human explicitly authorizes more.
4. **Define durable waiting.** Represent waiting for a human answer,
   review decision, or approved event without burning model turns. Correlate
   the response with the waiting goal or agent activation and reject stale
   or unrelated wakeups.
   Make completion, blocking, pause, and stop visible and distinct.
5. **Expand trusted configuration only where needed.** Add per-agent model,
   tool, skill, and MCP choices through native trusted compositions. Provide
   reusable templates and explicit selection if that is the agreed UX.
   Changes apply to new conversations unless a separate migration is chosen.

### Exit criteria

- The chosen external trigger wakes only its configured conversation and
  agent; unchanged monitored state incurs no model requests.
- Duplicate, burst, stale, and invalid inputs are bounded and observable.
- Restart recovery and retry tests cover safe replay and uncertain effects.
- A native goal can continue, wait, resume, finish, or exhaust its budget
  without depending on an executable workflow.
- All model work, including continuation and retry requests, is charged to
  the appropriate human-authorized budget.
- Existing focused behavior and owner mutation policies remain covered by
  regression tests.

## Phase 3 — Visual configuration and causal inspection

### Objective

Make the running event system understandable and configurable without
requiring humans to edit every YAML field manually.

### Implementation

1. **Build an event topology editor.** Display agents, event types,
   subscriptions, and external sources. Edit their existing text definition;
   do not create a separate canvas-only configuration. A subscription edge
   represents a reaction, not a workflow dependency or join.
2. **Add inspectors and preflight validation.** Show prompts, model settings,
   approved capabilities, payload contracts, filters, and limits. Detect
   missing references, incompatible payloads, unused events, and potentially
   unbounded reaction cycles. Some cycles are valid; limits remain mandatory.
3. **Add causal execution inspection.** Follow event → matching subscription
   → delivery → activation → emitted result. Show why an agent ran, the
   triggering payload, retries, failures, budget charges, and related native
   session history.
4. **Support human-reviewed configuration changes.** Preview text diffs and
   validation results before saving. Make the pinned configuration of an
   existing conversation visible. Start new conversations from changed
   definitions rather than silently rewriting running systems.
5. **Complete the operational UX.** Add template selection, failure handling,
   accessible controls, and documentation illustrated with working examples.

### Exit criteria

- A human can create or edit a valid event setup visually and obtain a stable
  text representation that reloads with the same meaning.
- Text and visual edits round-trip without changing prompts, subscriptions,
  permissions, or configuration identity unexpectedly.
- A human can answer “why did this agent run?” and “where did the budget go?”
  from the UI.
- UI actions retain the same host validation, authority, and review checks as
  the text/API path.

## Decision record

1. **Phase allocation — confirmed:** update both `orchestrated` and `goal` in
   Phase 1. External sources, durable waiting, and advanced recovery remain
   in Phase 2; visual tooling remains in Phase 3.
2. **Package ownership:** reusable Harness packages with a spec2gds adapter,
   or a product-local prototype first?
3. **First scenario:** generic analysis/review, Spec refinement, or Circuit
   refinement? Which concrete request demonstrates success?
4. **Trigger priority — confirmed:** HTTP condition polling is the first Phase 2 source.
5. **Configuration authority:** confirm human-only roster/subscription edits
   and conversation-pinned definitions, or identify a required exception.
6. **Budget scope:** confirm aggregate spending per human authorization,
   rather than fresh allowances on each event. Are current limits suitable?
7. **Restart policy:** confirm explicit Resume before model execution, or
   define a narrower class of work allowed to resume automatically.
8. **Conversation cutover:** retain old chats as readable history, migrate
   compatible chats, or explicitly remove only old goal/orchestrated chats?
   No deletion is authorized by this plan.
9. **Owner approval:** retain the existing Spec automatic/restricted policy
   and Circuit review/save policy, or require human approval for every change
   produced by these two presets?

The implementation guides record the chosen policies and verified APIs. Generic execution, HTTP ingestion, and waiting live in the Harness fork; owner integration and human configuration/inspection live in the product adapter. Conversation-pinned definitions, aggregate budgets, explicit restart Resume, preserved history, and existing owner approval rules apply throughout.

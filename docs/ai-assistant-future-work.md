# AI Assistant future work

Status: proposals only. These items are not accepted product requirements.

The [system contract](ai-assistant.md) defines required behavior. Required code
changes belong in [TEMP implementation gaps](TEMP-ai-assistant-implementation-gaps.md).
This list preserves useful open ideas from the old roadmap without repeating
accepted rules or completed work. Stable old IDs remain where useful.

Do not implement an item merely because it is listed here. Before accepting it,
define the problem, intended behavior, evidence, cost, interfaces, and tests.
Record the decision in the system contract and its acceptance matrix. Then move
any code difference into TEMP. An idea that changes a contract rule needs explicit
product approval. The rule remains in force until that change is accepted.

## First priority: UI-02 — New chat opens unbound

Priority: highest in this future-work list. Requested on 2026-10-05.

Remove the automatic connection card from **New chat**. Open an unbound chat
immediately. Do not infer a target from the current editor, Workspace, or previous
chat. A user can discuss hardware or request a new specification document there.

Show the connection or target selector only after an explicit **Connect service**
or **Select existing document** action. This supports another server or an existing
document that Assistant does not yet know. Selecting a document opens a separate
chat bound to its exact owner, document, and scope. Keep the original chat intact.
Known targets can also open bound chats directly through their editor actions.

Request creation of a document that does not exist through chat. Keep architecture
approval for design content and the exception for explicitly empty documents.
Keep execution-preset selection available without requiring the connection card.
The selected preset remains pinned to its chat.

Acceptance cases:

- **New chat** opens unbound without connection, target, or empty-creation forms.
  Check both global and Workspace entry points, including when a document is open.
- Explicit editor launches still open the exact document, entity, or Circuit chat.
- Explicit connection/selection works with multiple owners, duplicate document
  names, unknown documents, and offline services. No target is chosen silently.
- New-document requests retain architecture approval, separate destination chats,
  exact creation receipts, and the automatic/restricted content-save policies.
- Existing chats keep their bindings and pending work. Preset selection remains
  explicit and does not silently change an existing chat.

The current [new-session handler](../ai-assistant/client/index.js) opens the binding
dialog for New chat. This item proposes a change to that default. Update
[AS-03](ai-assistant.md#as-03), related workflows, and their acceptance rows when
this change enters the system contract. This future-work entry does not change
runtime behavior.

## Product and interaction proposals

| ID | Proposal | Decision or evidence needed |
| --- | --- | --- |
| AA-04 / PA-04 | A catalog of domain defaults and blocking ambiguity classes. | Define scope/preconditions, counterexamples, source, and visible assumptions. The accepted basic default/question policy already applies. No universal reset or width default. |
| AA-05 | Suggest a focused, goal, or orchestrated preset from measured request complexity. | Show a recurring focused failure class and a benefit from another preset. Define visibility/override and budget effects. Do not silently change an existing chat's preset. |
| AA-06 | Route to additional domain specialists. | Measure quality/latency/cost after an accepted routing policy. Keep specialists read-only and primary proposal ownership. Existing analyst/reviewer agents are already supported. |
| AA-07 | An optional planning checkpoint for complex work. | Show a need for a decision beyond the mandatory architecture review. It must not replace architecture or Editor content approval. |
| UX-02 | A richer entity-grouped hierarchical diff. | Define owner/client responsibility and a normalized diff model. Prove that displayed changes match the stored artifact and revision. Existing semantic before/after details remain supported. |
| UX-03 | Richer display of defaulted and normalized fields. | Keep original/admitted values and traceable reasons. Basic assumption/error visibility is already required; this proposal concerns richer presentation. |
| UX-04 | Per-change selection during content review. | Rebuild and owner-validate a new atomic proposal after selections. Never apply a client-filtered subset of an approved artifact. |
| CS-04 | Broader cross-entity work from a narrow chat. | Define a new explicit workflow and authority checks. The current permanent binding cannot widen. Existing other-target requests must explain and stop. |

## Prompt, tool, and context proposals

| ID | Proposal | Decision or evidence needed |
| --- | --- | --- |
| PA-03 | A small measured few-shot example set. | Identify the failure each example addresses, inline/on-demand placement, token cost, and regression effect. Do not add benchmark-specific canned RTL. |
| PA-05 | Load stable domain knowledge through Harness skills. | Verify real discovery/loading/packaging and exact versions. Show a token or maintenance benefit. General skill tools are outside the current capability boundary. |
| TD-03 | Contextual tool masking. | Measure tool-order errors that schemas/guards cannot resolve. Verify native per-message masking. It must not replace host/owner checks. |
| TD-04 | Specialist or finer-grained operation tools. | Show that atomic batch schemas and measured prompt changes are insufficient. Preserve atomic preview, identity, and the owner save policy. |
| TD-05 | A common tool-module structure and extension procedure. | Define registration, schemas, handlers, capability checks, and tests. Keep static tool instructions in one versioned catalogue. Document how to add a tool or owner adapter. Preserve owner-published operation schemas, atomic proposals, exact identities, revision checks, and approval rules. This is a structure refactor; it does not grant new capabilities. |
| CS-03 | Three-tier context: target, connected peers, global environment. | Define owner schema, connectivity, scope, versioning, and missing-data behavior. Measure current pagination before claiming size reduction. This differs from supported lossless semantic pages. |
| CS-05 | A revision-keyed advisory context cache. | Demonstrate material read cost. Fresh authoritative reads at authoring/save boundaries remain required. |
| VE-03 | Expand deterministic admission beyond the current formatting rules. | Prove preservation of meaning and identity; show original/admitted values. Reset polarity and width adaptation are not trivial fixes. Validation failure still stops the request. |

Automatic model repair of validation failures is no longer an open default: the
accepted policy stops after the first failure. Old VE-04 owner-retry questions are
resolved by that rule. Any proposal to change it needs a new explicit decision.
Read-only transport retries and exact receipt recovery remain separate.

## Evaluation and resilience proposals

| ID | Proposal | Decision or evidence needed |
| --- | --- | --- |
| TQ-04 | Quantitative release quality thresholds. | Establish baseline, representative sample, model/version matrix, confidence, and regression policy. Old validity/DRC/efficiency targets are hypotheses. |
| TQ-05 | A headless conversation simulator with simulated users. | Define independent evaluator, clarification policy, stopping, cost, and final owner-state checks. It supplements fixed assertions. |
| TQ-06 | A broad chaos/recovery suite. | Define injection seams and expected outcomes for transport, persistence, owner, and human-wait faults. Required known regressions remain in TEMP. |
| TQ-07 | Automatic prompt optimization. | Accept quality gates and an overfitting-resistant corpus first. Human-review exact prompt versions before deployment. |
| TQ-08 | Shadow prompt execution. | Approve privacy, cost, cancellation, retention, and no-mutation boundaries. Show why offline replay is insufficient. |
| TQ-09 | Adopt a third-party prompt test framework. | Compare maintenance benefit after native evaluation contracts are stable. `promptfoo` and `DeepEval` are candidates, not selected dependencies. |

## Owner, runtime, and release proposals

| ID | Proposal | Decision or evidence needed |
| --- | --- | --- |
| ISSUE-CD-02 | Source preview during Assistant Circuit preview. | Define honest Circuit/Spec validation scopes and a read-only source preflight. Preserve independent Circuit behavior and explicit Save to Specification. Test Circuit-valid/source-invalid candidates with unchanged package bytes. |
| ISSUE-CD-03 | Durable downstream Circuit decision/status tracking. | Distinguish sent, accepted draft, rejected, and saved source. Define identities, event/poll policy, and restart recovery. Do not complete a saved-source request from a send receipt. |
| RT-01 | Executable workflow stages on top of events. | Define host-owned dependencies, typed mappings, tool-only stages, committed results, conditions/joins, cycles, cancellation, and recovery. Event reactions do not provide a graph scheduler. |
| RT-02 | Webhooks, file watchers, distributed or cross-chat dispatch. | Separate authority, transport, lifetime, budget, and recovery design. Current monitoring is owner-bound HTTP polling. |
| RT-03 | Pin-enforcing setup and registry distribution. | Validate checkout origin/cleanliness/pin before bootstrap mutation. Provide an explicit pin-update path. Published native packages and lockfile regeneration are separate release work. |
| OW-01 | Verification Planner as an Assistant owner. | Define binding, context/schema, preview, approval, and receipt adapters before adding it to the chooser. See [Planner backlog](verification-planner-backlog.md). |
| UI-01 | Broader full-Harness-shell acceptance and renderer reuse. | Separate event-preset adapter-shell tests from full product-shell controls. Measure value of the production Circuit renderer or owner-native attachments before adding them. |

Parameterized RTL and unsupported slice/bus generation need separate generator
requirements. They are not enabled by prompt changes. Keep Activity details in the
[RTL generator guide](rtl-generation-activity.md), rather than another Assistant plan.

## Research and decisions

The preserved [Spec-to-RTL research guide](research/ai-spec-to-rtl-design-research-guide.md)
is provenance. Verify claims and dependencies before adopting them. Historical
benchmark gains and quality targets are not release requirements. Keep raw
[evidence](evidence) and Git history; do not retain duplicate release diaries.

For an accepted idea, record its requirement IDs, scope, interfaces, acceptance
cases, and evidence. For an abandoned idea, remove it from this list. Do not keep
completed work as an open roadmap item.

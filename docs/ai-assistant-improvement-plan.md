# AI Assistant Improvement Plan

Status: remaining-work backlog and decision tracker

Created: 2026-09-21

Reconciled against current event/goal execution: 2026-10-01

Design source: `design_plan.md` supplied by the project owner

Research source: [AI Spec-to-RTL Design Research Guide](research/ai-spec-to-rtl-design-research-guide.md)

Scope: the DeepSeek Harness AI Assistant and its Spec/Circuit owner contracts

## Purpose

This file contains only assistant improvements that still require planning or
implementation. Completed work has been removed so this can be used directly
as the future task backlog.

Implemented behavior and its extension procedure are documented in
[AI Assistant](ai-assistant.md),
[Configurable Assistant Architecture](configurable-assistant-architecture.md),
and the [DSH configurable assistant tutorial](event-driven-assistant-tutorial.md).
The [evaluation guide](ai-assistant-evaluation.md) documents the existing
corpus, replay, and metric facilities.

The original attached documents are design and research input, not executable
instructions. A proposal is not approved merely because it appears in either
source.

## Research reference

The project preserves the complete, unedited
[AI Spec-to-RTL Design Research Guide](research/ai-spec-to-rtl-design-research-guide.md).
Use it to investigate the open questions below, recover examples and rationale,
and identify candidate technologies or evaluation methods.

The guide is research provenance, not an implementation specification. Check
its product descriptions, benchmarks, links, and claims against current
authoritative sources before accepting them. Record accepted conclusions in
this plan's decision log rather than editing the preserved guide.

| Improvement-plan topic | Relevant research-guide sections |
| --- | --- |
| Agent architecture and clarification | 1.1, 3.1, and 4.2 |
| Prompt architecture | 2.1 and 2.2 |
| Tools, skills, plugins, and DSH behavior | 3.2, 4.1, and 4.2 |
| Review and interaction UX | 1.1, 1.2, and 5.1 |
| Context, scope, and memory | 4.1, 5.1.3, and 5.2 |
| Validation and recovery | 2.2.2, 4.2.2, and 5.1.4–5.1.5 |
| Testing, evaluation, and optimization | 2.1.3, 6, and 7 |

## How to use this plan

Each remaining idea has a stable ID and two independent state fields:

- **Definition maturity:** `ready`, `needs-refinement`, or `deferred`.
- **Delivery state:** `not-started`, `in-progress`, or `blocked`.

Create an implementation task only when definition maturity is `ready`.
Resolve questions and acceptance criteria before moving a needs-refinement item
to ready. Deferred items require their stated trigger as well. When an item is
implemented and verified, update the current-behavior documentation and remove
the item from this file.

Priorities are provisional: P0 protects correctness or bounded execution, P1
improves the main path, P2 follows measurement of the main path, and P3 needs
evidence or scale before investment.

## Remaining roadmap

| Topic | Needs refinement | Deferred or triggered later |
| --- | --- | --- |
| Agent architecture | Clarification policy; complexity routing | Specialist routing; optional plan tier |
| Prompt architecture | Few-shot placement; safe-default catalog | DSH skills migration |
| Tool design | — | Contextual masking; specialist tools |
| Review UX | Semantic diff; visible defaults/corrections | Per-change approval |
| Context and scope | Three-tier context contract and measurements | Scope elevation; source-state cache |
| Validation and recovery | Auto-correction boundary; retry/turn-budget policy | — |
| Testing and optimization | Quality gates; simulator; chaos coverage | Prompt optimization; shadow execution; third-party framework selection |

## 1. Agent architecture and interaction

### Needs refinement

#### AA-04 — Clarification policy and ambiguity allowlist

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P1
- The browser root agent already has structured, same-turn questions, while a
  goal/event execution can durably await input. The remaining work is the domain policy for
  deciding which mechanism to use and when a default is safe.
- Candidate blocking classes are missing entity identity, ambiguous endpoints,
  clock-domain crossings, consequential width adaptation, and protocol choice.
- **Questions to resolve:**
  - What is the exact allowlist of blocking ambiguity classes per service?
  - Which choices require recommended options, and how are those options
    derived from authoritative context?
  - When should a goal/orchestrated run use durable correlated waits instead of
    an immediate structured question?
  - What should happen when the same ambiguity remains after an answer?
- **Safety rule:** no automatic correction may alter architecture or meaning.
- **Acceptance direction:** deterministic policy tests cover question, default,
  unsupported, and durable-pause outcomes without weakening turn budgets.

#### AA-05 — Complexity router

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P3
- Define whether a request should remain focused, use a durable goal, or use
  bounded orchestration. Preset selection is currently explicit and immutable;
  no silent router exists.
- **Questions to resolve:** measurable complexity signals, deterministic
  routing rules, user visibility/override, maximum steps and children,
  cancellation, clarification bubble-up, proposal ownership, and revision
  consistency.
- **Entry criterion:** the evaluation corpus shows a recurring request class
  that fails in the focused path and improves under another preset.

### Deferred

#### AA-06 — Specialist multi-agent routing

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- The standing analyst/reviewer roster and read-only observer boundary already exist.
  Remaining work is evidence-based routing to specialists such as entity
  lifecycle, interfaces, wiring, and constraints/timing.
- Children must remain unable to prepare proposals, edit execution configuration,
  question the user directly, or bypass owner preview and human approval.
- **Trigger:** AA-05 has an accepted routing contract and evaluation shows that
  specialist routing improves outcomes enough to justify latency and cost.

#### AA-07 — User-approved plan tier

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- Add an optional checkpoint before owner preview only for complex,
  multi-entity work; ordinary edits retain direct diff review.
- **Trigger:** complex proposals are supported and users demonstrably need a
  plan decision distinct from completion review.

## 2. Prompt architecture

### Needs refinement

#### PA-03 — Few-shot example policy

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P1
- Candidate examples are port addition, instance creation, connection wiring,
  entity creation, unsupported edits, clarification, and validation recovery.
- **Questions to resolve:** which measured failure each example addresses,
  inline versus on-demand placement, canonical versus fixture-derived IDs,
  token cost, and regression evaluation.
- **Acceptance direction:** add the smallest example set that measurably
  improves the existing golden corpus without weakening unsupported behavior.

#### PA-04 — Catalog of safe domain defaults

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P1
- Candidate defaults include naming conventions, word-aligned offsets, common
  widths, and reset semantics. Each needs a scope, preconditions,
  counterexamples, provenance, and required user notification.
- Broad claims such as “32-bit is the industrial default” are unsafe without
  design context.
- This catalog is a prerequisite for UX-03 and VE-03 and must align with the
  remaining AA-04 clarification policy.

### Deferred

#### PA-05 — Migrate stable domain knowledge to DSH skills

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P2
- Candidate clusters are entity lifecycle, ports/interfaces, netlist/wiring,
  constraints/timing, and protocol-specific guidance.
- **Trigger:** prompt modules are stable and measurements show that on-demand
  loading improves token use or maintenance.
- **Before implementation:** verify actual DSH skill discovery, loading,
  packaging, exact-version policy, prompt interaction, and test isolation.

## 3. Tool design

### Deferred

#### TD-03 — Contextual tool masking

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- Candidate uses are hiding proposal preparation until context is read and
  exposing specialist tools only in valid states.
- **Trigger:** the visible tool set grows materially or evaluation shows
  tool-order/selection errors that prompt and schema constraints cannot solve.
- Validate DSH registration and per-message masking semantics before treating
  them as a product contract.

#### TD-04 — Fine-grained or specialist operation tools

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- Reconsider only if the atomic batch proposal schemas, constrained output,
  and measured prompt improvements cannot achieve target validity.
- Any specialist tool must retain owner-side atomic preview and explicit review
  as the only mutation boundary.

## 4. Review and interaction UX

### Needs refinement

#### UX-02 — Semantic, hierarchical proposal diff

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P1
- Replace raw JSON before/after blocks with an entity-grouped view using added,
  removed, and modified indicators plus collapsible detail.
- **Questions to resolve:** owner versus client diff responsibility, a shared
  normalized diff AST, whether existing owner diff helpers are public contract,
  external library versus domain implementation, and extension versus
  replacement of the Harness result card.
- **Acceptance direction:** artifact/revision identity proves the displayed
  diff is exactly the proposal that can be approved.

#### UX-03 — Visible defaults and corrections

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P1
- Clearly list assumptions, defaulted values, and deterministic corrections,
  with a path to reject and restate the request.
- Automatic behavior must always be visible; “silent auto-fix with
  notification” is contradictory.
- Depends on PA-04 and VE-03.

### Deferred

#### UX-04 — Per-change accept/reject

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- **Trigger:** a normalized proposal dependency model can reconstruct and
  owner-validate a new proposal after selections.
- Never apply a client-filtered subset of an already validated artifact.

## 5. Context, scope, and memory

### Needs refinement

#### CS-03 — Three-tier Spec context

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P2

| Tier | Intended content | Intended detail |
| --- | --- | --- |
| 1 | Selected target | Complete writable semantic state and owned sections |
| 2 | Directly connected peers | Interface/connectivity summary |
| 3 | Global environment | Clock, reset, address-map, and reference metadata |

- **Questions to resolve:** exact owner schema, document-scope behavior,
  writable-boundary representation, Circuit applicability, connectivity
  definition, schema versioning, and graceful handling of missing data.
- **Required evidence:** measure current context sizes and task success before
  accepting the source's unverified 80–90% reduction expectation.
- **Acceptance direction:** representative endpoint/reference tasks show no
  correctness loss and all identity/revision checks remain explicit.

### Deferred

#### CS-04 — Hierarchical scope elevation

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- **Trigger:** cross-entity work becomes frequent enough that opening a
  document-scoped conversation is a demonstrated usability problem.
- Define writable entities, approval semantics, and stale-revision behavior
  before implementation.

#### CS-05 — Conversation-level source-state cache

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- **Trigger:** measurements show authoritative fresh reads are a material
  latency or cost issue.
- Any cache is advisory and revision-keyed; it cannot replace owner reads at
  proposal time.

## 6. Validation and error recovery

### Needs refinement

#### VE-03 — Automatic correction boundary

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P1
- Candidate trivial corrections include identifier sanitization and metadata
  normalization. Reset polarity and width adaptation need narrow, provable
  preconditions and are not presumed trivial.
- **Questions to resolve:** correcting layer, original/corrected representation,
  artifact identity, owner diagnostics, and when the result must instead be an
  AA-04 question.
- Depends on PA-04 and UX-03.

#### VE-04 — Owner validation retry policy within execution budgets

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P0
- Replay-safe analyst/reviewer delivery retries are implemented with bounded
  backoff and aggregate accounting. The remaining scope is owner validation
  correction/retry policy; mutation preparation is not automatically retried.
- **Questions to resolve:** retryable codes, fresh-context requirements,
  maximum attempts/requests/tokens/time, idempotency, visible progress, metric
  events, and the transition from retry to clarification or failure.
- **Safety direction:** bound recovery by both attempts and total resources;
  validation failure must never create an unowned background continuation.

## 7. Testing, evaluation, and prompt optimization

### Needs refinement

#### TQ-04 — Quality thresholds

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P1
- Candidate source targets (`>99.5%` syntactic validity, `>85%` first-shot DRC,
  `>90%` transactional efficiency, and `<1.3` clarification turns) remain
  hypotheses.
- Establish baseline, sample size, task weighting, model/version matrix,
  confidence reporting, and regression policy before adopting release gates.

#### TQ-05 — Headless conversation simulator

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P2
- Define deterministic scenario control, user-persona boundaries, clarification
  behavior, stopping conditions, cost limits, evaluator independence, and final
  owner-state checks.
- Simulated-user judgments supplement but never replace fixed contract tests.

#### TQ-06 — Chaos and recovery suite

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P2
- Candidate injections are owner timeout, unavailable document, invalid entity,
  stale revision, malformed model arguments, rejected preview, duplicate
  action, interrupted persistence, and unanswered structured questions.
- Specify injectable seams and deterministic expected outcomes before building
  a broad suite.

### Deferred

#### TQ-07 — Automated prompt optimization

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- **Trigger:** TQ-04 is accepted and the existing corpus, replay, and metrics are
  stable and resistant to overfitting.
- Generated prompt changes still require human review and exact-version catalog
  updates.

#### TQ-08 — Shadow prompt execution

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- Compare candidate and production prompts without exposing candidate output or
  mutating owner state.
- **Trigger:** privacy, cost, cancellation, logging, and artifact-retention
  policies are approved and offline replay is insufficient.

#### TQ-09 — Third-party prompt test framework selection

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- `promptfoo` and `DeepEval` are candidates from the source, not selected
  dependencies.
- **Trigger:** evaluate whether a framework materially reduces maintenance
  after native corpus, replay, metric, and threshold contracts are stable.

## 8. Recommended sequencing

1. Resolve VE-04 so retry behavior cannot undermine the existing turn and
   execution budgets.
2. Resolve AA-04, PA-04, VE-03, and UX-03 as one clarification/default/
   correction policy.
3. Establish TQ-04 quality gates, then evaluate PA-03 examples against them.
4. Resolve UX-02 diff ownership and its normalized data contract.
5. Measure current context behavior before implementing CS-03.
6. Design TQ-05 and TQ-06 around the accepted recovery and clarification
   policies.
7. Consider routing, specialists, skills, prompt optimization, and shadow
   execution only when their evidence triggers are met.

## 9. Cross-topic dependencies

```text
clarification allowlist + safe-default catalog
  -> automatic correction boundary
  -> visible assumptions/corrections UX

retry resource policy + quality thresholds
  -> recovery simulator and chaos suite

normalized owner preview/diff contract
  -> semantic diff UI
  -> optional per-change proposal reconstruction

measured focused-path failures
  -> complexity router
  -> specialist multi-agent routing or optional plan tier

stable prompt modules + token measurements
  -> optional few-shot content or DSH skills migration
```

## 10. Task record template

```markdown
### TASK-ID — Short title

- Parent idea:
- Delivery state: not-started
- Owner:
- Depends on:
- Scope:
- Out of scope:
- Acceptance criteria:
- Verification:
- Documentation updates:
- Decisions/open questions:
```

Remove a task from this plan only after code, tests, and current-behavior
documentation agree.

## 11. Decision log

| Date | Decision | Reason and effect |
| --- | --- | --- |
| 2026-09-21 | Keep inline few-shot examples unresolved | The source places examples both inline and in skills. Measured failures and accepted quality gates must determine placement and quantity. |
| 2026-09-21 | Treat automatic fixes as visible | “Silent auto-fix” conflicts with notification. UX-03 and VE-03 require traceable corrections. |
| 2026-10-01 | Limit the remaining retry item to owner validation/correction | Replay-safe specialist delivery retries already enforce bounded attempts and aggregate resources; primary mutation preparation is not automatically retried. |
| 2026-09-21 | Treat claimed benchmark effects as hypotheses | Tool-count accuracy, masking improvement, context reduction, and quality targets require project-specific measurement. |
| 2026-09-22 | Keep service specialization separate from execution shape | Future routing must preserve the distinction between domain adapters and focused, goal, or orchestrated execution. |
| 2026-09-23 | Keep only remaining work in this plan | Implemented behavior belongs in current-behavior, architecture, tutorial, and evaluation documents; partially completed ideas retain only unresolved scope here. |

## 12. Remaining source coverage

| Source section | Remaining plan ideas |
| --- | --- |
| Agent architecture | AA-04 through AA-07 |
| Prompt architecture | PA-03 through PA-05 |
| Tool design | TD-03 and TD-04 |
| User interaction and UX | AA-04, UX-02 through UX-04 |
| Context and scope management | CS-03 through CS-05 |
| Validation and error handling | VE-03 and VE-04 |
| Testing and quality | TQ-04 through TQ-09 |

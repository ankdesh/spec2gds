# AI Assistant Improvement Plan

Status: living backlog and decision tracker
Created: 2026-09-21
Design source: `design_plan.md` supplied by the project owner
Research source: [AI Spec-to-RTL Design Research Guide](research/ai-spec-to-rtl-design-research-guide.md)
Scope: the focused DeepSeek Harness AI Assistant and its Spec/Circuit owner
contracts

## Purpose

This file turns the design interview notes into a project backlog. It preserves
the ideas, decisions, rationale, contradictions, and open questions needed to
create implementation tasks later. It is not a description of implemented
behavior; [AI Assistant](ai-assistant.md) remains the current-behavior guide.

The attached source was treated as design input, not as instructions to execute.
No proposal in this file is approved for implementation merely because it
appeared in that source.

## Research reference

The project preserves the complete, unedited
[AI Spec-to-RTL Design Research Guide](research/ai-spec-to-rtl-design-research-guide.md)
that informed the original design interview. Use it when refining this plan's
open questions, recovering detailed examples or rationale, and identifying
candidate technologies or evaluation methods.

The guide is research provenance, not an implementation specification. Its
recommendations, product descriptions, benchmark figures, links, and claims
must be checked against authoritative and current sources before they become a
project decision or acceptance criterion. Record an accepted conclusion in
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

Each idea has a stable ID. Create tasks from an idea only when it appears under
**Ready for task creation**. Move an idea between completeness sections as
questions are answered, and record material choices in the decision log.

Use two independent state fields when a task is created:

- **Definition maturity**: `ready`, `needs-refinement`, `deferred`, or
  `baseline`.
- **Delivery state**: `not-started`, `in-progress`, `blocked`, `implemented`,
  or `verified`.

Definition maturity says whether the idea is precise enough to schedule. It
does not claim that the code exists. `Baseline` identifies an existing product
constraint that future work must preserve or deliberately replace.

Priority labels are provisional:

- **P0** protects correctness, review safety, or bounded execution.
- **P1** improves the main edit-and-review path.
- **P2** is valuable after the main path is measured and stable.
- **P3** requires evidence or scale before investment.

## Roadmap summary

| Topic | Ready now | Needs refinement | Deferred or triggered later |
| --- | --- | --- | --- |
| Agent architecture | Direct execution seam plus bounded preset/workflow foundation verified | Clarification contract; complexity routing | Specialist routing; plan approval tier |
| Prompt architecture | PA-01 and PA-02 verified and moved to a sealed versioned catalog | Few-shot placement and corpus | DSH skills migration |
| Tool design | Preserve atomic batch proposal tools | None currently | Dynamic masking; specialist tools |
| Review UX | Owner-derived natural-language summary verified | Semantic diff ownership and interaction model | Per-change approval |
| Context and scope | Preserve immutable binding and fresh reads | Three-tier context contract and measurements | Scope elevation; conversation state cache |
| Validation and recovery | Structured error envelopes and deterministic invariants verified | Auto-fix policy; retry/turn-budget policy | Adaptive recovery based on measured failures |
| Testing and optimization | Versioned corpus, DSH replay, and raw metrics verified | Simulator design and quality thresholds | Prompt optimization and shadow execution |

## Immediate implementation record

| Improvement | Product/runtime changes | Tests and evaluation | DSH capability used |
| --- | --- | --- | --- |
| AA-03 | `ai-assistant/src/proposal-pipeline.ts`, `tools.ts`, and the existing review action in `index.ts` separate artifact construction, preview-state mapping, and explicit mutation. | `proposal-pipeline.test.ts` and Harness integration. | Existing typed tool registration and bounded agent loop; no plan or goal subsystem. |
| UX-01 | `proposal-presentation.ts`, public review serialization, and `client/index.js` derive and render an owner-backed summary before model-authored text. | `proposal-presentation.test.ts` and client launch tests. | Existing tool-result renderer only; no new DSH UI primitive. |
| VE-01 | Typed error envelopes in `types.ts`, normalization/logging in `proposal-presentation.ts`, persistence/migration in `state.ts`, and consistent tool/action responses. | Presentation, state, launch, and Harness integration tests. | Existing DSH tool-result transport and session persistence. |
| VE-02 | Pure proposal builders plus Spec owner diff/invariant coverage. | TypeScript unit suite and `tests/agent_spec/spec_format/test_assistant_diff.py` with related owner regressions. | None; deterministic native tests. |
| TQ-01 | Versioned non-production cases and manifest under `ai-assistant/evals/`, validated by `scripts/evaluate.mjs`. | Fourteen Spec, Circuit, stale, invalid, unsupported, and ambiguous cases plus owner-native semantic tests. | None for corpus storage; it intentionally remains independent of a provider transcript. |
| TQ-02 | A test-only replay bundle under `ai-assistant/bundles/replay/` and dynamic replay profile wiring in `scripts/dev.mjs`. | Harness integration records then replays the exact context/proposal/final-response trajectory with a dead provider endpoint. | Pinned `@deepseek-ai/dsh-session-persistence-jsonl` and `@deepseek-ai/dsh-llm-replay`; production retains compressed sessions and no replay profile. |
| TQ-03 | `eval-metrics.ts` calculates raw counts from DSH JSONL and `evaluate.mjs` emits versioned event, result, and metric artifacts. | `eval-metrics.test.ts` plus metrics assertions against the recorded Harness session. | DSH Session event schema and model usage fields; no analytics service or new runtime plugin. |

### Configurable assistant foundation

| Improvement | Product/runtime changes | Tests and evaluation | DSH capability used |
| --- | --- | --- | --- |
| CF-01 — Prompt catalog | Exact Spec/Circuit YAML bundles replace runtime-owned prompt text; the product binds immutable target variables and verifies the four required sections. | Catalog parser/unit tests, product prompt contracts, and real system-prompt integration assertions. | New sealed Cordis prompt catalog and strict startup YAML provider. |
| CF-02 — Preset catalog | Browser sessions select immutable `focused`, `goal`, or `orchestrated`; headless remains focused. | Profile composition assertions and focused Harness integration. | Existing DSH agent presets, persona, goal command/tool, and goal UI. |
| CF-03 — Generic workflow | `prepare-reviewed-change@1.0.0` composes with exact Spec/Circuit adapter manifests and immutable owner/review contracts. | Strict YAML and projection tests plus startup exact-ref checks. | New sealed workflow catalog and strict startup YAML provider. |
| CF-04 — Durable lifecycle | Full workflow snapshots preserve refs/digests, status, budgets, usage, draft, checkpoint, and pending human decision. | Projection replay/invariant tests and persistence catalog/change records. | DSH Session v3 event/projection contract using `s-workflow/change`. |
| CF-05 — Restricted workflow tools | Five model tools read state, replace a draft, checkpoint, or request input/completion. Lifecycle, budget, approval, apply, and send remain host-only. | Tool schema catalog, model-experience gate, typecheck, and product capability tests. | DSH typed tool registry and system-prompt sections. |
| CF-06 — Human controls | Browser workflow dock and CAS HTTP endpoints pause, resume, cancel, answer, and raise budgets; review apply/send completes and discard cancels. | Product build/unit suite and real focused integration regression. | Client input-dock slot and live DSH Session projection. |
| CF-07 — Bounded delegation | Orchestrated children inherit the binding but receive only `get_bound_context`, a read-only persona, depth one, and child/concurrency budget checks. | Preset assertions, compile checks, and DSH subagent capability reuse. | Stock one-shot in-process subagent provider, tool filters, persona shadowing, and depth caps. |

The complete implemented design and extension procedure are documented in
[Configurable Assistant Architecture](configurable-assistant-architecture.md).

## 1. Agent architecture and interaction

### Baseline to preserve

#### AA-01 — Direct proposal execution for ordinary edits

- **Definition maturity:** baseline
- **Delivery state:** implemented, pending continuing regression coverage
- **Priority:** P0
- A normal concrete request reads authoritative context and prepares one typed,
  reviewable proposal without an intermediate plan-approval conversation.
- Owner preview and an explicit review-card action remain the mutation boundary.
- Prompts, tools, and state should not prevent an additive plan stage later.

#### AA-02 — Bounded single-agent path

- **Definition maturity:** baseline
- **Delivery state:** implemented, with current worktree validation in progress
- **Priority:** P0
- The focused preset exposes owner context and coarse proposal tools. Goal and
  orchestrated presets add only the bounded, catalog-defined capabilities
  documented in CF-02 through CF-07; general coding tools and skills remain
  disabled.
- Future orchestration must not reintroduce unbounded background loops or false
  completion claims.

### Implemented and verified

#### AA-03 — Preserve a future plan/approve/execute extension seam

- **Definition maturity:** ready
- **Delivery state:** verified
- **Priority:** P1
- Document and test boundaries between intent interpretation, proposal planning,
  owner preview, user approval, and application.
- Keep direct execution as the active path. The task is architectural cleanup
  and contract coverage, not a plan UI.
- **Acceptance direction:** adding an optional plan-review state later should
  not require changing operation schemas or owner apply contracts.
- **Verification:** proposal artifact construction and preview-state mapping are
  pure, typed stages with direct unit coverage; owner mutation remains confined
  to the explicit review action path.

### Needs refinement

#### AA-04 — Structured clarification contract

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P1
- Blocking questions are intended for structural ambiguity: missing entity
  identity, ambiguous endpoints, clock-domain crossings, consequential width
  adaptation, and protocol choice.
- Deterministic details may use a declared default and remain visible in the
  proposal assumptions.
- **Questions to resolve:**
  - Which Harness question tool and client view will be supported?
  - Can a question be answered and proposal generation resume in the same
    bounded turn, or does it require a new turn?
  - What is the exact allowlist of blocking ambiguity classes?
  - How are recommended options represented and persisted?
- **Safety rule:** no “silent” correction may alter architecture or meaning.

#### AA-05 — Complexity router

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P3
- The source proposes routing simple edits to one agent and complex,
  multi-entity work to an orchestrator with specialists.
- **Questions to resolve:** measurable complexity signals, deterministic routing
  rules, maximum steps/agents, cancellation, clarification bubble-up, proposal
  ownership, and how all agents share one authoritative revision.
- **Entry criterion:** pursue only after single-agent evaluation shows a
  recurring class of valid requests that cannot be handled reliably within the
  bounded proposal path.

### Deferred

#### AA-06 — Multi-agent orchestration

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- Possible specialists include entity lifecycle, interfaces, wiring, and
  constraints/timing.
- Child agents must never bypass the owner preview or approval boundary.
- **Trigger:** AA-05 has an accepted routing contract and evaluation evidence
  that orchestration improves outcomes enough to justify latency and cost.

#### AA-07 — User-approved plan tier

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- Intended for complex multi-entity operations only; ordinary edits retain
  direct diff review.
- **Trigger:** complex proposals are supported and users demonstrably need a
  checkpoint before owner preview.

## 2. Prompt architecture

### Implemented and verified

#### PA-01 — Replace complete prompt overrides with composable sections

- **Definition maturity:** ready
- **Delivery state:** verified
- **Priority:** P0
- Bound-domain prompt registration no longer uses `complete: true`. The
  unbound-session fail-closed guard deliberately retains it.
- Implemented section groups:

  | Approximate order | Section | Responsibility |
  | ---: | --- | --- |
  | 100 | Domain persona | Hardware-design role and communication boundary |
  | 150 | Immutable binding | Owner, document, scope, and selected target |
  | 200 | Operation constraints | Writable boundary, vocabulary, assumptions |
  | 300 | Output contract | Tool/schema and unsupported-request behavior |

- **Verification:** the deployment identity and four product sections compose
  once in deterministic order; bound and unbound tests pass; no generic goal or
  general-purpose tool becomes reachable.

#### PA-02 — Split runtime prompt assembly into typed sections

- **Definition maturity:** ready
- **Delivery state:** verified
- **Priority:** P1
- `promptSectionsFor(binding)` now constructs typed persona, binding, operation,
  and output sections while the existing context shapers retain runtime owner
  identity checks.
- The runtime sections are sourced from exact sealed YAML bundles through
  `catalogPromptSectionsFor`; the original typed helper remains as a regression
  oracle for instruction-equivalence tests.
- Unit tests protect section names, order, content, binding interpolation, and
  the absence of a bound complete override. The real Harness integration test
  protects final prompt composition and the context-to-proposal path.

### Needs refinement

#### PA-03 — Few-shot example policy

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P1
- Candidate examples are port addition, instance creation, connection wiring,
  entity creation, unsupported edits, and validation recovery.
- The source alternately places examples inline in the base prompt and inside
  on-demand skills. That conflict must be resolved before authoring examples.
- **Questions to resolve:**
  - What failure does each example address?
  - Which examples are always valuable enough to pay their token cost?
  - Should examples use canonical synthetic IDs or fixture-derived IDs?
  - How will examples be evaluated for positive improvement and regressions?
- **Preferred sequence:** establish the golden evaluation corpus first, then
  add the smallest example set that improves measured outcomes.

#### PA-04 — Catalog of safe domain defaults

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P1
- Candidate defaults include naming conventions, word-aligned offsets, common
  widths, and standard reset semantics.
- Each default needs a scope, preconditions, counterexamples, and required user
  notification. Broad claims such as “32-bit is the industrial default” are not
  safe without design context.
- This catalog is a prerequisite for UX-03 and VE-03.

### Deferred

#### PA-05 — Migrate stable domain knowledge to DSH skills

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P2
- The later design decision in the source supersedes the earlier immediate
  skills proposal: keep prompt content programmatic until PA-01 and PA-02 are
  stable and evaluated.
- Candidate domain clusters are entity lifecycle, ports/interfaces,
  netlist/wiring, constraints/timing, and protocol-specific guidance.
- **Trigger:** prompt modules are stable and token or maintenance measurements
  show that on-demand loading is worthwhile.
- **Before implementation:** verify the actual Harness skill registration,
  catalog injection, loading semantics, packaging, and test isolation rather
  than relying on the design notes alone.

## 3. Tool design

### Baseline to preserve

#### TD-01 — Coarse, atomic proposal tools

- **Definition maturity:** baseline
- **Delivery state:** implemented
- **Priority:** P0
- Keep one batch proposal tool per owner domain rather than one tool per
  operation type.
- A proposal contains an ordered operation list and is validated atomically by
  its owner before any review action can apply or send it.
- Tool descriptions and schemas may be modular internally without expanding
  the model-visible tool count.

#### TD-02 — Small domain tool surface

- **Definition maturity:** baseline
- **Delivery state:** implemented
- **Priority:** P0
- Current conversations need a fresh-context tool and the proposal tool for the
  bound domain. A future clarification tool would still leave the surface
  small.

### Deferred

#### TD-03 — Contextual tool masking

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- Potential uses include hiding proposal preparation until context is read or
  exposing specialist tools only in valid states.
- **Trigger:** the model-visible tool set grows materially or evaluation shows
  tool-order/selection errors that prompt and schema constraints do not solve.
- Validate the Harness registration lifecycle before treating unregistering or
  per-message masks as available product contracts.

#### TD-04 — Fine-grained or specialist operation tools

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- This is intentionally not planned. Reconsider only with evidence that the
  atomic batch schema, constrained output, and examples cannot achieve target
  validity.

## 4. Review and interaction UX

### Implemented and verified

#### UX-01 — Natural-language change summary

- **Definition maturity:** ready
- **Delivery state:** verified
- **Priority:** P1
- Derive a concise summary from the validated preview/diff artifact, not from
  an unverified model claim.
- Mention changed entities, operation counts/types, material assumptions, and
  owner diagnostics. Never say the change was applied before the action result.
- Cover summaries with deterministic fixture tests.
- **Verification:** public review results derive stable operation counts,
  changed targets, assumptions, and diagnostics from the persisted artifact and
  owner preview. The client renders this before the model-authored request text.

### Needs refinement

#### UX-02 — Semantic, hierarchical proposal diff

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P1
- Direction: replace raw JSON before/after blocks with an entity-grouped table
  using added, removed, and modified indicators and collapsible detail.
- **Questions to resolve:**
  - Is the semantic diff produced by the Python owner, Circuit owner, or the
    TypeScript client?
  - Can both owners expose one normalized diff AST without losing domain detail?
  - Is an existing owner `_json_diff()` sufficient, and is it public contract?
  - Use an external diff library or a small domain-aware implementation?
  - Extend the Harness result card or own the complete proposal view?
- **Dependency:** preserve revision and artifact identity so the rendered diff
  is provably the one approved.

#### UX-03 — Visible defaults and corrections

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P1
- A proposal should clearly list assumptions, defaulted values, and
  deterministic corrections with a path to reject and restate the request.
- The source phrase “silent auto-fix with notification” is contradictory. The
  working rule is **automatic but visible**.
- Depends on PA-04 and VE-01.

### Deferred

#### UX-04 — Per-change accept/reject

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- Partial approval can break atomic invariants and operation dependencies.
- **Trigger:** a normalized diff/proposal dependency model can produce a new
  owner-validated proposal after selections; never apply a client-filtered
  subset of a previously validated artifact.

## 5. Context, scope, and memory

### Baseline to preserve

#### CS-01 — Immutable conversation binding

- **Definition maturity:** baseline
- **Delivery state:** implemented
- **Priority:** P0
- One conversation stays bound to one Spec document/entity or Circuit document.
- Cross-entity Spec mutations require the document-scoped contract or a new
  appropriately bound conversation.

#### CS-02 — Fresh authoritative reads

- **Definition maturity:** baseline
- **Delivery state:** implemented
- **Priority:** P0
- Read owner context for each design-specific turn. Do not treat conversation
  history as current source state.
- Revision checks remain authoritative at preview and application boundaries.

### Needs refinement

#### CS-03 — Three-tier Spec context

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P2
- Proposed tiers:

  | Tier | Intended content | Intended detail |
  | --- | --- | --- |
  | 1 | Selected target | Complete writable semantic state and owned sections |
  | 2 | Directly connected peers | Interface/connectivity summary |
  | 3 | Global environment | Clock, reset, address-map, and reference metadata |

- **Questions to resolve:** exact owner schema, document-scope behavior,
  writable-boundary representation, Circuit applicability, connectivity
  definition, and graceful handling of missing data.
- **Required evidence:** measure current context sizes and task success before
  accepting the source's unverified 80–90% reduction expectation.
- **Acceptance direction:** no loss in endpoint/reference correctness across a
  representative evaluation corpus; schema versioning and identity checks are
  explicit.

### Deferred

#### CS-04 — Hierarchical scope elevation

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- **Trigger:** cross-entity work becomes frequent enough that opening a
  document-scoped conversation is a demonstrated usability problem.
- Must define writable entities, approval semantics, and stale-revision
  behavior before implementation.

#### CS-05 — Conversation-level source-state cache

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- **Trigger:** measurements show fresh reads are a material latency/cost issue.
- Any cache is advisory and revision-keyed; it cannot replace authoritative
  owner reads at proposal time.

## 6. Validation and error recovery

### Implemented and verified

#### VE-01 — Structured validation error envelopes

- **Definition maturity:** ready
- **Delivery state:** verified
- **Priority:** P0
- Normalize proposal failures into a stable machine-readable envelope, while
  retaining owner diagnostics without inventing repair advice.
- Minimum candidate fields: `success`, `error_code`, `target`, `details`,
  `retryable`, and structured `suggested_actions` where the owner can safely
  provide them.
- Define whether multiple validation failures are returned together and how
  owner-specific details are nested.
- **Acceptance direction:** Spec and Circuit failures render consistently;
  unknown errors fail closed; logs retain correlation IDs; the assistant never
  claims a rejected preview is ready.
- **Verification:** proposal validation, owner rejection, stale revision,
  owner-contract, unavailable-owner, and unknown failures use the typed product
  envelope and deterministic client presentation. Owner diagnostics remain
  nested without synthesized repair advice.

#### VE-02 — Deterministic validation and diff unit coverage

- **Definition maturity:** ready
- **Delivery state:** verified
- **Priority:** P0
- Cover schema validators, normalization, AST application, source invariants,
  diff generation, revision mismatch, and proposal artifact identity.
- Start with defects and unsupported cases already observed in evaluation.
- **Verification:** TypeScript unit tests cover proposal normalization, artifact
  identity, summary/diff derivation, stale review persistence, and database
  migration. Python owner tests cover Spec AST application, invariants, and
  assistant diff behavior.

### Needs refinement

#### VE-03 — Automatic correction boundary

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P1
- Candidate trivial corrections include identifier sanitization and metadata
  normalization. Reset polarity and width adaptation are not automatically
  trivial; they need narrow, provable preconditions.
- **Questions to resolve:** which layer corrects, how the original and corrected
  values are represented, whether corrections affect artifact identity, and
  which cases must instead ask the user.
- Depends on PA-04 and AA-04.

#### VE-04 — Retry policy compatible with the turn budget

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P0
- The source proposes up to three automated retries. The current product allows
  three model steps total, normally consumed by context read, proposal call,
  and final response. These policies cannot both hold as written.
- **Questions to resolve:** retryable codes, whether a retry needs another
  context read, maximum model/tool calls, token ceiling, user-visible progress,
  and when to stop or ask a question.
- **Safety direction:** bounded by both attempts and total turn resources;
  validation failures must never launch background continuation.

## 7. Testing, evaluation, and prompt optimization

### Implemented and verified

#### TQ-01 — Golden semantic evaluation corpus

- **Definition maturity:** ready
- **Delivery state:** verified
- **Priority:** P0
- Store versioned cases mapping initial fixture plus user intent to allowed
  outcomes, expected semantic changes, assumptions, and unsupported reasons.
- Compare final semantic state/graph where operation ordering is not material;
  also assert safety properties such as no mutation before approval.
- Seed the corpus with the existing Spec evaluation request matrix and add
  successful, ambiguous, invalid, revision-conflict, and Circuit cases.
- Avoid storing secrets or production conversations.
- **Verification:** the versioned 14-case manifest validates fixture presence,
  semantic assertions, allowed outcomes, and the no-mutation/three-step safety
  contract. Owner-native regression tests exercise the corresponding semantic
  operations; automated model-matrix simulation remains TQ-05.

#### TQ-02 — Deterministic replay layer

- **Definition maturity:** ready
- **Delivery state:** verified
- **Priority:** P1
- Record sanitized model/tool event fixtures at an explicit contract boundary so
  UI, diff, state, and recovery tests can replay without provider calls.
- Version fixture formats and distinguish model fixtures from authoritative
  owner fixtures.
- **Verification:** the real Harness integration records an uncompressed DSH
  Session, replays it through `@deepseek-ai/dsh-llm-replay`, and proves that the
  replayed context/proposal/final-response trajectory makes no provider call.
  The replay profile is test-only and is absent from the release manifest.

#### TQ-03 — Core metric instrumentation

- **Definition maturity:** ready
- **Delivery state:** verified
- **Priority:** P1
- Capture raw counts needed to calculate candidate metrics before fixing target
  thresholds: schema-valid tool calls, first-preview DRC pass, applied versus
  proposed operations, clarification turns, retries, latency, tokens, and false
  completion/safety violations.
- Metric names and formulas become stable only after event definitions are
  documented and tested.
- **Verification:** deterministic JSONL metric tests cover proposal validity,
  first-preview readiness, proposed/applied operation counts, clarifications,
  retries, latency, token buckets, and false-completion violations. The Harness
  integration calculates the same metrics from its recorded session.

### Needs refinement

#### TQ-04 — Quality thresholds

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P1
- Candidate source targets (`>99.5%` syntactic validity, `>85%` first-shot DRC,
  `>90%` transactional efficiency, and `<1.3` clarification turns) are
  hypotheses, not accepted release gates.
- Establish a baseline, sample size, model/version matrix, confidence reporting,
  and task weighting before adopting thresholds.

#### TQ-05 — Headless conversation simulator

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P2
- Define deterministic scenario control, user-persona boundaries, stopping
  conditions, cost limits, evaluator independence, and how final owner state is
  checked.
- Simulated-user judgments supplement but do not replace fixed contract tests.

#### TQ-06 — Chaos and recovery suite

- **Definition maturity:** needs-refinement
- **Delivery state:** not-started
- **Priority:** P2
- Candidate injections: owner timeout, unavailable document, invalid entity,
  stale revision, malformed model arguments, rejected preview, duplicate action,
  and interrupted persistence.
- Specify injectable seams and deterministic expected outcomes before creating
  a broad suite.

### Deferred

#### TQ-07 — Automated prompt optimization

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- Candidate approaches include prompt compilation/optimization against the
  golden corpus. Tool choice remains open.
- **Trigger:** TQ-01 through TQ-04 are stable, reproducible, and resistant to
  overfitting. Any generated prompt change still requires human review.

#### TQ-08 — Shadow prompt execution

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- Compare candidate and production prompts without exposing the candidate
  result to the user or mutating owner state.
- **Trigger:** privacy, cost, cancellation, logging, and artifact-retention
  policies are approved, and offline replay is insufficient.

#### TQ-09 — Third-party prompt test framework selection

- **Definition maturity:** deferred
- **Delivery state:** not-started
- **Priority:** P3
- `promptfoo` and `DeepEval` are candidates from the source, not dependencies or
  selected technologies.
- **Trigger:** define TQ-01's native data and assertion contracts first, then
  evaluate whether a framework reduces maintenance without owning core semantics.

## 8. Recommended sequencing

1. Finish and verify current binding, bounded-execution, and false-completion
   protections before judging prompt quality.
2. Build TQ-01, VE-02, and the raw instrumentation in TQ-03 so later changes
   have a reproducible baseline.
3. Treat the verified PA-01 and PA-02 composition as the prompt baseline; rerun
   it against the golden corpus after TQ-01 exists.
4. Define VE-01 and reconcile VE-04 with the turn budget.
5. Resolve AA-04, PA-04, and VE-03 as one clarification/default/correction
   policy rather than three independent features.
6. Resolve UX-02's normalized diff ownership; add UX-01 once its source
   artifact is stable.
7. Measure context behavior before implementing CS-03.
8. Consider skills, multi-agent routing, prompt optimization, and shadow
   execution only when their trigger evidence exists.

## 9. Cross-topic dependencies

```text
current safety baseline
  -> golden corpus + invariant tests
  -> composable prompts
  -> structured validation errors

safe-default catalog + clarification contract
  -> automatic correction boundary
  -> visible assumptions/corrections UX

normalized owner preview/diff contract
  -> semantic diff UI
  -> optional per-change proposal reconstruction

measured single-agent failures
  -> complexity router
  -> bounded multi-agent orchestration

stable prompt modules + token measurements
  -> optional DSH skills migration
```

## 10. Task record template

Copy this block below the relevant idea or into the project task system:

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

Do not mark a task `implemented` until code and documentation agree. Mark it
`verified` only after the stated checks pass against the intended owner/model
matrix.

## 11. Decision log

| Date | Decision | Reason and effect |
| --- | --- | --- |
| 2026-09-21 | Treat DSH skills as deferred, not immediate | The source's later decision explicitly defers skills until composable TypeScript prompts work. PA-05 records the trigger for revisiting them. |
| 2026-09-21 | Keep inline few-shot examples unresolved | The source places examples both inline and in skills. TQ-01 must exist before choosing placement or quantity. |
| 2026-09-21 | Treat automatic fixes as visible | “Silent auto-fix” conflicts with the requirement to notify. UX-03 and VE-03 require traceable corrections. |
| 2026-09-21 | Do not accept a three-retry cap yet | It conflicts with the current three-model-step turn limit. VE-04 owns the combined resource policy. |
| 2026-09-21 | Treat claimed benchmark effects as hypotheses | Tool-count accuracy, masking improvement, context reduction, and proposed quality targets require project-specific measurement before they become requirements. |
| 2026-09-21 | Compose bound prompts; retain a complete unbound guard | PA-01 and PA-02 are verified. The pinned Harness confirms that `complete: true` restores that section as the entire prompt after assembly, so bound conversations use four ordinary sections while the fail-closed unbound prompt intentionally remains complete. |
| 2026-09-21 | Keep proposal presentation owner-derived and replay at the DSH event boundary | AA-03, UX-01, VE-01, VE-02, and TQ-01 through TQ-03 are verified. Deterministic summaries and errors come from typed artifacts and owner previews; the existing review action remains the only mutation boundary. Test-only replay uses the pinned Harness `dsh-llm-replay` capability without adding a production profile or forking DSH. |
| 2026-09-22 | Separate service adapters from execution presets | Exact prompt/workflow catalogs now provide service-specific instructions and review contracts, while immutable `focused`, `goal`, and `orchestrated` presets choose execution shape. This is the reusable foundation for future services. |
| 2026-09-22 | Reuse stock DSH goal and subagent capabilities behind a product workflow boundary | Goal continuation/UI and one-shot in-process children are reused. New DSH packages own only the missing prompt catalog, durable generic workflow, strict YAML providers, and restricted workflow tools. Children are read-only and budgeted; host/review surfaces retain lifecycle and mutation authority. |

## 12. Source coverage

| Source section | Plan ideas |
| --- | --- |
| Agent architecture | AA-01 through AA-07 |
| Prompt architecture | PA-01 through PA-05 |
| Tool design | TD-01 through TD-04 |
| User interaction and UX | AA-04, UX-01 through UX-04 |
| Context and scope management | CS-01 through CS-05 |
| Validation and error handling | VE-01 through VE-04 |
| Testing and quality | VE-02, TQ-01 through TQ-09 |

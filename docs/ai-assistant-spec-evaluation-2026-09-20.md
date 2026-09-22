# AI Assistant to Spec Editor Evaluation

Date: 2026-09-20
Branch and revision: `main` at `afc922a`
Model: `gpt-4o-mini`
Scope: Spec Editor only; Circuit Designer was not evaluated.

## Executive summary

The current Spec Editor launch path is not usable for Spec editing. Seven simple
component update requests were submitted through the real browser UI. None
created a typed Spec proposal, none reached owner preview, and none created a
review record.

The primary failure occurs before model-quality evaluation: the launch route
reserves a Spec-bound session ID, but the DSH browser creates a different,
generic session ID. The product plugin therefore never attaches the immutable
Spec binding, bound system prompt, `get_bound_context`, or
`prepare_spec_proposal` tool to the conversation. Generic DSH goal tools remain
available and reinterpret ordinary edit requests as autonomous goals.

This produces misleading and potentially expensive behavior. Several runs
claimed success without a proposal or source change. The unsupported rename
request entered a 51-turn goal loop and accumulated approximately 906K tokens
of DSH usage accounting before it was manually stopped.

The review boundary itself remained safe. No test changed the source package.

## Test subject and safety controls

The evaluation used:

- Spec package: `samples/minimal/single_component_with_2cycle_rtl.spec`
- Document ID: `spec_single_component_two_cycle`
- Component ID: `component_new_component_ac94282c1aeb4b178807e77e8f10c280`
- Component VLNV: `spec2gds.local:work:new_component:1.0`
- Initial source revision:
  `sha256:0a71a323d76d2fe7b4ce59ae861fda6f1c6346286f42034f264cd96974a9666e`
- Initial package SHA-256:
  `61d2d9cc3a1e0460f0b478fa3ba2378c439959d4b34daeca1b829656d753d228`

Every request opened a fresh browser conversation using the component-scoped
`/launch/spec` route. Proposals were permitted to reach preview, but the Apply
action and Spec apply endpoint were never used. Browser output, DSH session
projections, the product SQLite database, and the Spec snapshot were inspected.

The expected success criteria for an update request were:

1. The launched conversation is bound to the selected component.
2. The assistant reads fresh context with `get_bound_context`.
3. The assistant calls `prepare_spec_proposal` with the minimal typed operation
   set.
4. The Spec owner validates the proposal and returns a reviewable diff.
5. The assistant says that the proposal is ready for review and does not claim
   the source was changed.

No run passed criterion 1, so criteria 2–5 could not be meaningfully assessed.

## Connection evidence

A component launch successfully reserved this product binding:

```text
reserved session: 22c9dbe0-7cd7-4c3f-85b8-901fbe2ff009
status: creating
scope: entity
entity kind: component
entity ID: component_new_component_ac94282c1aeb4b178807e77e8f10c280
workspace title: Spec Editor · spec_single_component_two_cycle
```

The browser conversation created from that launch instead had a DSH-generated
identity such as:

```text
session-cce8b124-7f1c-4e45-b626-67b4fcfa61df
```

The DSH workspace displayed the raw workspace hash as its title, and the
product binding remained in `creating` state. The seven browser conversations
were present in DSH session projections, but no corresponding active entity
bindings were present in `assistant.sqlite3`.

The observed tool trajectory was generic DSH goal behavior, including
`create_goal`, repeated `get_goal`, and goal completion/pause transitions. No
tested conversation showed `get_bound_context` or `prepare_spec_proposal`.

The product review table contained only two older document-scoped reviews from
before this evaluation. It acquired no new review records during these seven
runs.

## Results

| # | Request | Observed result | Time | DSH token accounting |
|---|---|---|---:|---:|
| 1 | Change the component description | Created a generic goal, asked for confirmation, then claimed the goal was completed. No proposal. | 11.6 s | 4.4K |
| 2 | Add one-bit `enable` input | Entered a six-round goal flow, emitted generic Verilog examples, asked the user to modify and verify the design, then claimed completion. | 32.8 s | 37K |
| 3 | Change only the `data_out` description | Repeated goal checks, admitted it could not retrieve the change, then marked the goal complete and advised manual review. | 25.2 s | 42.5K |
| 4 | Make a reset-value SystemVerilog change | Returned a generic active-high reset example using `posedge reset`; it did not read the actual active-low `rst_n` implementation. No proposal. | 7.0 s | 1.5K |
| 5 | Add `valid_out` and update SystemVerilog together | Asked permission to create a goal instead of preparing the requested two-operation proposal. | 6.5 s | 1.4K |
| 6 | Rename `new_component` to `pipeline_stage` | Failed to recognize the immutable identity boundary and entered a runaway goal loop. It was manually stopped after 51 turns and 106 steps. | >134 s | 906K |
| 7 | Explicitly read context and prepare a formal proposal | Created a generic goal and repeatedly printed a prose “proposal.” It said the current description was unavailable and never created a typed review. | 35.0 s | 53.8K |

The seven runs accumulated approximately 1.05M tokens in DSH usage accounting,
most of which were cached input tokens from the runaway goal behavior. This is
not necessarily equal to billable provider tokens, but it accurately reflects
the excessive loop size shown by the UI.

## Detailed behavioral findings

### 1. False completion claims

Runs 1, 2, and 3 marked goals complete even though no formal proposal existed,
the owner had not previewed a change, and the Spec source remained untouched.
This breaks the product rule that discussion and model output must never imply
that a change was applied.

### 2. Generic goal behavior overrides direct editing intent

Straightforward imperative requests were converted into goals. Depending on
the run, the assistant then asked for confirmation, asked the user for commands,
or repeatedly polled goal state. The `/goal` behavior is not merely extra UI;
in the unbound sessions it becomes the dominant execution path.

### 3. The model never sees authoritative Spec context

The SystemVerilog request demonstrates the consequence clearly. The actual
source uses an active-low asynchronous reset:

```systemverilog
always_ff @(posedge clk or negedge rst_n)
```

The assistant instead suggested a generic active-high example using
`posedge reset`. The explicit proposal test reported that the current component
description was unavailable, even though the owner context endpoint exposes it.

### 4. Unsupported operations are not rejected safely

Renaming the component is outside the current assistant contract because the
component identity/VLNV is immutable. The expected response was a concise
unsupported result with no operations. Instead, the generic goal runner tried
to discover nonexistent commands and repeatedly requested environment details.

### 5. Goal loops can consume substantial resources

The rename session reached:

- 51 turns
- 106 steps
- 48,085 uncached input tokens
- 852,224 cached input tokens
- 5,648 output tokens

Closing the browser that initiated the run did not stop the background goal.
The session had to be reopened and stopped explicitly. Its final goal phase is
`paused`, and the UI offers “Resume goal.”

### 6. Owner context is available and sufficiently rich

The Spec owner endpoint itself returned a coherent entity-scoped context of
approximately 19 KB containing:

- the exact component reference and source revision;
- all five port definitions;
- the complete SystemVerilog body;
- section validation diagnostics;
- read-only design usages; and
- the existing component/design reference catalog.

This suggests the immediate blocker is launch/session attachment rather than
missing Spec-side data. Model quality for typed Spec operations cannot be judged
until the binding reaches the actual DSH conversation.

## Source integrity after evaluation

No source mutation occurred.

- Final package SHA-256:
  `61d2d9cc3a1e0460f0b478fa3ba2378c439959d4b34daeca1b829656d753d228`
- Final source revision:
  `sha256:0a71a323d76d2fe7b4ce59ae861fda6f1c6346286f42034f264cd96974a9666e`
- Component description remains absent.
- Ports remain `clk`, `rst_n`, `data_in`, `valid_in`, and `data_out`.
- SystemVerilog source SHA-256 remains
  `sha256:a59f7ff4791da6ee7908a28b0056e0e00bba33172081e0fef6fd683a4a945714`.

## Issue classification

| Severity | Finding |
|---|---|
| Critical | Reserved Spec-bound session ID is not the DSH conversation ID created by the browser launch. |
| Critical | Generic goal machinery can loop unattended and consume very large token volume. |
| Critical | The assistant can claim completion without a proposal, preview, review, or source change. |
| High | Bound context and Spec proposal tools are absent from editor-launched conversations. |
| High | Unsupported edits are not rejected using the Spec contract. |
| Medium | The new DSH workspace initially displays its hash instead of the resolved Spec workspace title. |
| Positive safety result | Review gating prevented hallucinated changes from mutating the `.spec` package. |

## Evaluation limitation

This report does not yet measure how well `gpt-4o-mini` constructs valid Spec
operations. The launch/session mismatch prevents the model from receiving the
Spec prompt and tools. After that connection is corrected, the same request
matrix should be rerun, including repeated trials and preview-diff inspection,
before prompt or schema quality is assessed.

## Post-evaluation fix validation

The critical connection and runaway-loop defects identified above were fixed
after the baseline evaluation. This section records fix validation without
rewriting the historical results.

- The browser now creates the exact session ID reserved by the Spec launch and
  fails closed if DSH returns a different ID.
- A workspace-title collision is disambiguated with owner authority and a
  stable workspace-key prefix instead of aborting launch.
- Unbound conversations receive a complete product guard that refuses document
  and editing claims.
- Generic goal state, the background goal-round driver, `/goal`, goal model
  tools, and goal UI are disabled together.
- Product policy allows at most three model steps per user turn and caps each
  model response at 1,200 output tokens by default.

The real browser launch was repeated against the running Spec service. It
opened a new active entity binding for
`component_new_component_ac94282c1aeb4b178807e77e8f10c280`, selected that
exact session, produced no dialog or console error, and displayed the resolved
Spec workspace title. The new session projection contained no goal state or
goal UI.

The real headless Harness profile was tested with a local deterministic model
fixture. A normal three-step flow read authoritative bound context, prepared a
typed `create_entity` proposal, persisted a ready review, and applied the
1,200-token request cap to all three model calls. A malicious fixture that
requested `get_bound_context` forever was stopped after exactly three model
steps; step four was never sent and the request ended with a blocked status.
The fixture also verified that goal tools are absent.

A live `gpt-4o-mini` rerun was not performed in this validation pass because
the restarted local Assistant process had no `OPENAI_API_KEY`. This does not
affect the deterministic launch, binding, proposal, or loop-limit results, but
the original seven-request quality matrix should still be rerun once a key is
configured.

## Live browser follow-up

Date: 2026-09-21
Model: `gpt-4o-mini`

The running browser profile was subsequently tested with a configured live
model. Two fresh component-bound conversations were opened through the real
`/launch/spec` path. No proposal action was clicked.

| Request | Result | Tool calls | Model steps | DSH usage accounting |
|---|---|---:|---:|---:|
| Read bound context and list ports | Correctly returned `clk`, `rst_n`, `data_in`, `valid_in`, and `data_out` with directions and display names. | 1 | 2 | 19.3K tokens |
| Prepare a description-change proposal | Read context, created a valid typed proposal, persisted a `ready` review, and correctly said that explicit review was required. | 2 | 3 | 43.3K tokens |

Neither request entered an autonomous goal or repeated tool loop. The proposal
request legitimately reached the configured three-step limit: context read,
proposal preparation, then final response. The source package remained
unchanged with package SHA-256
`61d2d9cc3a1e0460f0b478fa3ba2378c439959d4b34daeca1b829656d753d228`
and source revision
`sha256:0a71a323d76d2fe7b4ce59ae861fda6f1c6346286f42034f264cd96974a9666e`.

Two UI observations remain:

1. An automation that types immediately when the first composer appears can
   race the launch-time switch from a transient blank session to the reserved
   bound session. The composer is replaced and the draft is lost. Waiting two
   seconds for the bound-session switch avoided the race. Normal human timing
   makes this less likely, but the launch should eventually suppress the
   transient composer entirely.
2. The ready proposal card is rendered correctly, including **Discard** and
   **Approve and apply**, but it is hidden by default inside the collapsed
   **2 tool calls** group. Expanding that group reveals the owner diff and
   review actions. This is functional but makes the most important result easy
   to miss and should be addressed as a presentation improvement.

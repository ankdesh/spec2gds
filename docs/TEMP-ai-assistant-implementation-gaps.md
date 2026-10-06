# TEMP: AI Assistant implementation gaps

Status: temporary code-gap and evidence register. Inspected on 2026-10-05.

The [system contract](ai-assistant.md) defines required behavior. This file records
where the inspected code or tests differ. It is not a second behavior contract.
The documentation replacement does not implement these code changes. Existing
uncommitted code fixes are retained.

Use the [operations guide](ai-assistant-operations.md) for reproduction and the
requirement/test matrix. Keep proposed features in [future work](ai-assistant-future-work.md).
Close a row only after its acceptance cases pass and the corresponding requirement
matches the code. Remove closed rows. Delete this file and its incoming links when
all rows are closed. Git retains the audit history.

## Audit conclusions and approved decisions

The old documents mixed delivered behavior, required behavior, and proposed work.
The audit found direct conflicts and unclear boundaries. These are different:

| Finding | Resolution in the replacement documents |
| --- | --- |
| Main/event guides used the former output cap; another table and the profile used the increased cap. | One configuration table in operations, checked against the profile. |
| “Zero confirmation” acceptance text conflicted with architecture approval. | Architecture decisions are required; automatic content saves have no extra save confirmation. |
| Restricted component details and creation confirmations overlapped with architecture approval. | No repeated confirmation for approved values. Create and continue after architecture approval. |
| Ordinary RTL refinement was exempt from architecture approval. | The accepted policy now requires architecture approval for stored RTL edits. GAP-01. |
| Assistant and Editor both offered Spec content approval. | Browser content approval belongs to Spec Editor only. CLI remains an explicit exception. GAP-02. |
| Error instructions requested correction/retry while the desired behavior stops after failure. | Stop after the first validation failure. Preserve a clear diagnostic. GAP-04/06. |
| Guides described approval of an exact architecture; code checked only part of it. | Keep the exact-plan requirement and record partial enforcement. GAP-05. |
| Creation continuation and Circuit handoff were used near completion language. | Define each phase separately. Saved content needs a saved receipt. GAP-07/13. |
| The UI's dropped-tool list appeared to exclude orchestrated agents. | Generic coding subagents are disabled; permitted standing event members are separate capabilities. This was unclear wording, not proof of a runtime defect. |
| A future optional planning checkpoint overlapped with mandatory architecture review. | The optional checkpoint remains a distinct future idea. It cannot replace architecture approval. |
| Bounded semantic context and a proposed three-tier context design appeared together. | Pagination is the supported contract; three-tier shaping remains proposed. |
| Live catalogue and fallback prompt strings differed on names and output details. | TD-05 removed the duplicate prompt source. Default visibility and explicit hierarchy still need proof in GAP-12. |
| Setup guides implied a pinned bootstrap while setup follows a branch. | Require manual pin verification before supported tests/releases. Pin-enforcing bootstrap remains proposed. |
| Catalogue/replay/fixture results appeared alongside model-quality evidence. | Label each proof scope. Dated raw evidence is retained without a new quality claim. |

Accepted decisions: keep a permanent conversation target; add unqualified new designs to
that document; stop on an explicit other-document request; show safe new-design
defaults; require architecture approval for structure/RTL; approve restricted
content only in Editor or explicit CLI; create after architecture approval without
another confirmation; allow empty creation without architecture; stop after the
first validation failure; keep future proposals separate.

## Open work index

All rows are open. “Confirmed defect” means the inspected path contradicts an
existing identity/state promise. “Policy change” means the accepted contract changed
the previous product rule. “Coverage gap” means code behavior is not yet proved;
absence of a test is not itself proof of failure.

| ID | Class | Requirement | Work |
| --- | --- | --- | --- |
| [GAP-01](#gap-01) | Policy/enforcement change | AS-09/18 | Require architecture for RTL and all supported structural edits. |
| [GAP-02](#gap-02) | Policy/UI change; coverage gap | AS-13/22/29 | Remove Assistant Spec approval; verify Editor decision reconciliation. |
| [GAP-03](#gap-03) | Policy change | AS-10/11/12 | Create/continue after approved architecture under both policies. |
| [GAP-04](#gap-04) | Policy/enforcement change | AS-19/22 | Stop at the first validation failure in every preset. |
| [GAP-05](#gap-05) | Confirmed partial enforcement | AS-10 | Compare the full affected architecture with approval. |
| [GAP-06](#gap-06) | Diagnostic contract gap | AS-20/29 | Uniform failure-stage and mutation-outcome details. |
| [GAP-07](#gap-07) | State presentation/coverage gap | AS-12/24/27 | Distinguish created, continued, pending, failed, and saved content. |
| [GAP-08](#gap-08) | Confirmed dependency conflict | AS-10/12 | Independent new documents must not depend on the old binding. |
| [GAP-09](#gap-09) | Confirmed service-selection conflict | AS-05/11 | Do not replace an explicitly chosen offline service. |
| [GAP-10](#gap-10) | Intent enforcement/coverage gap | AS-04 | Stop other-target requests before authoring bound edits. |
| [GAP-11](#gap-11) | Confirmed label defect; coverage gap | AS-25/29 | Correct writable scope labels; prove close/reopen behavior. |
| [GAP-12](#gap-12) | Prompt/default coverage gap | AS-08/16/18 | Show assumptions; respect explicit hierarchy; align prompt sources. |
| [GAP-13](#gap-13) | Metric/corpus/acceptance gap | AS-21/27/30 | Measure the right stages and verify the revised flow. |

## GAP-01

Requirements: [AS-09](ai-assistant.md#as-09), [AS-18](ai-assistant.md#as-18).

**Architecture approval for RTL and the complete operation vocabulary.**

Evidence: [Spec proposal guard](../ai-assistant/src/tools.ts),
[architecture prompt](../ai-assistant/src/architecture-review.ts), and
[service schema](../spec2gds/spec/spec_format/assistant_operation_schema.json).
The guard has a structural operation allowlist. It does not include
`upsert_entity_section` with `section_type=sv` or deletion of stored RTL.
The prompt explicitly permits later RTL refinements through the ordinary flow.
The section branch uses `upsert_section`/`delete_section`, while the service exposes
`upsert_entity_section`/`delete_entity_section`. A review must also cover parameters
and other supported operations when they affect behavior/interface.

Required result: classify the actual service vocabulary. Require approved architecture
for any stored RTL change and supported structural/behavioral configuration change.
Keep text-only changes exempt. Use the same rule in prompt, tool description, host,
CLI, and tests. Do not infer RTL semantic equivalence to bypass the gate.

Acceptance: automatic and restricted proposals cannot change/create/delete RTL
without approval. An approved fresh review permits the requested change. Test
mixed text/RTL, each relevant operation family, stale review, and text-only SV
byte stability. Extend `architecture-review.test.ts`, `iterative-refinement.test.ts`,
`test_unified_assistant.py`, and native/browser coverage.

## GAP-02

Requirements: [AS-13](ai-assistant.md#as-13), [AS-22](ai-assistant.md#as-22), [AS-29](ai-assistant.md#as-29).

**Editor-only browser content approval and exact receipt updates.**

Evidence: [Assistant ReviewCard](../ai-assistant/client/index.js) offers
**Approve and apply** for Spec. [Host reviewAction](../ai-assistant/src/index.ts)
accepts `apply` and invokes service approval. [Spec Editor history](../circuit-designer/apps/editor/src/App.tsx)
already has Approve/Reject actions. The host's binding-review GET already reads
service applied/discarded receipts and calls `settleReviewedExecution`; this is an
existing reconciliation seam, not a missing API.

Required result: the Assistant shows a pending Spec proposal, details, status,
and an exact-target Editor link. It cannot approve a browser content save. Keep
service/Editor and explicit CLI approval. Preserve Circuit send and safe receipt-only
reconciliation. Editor decisions must update Assistant cards and correlated goal
waits without a second approval or content write.

Acceptance: restricted content remains unchanged before Editor approval. The
Assistant has no Spec approval action. Approve/reject in Editor updates the same
proposal in Assistant, including after reload/restart. Stale approval fails without
mutation. Goal continuation uses the same receipt and remaining budget. Update
restricted/native/browser fixtures that currently click the Assistant button.

## GAP-03

Requirements: [AS-10](ai-assistant.md#as-10), [AS-11](ai-assistant.md#as-11), [AS-12](ai-assistant.md#as-12).

**No extra document creation confirmation after architecture approval.**

Evidence: [Source creation tool and coordinator](../ai-assistant/src/source-creation.ts)
sets `automatic` from service policy, creates immediately only for automatic services,
and returns a creation card for restricted services. [Client creation card](../ai-assistant/client/index.js)
requires **Create specification and continue** in that path. Architecture currently
stores a title/plan but does not establish a complete reviewed destination-name
and service selection contract.

Required result: approve the new document's name, service, intent, and architecture
before creation. Then create/continue under either content-save policy without
another confirmation. Keep restricted content pending for Editor approval. Preserve
creation reservation, collisions, cancellation-before-write, and exact receipts.
The empty-document exception remains supported.

Acceptance: automatic and restricted new documents require one architecture
approval and no creation confirmation. Restricted content still needs Editor
approval. Explicitly empty requests need no architecture review or repeated
creation confirmation under either policy. Reject/revise/cancel architecture
creates no document. A duplicate
creation admission produces one document/conversation. Extend source-creation host/client
and architecture/restricted browser cases. Coordinate with GAP-08/09.

## GAP-04

Requirements: [AS-19](ai-assistant.md#as-19), [AS-22](ai-assistant.md#as-22).

**First validation failure must stop the request.**

Evidence: [Architecture tool instructions](../ai-assistant/src/architecture-review.ts)
ask the model to correct fields before retrying. [Spec tool failures](../ai-assistant/src/tools.ts)
also request repair. [Turn policy](../ai-assistant/src/index.ts) bounds steps but
has no first-validation-failure terminal guard. The native
[architecture runtime fixture](../ai-assistant/tests/architecture-runtime.integration.test.mjs)
currently permits a malformed call followed by a corrected call. The existing
stopped-turn footer preserves the error but does not enforce the new policy.

Required result: after native schema, formatting, architecture, service-schema, or
preview rejection, mark that request stopped and show the error. Block more authoring
calls and goal/event repair continuations for it. Do not confuse an input question
or a replay-safe transport retry with validation repair. A later explicit user retry
can reread and author new content. Receipt-only recovery of uncertain writes remains
possible with exact identities.

Acceptance: one malformed call in each preset causes no second proposal/review
call, service save, or background repair. The diagnostic remains after collapse/reload.
An explicit user retry is admitted separately. Test native schema rejection before
tool execution, in-tool rejection, rejected preview, and token/step exhaustion.
Update the native fixture and event/goal cases, not just the prompt assertion.

## GAP-05

Requirements: [AS-10](ai-assistant.md#as-10).

**Approved architecture is only partly checked.**

Evidence: [validateArchitectureOperations](../ai-assistant/src/architecture-review.ts)
loops over `create_entity` component/design operations. It checks included names
and initial component ports/directions/widths. It does not compare existing-target
port changes, deletions, instance/connection edits, internal-design ownership,
or other affected structure with the plan. Review validity in
[state.ts](../ai-assistant/src/state.ts) does check status, binding, and revision.
The plan itself has no typed complete topology/change representation.

Required result: capture the affected baseline and approved structure/change,
then compare the candidate's affected typed structure. Preserve service semantic
validation as another check. Capture intended RTL behavior and report its relationship
to the approved intent; do not claim automatic functional equivalence. Do not accept
any structural operation merely because an unrelated approved review exists.

Acceptance: unchanged approved structure passes; altered existing port, unapproved
target deletion, changed child reference/connection, extra hierarchy, or wrong service
fails. Test atomic mixed proposals and old reviewed revisions. Extend architecture
and iterative fixtures with edits to existing targets, not only creation.

## GAP-06

Requirements: [AS-20](ai-assistant.md#as-20), [AS-29](ai-assistant.md#as-29).

**One diagnostic contract for all failure paths.**

Evidence: [ProposalError](../ai-assistant/src/types.ts) and
[proposal presentation](../ai-assistant/src/proposal-presentation.ts) have codes,
target, details, retryability, issues, service diagnostics, and correlation ID.
They do not have a consistent failure-stage/mutation-outcome record. Architecture
and creation often return plain `creation_error`; native schema errors occur outside
that envelope. Some suggested-action arrays are empty. Existing client regression
coverage retains these errors but does not supply all investigation details.

Required result: preserve one structured diagnostic for native and product failures.
Include tool/field or operation, failed stage, exact request/binding, prompt version,
schema digest, and known write outcome. Lead with plain text and a useful next action.
A missing optional datum must be explicit; do not invent it. Preserve original service
messages and distinguish suspected cause from proven cause. Export redacted details.

Acceptance: schema, context, formatting, architecture, preview, save, creation,
continuation, and limit failures show their actual stage and identity. A stopped
turn has the same diagnostic after reload. The saved/unchanged/uncertain result is
correct. Cover absence of a proposal record and ensure no credential exposure.

## GAP-07

Requirements: [AS-12](ai-assistant.md#as-12), [AS-24](ai-assistant.md#as-24), [AS-27](ai-assistant.md#as-27).

**Document-created is not content-saved.**

Evidence: [SourceCreationRequest](../ai-assistant/src/types.ts) and
[creation coordinator](../ai-assistant/src/source-creation.ts) persist creation,
reservation, and `continued`. `continued` acknowledges admission into the destination
conversation, not service content application. [Client continuation](../ai-assistant/client/index.js)
opens that conversation. Content proposal receipts are separate. Existing tests cover saved
`.spec` file/conversation setup recovery, but do not prove all content-failure/restart presentations.

Required result: derive visible progress from both creation and content records.
Show created-but-empty, content pending, content failed, or content saved accurately.
Retain the original request, destination, and last confirmed phase. A failed population
request stops. User retry must use the same saved document, not another creation.
An independent creation receipt must not complete a goal requesting saved content.

Acceptance: lose conversation setup after `.spec` file save; fail initial content validation;
reject/stale the restricted content; lose an applied response; reload/restart at
these boundaries. Assert one document/conversation, correct pending/failure state, exact
saved receipt, and no duplicate population write. Extend full service browser and
source-creation/native cases.

## GAP-08

Requirements: [AS-10](ai-assistant.md#as-10), [AS-12](ai-assistant.md#as-12).

**Review purpose and source dependencies are not explicit.**

Evidence: [Architecture capture](../ai-assistant/src/architecture-review.ts)
reads and pins the current Spec binding whenever one exists.
[SourceCreations.prepare](../ai-assistant/src/source-creation.ts) reads it again
for approved-architecture creation. This blocks independent document B if unrelated
A is offline or changes. Meanwhile the creation prompt says a new document needs
no existing context. The record has source/destination fields but no explicit
independent-versus-derived purpose/dependency contract.

Required result: distinguish editing the bound document, creating an independent
document, and creating a document derived from that source. Only an actual source
dependency needs a fresh A read and pins A's revision. Review the new name/service before
its independent creation. Keep the source conversation immutable and record the approved
creation destination. Document any new metadata/tool fields when the API is designed;
do not silently reinterpret existing fields.

Acceptance: independent B succeeds from an unavailable A conversation after human review;
derived B fails when its required A source is unavailable/stale. A's identity and
pending proposals are unchanged. Test document/Component or Design scopes and exact destination
review transfer. Coordinate with GAP-03/05/09.

## GAP-09

Requirements: [AS-05](ai-assistant.md#as-05), [AS-11](ai-assistant.md#as-11).

**An explicit offline service can be replaced silently.**

Evidence: [SourceCreations.prepare](../ai-assistant/src/source-creation.ts) tries an
available `preferredOwner`, then falls back to another available service. The model
creation tool has no explicit service-selection field; the restricted card can select
one, which will no longer be an extra confirmation under the accepted policy.

Required result: distinguish an explicit selection from absence of a selection.
Keep an explicit service even when offline and report its failure. With several
possible services and no selection, obtain the choice before approving/creating.
Do not change the reviewed service after approval. Pin the selected URL in the
creation record and reuse it during recovery.

Acceptance: configure two Spec services, select offline A, keep B available, and assert
no B request or document. Selecting B explicitly uses B. An unavailable selected
service remains A after reload/retry. Test root unbound and bound creation.

## GAP-10

Requirements: [AS-04](ai-assistant.md#as-04).

**Binding safety does not prove request-intent safety.**

Evidence: [Binding prompt](../ai-assistant/profile/catalog/prompts/spec.yaml)
assigns unqualified references to the bound target and says never ask which document
is meant. Exact binding/service guards protect keyed writes. They cannot by themselves
detect that operations valid for A were authored for a user request naming B.
The old lifecycle guide proposed an automatic target-selection handoff; that proposal
was rejected in favor of explaining the mismatch and stopping.

Required result: distinguish unqualified edits, new-document creation, scope ambiguity,
and explicit other-document edits. Stop an explicit B edit before authoring A
operations. Do not add automatic cross-target routing. “Create a counter” uses the
bound document when document scope is clear. Scope ambiguity can ask a question.

Acceptance: send unqualified creation, explicit B edit, visible-editor-B request,
Component or Design scope top-level creation, duplicate titles/IDs, and unavailable-target requests.
Assert the selected intent and zero wrong-target authoring/save. Existing API binding
tests are partial; add native language-intent and browser cases.

## GAP-11

Requirements: [AS-25](ai-assistant.md#as-25), [AS-29](ai-assistant.md#as-29).

**Writable scope label and lifecycle evidence.**

Evidence: [Editor launch notice](../circuit-designer/apps/editor/src/App.tsx)
calls a document Assistant conversation “read-only”, although document proposals support
service-authorized edits. Native archive/tab close and execution controls are separate;
there is no product close-to-stop hook. Card tests cover reload, but full pending
architecture/proposal and running-execution close/reopen behavior is not established.

Required result: show the actual scope and save policy. Closing/archiving must not
approve, discard, cancel a write, or silently stop execution. On reopen, restore
pending/running status and last confirmed receipts. Preserve explicit Pause, Stop,
Cancel, and service reject behavior as different actions.

Acceptance: correct document/target launch notices. Close/reopen or archive/restore
with pending architecture, pending restricted content, and active persistent work.
Inspect source bytes, receipts, waits, and execution state. A stopped execution must
not resume by reopening. Use full native-shell browser coverage for these controls.

## GAP-12

Requirements: [AS-08](ai-assistant.md#as-08), [AS-16](ai-assistant.md#as-16), [AS-18](ai-assistant.md#as-18).

**Default visibility, explicit hierarchy, and prompt agreement need proof.**

Evidence: the [catalogue architecture guidance](../ai-assistant/profile/catalog/instructions.json)
prefers cohesive counters. It has no explicit clause that designer-requested hierarchy
wins over that general preference. TD-05 removed the divergent TypeScript prompt
copies. Production and deterministic tests now read the same catalogue. Snapshot
and native-schema checks verify this structure; they do not prove model accuracy.
Details/default logic exists in the [Spec execution module](../ai-assistant/src/tools/prepare_spec_proposal.ts),
but the full accepted clarification/default policy is not measured by those fixtures.
The duplicate-source part passed TD-05 regression verification and is removed
from this gap. The hierarchy and default-visibility parts remain open.

Required result: prove that catalogue guidance follows the contract. Show each material
new-design default in the review. Ask about unresolved existing behavior. Respect
explicit hierarchy, preserve unrelated authored text, and avoid repeated confirmation
of approved values. Keep authoritative IDs in artifacts and readable names in UI.
A safe-default catalogue is optional future work; it is not required to close this row.

Acceptance: explicit control/register counter hierarchy is preserved; an unqualified
cohesive counter can remain a leaf. Test missing new reset/overflow defaults, ambiguous
existing widths/protocols, text-only requests, and exact same-batch descriptions.
Compare the actual native prompt/tool request, not only static instruction checks.

## GAP-13

Requirements: [AS-21](ai-assistant.md#as-21), [AS-27](ai-assistant.md#as-27), [AS-30](ai-assistant.md#as-30).

**Metrics, corpus, and browser expectations need contract alignment.**

Evidence: [evaluate.mjs](../ai-assistant/scripts/evaluate.mjs) validates catalogue
shape/fixtures and writes `catalogued`; it does not execute semantic assertions.
[Metrics](../ai-assistant/src/eval-metrics.ts) count structured `success` results
without associating each result with its proposal call. First-preview readiness
counts `ready`, so an automatically applied first proposal is excluded. False
completion counts only explicit failed assertion events. Applied/sent operations
are combined. Corpus cases retain `ready`/no-mutation-before-action expectations.
[UI scenarios](../tests/ui-scenarios/runner/run_scenario.ts) use separate test limits
and currently approve restricted content through the Assistant.

Required result: correlate proposal calls/results, distinguish preview pass from
pending/applied state, and measure handoff separately from saved source. Record whether
completion assertions were executed. Keep catalogue checks distinct from actual
case execution and live inference. Align fixture outcomes and browser decisions with
the accepted policy. Record actual limits and prompt/schema versions. Do not turn
unapproved numeric quality targets into release gates.

Acceptance: use recorded automatic/restricted/rejected/stale results and unrelated
successful tools to check counters. Test sent-but-rejected and sent-but-source-save-failed
outcomes without claiming completion. Execute deterministic final-service-state assertions
for the required scenarios. Mark missing live/toolchain checks unverified. Extend
metric tests, the corpus, and restricted/browser/evaluation fixtures. A new general
conversation simulator remains proposed; existing deterministic tests can provide
these required assertions.

## Implementation sequence

1. Define the uniform diagnostic and first-failure stop path (GAP-06/04).
2. Align architecture triggers, review contents, and full plan checks (GAP-01/05/08).
3. Apply the reviewed creation/service rules (GAP-03/09).
4. Remove Assistant content approval and verify Editor receipt/wait updates (GAP-02).
5. Finish intent, state presentation, prompt, and lifecycle checks (GAP-07/10/11/12).
6. Update acceptance fixtures and metrics alongside each change; close GAP-13 after
   the revised scenarios and stage measurements agree.

This order is a suggested implementation sequence, not permission to merge unrelated
changes. Each code change must cite its requirement and regression. Do not mark a
row complete from a prompt edit, a passing old fixture, or a model success sentence.

## Documentation verification

Checked on 2026-10-05:

- Local Markdown targets and heading anchors passed. No active reference points
  to a removed guide. The deletion inventory below is intentional.
- All 30 stable requirement IDs have acceptance rows. All 13 open gaps have
  requirement references, code evidence, required results, and acceptance cases.
- All four JSON examples passed the registered native tool schemas. The counter
  operations passed the Spec service schema before and after alias normalization.
  The normalized proposal passed the actual service semantic preview in memory.
- The architecture example passed prepare/approve and plan matching in temporary
  state. Proposal rebuilding preserved the same persistent IDs and typed references.
- Hash checks confirmed that the earlier code/test fixes, research, and raw evidence
  were unchanged. This task changed documentation only.

No live provider or developer service was called. The full runtime, browser, live-model,
and RTL functional suites were not run for this documentation change. Schema/example
checks do not close runtime gaps or establish model quality.

## Explicit deletion list

The following files were removed on 2026-10-05. This is an inventory, not a list
of active references. Git retains their history. Useful requirements, commands,
and proposed work were transferred to the four guides. Raw research and test
evidence were kept.

| Removed file | Content destination |
| --- | --- |
| `docs/assistant-acceptance-tests.md` | Operations: verification commands and acceptance matrix |
| `docs/assistant-document-lifecycle.md` | Contract: binding, creation, recovery, and close/cancel rules |
| `docs/assistant-hierarchical-spec-evaluation.md` | Operations: live-model evidence limits; raw evidence retained |
| `docs/assistant-hierarchical-spec-integration.md` | Contract: hierarchy and stored RTL authority |
| `docs/assistant-owner-operation-contract.md` | Contract: live schema, normalization, identity, and tool examples |
| `docs/assistant-spec-creation.md` | Contract: architecture, document creation, and separate outcomes |
| `docs/assistant-ui.md` | Contract: UI decisions and status; TEMP: current UI gaps |
| `docs/ai-assistant-evaluation.md` | Operations: evaluation commands and evidence limits |
| `docs/ai-assistant-improvement-plan.md` | Future work: unaccepted proposals; TEMP: accepted gaps |
| `docs/ai-assistant-integration-issues.md` | TEMP: current gaps; future work: unaccepted integration proposals |
| `docs/configurable-assistant-architecture.md` | Contract: presets, events, capabilities, and persistence |
| `docs/agentic-systems-architecture-report.md` | Contract: responsibilities and execution; future work: proposed extensions |
| `docs/event-driven-assistant-system.md` | Contract: event contracts and state; operations: configuration limits |
| `docs/event-driven-assistant-operations.md` | Operations: configuration, recovery, and test commands |
| `docs/event-driven-assistant-tutorial.md` | Operations: browser setup, flows, and checks |
| `docs/harness-setup-troubleshooting.md` | Operations: source setup, pin checks, and setup diagnosis |
| `docs/spec-workspace-cli.md` | Operations: headless CLI and approval commands |
| `ai-assistant/docs/architecture.md` | Contract: system boundaries; operations: source map |
| `tests/ui-scenarios/create_spec_and_component.md` | Operations: creation flow and isolated browser commands |

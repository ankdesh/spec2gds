# Flow implementation evidence, 10 October 2026

This record covers the reusable Harness flows and the removal of legacy Assistant
Spec mutation paths. The complete implementation is still under verification.
A completed flow requires its declared receipt. Acceptance and a created file are
separate outcomes.

## Breaking Spec interface change

The following model tools and their handlers are removed:

- `prepare_spec_document_creation`
- `prepare_architecture_review`
- `prepare_spec_proposal`

The browser no longer sends document-creation continuation messages. It cannot
save or discard a Spec proposal through the Assistant. The old creation request
routes and architecture continuation route are removed. Direct Spec creation and
old Assistant Spec review actions are rejected. A context refresh cannot restore
a Spec mutation tool. Old pending Spec requests have no compatibility path.
The Python review bridge is read-only. Spec CLI approval, rejection and architecture
decision commands are removed. The Assistant CLI requires an existing Spec and
returns a correlated flow wait; it cannot create a file before starting a flow.
It requires an explicitly selected running Spec service so the service remains
available after the CLI exits. The selected service determines the content policy.

Focused and Goal use four published tools: `flow_create_empty_spec`,
`flow_create_spec_with_component`, `flow_add_component`, and `flow_edit_spec`.
Selected Component and Design conversations use the edit flow for existing
content. Adding a new leaf Component requires a document binding. Orchestrated
Spec conversations support reads and analysis. Circuit proposal controls remain
in their own domain.

Legacy proposal details are restricted to Circuit bindings; Spec details inputs
are rejected without changing their stored values under both content policies.

The generic product start adapter selects an eligible published flow and requires
a stable request ID. Controls and architecture decisions require the observed
execution revision. Spec Editor decides restricted content proposals; the host
reads the exact service receipt. Review-history reads do not advance Spec work.

Spec definitions and operations use version `2.0.0`. Instruction handler
compatibility is `2`. Incompatible old releases stop explicitly. Existing saved
files are retained.

## Validation changes

Spec model phases receive dedicated pinned instructions and their result schema.
They cannot use domain tools. Missing or invalid typed results end the attempt.
There is no automatic correction request.

The edit flow checks the current operation schema and authored revision. Structural
approval covers the exact normalized operation batch. Conflicting set and clear
values are rejected before submission. Context pages must carry the complete page
contract, exact binding scope and one revision. Repeated cursors stop execution.
Creation receipts must identify the saved path, service document key and revision.
The flow view distinguishes confirmed creation from an incomplete content request.
Document-scope edits can create a complete Design from existing Components in one
reviewed atomic batch. The approval dock follows the native content width so its
controls do not overlap the conversation resize handles.

The Spec profile allows 8 MiB of retained execution data and 1,000,000 tokens.
The token limit covers the actual native request envelope, including retained
conversation history. Each attempt keeps its declared request and output limits.
A reservation rejection now reports its budget cause before provider access.

## Executed checks

| Command or check | Result | Evidence |
| --- | --- | --- |
| Assistant `npm test` after removal and fixes | 146 passed | `/tmp/spec-flow-removal-final-units-local.log` |
| Assistant `npm run build` | Passed | `/tmp/spec-flow-creation-view-build.log`, `/tmp/spec-flow-final-build4.log` |
| Final flow-only edit and removed-route checks | 2 passed under both policies | `/tmp/spec-flow-no-fallback-final-integration-fixed.log` |
| Native flow and architecture integration | 17 passed; browser dependency prerequisites then corrected and its focused test passed | `/tmp/spec-flow-final-native-integration.log`, `/tmp/spec-flow-browser-close-fixed.log` |
| Shared profile Harness integration | 21 passed; one old page fixture failed and was corrected | `/tmp/spec-flow-only-shared-20261010/harness/command.log` |
| Automatic browser flow scenario | Passed | `/tmp/spec-flow-browser-automatic-current` |
| Restricted browser flow scenario | Passed | `/tmp/spec-flow-browser-restricted-current2` |
| Earlier `scripts/test-all.sh fast` | Passed before the final CLI migration, including all three live checks | `/tmp/spec-flow-only-fast-current-20261010/summary.html` |
| `scripts/test-all.sh integration --scope shared` | Failed; retains original pre-fix outcomes and unrelated browser failures | `/tmp/spec-flow-only-shared-20261010/summary.html` |
| Flow-only Python CLI and direct bridge rejection checks | 20 passed | `/tmp/spec-flow-cli-direct-bridge-final.log` |
| Receipt history and CLI boundary checks | 30 passed after the Editor build settled | `/tmp/spec-flow-cli-history-after-build.log` |
| Extensive Python Spec checks | 3 passed before the final running-service option; both policy cases also passed afterward | `/tmp/spec-flow-cli-extensive-final.log` |
| Spec-to-Circuit presentation through explicit flows | Passed | `/tmp/spec-flow-design-presentation-current` |
| Architecture revise and cancel browser controls | Passed | `/tmp/spec-flow-architecture-layout-current` |
| Large automatic-policy proposal and edit | Passed; restricted path then fixed for token budget | `/tmp/spec-flow-large-proposal-current.log` |
| Large restricted-policy proposal, discard and stale checks | Passed | `/tmp/spec-flow-large-restricted-budget-fixed` |
| Native reservation and receipt-integrity regressions | 11 passed; closed conversations also require matching persisted receipts | `/tmp/dsh-flow-receipt-fracture-fixed.log` |
| `scripts/test-all.sh regression` | Running; its Python CLI result preceded the CLI migration | `/tmp/spec-flow-only-regression-20261010/summary.html` |
| Harness focused compiler, runtime, YAML, native, tool, UI, accounting and SDK tests | 83 passed in 10 files | `/tmp/dsh-flow-focused-current.log` |
| Harness `hygiene` | 16 gates passed | `/tmp/dsh-flow-hygiene-current.log` |
| Harness `doc-sync` | 39 passed; two documentation failures corrected through their focused gates | `/tmp/dsh-flow-doc-sync-current.log` |
| Harness translation pairing | 941 pairs passed after correction | `/tmp/dsh-flow-pairs-verified.log` |
| Harness Markdown wrapping | 1,897 files passed after correction | `/tmp/dsh-flow-wrap-verified.log` |

Earlier failed fast runs are retained. They exposed omitted operation output,
general prompt interference, empty architecture configuration, and conflicting
metadata clear instructions. The live fast checks use saved source and uses Spec
Editor for restricted decisions. It does not use fixture model responses.

## Coverage and remaining release work

The final regression result, package closure and Harness pin,
and final source review remain required. Earlier broad profile evidence does not
validate the breaking removal. Live checks provide observed outcomes, not a
claim that every model response will succeed.

The previous focused coverage run did not meet the repository's per-file 100%
coverage gate. The new flow-specific recorded-session scenario and whole-process
cold recovery around a Spec save also remain gaps. Current recovery evidence
covers independent native receipt integrity, real persistence and lost service responses before and after dispatch.
A cached dependency composition was used after the earlier registry install
failed; a clean dependency install is not verified.

The later fast profile retained a failed receipt-history test before its correction.
All three live checks in that run passed. The next fast profile passed all other
suites but failed the live wire edit because the model copied snapshot-only
`style` and `packed` fields. That result is retained in
`/tmp/spec-flow-only-fast-history-verified-20261010`. Exact-key prompt instructions
and deterministic schema rejection protection were added. The changed prompt
passed a separate live check in `/tmp/spec-flow-wire-explicit-keys-live`.
Direct history and CLI checks pass after their correction. The broad regression
preserves its earlier CLI failure; the migrated CLI checks pass separately.

Broad live RTL evaluation has observed invalid carry-in widths. The service
rejected these drafts before Component save; the created empty Spec remains.
Explicit operand-width instructions were added, but a following adder check still
failed width validation. This is a release limitation, not a functional pass.
Evaluation now stops promptly with the flow diagnostic, requires successful
receipt-backed completion, and opens the confirmed bound conversation before
description refinement. No automatic repair or legacy
proposal fallback was added.

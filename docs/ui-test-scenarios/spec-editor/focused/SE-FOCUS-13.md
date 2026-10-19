# SE-FOCUS-13: Cancel and confirm SystemVerilog deletion

## Case contract

- Application: **Spec Editor**.
- Intended executor: **Playwright in a later implementation pass**. This file is a detailed specification, not an implemented automated check.
- Priority: source/identity protection is mandatory; visual and interaction quality is separately rated.
- Estimated effort: 10–25 minutes to inspect manually after fixture setup; future automation runtime must be measured.
- Regression scope: `spec`.
- Future profile selection: affected `integration --scope spec` and full `regression`.
- Fast suitability: candidate: deletion/Section cardinality units; browser confirmation in integration. This document changes no profile selection.
- Future layer: browser for rendered actions; add lower-layer state/contract protection only where it reliably detects the same defect.
- Inputs: [complete focused fixtures](../../inputs/focus-fixtures.md), including all linked leaf/composite packs.
- Additional direct input references: the exact interface/snippets in this case and the focused fixture pack.

## Exact setup

Use F-A. Record the Component ID, explanation, five ports, and SV body. This case intentionally ends with an interface-only Component.

Use fresh isolated source/storage and dedicated service bindings. Future setup
may seed prerequisites through existing public real-service fixtures. It must
not perform or fake the UI operation under assessment. A missing required UI
capability remains a failed acceptance criterion; do not silently skip it.

## Actions, observable assertions, and evidence

| Step | Designer action | Expected visible result | Evidence to retain |
| ---: | --- | --- | --- |
| 1 | Prepare the exact isolated starting fixture below. Record its identities and saved source/graph before the action. | The starting state matches the fixture and is separate from other cases; setup has not already performed the behavior under test. | Fixture, initial screenshot, source/graph inventory, and active binding. |
| 2 | Choose the SV Section Delete action and cancel the confirmation. | The body remains visible and saved with unchanged text. | Step 2 screenshot/recording and observable state. |
| 3 | Choose Delete again and confirm. | Only the optional SV Section disappears; Component, explanation, and five ports remain. | Step 3 screenshot/recording and observable state. |
| 4 | Reopen the Spec and inspect all remaining Sections. | The deletion persists without deleting the Component or unrelated source. The UI must not imply that a functional adder implementation still exists. | Step 4 screenshot/recording and observable state. |
| 5 | Inspect the final visible state and saved result specified below; record ratings and any missing capability. | The same Component with its explanation and interface, intentionally without an SV Section. No successful functional generation is claimed. | Final screenshot, relevant read-only service/archive comparison, and criterion ratings. |

## Expected final Spec and Circuit

The same Component with its explanation and interface, intentionally without an SV Section. No successful functional generation is claimed.

Keep all unmentioned source Sections, definition references, instance IDs, and
connections unchanged. If this is an interface-only or intentionally incomplete
fixture, do not infer functional RTL success. For any explicitly required
generation step, obtain the actual saved-target project through the UI and run
its published `make lint`; keep simulation marked unverified.

## Automation-ready assertions

The body remains visible and saved with unchanged text. Only the optional SV Section disappears; Component, explanation, and five ports remain. The deletion persists without deleting the Component or unrelated source. The UI must not imply that a functional adder implementation still exists.

Use semantic roles/labels and stable item references. Assert the visible result
and the relevant real saved data. Use condition-based waits rather than sleeps.
Collect unexpected console/network failures, screenshots, and a retained trace
on failure. Narrowly identify expected rejection/cancellation events; no blanket
error suppression. For delayed-response cases, control read delivery without
mocking successful writes. Preserve the original failing evidence on reruns.

## Weighted criteria

| Criterion ID | Observable criterion | Weight | Mandatory | Rating kind | Required evidence |
| --- | --- | ---: | --- | --- | --- |
| SE-FOCUS-13-C01 | The protected source, identity, graph, or draft identified in setup survives the failed/cancelled operation: The same Component with its explanation and interface, intentionally without an SV Section. No successful functional generation is claimed. | 40 | yes | 0 or 4 | Before/after saved-state and identity comparison. |
| SE-FOCUS-13-C02 | The attempted operation is rejected, cancelled, or isolated exactly as specified: The body remains visible and saved with unchanged text. | 25 | yes | 0 or 4 | Browser action and rejection/state evidence. |
| SE-FOCUS-13-C03 | The case-specific recovery or final valid operation completes without a hidden bypass: The deletion persists without deleting the Component or unrelated source. The UI must not imply that a functional adder implementation still exists. | 20 | yes | 0 or 4 | Recovery recording and reopened result. |
| SE-FOCUS-13-C04 | The user can identify the affected operation, retained state, and next action; feedback and focus do not hide the failure. | 15 | no | 0–4 | Visible feedback/focus and rationale for partial ratings. |

Use [scoring rules](../../SCORING.md). Weights total 100. Mandatory failures
remain failures regardless of partial visual/usability credit.

### Partial-credit anchors for this check

The concrete result under review is: The same Component with its explanation and interface, intentionally without an SV Section. No successful functional generation is claimed.
For qualitative feedback/readability criteria, rating 2 means this result can
be understood only after substantial extra inspection; rating 3 means it is
clear with one minor local wording, focus, or spacing issue; rating 4 means the
result and next action are clear in every requested view. Rating 1 means severe
confusion or obstruction; rating 0 means absent or incorrect feedback/content.
Objective data, availability, rejection, and persistence checks remain binary.

## Result fields

Copy the [run template](../../RUN-TEMPLATE.md) into the run directory and fill it
for `SE-FOCUS-13`. Record run ID, code revision, browser/version, theme, window size,
actual Spec path, source revision if exposed, ratings for every criterion,
mandatory failures, capability gaps, evidence links, and verification limits.
Default result: **unrun**. Do not prefill a passing score from this casebook.
Functional simulation: **unverified**.

Return to the [catalogue](../../README.md).

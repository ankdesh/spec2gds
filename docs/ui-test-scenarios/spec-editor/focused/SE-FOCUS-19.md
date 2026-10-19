# SE-FOCUS-19: Publish RTL generation status and correct artifacts

## Case contract

- Application: **Spec Editor**.
- Intended executor: **Playwright in a later implementation pass**. This file is a detailed specification, not an implemented automated check.
- Priority: source/identity protection is mandatory; visual and interaction quality is separately rated.
- Estimated effort: 10–25 minutes to inspect manually after fixture setup; future automation runtime must be measured.
- Regression scope: `spec,activities`.
- Future profile selection: affected `integration --scope spec,activities` and full `regression`.
- Fast suitability: integration only: real Activity and compiler evidence. This document changes no profile selection.
- Future layer: browser for rendered actions; add lower-layer state/contract protection only where it reliably detects the same defect.
- Inputs: [complete focused fixtures](../../inputs/focus-fixtures.md), including all linked leaf/composite packs.
- Additional direct input references: the exact interface/snippets in this case and the focused fixture pack.

## Exact setup

Use F-A and the actual rtl.generate Activity. No live model is needed. The Activity scratch root and all downloads are beneath the temporary run directory.

Use fresh isolated source/storage and dedicated service bindings. Future setup
may seed prerequisites through existing public real-service fixtures. It must
not perform or fake the UI operation under assessment. A missing required UI
capability remains a failed acceptance criterion; do not silently skip it.

## Actions, observable assertions, and evidence

| Step | Designer action | Expected visible result | Evidence to retain |
| ---: | --- | --- | --- |
| 1 | Prepare the exact isolated starting fixture below. Record its identities and saved source/graph before the action. | The starting state matches the fixture and is separate from other cases; setup has not already performed the behavior under test. | Fixture, initial screenshot, source/graph inventory, and active binding. |
| 2 | Choose the saved add32 target, select Verify Component and require Lint passed for the saved revision, then Options → Generate RTL, and observe status through completion without refreshing the page. | Running and terminal states identify the same target and saved revision; the artifact list refreshes after completion. | Step 2 screenshot/recording and observable state. |
| 3 | Obtain the full published project through the UI and inspect manifest, module interface, and body. | The exact five-port add32 interface and complete 33-bit implementation are present; no output tie-off substitutes for the body. | Step 3 screenshot/recording and observable state. |
| 4 | Run the project make lint and reopen the Spec. | Lint exits zero without unexpected diagnostics; generation did not alter source content or identity. | Step 4 screenshot/recording and observable state. |
| 5 | Inspect the final visible state and saved result specified below; record ratings and any missing capability. | A traceable UI-generated project and lint log bound to the original saved add32 Spec, with current artifacts visible without reconnect. | Final screenshot, relevant read-only service/archive comparison, and criterion ratings. |

## Expected final Spec and Circuit

A traceable UI-generated project and lint log bound to the original saved add32 Spec, with current artifacts visible without reconnect.

Keep all unmentioned source Sections, definition references, instance IDs, and
connections unchanged. If this is an interface-only or intentionally incomplete
fixture, do not infer functional RTL success. For any explicitly required
generation step, obtain the actual saved-target project through the UI and run
its published `make lint`; keep simulation marked unverified.

## Automation-ready assertions

Running and terminal states identify the same target and saved revision; the artifact list refreshes after completion. The exact five-port add32 interface and complete 33-bit implementation are present; no output tie-off substitutes for the body. Lint exits zero without unexpected diagnostics; generation did not alter source content or identity.

Use semantic roles/labels and stable item references. Assert the visible result
and the relevant real saved data. Use condition-based waits rather than sleeps.
Collect unexpected console/network failures, screenshots, and a retained trace
on failure. Narrowly identify expected rejection/cancellation events; no blanket
error suppression. For delayed-response cases, control read delivery without
mocking successful writes. Preserve the original failing evidence on reruns.

## Weighted criteria

| Criterion ID | Observable criterion | Weight | Mandatory | Rating kind | Required evidence |
| --- | --- | ---: | --- | --- | --- |
| SE-FOCUS-19-C01 | The main browser action produces the exact visible result: Running and terminal states identify the same target and saved revision; the artifact list refreshes after completion. | 35 | yes | 0 or 4 | Action recording and first result. |
| SE-FOCUS-19-C02 | The final data and identities match this case contract: A traceable UI-generated project and lint log bound to the original saved add32 Spec, with current artifacts visible without reconnect. | 30 | yes | 0 or 4 | Final visible and authoritative state. |
| SE-FOCUS-19-C03 | Status, labels, selection, and focus make the case-specific result clear without misleading completion messages. | 15 | no | 0–4 | Feedback and focus screenshots; partial-rating explanation. |
| SE-FOCUS-19-C04 | The specified reopen, recovery, or final-state inspection succeeds: Lint exits zero without unexpected diagnostics; generation did not alter source content or identity. | 20 | yes | 0 or 4 | Final step evidence and unchanged unrelated data. |

Use [scoring rules](../../SCORING.md). Weights total 100. Mandatory failures
remain failures regardless of partial visual/usability credit.

### Partial-credit anchors for this check

The concrete result under review is: A traceable UI-generated project and lint log bound to the original saved add32 Spec, with current artifacts visible without reconnect.
For qualitative feedback/readability criteria, rating 2 means this result can
be understood only after substantial extra inspection; rating 3 means it is
clear with one minor local wording, focus, or spacing issue; rating 4 means the
result and next action are clear in every requested view. Rating 1 means severe
confusion or obstruction; rating 0 means absent or incorrect feedback/content.
Objective data, availability, rejection, and persistence checks remain binary.

## Result fields

Copy the [run template](../../RUN-TEMPLATE.md) into the run directory and fill it
for `SE-FOCUS-19`. Record run ID, code revision, browser/version, theme, window size,
actual Spec path, source revision if exposed, ratings for every criterion,
mandatory failures, capability gaps, evidence links, and verification limits.
Default result: **unrun**. Do not prefill a passing score from this casebook.
Functional simulation: **unverified**.

Return to the [catalogue](../../README.md).

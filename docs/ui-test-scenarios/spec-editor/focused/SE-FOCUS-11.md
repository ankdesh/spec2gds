# SE-FOCUS-11: Add and edit a SystemVerilog Section

## Case contract

- Application: **Spec Editor**.
- Intended executor: **Playwright in a later implementation pass**. This file is a detailed specification, not an implemented automated check.
- Priority: source/identity protection is mandatory; visual and interaction quality is separately rated.
- Estimated effort: 10–25 minutes to inspect manually after fixture setup; future automation runtime must be measured.
- Regression scope: `spec`.
- Future profile selection: affected `integration --scope spec` and full `regression`.
- Fast suitability: candidate: Section state units; integration for browser persistence. This document changes no profile selection.
- Future layer: browser for rendered actions; add lower-layer state/contract protection only where it reliably detects the same defect.
- Inputs: [complete focused fixtures](../../inputs/focus-fixtures.md), including all linked leaf/composite packs.
- Additional direct input references: the exact interface/snippets in this case and the focused fixture pack.

## Exact setup

Create Component Pass-through body fixture with a: in, 7:0 and y: out, 7:0. Initial body assign y = a;. Revised body assign y = a ^ 8'hFF;. Explanation explicitly says the final revision inverts each input bit.

Use fresh isolated source/storage and dedicated service bindings. Future setup
may seed prerequisites through existing public real-service fixtures. It must
not perform or fake the UI operation under assessment. A missing required UI
capability remains a failed acceptance criterion; do not silently skip it.

## Actions, observable assertions, and evidence

| Step | Designer action | Expected visible result | Evidence to retain |
| ---: | --- | --- | --- |
| 1 | Prepare the exact isolated starting fixture below. Record its identities and saved source/graph before the action. | The starting state matches the fixture and is separate from other cases; setup has not already performed the behavior under test. | Fixture, initial screenshot, source/graph inventory, and active binding. |
| 2 | Use Options → Add SystemVerilog section… and save the initial body. | One body-only SystemVerilog Section appears and contains the initial assignment. | Step 2 screenshot/recording and observable state. |
| 3 | Use the Section Edit action to replace it with the revised body; Save to Spec. | The same logical Section contains the inversion expression and no module header or duplicate Section. | Step 3 screenshot/recording and observable state. |
| 4 | Reopen and inspect the final body and explanation. | The inversion body and its revised explanation persist; the two-port interface remains unchanged. | Step 4 screenshot/recording and observable state. |
| 5 | Inspect the final visible state and saved result specified below; record ratings and any missing capability. | One complete eight-bit inversion body with a consistent explanation and no duplicate SV Section. | Final screenshot, relevant read-only service/archive comparison, and criterion ratings. |

## Expected final Spec and Circuit

One complete eight-bit inversion body with a consistent explanation and no duplicate SV Section.

Keep all unmentioned source Sections, definition references, instance IDs, and
connections unchanged. If this is an interface-only or intentionally incomplete
fixture, do not infer functional RTL success. For any explicitly required
generation step, obtain the actual saved-target project through the UI and run
its published `make lint`; keep simulation marked unverified.

## Automation-ready assertions

One body-only SystemVerilog Section appears and contains the initial assignment. The same logical Section contains the inversion expression and no module header or duplicate Section. The inversion body and its revised explanation persist; the two-port interface remains unchanged.

Use semantic roles/labels and stable item references. Assert the visible result
and the relevant real saved data. Use condition-based waits rather than sleeps.
Collect unexpected console/network failures, screenshots, and a retained trace
on failure. Narrowly identify expected rejection/cancellation events; no blanket
error suppression. For delayed-response cases, control read delivery without
mocking successful writes. Preserve the original failing evidence on reruns.

## Weighted criteria

| Criterion ID | Observable criterion | Weight | Mandatory | Rating kind | Required evidence |
| --- | --- | ---: | --- | --- | --- |
| SE-FOCUS-11-C01 | The main browser action produces the exact visible result: One body-only SystemVerilog Section appears and contains the initial assignment. | 35 | yes | 0 or 4 | Action recording and first result. |
| SE-FOCUS-11-C02 | The final data and identities match this case contract: One complete eight-bit inversion body with a consistent explanation and no duplicate SV Section. | 30 | yes | 0 or 4 | Final visible and authoritative state. |
| SE-FOCUS-11-C03 | Status, labels, selection, and focus make the case-specific result clear without misleading completion messages. | 15 | no | 0–4 | Feedback and focus screenshots; partial-rating explanation. |
| SE-FOCUS-11-C04 | The specified reopen, recovery, or final-state inspection succeeds: The inversion body and its revised explanation persist; the two-port interface remains unchanged. | 20 | yes | 0 or 4 | Final step evidence and unchanged unrelated data. |

Use [scoring rules](../../SCORING.md). Weights total 100. Mandatory failures
remain failures regardless of partial visual/usability credit.

### Partial-credit anchors for this check

The concrete result under review is: One complete eight-bit inversion body with a consistent explanation and no duplicate SV Section.
For qualitative feedback/readability criteria, rating 2 means this result can
be understood only after substantial extra inspection; rating 3 means it is
clear with one minor local wording, focus, or spacing issue; rating 4 means the
result and next action are clear in every requested view. Rating 1 means severe
confusion or obstruction; rating 0 means absent or incorrect feedback/content.
Objective data, availability, rejection, and persistence checks remain binary.

## Result fields

Copy the [run template](../../RUN-TEMPLATE.md) into the run directory and fill it
for `SE-FOCUS-11`. Record run ID, code revision, browser/version, theme, window size,
actual Spec path, source revision if exposed, ratings for every criterion,
mandatory failures, capability gaps, evidence links, and verification limits.
Default result: **unrun**. Do not prefill a passing score from this casebook.
Functional simulation: **unverified**.

Return to the [catalogue](../../README.md).

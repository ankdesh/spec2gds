# CD-FOCUS-09: Preserve numeric bus slices and reject invalid bounds

## Case contract

- Application: **Circuit Designer**.
- Intended executor: **Playwright in a later implementation pass**. This file is a detailed specification, not an implemented automated check.
- Priority: source/identity protection is mandatory; visual and interaction quality is separately rated.
- Estimated effort: 10–25 minutes to inspect manually after fixture setup; future automation runtime must be measured.
- Regression scope: `spec,circuit`.
- Future profile selection: affected `integration --scope spec,circuit` and full `regression`.
- Fast suitability: candidate: slice boundary units; browser preservation in integration. This document changes no profile selection.
- Future layer: browser for rendered actions; add lower-layer state/contract protection only where it reliably detects the same defect.
- Inputs: [complete focused fixtures](../../inputs/focus-fixtures.md), including all linked leaf/composite packs.
- Additional direct input references: [Reusable hierarchical 64-bit adder](../../inputs/add64.md).

## Exact setup

Use add64 as a prepared focused fixture. Select a_low: top.a[31:0] → u_low.a. Its high-half peer is top.a[63:32] → u_high.a.

Use fresh isolated source/storage and dedicated service bindings. Future setup
may seed prerequisites through existing public real-service fixtures. It must
not perform or fake the UI operation under assessment. A missing required UI
capability remains a failed acceptance criterion; do not silently skip it.

## Actions, observable assertions, and evidence

| Step | Designer action | Expected visible result | Evidence to retain |
| ---: | --- | --- | --- |
| 1 | Prepare the exact isolated starting fixture below. Record its identities and saved source/graph before the action. | The starting state matches the fixture and is separate from other cases; setup has not already performed the behavior under test. | Fixture, initial screenshot, source/graph inventory, and active binding. |
| 2 | Inspect or edit both low and high mappings, then save the unchanged valid mapping. | Source and destination offsets are explicit and retain the intended 32-bit widths. | Step 2 screenshot/recording and observable state. |
| 3 | Attempt a 33-bit slice from u_low.a or an out-of-range root slice. | A diagnostic rejects the invalid mapping without altering either existing half. | Step 3 screenshot/recording and observable state. |
| 4 | Reopen and inspect a_low and a_high independently. | The two distinct slices persist; neither becomes a whole-port or reversed half connection. | Step 4 screenshot/recording and observable state. |
| 5 | Inspect the final visible state and saved result specified below; record ratings and any missing capability. | An unchanged correct 64-bit split mapping and atomic rejection of the invalid slice. | Final screenshot, relevant read-only service/archive comparison, and criterion ratings. |

## Expected final Spec and Circuit

An unchanged correct 64-bit split mapping and atomic rejection of the invalid slice.

Keep all unmentioned source Sections, definition references, instance IDs, and
connections unchanged. If this is an interface-only or intentionally incomplete
fixture, do not infer functional RTL success. For any explicitly required
generation step, obtain the actual saved-target project through the UI and run
its published `make lint`; keep simulation marked unverified.

## Automation-ready assertions

Source and destination offsets are explicit and retain the intended 32-bit widths. A diagnostic rejects the invalid mapping without altering either existing half. The two distinct slices persist; neither becomes a whole-port or reversed half connection.

Use semantic roles/labels and stable item references. Assert the visible result
and the relevant real saved data. Use condition-based waits rather than sleeps.
Collect unexpected console/network failures, screenshots, and a retained trace
on failure. Narrowly identify expected rejection/cancellation events; no blanket
error suppression. For delayed-response cases, control read delivery without
mocking successful writes. Preserve the original failing evidence on reruns.

## Weighted criteria

| Criterion ID | Observable criterion | Weight | Mandatory | Rating kind | Required evidence |
| --- | --- | ---: | --- | --- | --- |
| CD-FOCUS-09-C01 | The protected source, identity, graph, or draft identified in setup survives the failed/cancelled operation: An unchanged correct 64-bit split mapping and atomic rejection of the invalid slice. | 40 | yes | 0 or 4 | Before/after saved-state and identity comparison. |
| CD-FOCUS-09-C02 | The attempted operation is rejected, cancelled, or isolated exactly as specified: Source and destination offsets are explicit and retain the intended 32-bit widths. | 25 | yes | 0 or 4 | Browser action and rejection/state evidence. |
| CD-FOCUS-09-C03 | The case-specific recovery or final valid operation completes without a hidden bypass: The two distinct slices persist; neither becomes a whole-port or reversed half connection. | 20 | yes | 0 or 4 | Recovery recording and reopened result. |
| CD-FOCUS-09-C04 | The user can identify the affected operation, retained state, and next action; feedback and focus do not hide the failure. | 15 | no | 0–4 | Visible feedback/focus and rationale for partial ratings. |

Use [scoring rules](../../SCORING.md). Weights total 100. Mandatory failures
remain failures regardless of partial visual/usability credit.

### Partial-credit anchors for this check

The concrete result under review is: An unchanged correct 64-bit split mapping and atomic rejection of the invalid slice.
For qualitative feedback/readability criteria, rating 2 means this result can
be understood only after substantial extra inspection; rating 3 means it is
clear with one minor local wording, focus, or spacing issue; rating 4 means the
result and next action are clear in every requested view. Rating 1 means severe
confusion or obstruction; rating 0 means absent or incorrect feedback/content.
Objective data, availability, rejection, and persistence checks remain binary.

## Result fields

Copy the [run template](../../RUN-TEMPLATE.md) into the run directory and fill it
for `CD-FOCUS-09`. Record run ID, code revision, browser/version, theme, window size,
actual Spec path, source revision if exposed, ratings for every criterion,
mandatory failures, capability gaps, evidence links, and verification limits.
Default result: **unrun**. Do not prefill a passing score from this casebook.
Functional simulation: **unverified**.

Return to the [catalogue](../../README.md).

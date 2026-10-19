# CD-FOCUS-17: Inspect cycle markers and clock-domain timing

## Case contract

- Application: **Circuit Designer**.
- Intended executor: **Playwright in a later implementation pass**. This file is a detailed specification, not an implemented automated check.
- Priority: source/identity protection is mandatory; visual and interaction quality is separately rated.
- Estimated effort: 10–25 minutes to inspect manually after fixture setup; future automation runtime must be measured.
- Regression scope: `spec,circuit`.
- Future profile selection: affected `integration --scope spec,circuit` and full `regression`.
- Fast suitability: candidate: timing/domain units; browser controls in integration. This document changes no profile selection.
- Future layer: browser for rendered actions; add lower-layer state/contract protection only where it reliably detects the same defect.
- Inputs: [complete focused fixtures](../../inputs/focus-fixtures.md), including all linked leaf/composite packs.
- Additional direct input references: [Two-stage enabled 32-bit addition datapath](../../inputs/pipeline32.md).

## Exact setup

Use pipeline32 as a prepared focused fixture. Place u_add left of u_output with a clear gap. Record the path u_add.sum → u_output.din[31:0], default domain clk, and no marker in that gap.

Use fresh isolated source/storage and dedicated service bindings. Future setup
may seed prerequisites through existing public real-service fixtures. It must
not perform or fake the UI operation under assessment. A missing required UI
capability remains a failed acceptance criterion; do not silently skip it.

## Actions, observable assertions, and evidence

| Step | Designer action | Expected visible result | Evidence to retain |
| ---: | --- | --- | --- |
| 1 | Prepare the exact isolated starting fixture below. Record its identities and saved source/graph before the action. | The starting state matches the fixture and is separate from other cases; setup has not already performed the behavior under test. | Fixture, initial screenshot, source/graph inventory, and active binding. |
| 2 | Add one cycle edge in the gap, name it Result capture, and keep both nodes entirely inside their stages. | The selected same-domain path crosses exactly that marker and analysis reports one annotated cycle for that path. | Step 2 screenshot/recording and observable state. |
| 3 | Hide and show the timing overlay; inspect Clock settings and assign an additional domain aux to one endpoint subject. | Overlay changes do not change topology. The cross-domain path is reported as a domain crossing instead of silently treated as a synchronous one-cycle path. | Step 3 screenshot/recording and observable state. |
| 4 | Restore the clk assignment, save, and reopen. | The one marker and its labels persist. The RTL still contains only the explicitly authored registers; markers do not synthesize extra state. | Step 4 screenshot/recording and observable state. |
| 5 | Inspect the final visible state and saved result specified below; record ratings and any missing capability. | A saved annotated path with correct visibility, labels, and clock-domain warnings, independent of hardware register creation. | Final screenshot, relevant read-only service/archive comparison, and criterion ratings. |

## Expected final Spec and Circuit

A saved annotated path with correct visibility, labels, and clock-domain warnings, independent of hardware register creation.

Keep all unmentioned source Sections, definition references, instance IDs, and
connections unchanged. If this is an interface-only or intentionally incomplete
fixture, do not infer functional RTL success. For any explicitly required
generation step, obtain the actual saved-target project through the UI and run
its published `make lint`; keep simulation marked unverified.

## Automation-ready assertions

The selected same-domain path crosses exactly that marker and analysis reports one annotated cycle for that path. Overlay changes do not change topology. The cross-domain path is reported as a domain crossing instead of silently treated as a synchronous one-cycle path. The one marker and its labels persist. The RTL still contains only the explicitly authored registers; markers do not synthesize extra state.

Use semantic roles/labels and stable item references. Assert the visible result
and the relevant real saved data. Use condition-based waits rather than sleeps.
Collect unexpected console/network failures, screenshots, and a retained trace
on failure. Narrowly identify expected rejection/cancellation events; no blanket
error suppression. For delayed-response cases, control read delivery without
mocking successful writes. Preserve the original failing evidence on reruns.

## Weighted criteria

| Criterion ID | Observable criterion | Weight | Mandatory | Rating kind | Required evidence |
| --- | --- | ---: | --- | --- | --- |
| CD-FOCUS-17-C01 | The main browser action produces the exact visible result: The selected same-domain path crosses exactly that marker and analysis reports one annotated cycle for that path. | 35 | yes | 0 or 4 | Action recording and first result. |
| CD-FOCUS-17-C02 | The final data and identities match this case contract: A saved annotated path with correct visibility, labels, and clock-domain warnings, independent of hardware register creation. | 30 | yes | 0 or 4 | Final visible and authoritative state. |
| CD-FOCUS-17-C03 | Status, labels, selection, and focus make the case-specific result clear without misleading completion messages. | 15 | no | 0–4 | Feedback and focus screenshots; partial-rating explanation. |
| CD-FOCUS-17-C04 | The specified reopen, recovery, or final-state inspection succeeds: The one marker and its labels persist. The RTL still contains only the explicitly authored registers; markers do not synthesize extra state. | 20 | yes | 0 or 4 | Final step evidence and unchanged unrelated data. |

Use [scoring rules](../../SCORING.md). Weights total 100. Mandatory failures
remain failures regardless of partial visual/usability credit.

### Partial-credit anchors for this check

The concrete result under review is: A saved annotated path with correct visibility, labels, and clock-domain warnings, independent of hardware register creation.
For qualitative feedback/readability criteria, rating 2 means this result can
be understood only after substantial extra inspection; rating 3 means it is
clear with one minor local wording, focus, or spacing issue; rating 4 means the
result and next action are clear in every requested view. Rating 1 means severe
confusion or obstruction; rating 0 means absent or incorrect feedback/content.
Objective data, availability, rejection, and persistence checks remain binary.

## Result fields

Copy the [run template](../../RUN-TEMPLATE.md) into the run directory and fill it
for `CD-FOCUS-17`. Record run ID, code revision, browser/version, theme, window size,
actual Spec path, source revision if exposed, ratings for every criterion,
mandatory failures, capability gaps, evidence links, and verification limits.
Default result: **unrun**. Do not prefill a passing score from this casebook.
Functional simulation: **unverified**.

Return to the [catalogue](../../README.md).

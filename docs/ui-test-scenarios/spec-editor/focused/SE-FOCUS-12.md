# SE-FOCUS-12: Reject invalid SystemVerilog without losing saved logic

## Case contract

- Application: **Spec Editor**.
- Intended executor: **Playwright in a later implementation pass**. This file is a detailed specification, not an implemented automated check.
- Priority: source/identity protection is mandatory; visual and interaction quality is separately rated.
- Estimated effort: 10–25 minutes to inspect manually after fixture setup; future automation runtime must be measured.
- Regression scope: `spec`.
- Future profile selection: affected `integration --scope spec` and full `regression`.
- Fast suitability: candidate: SV validation unit contract plus scoped editor protection. This document changes no profile selection.
- Future layer: browser for rendered actions; add lower-layer state/contract protection only where it reliably detects the same defect.
- Inputs: [complete focused fixtures](../../inputs/focus-fixtures.md), including all linked leaf/composite packs.
- Additional direct input references: [32-bit unsigned adder](../../inputs/add32.md).

## Exact setup

Use F-A. Record the exact complete saved add32 body. Invalid replacement text: assign sum = ;.

Use fresh isolated source/storage and dedicated service bindings. Future setup
may seed prerequisites through existing public real-service fixtures. It must
not perform or fake the UI operation under assessment. A missing required UI
capability remains a failed acceptance criterion; do not silently skip it.

## Actions, observable assertions, and evidence

| Step | Designer action | Expected visible result | Evidence to retain |
| ---: | --- | --- | --- |
| 1 | Prepare the exact isolated starting fixture below. Record its identities and saved source/graph before the action. | The starting state matches the fixture and is separate from other cases; setup has not already performed the behavior under test. | Fixture, initial screenshot, source/graph inventory, and active binding. |
| 2 | Edit the SV Section, replace its draft with the invalid text, and attempt Save to Spec. | A relevant source diagnostic appears; the invalid draft remains available for correction. | Step 2 screenshot/recording and observable state. |
| 3 | Inspect the saved view from a second browser context without modifying it. | The original valid body is still authoritative; no partial or empty replacement was saved. | Step 3 screenshot/recording and observable state. |
| 4 | Restore the complete add32 body from the input pack, save, and reopen. | The corrected body persists with all five ports and the original Component identity. | Step 4 screenshot/recording and observable state. |
| 5 | Inspect the final visible state and saved result specified below; record ratings and any missing capability. | Saved valid arithmetic survives the failed edit; a corrected draft can be saved without losing other Sections. | Final screenshot, relevant read-only service/archive comparison, and criterion ratings. |

## Expected final Spec and Circuit

Saved valid arithmetic survives the failed edit; a corrected draft can be saved without losing other Sections.

Keep all unmentioned source Sections, definition references, instance IDs, and
connections unchanged. If this is an interface-only or intentionally incomplete
fixture, do not infer functional RTL success. For any explicitly required
generation step, obtain the actual saved-target project through the UI and run
its published `make lint`; keep simulation marked unverified.

## Automation-ready assertions

A relevant source diagnostic appears; the invalid draft remains available for correction. The original valid body is still authoritative; no partial or empty replacement was saved. The corrected body persists with all five ports and the original Component identity.

Use semantic roles/labels and stable item references. Assert the visible result
and the relevant real saved data. Use condition-based waits rather than sleeps.
Collect unexpected console/network failures, screenshots, and a retained trace
on failure. Narrowly identify expected rejection/cancellation events; no blanket
error suppression. For delayed-response cases, control read delivery without
mocking successful writes. Preserve the original failing evidence on reruns.

## Weighted criteria

| Criterion ID | Observable criterion | Weight | Mandatory | Rating kind | Required evidence |
| --- | --- | ---: | --- | --- | --- |
| SE-FOCUS-12-C01 | The protected source, identity, graph, or draft identified in setup survives the failed/cancelled operation: Saved valid arithmetic survives the failed edit; a corrected draft can be saved without losing other Sections. | 40 | yes | 0 or 4 | Before/after saved-state and identity comparison. |
| SE-FOCUS-12-C02 | The attempted operation is rejected, cancelled, or isolated exactly as specified: A relevant source diagnostic appears; the invalid draft remains available for correction. | 25 | yes | 0 or 4 | Browser action and rejection/state evidence. |
| SE-FOCUS-12-C03 | The case-specific recovery or final valid operation completes without a hidden bypass: The corrected body persists with all five ports and the original Component identity. | 20 | yes | 0 or 4 | Recovery recording and reopened result. |
| SE-FOCUS-12-C04 | The user can identify the affected operation, retained state, and next action; feedback and focus do not hide the failure. | 15 | no | 0–4 | Visible feedback/focus and rationale for partial ratings. |

Use [scoring rules](../../SCORING.md). Weights total 100. Mandatory failures
remain failures regardless of partial visual/usability credit.

### Partial-credit anchors for this check

The concrete result under review is: Saved valid arithmetic survives the failed edit; a corrected draft can be saved without losing other Sections.
For qualitative feedback/readability criteria, rating 2 means this result can
be understood only after substantial extra inspection; rating 3 means it is
clear with one minor local wording, focus, or spacing issue; rating 4 means the
result and next action are clear in every requested view. Rating 1 means severe
confusion or obstruction; rating 0 means absent or incorrect feedback/content.
Objective data, availability, rejection, and persistence checks remain binary.

## Result fields

Copy the [run template](../../RUN-TEMPLATE.md) into the run directory and fill it
for `SE-FOCUS-12`. Record run ID, code revision, browser/version, theme, window size,
actual Spec path, source revision if exposed, ratings for every criterion,
mandatory failures, capability gaps, evidence links, and verification limits.
Default result: **unrun**. Do not prefill a passing score from this casebook.
Functional simulation: **unverified**.

Return to the [catalogue](../../README.md).

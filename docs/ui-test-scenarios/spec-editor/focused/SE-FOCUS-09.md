# SE-FOCUS-09: Author parameters and symbolic port ranges

## Case contract

- Application: **Spec Editor**.
- Intended executor: **Playwright in a later implementation pass**. This file is a detailed specification, not an implemented automated check.
- Priority: source/identity protection is mandatory; visual and interaction quality is separately rated.
- Estimated effort: 10–25 minutes to inspect manually after fixture setup; future automation runtime must be measured.
- Regression scope: `spec,activities`.
- Future profile selection: affected `integration --scope spec,activities` and full `regression`.
- Fast suitability: integration only: compiler-dependent symbolic interface check. This document changes no profile selection.
- Future layer: browser for rendered actions; add lower-layer state/contract protection only where it reliably detects the same defect.
- Inputs: [complete focused fixtures](../../inputs/focus-fixtures.md), including all linked leaf/composite packs.
- Additional direct input references: the exact interface/snippets in this case and the focused fixture pack.

## Exact setup

Use the symbolic-interface input in the focused pack: Component Parameterized pass-through; stored parameter N has type int unsigned and default 13; a: in, N-1:0; y: out, N-1:0; body assign y = a;.

Use fresh isolated source/storage and dedicated service bindings. Future setup
may seed prerequisites through existing public real-service fixtures. It must
not perform or fake the UI operation under assessment. A missing required UI
capability remains a failed acceptance criterion; do not silently skip it.

## Actions, observable assertions, and evidence

| Step | Designer action | Expected visible result | Evidence to retain |
| ---: | --- | --- | --- |
| 1 | Prepare the exact isolated starting fixture below. Record its identities and saved source/graph before the action. | The starting state matches the fixture and is separate from other cases; setup has not already performed the behavior under test. | Fixture, initial screenshot, source/graph inventory, and active binding. |
| 2 | Through UI authoring controls, create the typed N declaration and both exact symbolic ranges. | The declaration and source expressions are visible and saved. A missing parameter-authoring path is a capability failure, not an instruction to use an API. | Step 2 screenshot/recording and observable state. |
| 3 | Select Verify Component with the default value and inspect Verification details, then revise N to 5 through the UI and verify again. | The visible resolved widths are 13, then 5; source ranges remain N-1:0 and the body remains unchanged. | Step 3 screenshot/recording and observable state. |
| 4 | Reopen the saved Component, run Verify Component if the current result is absent or out of date, generate RTL, and run its make lint. | The parameter type/default and symbolic ranges persist in generated declarations and lint succeeds. | Step 4 screenshot/recording and observable state. |
| 5 | Inspect the final visible state and saved result specified below; record ratings and any missing capability. | One typed parameter and two symbolic ports with independently recorded source expressions and resolved widths; the final default is N=5. | Final screenshot, relevant read-only service/archive comparison, and criterion ratings. |

## Expected final Spec and Circuit

One typed parameter and two symbolic ports with independently recorded source expressions and resolved widths; the final default is N=5.

Keep all unmentioned source Sections, definition references, instance IDs, and
connections unchanged. If this is an interface-only or intentionally incomplete
fixture, do not infer functional RTL success. For any explicitly required
generation step, obtain the actual saved-target project through the UI and run
its published `make lint`; keep simulation marked unverified.

## Automation-ready assertions

The declaration and source expressions are visible and saved. A missing parameter-authoring path is a capability failure, not an instruction to use an API. The visible resolved widths are 13, then 5; source ranges remain N-1:0 and the body remains unchanged. The parameter type/default and symbolic ranges persist in generated declarations and lint succeeds.

Use semantic roles/labels and stable item references. Assert the visible result
and the relevant real saved data. Use condition-based waits rather than sleeps.
Collect unexpected console/network failures, screenshots, and a retained trace
on failure. Narrowly identify expected rejection/cancellation events; no blanket
error suppression. For delayed-response cases, control read delivery without
mocking successful writes. Preserve the original failing evidence on reruns.

## Weighted criteria

| Criterion ID | Observable criterion | Weight | Mandatory | Rating kind | Required evidence |
| --- | --- | ---: | --- | --- | --- |
| SE-FOCUS-09-C01 | The main browser action produces the exact visible result: The declaration and source expressions are visible and saved. A missing parameter-authoring path is a capability failure, not an instruction to use an API. | 35 | yes | 0 or 4 | Action recording and first result. |
| SE-FOCUS-09-C02 | The final data and identities match this case contract: One typed parameter and two symbolic ports with independently recorded source expressions and resolved widths; the final default is N=5. | 30 | yes | 0 or 4 | Final visible and authoritative state. |
| SE-FOCUS-09-C03 | Status, labels, selection, and focus make the case-specific result clear without misleading completion messages. | 15 | no | 0–4 | Feedback and focus screenshots; partial-rating explanation. |
| SE-FOCUS-09-C04 | The specified reopen, recovery, or final-state inspection succeeds: The parameter type/default and symbolic ranges persist in generated declarations and lint succeeds. | 20 | yes | 0 or 4 | Final step evidence and unchanged unrelated data. |

Use [scoring rules](../../SCORING.md). Weights total 100. Mandatory failures
remain failures regardless of partial visual/usability credit.

### Partial-credit anchors for this check

The concrete result under review is: One typed parameter and two symbolic ports with independently recorded source expressions and resolved widths; the final default is N=5.
For qualitative feedback/readability criteria, rating 2 means this result can
be understood only after substantial extra inspection; rating 3 means it is
clear with one minor local wording, focus, or spacing issue; rating 4 means the
result and next action are clear in every requested view. Rating 1 means severe
confusion or obstruction; rating 0 means absent or incorrect feedback/content.
Objective data, availability, rejection, and persistence checks remain binary.

## Result fields

Copy the [run template](../../RUN-TEMPLATE.md) into the run directory and fill it
for `SE-FOCUS-09`. Record run ID, code revision, browser/version, theme, window size,
actual Spec path, source revision if exposed, ratings for every criterion,
mandatory failures, capability gaps, evidence links, and verification limits.
Default result: **unrun**. Do not prefill a passing score from this casebook.
Functional simulation: **unverified**.

Return to the [catalogue](../../README.md).

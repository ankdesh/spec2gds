# SE-FOCUS-16: Ignore a delayed response after switching Specs

## Case contract

- Application: **Spec Editor**.
- Intended executor: **Playwright in a later implementation pass**. This file is a detailed specification, not an implemented automated check.
- Priority: source/identity protection is mandatory; visual and interaction quality is separately rated.
- Estimated effort: 10–25 minutes to inspect manually after fixture setup; future automation runtime must be measured.
- Regression scope: `spec`.
- Future profile selection: affected `integration --scope spec` and full `regression`.
- Fast suitability: integration only: controlled browser response ordering and two real sources. This document changes no profile selection.
- Future layer: browser for rendered actions; add lower-layer state/contract protection only where it reliably detects the same defect.
- Inputs: [complete focused fixtures](../../inputs/focus-fixtures.md), including all linked leaf/composite packs.
- Additional direct input references: [Enabled eight-bit counter](../../inputs/counter8.md).

## Exact setup

Use F-A and F-B. F-B contains counter8 and title Focus authoring B. Future Playwright may delay a read-only F-A view response to make the ordering deterministic; it must not mock a successful write.

Use fresh isolated source/storage and dedicated service bindings. Future setup
may seed prerequisites through existing public real-service fixtures. It must
not perform or fake the UI operation under assessment. A missing required UI
capability remains a failed acceptance criterion; do not silently skip it.

## Actions, observable assertions, and evidence

| Step | Designer action | Expected visible result | Evidence to retain |
| ---: | --- | --- | --- |
| 1 | Prepare the exact isolated starting fixture below. Record its identities and saved source/graph before the action. | The starting state matches the fixture and is separate from other cases; setup has not already performed the behavior under test. | Fixture, initial screenshot, source/graph inventory, and active binding. |
| 2 | Start a refresh/read of F-A and hold that response in the future harness. Open F-B before releasing it. | The active title, path, identity, and content switch to F-B. | Step 2 screenshot/recording and observable state. |
| 3 | Release the delayed F-A response. | F-B remains active; no F-A explanation, ports, artifact target, or binding overwrites it. | Step 3 screenshot/recording and observable state. |
| 4 | Edit a harmless sentence in F-B and Save to Spec; reopen both files separately. | Only F-B receives that edit. F-A remains the original add32 Spec. | Step 4 screenshot/recording and observable state. |
| 5 | Inspect the final visible state and saved result specified below; record ratings and any missing capability. | Two distinct Specs with preserved identities and correct source targeting despite out-of-order reads. | Final screenshot, relevant read-only service/archive comparison, and criterion ratings. |

## Expected final Spec and Circuit

Two distinct Specs with preserved identities and correct source targeting despite out-of-order reads.

Keep all unmentioned source Sections, definition references, instance IDs, and
connections unchanged. If this is an interface-only or intentionally incomplete
fixture, do not infer functional RTL success. For any explicitly required
generation step, obtain the actual saved-target project through the UI and run
its published `make lint`; keep simulation marked unverified.

## Automation-ready assertions

The active title, path, identity, and content switch to F-B. F-B remains active; no F-A explanation, ports, artifact target, or binding overwrites it. Only F-B receives that edit. F-A remains the original add32 Spec.

Use semantic roles/labels and stable item references. Assert the visible result
and the relevant real saved data. Use condition-based waits rather than sleeps.
Collect unexpected console/network failures, screenshots, and a retained trace
on failure. Narrowly identify expected rejection/cancellation events; no blanket
error suppression. For delayed-response cases, control read delivery without
mocking successful writes. Preserve the original failing evidence on reruns.

## Weighted criteria

| Criterion ID | Observable criterion | Weight | Mandatory | Rating kind | Required evidence |
| --- | --- | ---: | --- | --- | --- |
| SE-FOCUS-16-C01 | The protected source, identity, graph, or draft identified in setup survives the failed/cancelled operation: Two distinct Specs with preserved identities and correct source targeting despite out-of-order reads. | 40 | yes | 0 or 4 | Before/after saved-state and identity comparison. |
| SE-FOCUS-16-C02 | The attempted operation is rejected, cancelled, or isolated exactly as specified: The active title, path, identity, and content switch to F-B. | 25 | yes | 0 or 4 | Browser action and rejection/state evidence. |
| SE-FOCUS-16-C03 | The case-specific recovery or final valid operation completes without a hidden bypass: Only F-B receives that edit. F-A remains the original add32 Spec. | 20 | yes | 0 or 4 | Recovery recording and reopened result. |
| SE-FOCUS-16-C04 | The user can identify the affected operation, retained state, and next action; feedback and focus do not hide the failure. | 15 | no | 0–4 | Visible feedback/focus and rationale for partial ratings. |

Use [scoring rules](../../SCORING.md). Weights total 100. Mandatory failures
remain failures regardless of partial visual/usability credit.

### Partial-credit anchors for this check

The concrete result under review is: Two distinct Specs with preserved identities and correct source targeting despite out-of-order reads.
For qualitative feedback/readability criteria, rating 2 means this result can
be understood only after substantial extra inspection; rating 3 means it is
clear with one minor local wording, focus, or spacing issue; rating 4 means the
result and next action are clear in every requested view. Rating 1 means severe
confusion or obstruction; rating 0 means absent or incorrect feedback/content.
Objective data, availability, rejection, and persistence checks remain binary.

## Result fields

Copy the [run template](../../RUN-TEMPLATE.md) into the run directory and fill it
for `SE-FOCUS-16`. Record run ID, code revision, browser/version, theme, window size,
actual Spec path, source revision if exposed, ratings for every criterion,
mandatory failures, capability gaps, evidence links, and verification limits.
Default result: **unrun**. Do not prefill a passing score from this casebook.
Functional simulation: **unverified**.

Return to the [catalogue](../../README.md).

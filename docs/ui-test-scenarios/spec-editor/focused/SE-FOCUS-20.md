# SE-FOCUS-20: Read long content in both themes and compact windows

## Case contract

- Application: **Spec Editor**.
- Intended executor: **Playwright in a later implementation pass**. This file is a detailed specification, not an implemented automated check.
- Priority: source/identity protection is mandatory; visual and interaction quality is separately rated.
- Estimated effort: 10–25 minutes to inspect manually after fixture setup; future automation runtime must be measured.
- Regression scope: `spec`.
- Future profile selection: affected `integration --scope spec` and full `regression`.
- Fast suitability: integration only: viewport/theme browser matrix. This document changes no profile selection.
- Future layer: browser for rendered actions; add lower-layer state/contract protection only where it reliably detects the same defect.
- Inputs: [complete focused fixtures](../../inputs/focus-fixtures.md), including all linked leaf/composite packs.
- Additional direct input references: the exact interface/snippets in this case and the focused fixture pack.

## Exact setup

Use the Long explanation from the focused pack, F-A ports, and the long readable title Arithmetic status and diagnostic explanation for release review. Use 1440×900, 1024×768, and 560×760 in both implemented themes.

Use fresh isolated source/storage and dedicated service bindings. Future setup
may seed prerequisites through existing public real-service fixtures. It must
not perform or fake the UI operation under assessment. A missing required UI
capability remains a failed acceptance criterion; do not silently skip it.

## Actions, observable assertions, and evidence

| Step | Designer action | Expected visible result | Evidence to retain |
| ---: | --- | --- | --- |
| 1 | Prepare the exact isolated starting fixture below. Record its identities and saved source/graph before the action. | The starting state matches the fixture and is separate from other cases; setup has not already performed the behavior under test. | Fixture, initial screenshot, source/graph inventory, and active binding. |
| 2 | At each size/theme inspect title, full port table, explanation, and Options/Edit controls. | Text remains legible, the full title is discoverable, and actions remain reachable without text overlap. | Step 2 screenshot/recording and observable state. |
| 3 | Use Contents navigation, scrolling, and keyboard menus; open a modal and use Tab, Shift+Tab, and Escape. | Anchored content is not covered by the sticky bar; focus stays inside the modal and returns to its trigger; compact navigation closes cleanly. | Step 3 screenshot/recording and observable state. |
| 4 | Reload and compare content and theme preference. | Saved data and the chosen theme persist; visual changes do not alter hardware source. | Step 4 screenshot/recording and observable state. |
| 5 | Inspect the final visible state and saved result specified below; record ratings and any missing capability. | A readable, navigable saved Spec in both themes and all target windows; screenshots cover the whole relevant content, not only the first screen. | Final screenshot, relevant read-only service/archive comparison, and criterion ratings. |

## Expected final Spec and Circuit

A readable, navigable saved Spec in both themes and all target windows; screenshots cover the whole relevant content, not only the first screen.

Keep all unmentioned source Sections, definition references, instance IDs, and
connections unchanged. If this is an interface-only or intentionally incomplete
fixture, do not infer functional RTL success. For any explicitly required
generation step, obtain the actual saved-target project through the UI and run
its published `make lint`; keep simulation marked unverified.

## Automation-ready assertions

Text remains legible, the full title is discoverable, and actions remain reachable without text overlap. Anchored content is not covered by the sticky bar; focus stays inside the modal and returns to its trigger; compact navigation closes cleanly. Saved data and the chosen theme persist; visual changes do not alter hardware source.

Use semantic roles/labels and stable item references. Assert the visible result
and the relevant real saved data. Use condition-based waits rather than sleeps.
Collect unexpected console/network failures, screenshots, and a retained trace
on failure. Narrowly identify expected rejection/cancellation events; no blanket
error suppression. For delayed-response cases, control read delivery without
mocking successful writes. Preserve the original failing evidence on reruns.

## Weighted criteria

| Criterion ID | Observable criterion | Weight | Mandatory | Rating kind | Required evidence |
| --- | --- | ---: | --- | --- | --- |
| SE-FOCUS-20-C01 | The named content and final representation are readable with the case-specific structure, labels, and reading order: A readable, navigable saved Spec in both themes and all target windows; screenshots cover the whole relevant content, not only the first screen. | 45 | no | 0–4 | Complete view plus difficult areas; no cropped evidence hiding a fault. |
| SE-FOCUS-20-C02 | All case-specific controls, content, and navigation targets can be reached and operated through the UI. | 25 | yes | 0 or 4 | Action/focus recording for the listed steps. |
| SE-FOCUS-20-C03 | Visible values and exported/saved representations agree with the source; layout operations do not corrupt hardware meaning. | 20 | yes | 0 or 4 | Source/graph and visible/export comparison. |
| SE-FOCUS-20-C04 | Both themes and the specified window/overlay states preserve legibility, geometry, and interaction consistency. | 10 | no | 0–4 | Named theme/window captures and export comparisons where requested. |

Use [scoring rules](../../SCORING.md). Weights total 100. Mandatory failures
remain failures regardless of partial visual/usability credit.

### Partial-credit anchors for this check

The concrete result under review is: A readable, navigable saved Spec in both themes and all target windows; screenshots cover the whole relevant content, not only the first screen.
For qualitative feedback/readability criteria, rating 2 means this result can
be understood only after substantial extra inspection; rating 3 means it is
clear with one minor local wording, focus, or spacing issue; rating 4 means the
result and next action are clear in every requested view. Rating 1 means severe
confusion or obstruction; rating 0 means absent or incorrect feedback/content.
Objective data, availability, rejection, and persistence checks remain binary.

## Result fields

Copy the [run template](../../RUN-TEMPLATE.md) into the run directory and fill it
for `SE-FOCUS-20`. Record run ID, code revision, browser/version, theme, window size,
actual Spec path, source revision if exposed, ratings for every criterion,
mandatory failures, capability gaps, evidence links, and verification limits.
Default result: **unrun**. Do not prefill a passing score from this casebook.
Functional simulation: **unverified**.

Return to the [catalogue](../../README.md).

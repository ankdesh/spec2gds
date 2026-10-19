# Acceptance scoring guide

## What the score measures

Score the actual saved and visible result against a case's intended outcome.
Do not score the input pack itself as a product result. Check complete content,
not just the first screen. The numeric score describes quality; mandatory checks
separately report integrity, interfaces, saved state, and required generation.
Functional simulation remains unverified, even when generation and lint pass.

## Criterion ratings

| Rating | General meaning | Example for readable explanation |
| ---: | --- | --- |
| 0 | Absent or incorrect | No explanation, or wrong behavior is described. |
| 1 | Severely incomplete | Only a title or vague purpose; most rules are missing. |
| 2 | Partial; substantial work remains | Purpose and ports are described, but timing, assumptions, or important corner cases are unclear. |
| 3 | Meets the expectation with minor issues | All required meaning is present; one small wording, grouping, or navigation issue remains. |
| 4 | Fully meets the expectation and is clear | Purpose, operation, timing, interface, assumptions, and verification limits are easy to find and consistent. |

For diagram readability, rating 0 means required structure cannot be read; 1
means major labels/routes are hidden; 2 means the diagram is usable only with
substantial effort; 3 means the required structure is clear with a minor local
issue; 4 means all required labels, directions, groups, and routes are legible
in the specified views. Retain the exact view and reason for partial credit.

Objective criteria use only **0 or 4**. Wrong width, missing required endpoint,
wrong source write, lost content, incorrect definition reference, failed required
generation, or failed required lint cannot receive partial correctness credit.
The case file identifies the criterion kind and mandatory status.
Materially false or contradictory required behavior in the explanation fails
the mandatory reference-agreement criterion even when the RTL lints. Score
wording and organization separately; style credit cannot waive false hardware
claims. Source review establishes agreement with the reference, not simulation.

## Calculate one case

Each case's criterion weights sum to 100:

`case score = sum(weight * rating / 4)`

Keep at least one decimal place. Do not round individual criterion contributions
before summing. A score can be finalized only when each criterion has an observed
rating or a documented product-caused unachieved outcome scored zero.

### Worked example: SE-E2E-01

| Area | Weight | Rating | Contribution |
| --- | ---: | ---: | ---: |
| Readable explanation | 20 | 3 | 15 |
| Exact interface | 15 | 4 | 15 |
| Reference implementation agreement | 15 | 4 | 15 |
| Section completeness/readability | 10 | 3 | 7.5 |
| Circuit representation/readability | 10 | 2 | 5 |
| UI generation and project access | 10 | 4 | 10 |
| Actual generated-project lint | 10 | 4 | 10 |
| Reopen and identity preservation | 10 | 4 | 10 |
| **Total** | **100** | | **87.5** |

All mandatory checks pass in this example, while readability still has recorded
improvement points. If required lint instead fails, its rating is 0, the score
becomes 77.5, and the mandatory outcome is **failed**. A good explanation or
diagram cannot cancel that failure. No numeric release threshold is assumed.

## Product failure versus missing prerequisites

- A demonstrated missing UI capability or incorrect product result is a product
  failure. Score the relevant objective criterion zero. Dependent required end
  outcomes that cannot be achieved because of that failure also receive zero;
  record the causal gap rather than claiming those steps were executed.
- Continue independent observations, retaining their evidence and ratings. A
  missing hierarchy authoring path cannot be bypassed by API fixture injection
  in a complete journey.
- An unavailable external tool, browser, service prerequisite, or inaccessible
  environment is **environment-blocked**. Affected criteria are unverified, not
  zero and not four. The case has no final numeric score until resolved.
- If ratings remain missing because execution has not finished, mark in progress
  or unrun. Never renormalize over only the completed criteria.
- When multiple problems occur, retain each category separately. An environment
  problem does not erase an already observed product failure.

## Mandatory outcome and execution state

Record execution state as unrun, in progress, environment-blocked, or complete.
Record mandatory outcome separately as passed, failed, or unverified. A product
gap can complete the assessment with a failed mandatory result and zero-valued
unachieved outcomes. A mandatory failure is retained even if other evidence is
environment-blocked. There is no overall release pass inferred from a case score.

## Four independent group scores

Report these separately:

1. Spec Editor complete journeys: SE-E2E.
2. Circuit Designer complete journeys: CD-E2E.
3. Spec Editor focused checks: SE-FOCUS.
4. Circuit Designer focused checks: CD-FOCUS.

For each group, use the arithmetic mean of finalized scores for selected cases,
including failed cases. All selected cases have equal case weight within their
group; criterion weights are internal to each case. Do not combine group scores.

Show selected, scored, mandatory-failed, environment-blocked, unrun/in-progress,
and excluded counts beside each mean. Failed is an outcome count that can overlap
the other counts; explain this rather than adding every count as if disjoint.
Label a mean **provisional** while any selected case lacks a finalized score.
If no selected case has a score, show **not scored**, not zero or 100.

Pruning changes the declared selection, not past results. Keep the excluded IDs,
reasons, reviewer, and date. Do not remove a failure from the evidence to improve
the mean. Comparisons between runs must state any selection or rubric change.

Return to the [catalogue](README.md) or copy the [run template](RUN-TEMPLATE.md).

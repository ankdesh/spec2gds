# Acceptance run record — copy to temporary storage

Copy this template under `/tmp/spec2gds-acceptance/RUN-ID/results.md`.
Keep this source template blank. This is not an executed result.

## Environment and selection

| Field | Value |
| --- | --- |
| Run ID / date / reviewer | unrecorded |
| Code revision / dirty state | unrecorded |
| Services / addresses / serving mode | unrecorded |
| Chromium version / OS / font environment | unrecorded |
| Theme / window dimensions | unrecorded |
| Verilator / GNU Make versions | unrecorded |
| Activity scratch / browser download root | unrecorded |
| Selected case IDs | copy the catalogue selection; unrecorded |
| Excluded IDs, reasons, decision date, reviewer | unrecorded |
| Input/rubric revision and deviations | unrecorded |

## Per-case result — duplicate for each selected case

| Field | Value |
| --- | --- |
| Case ID / title / case file | unrecorded |
| Actual executor / elapsed effort | unrecorded |
| Execution state | unrun |
| Mandatory outcome | unverified |
| Final quality score / 100 | not scored |
| Actual Spec path and document identity | unrecorded |
| Containing Component / Design / leaf identities | unrecorded |
| Starting and final source revision, if exposed | unrecorded |
| First failing action / expected / actual result | unrecorded |
| Independent observations after a failure | unrecorded |
| UI-generated project path / target / revision | unrecorded |
| Exact lint command / working directory / exit status / log | unrecorded |
| Reference-input validation evidence, separately labelled | unrecorded |
| Functional simulation | unverified; not requested by this catalogue |

### Criterion record

Copy every criterion row from the case; do not change its weight after seeing the
result. Replace the example row below. Use 0 or 4 for objective checks and the
documented anchors for qualitative checks. Leave externally blocked ratings
unverified and the total incomplete. Product-caused unmet outcomes receive zero
with the cause recorded.

| Criterion ID | Weight | Mandatory | Rating | Contribution = weight × rating / 4 | Evidence / reason / causal gap |
| --- | ---: | --- | --- | --- | --- |
| copy actual criterion | copy | copy | unverified | incomplete | unrecorded |
| **Weight total** | **must equal 100** | | | **sum only when finalized** | |

### Findings and capability gaps

| Finding ID | Case / action / criterion | Expected result | Observed result | Product gap or external prerequisite | Severity / affected outcome | Evidence | Decision / follow-up |
| --- | --- | --- | --- | --- | --- | --- | --- |
| unrecorded | | | | | | | |

### Evidence index

Link the initial and final saved Specs, before/after identity and content records,
screenshots in each required theme/window, interaction recording where useful,
connection inventory, generated project and manifest, lint log/exit status,
reopened views, and requested portable/SVG/PNG exports. Keep files below the
temporary run root. Label source inspection, reference-wrapper lint, actual UI
generation/lint, and unperformed simulation distinctly. Do not enter invented
paths or prefilled passing outcomes.

## Group summary — no combined overall score

| Group | Selected | Scored | Mandatory failed | Environment blocked | Unrun / in progress | Excluded | Mean / 100 | Final or provisional / limits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| SE-E2E | unrecorded | 0 | 0 | 0 | unrecorded | unrecorded | not scored | unrun |
| CD-E2E | unrecorded | 0 | 0 | 0 | unrecorded | unrecorded | not scored | unrun |
| SE-FOCUS | unrecorded | 0 | 0 | 0 | unrecorded | unrecorded | not scored | unrun |
| CD-FOCUS | unrecorded | 0 | 0 | 0 | unrecorded | unrecorded | not scored | unrun |

The mean includes finalized failed cases. Missing selected scores keep a group
provisional. Outcome counts can overlap execution-state counts. Record selection
changes and coverage limits; do not infer release readiness from a group mean.

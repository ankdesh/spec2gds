# Stage 1: establish and protect correct UI behavior

Status: implementation plan. No UI fixes or new tests have been implemented by
this document.

## 1. Goal and agreed constraints

Stage 1 must produce reviewed behavior requirements, corrected Spec Editor and
Circuit Designer interfaces, and regression protection in the existing test
profiles. The work has two linked packages: UI discovery and fixing, and
regression test creation. Complete both packages for each confirmed defect.

- Use the existing local test runner and Playwright installation. The planning
  window is one to two weeks. CI setup is outside this stage.
- Cover desktop Chromium, both implemented themes, behavior, and appearance.
  Keep existing responsive tests. Use 1440 x 900 and 1024 x 768 for both
  applications, plus 560 x 760 for Spec Editor compact navigation checks.
  These are desktop browser windows; this stage adds no mobile support claim.
- Automation operates the browser, inspects screenshots, reproduces defects,
  writes tests, proposes fixes, and runs checks. The designer reviews evidence
  and product decisions. Manual browser operation and test authoring are not
  required from the designer.
- Preserve public Spec and Circuit API contracts and their domain boundaries.
  Use service reads and saved source as independent checks on UI results.
  Record any defect that needs an API change as a separate scope decision.
- Keep existing natural-language scenarios. Add independent browser exploration
  of direct designer actions. A successful AI Assistant request alone does not
  establish that direct UI interaction works.

### Starting conditions

The repository already has fixture-based browser suites, real-service browser
tests, natural-language scenarios, isolated storage, and profile reports.
The release notes record visual coverage gaps and earlier failures; those
records require current verification.

Before UI review, resolve the conflict markers in `docs/testing-strategy.md`
and repair its missing coverage-matrix reference. Make the existing capability
report the source for executed coverage. Replace developer-specific screenshot
paths with paths inside each run's evidence directory.

Release evidence must exercise built UI assets. Spec Editor already has a
service-served build path. Add a built-asset mode for the Circuit Designer test
fixture, using Vite preview with the required API proxy and isolated ports.
Verify both the served page and service readiness. Keep development-server use
available for diagnosis, and identify the serving mode in the evidence.

## 2. Work package A: decide and fix correct behavior

### Establish the expected results

Inventory the visible menus, controls, editors, dialogs, canvas actions, and
application handoffs. Give each behavior a stable reference such as
`UI-SPEC-001` or `UI-CIRCUIT-001`. Group the inventory by designer flow.

For each behavior, record the starting state, designer action, visible result,
focus result, permitted source changes, persistence result, and failure result.
Cover empty, loading, ready, editing, invalid, saving, failed, stale, read-only,
and unavailable states where they apply. Check whether each advertised control
has a working action or a clear disabled reason.

Use explicit designer decisions, public service contracts, architecture rules,
and application requirements to establish the expectation. Compare them with
the observed UI. Flag conflicts and stale documentation. Existing screenshots,
current code, and passing tests are evidence; each can contain a defect.

Keep accepted behavior in the existing application documents. Maintain one
linked review ledger for findings, decisions, deferrals, evidence, and test
references. Use short Markdown records rather than a new issue-management
service. Approval of behavior does not automatically approve a visual baseline.

### Required review coverage

| Area | Spec Editor | Circuit Designer |
| --- | --- | --- |
| Entry and navigation | New, Open, Refresh from Disk, Contents, Section anchors, active Spec identity, empty and failed-open states | New, Open, document identity, menus, Inspector, hierarchy entry and return |
| Authoring | Component and Design creation, names and exact IDs, narrative, wire ports, existing read-only port families, SystemVerilog sections | Begin editing, local definitions and instances, properties, connections, deletion, edit availability |
| Draft safety | Save to Spec, Cancel, invalid inputs, duplicate identifiers, stale writes, retained drafts, reviewed retry | Edit leases, Save to Spec, Cancel, stale writes, read-only Component previews, undo and redo |
| Direct interaction | Table actions, text selection, clipboard access and denial, editor shortcuts, focus restoration | Selection and multi-selection, pan, zoom, marquee, move and snap, terminal drag, route editing, keyboard movement, context menus |
| Async behavior | Late responses, switching Specs, source events, reconnect, Activity states, cancellation, completed artifacts | Late responses, changed source, service interruption, lease conflicts, refresh and recovery |
| Output and handoff | Circuit launch, bound AI Assistant launch, derived previews, Activity downloads, preserved hidden source | Save and reopen in Spec Editor, portable circuit files, malformed-open recovery, SVG and PNG exports |
| Visual clarity | Long names and IDs, port tables, Section headings, draft errors, menus, dialogs, status, both themes, compact navigation | Dense diagrams, labels and terminals, route visibility, cycle markers, overlays, menus, dialogs, both themes |
| Preferences and access | Theme persistence, accessible names, keyboard order, visible focus, shortcuts while typing | Theme and shortcut persistence, shortcut conflicts, accessible controls, focus, shortcuts while editing fields |

For destructive actions, document and review the exact treatment of unsaved
work before changing it. For Circuit Designer undo and redo, specify which
document edits enter history and how history behaves after save or cancel.
For exports, check both content and agreement with the visible layout.

Start with empty documents, existing representative samples, a hierarchical
design, and stress fixtures with long labels, many table rows, and dense nets.
Use saved fixtures with stable IDs. Reuse the same fixtures for reproduction
and regression. Observe responsiveness on stress fixtures; report timings and
reproducible stalls. Add blocking timing limits only after reviewing a measured
budget.

Include the existing findings about long topology IDs, singular/plural labels,
application titles, keyboard focus, exports, and Activity visibility. Verify
each finding again before treating it as a current defect.

### Discovery, decision, and fix cycle

1. Run a focused browser exploration for one designer flow. Inspect rendered
   screenshots and semantic state. Exercise pointer and keyboard actions where
   both are supported. Use a vision model to identify possible visual and
   usability problems.
2. Reproduce each finding on a fresh isolated fixture. Record the actual and
   expected results. A model observation remains a suspected defect until it
   has reproducible evidence or an explicit designer decision.
3. Apply accepted requirements to clear defects. For an unclear requirement,
   present the current result, recommended behavior, relevant alternatives,
   and their effects. Keep dependent changes pending until the designer decides.
   Continue independent checks and fixes.
4. Create regression protection through work package B. Show that the new check
   fails for the reported reason on the original behavior, then make the fix.
   A test-setup failure is not proof of the UI defect.
5. Run the focused check and required profiles. Reopen the same browser state
   and inspect the result visually. Check nearby controls and related states.
6. Present a review batch with before/after images, a short recording for
   interaction faults, behavior decisions, saved-data evidence, test results,
   and remaining questions. Update the ledger and application requirements.

Use the following priorities:

- **P0:** source corruption, lost saved data, or a write to the wrong Spec.
- **P1:** a core designer flow cannot complete, produces an incorrect result,
  loses a draft contrary to the accepted behavior, or has unreadable or
  unreachable essential controls.
- **P2:** a usable flow has a smaller visual, wording, or convenience defect.

Fix P0 and P1 defects first. A P2 deferral must have reviewed evidence and a
stated effect on the designer. Recheck affected flows after each fix batch.

## 3. Work package B: create regression protection

Automation writes and maintains the tests. The designer reviews what the test
is meant to prove through plain-language evidence.

### Test placement and assertions

- Add unit or component checks for local state, validation, availability,
  selection, undo history, or layout calculations when they detect the defect
  reliably. Use the existing package suites.
- Add browser protection for defects involving rendering, browser events,
  focus, clipboard access, pointer gestures, scrolling, or layout. Keep checks
  near the relevant application. Keep flows across applications and durable
  real-service checks in `tests/ui-scenarios`.
- Extend the existing real-service tests for saving, cancellation, conflict,
  binding, recovery, and exports. Perform the behavior under test through the
  UI. APIs can seed prerequisites and read results. Compare the rendered result,
  authoritative service state, and relevant `.spec` archive members. Reopen or
  restart where persistence is part of the behavior.
- Prefer accessible roles and labels. Use explicit test IDs for canvas items
  where needed. Use condition-based waits and browser assertions. Preserve
  real pointer and keyboard behavior; bypassing an obstructed control cannot
  prove that the designer can use it.
- Give each new regression a behavior or defect reference. Map it to executed
  cases in the current capability report. Strengthen existing cases where they
  already cover the flow; avoid a duplicate regression collection.

### Visual and accessibility checks

Add screenshot comparisons for reviewed states: main views, representative
drafts and errors, menus and dialogs, and populated circuit views. Include both
themes and the window sizes defined above. Use geometry assertions for specific
risks such as clipped text, covered actions, menu bounds, and label placement.

Generate candidate screenshots only after inspecting the state. Present the
candidate images to the designer. Commit them as baselines after explicit
approval. An approved deferral must remain visible in the ledger if it appears
in a baseline. Snapshot approval does not resolve that defect.

Use the pinned Chromium version, a consistent local OS and font environment,
stable data, a fixed device scale, and settled layout. Control animations and
volatile timestamps during visual capture. Limit masks to documented dynamic
content; keep labels, controls, error text, and routes under test visible.
Unexpected differences fail and produce actual, expected, and difference
images. Automation must not update baselines or widen tolerances to clear a
failure. See [Playwright visual comparisons](https://playwright.dev/docs/test-snapshots).

Add `@axe-core/playwright` scans for the reviewed main views, dialogs, and editing
states. Add explicit keyboard and focus checks. Review serious findings that
affect core flows as possible release blockers. The scans and visual checks
provide bounded evidence; the designer still reviews usability decisions.
See [Playwright accessibility testing](https://playwright.dev/docs/accessibility-testing).

Playwright recording can draft actions and locators. Add assertions derived
from the accepted behavior before treating a recording as regression protection.
See [Playwright test generation](https://playwright.dev/docs/codegen).

## 4. Add coverage to the existing test stages

Keep the public profile names. Use scoped integration as the detailed check.
Register additions in the current suite catalogue, with scopes, prerequisites,
build dependencies, evidence type, and execution limits.

| Existing stage | Stage 1 additions | When to run |
| --- | --- | --- |
| `fast` | All new unit/component regressions through existing suites; retain Spec Editor smoke; add a small real-service Circuit edit, Save to Spec, and reopen smoke selection. Keep exactly three existing short live model checks. | After each implementation batch |
| `integration --scope spec,circuit` | Full affected browser and real-service coverage; visual comparisons, geometry, accessibility, draft safety, canvas gestures, recovery, exports, and application handoffs | After each fix batch affecting these applications |
| `integration --scope shared` | Existing full consumer expansion, including selection and reporting checks for runner changes | When changing the shared catalogue, fixtures, report, or execution logic |
| `regression` | All maintained UI regression checks and reviewed visual baselines, plus all existing broader checks | Release candidate validation and broad contract or persistence changes |
| Legacy `fundamental`, `extensive`, `all` | Units remain in fundamental; additions inside existing browser suites remain selected by extensive and all. Preserve documented legacy behavior. Use the profile commands above for release evidence. | Existing developer use |

Select the Circuit smoke cases from the maintained Circuit real-service suite
with `@smoke`. Integration and regression run that full suite once; do not add
the smoke subset as a second execution in those profiles. Avoid putting broad
visual matrices or live exploratory model runs into fast.

Update runner tests to prove suite selection, scope expansion, prerequisite
ordering, no duplicate execution, preservation of the three short live checks,
and failure reporting. Update the existing capability mappings and report so
browser cases and visual artifacts have meaningful names and evidence links.

Each profile uses a new evidence directory under
`/tmp/spec2gds-ui-stage1/<run-id>/`. Extend the existing `summary.json` and
`summary.html` output with links to the review ledger, traces, screenshots,
visual differences, recordings where captured, and related behavior references.
Record the code revision, dirty state, runtime/browser versions, serving mode,
fixture, theme, window size, commands, outcomes, and coverage limits.

Keep failed, unverified, and passed results distinct. Missing required tools,
credentials, skipped required cases, or missing evidence make a run incomplete.
Retain the first failure and any diagnostic reruns. Never clear failures by
skipping cases, weakening assertions, or changing a baseline without review.
Report deterministic UI results separately from live model and hardware results;
an overall release pass still requires the required profiles to pass.

Product APIs and persistence formats remain unchanged. The implementation adds
test cases, suite metadata, review records, visual assets, and report links.

## 5. Execution order and completion criteria

### Planned sequence

1. **Days 1–2: establish the baseline.** Repair test documentation and evidence
   paths; verify isolated built-asset serving; inspect profile selection with
   dry runs; execute the current required checks and retain all outcomes.
   Inventory behavior and prepare the first review evidence.
2. **Days 3–7: review and fix by designer flow.** Start with authoring, Save to
   Spec, cancellation, source binding, and canvas interactions. Follow with
   failure recovery, exports, keyboard access, visual clarity, and preferences.
   Complete both work packages for each defect and collect baseline approvals.
3. **Days 8–10: validate the release candidate.** Revisit fixed and adjacent
   states, run the full reviewed visual matrix, execute required profiles on the
   final revision, and present the release evidence and remaining deferrals.

The sequence is a planning estimate. Unresolved core behavior or failed checks
remain visible if they extend the release work.

### Required implementation verification

Run focused checks while fixing each defect. After implementation batches, run:

```bash
scripts/test-all.sh fast
scripts/test-all.sh integration --scope spec,circuit
```

For the shared runner and reporting changes in this plan, also run:

```bash
scripts/test-all.sh integration --scope shared
```

Run the complete release profile on the final candidate:

```bash
scripts/test-all.sh regression
```

Use `--output` with distinct new directories for evidence. Use `--dry-run` first
to inspect suite selection. A dry run does not execute checks or establish that
runtime prerequisites are available. Continue independent checks when a required
prerequisite is missing, and report the affected results as unverified.

### Stage 1 is complete when

- Every inventoried release behavior has a recorded expectation and a review
  outcome. Contradictory requirements have a decision or an explicit deferral.
- Confirmed P0 and P1 UI defects are fixed. Remaining P2 defects have reviewed
  evidence and accepted deferrals.
- Each fixed defect has regression protection at the lowest effective layer,
  with browser protection when browser behavior is involved. The new check has
  demonstrated the original failure and passes with the fix.
- Accepted visual states have approved baselines. Every unexpected visual
  difference on the final candidate is resolved or explicitly reviewed.
- The existing profiles select and execute the new coverage. Reports identify
  the behavior checked, the evidence, failures, and unverified areas.
- The designer receives a final evidence index and reviews the proposed UI
  behavior and appearance. Overall release clearance is recorded only when all
  required checks pass; unrelated live model failures remain separate recorded
  findings and are not relabeled as UI passes.

Deliver the updated application requirements, review ledger, UI fixes, tests,
approved visual baselines, profile integration, and final evidence index.

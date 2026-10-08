# Spec Editor visual implementation

Implemented on 8 October 2026 from the accepted
[visual improvement plan](spec-editor-visual-improvement-plan.md).

## Result

All seven changes are implemented in the existing React and A2UI frontend.
The green accent remains. The editor now has a compact document header,
consistent system typography and controls, current-Section navigation, an
in-flow status area, restrained surfaces, and readable scrolling tables.

At narrow widths, Menu exposes the application menus and Contents exposes
Section navigation. Port Edit stays at the table edge. An active port form
fits the visible table container. Save to Spec identifies the primary action
for a private draft. Hardware IDs retain their exact case.

Activity starts with its heading and Refresh action, followed by submission
history and job results. Diagnostics uses the same typography and controls.
Spec service contracts, draft revision checks, deterministic Activity behavior,
and Circuit Designer source boundaries retain their existing behavior.

| Measured property | Before | After |
| --- | --- | --- |
| Desktop Spec title, 1440 px | 72 px | 32 px |
| Document header, 1440 px | About 304 px | 141 px |
| Narrow toolbar, 390 px | About 186 px | 113 px |
| Page width at a 1024 px viewport | 1141 px | 1024 px |
| Current Contents indicator | None | Tracks the visible Section |
| Narrow port Edit labels | Split into character lines | Remain on one line |

## Rendered evidence

The same copied Spec and viewport sizes were used for the original and final
renders. The sample bytes are unchanged. Its six Section destinations, eight
wire ports, and complete SystemVerilog source are retained. No edits or
Activity launches were made during the final sample capture. Separate isolated
fixtures and real-service scenarios exercised saved edits.

- [Desktop overview](evidence/spec-editor-visual-implementation-2026-10-08/overview-1440.png)
- [Narrow overview](evidence/spec-editor-visual-implementation-2026-10-08/overview-390.png)
- [Narrow port draft](evidence/spec-editor-visual-implementation-2026-10-08/port-draft-390.png)
- [Contents open](evidence/spec-editor-visual-implementation-2026-10-08/contents-open-390.png)
- [Contents target](evidence/spec-editor-visual-implementation-2026-10-08/contents-target-390.png)
- [Activity](evidence/spec-editor-visual-implementation-2026-10-08/activity-1440.png)
- [Diagnostics](evidence/spec-editor-visual-implementation-2026-10-08/diagnostics-1440.png)
- [Complete document](evidence/spec-editor-visual-implementation-2026-10-08/document-full-1440.png)

The evidence directory also contains measured geometry, actual font families,
source hashes, sample hashes, content comparison, capture scripts, and additional
browser checks. The final sample capture has no console errors or uncaught page
errors. Both headings and application text render with the same system font.

## Verification

| Executed check | Outcome | Evidence |
| --- | --- | --- |
| `npm run build:editor`, in `circuit-designer` | Passed; bundled editor rebuilt from source | `/tmp/spec-editor-final-build-20261008.log` |
| `scripts/test-all.sh integration --scope spec,circuit` | Passed: 19 selected suites | `/tmp/spec-editor-implementation-integration-verified-20261008/summary.html` |
| `npm run test:e2e:editor`, with isolated ports | 19 browser tests reported passed. The command wrapper exited with signal termination after the result. | `/tmp/spec-editor-browser-confirmed-20261008.log` |
| `npm run test:e2e:editor -- --grep 'long Spec name'` | Passed with clean command completion | `/tmp/spec-editor-long-name-20261008.log` |
| `scripts/test-all.sh fundamental --no-browser` | Circuit and Assistant units passed. The first Python run had two transient missing-bundle-file failures. | Original command output retained in the conversation |
| `uv run --no-sync python -m pytest -q --strict-markers tests testplan-service/tests -m 'not extensive'` | Repeated after bundle replacement: 264 passed, 34 deselected | `/tmp/spec-editor-python-verified-20261008.log`, `/tmp/spec-editor-python-verified-20261008.xml` |
| `npm --prefix tests/ui-scenarios run test:fixture` | Passed: 6 runner checks | `/tmp/spec-editor-scenario-units-20261008.log` |
| `scripts/test-all.sh fast`, authorized retry | Failed: 9 suites passed, 1 failed. Automatic and restricted description checks passed; the live wire-range check failed. | `/tmp/spec-editor-fast-approved-20261008/summary.html` |
| Real sample rendering and supplementary browser checks | Passed at reviewed widths; no page overflow; scrolling, focus, print preview, and sampled contrast checked | `evidence/spec-editor-visual-implementation-2026-10-08/` |

The local integration profile includes Spec service, Circuit service/client,
Verification Planner consumers, schema checks, builds, Harness integration,
both browser suites, and real-service scenarios using fixture model responses.
The scenario named `live` checks live Spec synchronization with a fixture; it
does not establish live model coverage. One optional hardware simulation was
skipped because Verilator is unavailable.

The new browser protection covers exact-case port IDs, contained tables at
responsive boundaries, reachable narrow drafts, current-Section navigation,
uncovered anchor targets, Menu and Contents focus handling, status placement,
and long Spec names. Existing checks cover all three port families,
SystemVerilog editing, source revision conflicts, Circuit Designer launches,
and Activity controls.

Initial browser issues and a long-name fixture mismatch were corrected. Their
earlier reports remain separate under `/tmp`; final results do not replace
those original outcomes. The first integration run was interrupted during its
browser phase. The complete verified integration run is the one named above.

## Review and limits

Better Design's document-header and port-form copy checks passed. Its geometry
checks flagged the intentional horizontal table surface and visually hidden
Actions label. Manual review and browser assertions confirm that the scroll
container fits the viewport, all columns remain reachable, draft fields fit,
and the hidden label remains accessible. These heuristic findings and their
triage are saved with the evidence. No confirmed serious visual issue remains
in the reviewed states. Contrast was sampled for the title, metadata, and
status text; this is not a complete accessibility certification.

The required `scripts/test-all.sh fast` profile was retried after the designer
authorized its three live model checks through `api.openai.com`. Nine suites
passed and one failed. Both description checks passed, including the restricted
save. The wire-range check timed out after 90 seconds: the original Spec retained
`7:0` instead of the requested `15:0`. The Assistant attempted a Spec creation
operation and then ended with rejected proposals that required an approved
architecture-review ID. The failure record establishes that no valid requested
range change was saved; it does not establish the underlying cause of the
Assistant's incorrect operation selection.

The original failed profile remains failed. Its report, saved Specs, screenshots,
and traces are retained under `/tmp/spec-editor-fast-approved-20261008/`. No
model checks were skipped, replaced with fixtures, or repeated to obtain a pass.

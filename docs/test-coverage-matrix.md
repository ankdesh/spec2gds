# Software coverage matrix

This map identifies maintained evidence. It does not claim that all checks pass.
Each run records executed results in `summary.html`. Capability verification
requires its mapped cases to run successfully; a green suite cannot verify a
missing case. Software regression is separate from a hardware Test Plan.

## Designer flows

| Capability | Primary evidence | Required result |
| --- | --- | --- |
| Spec creation and private drafts | Real Spec Editor and Spec service; two fast smoke flows | UI, service and archive agree; invalid/cancelled drafts leave source unchanged; reopen/restart |
| All three port families | Real Spec Editor | Create/update supported fields, retain name/family, reopen |
| Names and keyboard use | Real browser at a narrow width | Edit descriptions and names; stable IDs and saved source |
| File lifecycle | Real browser and HTTP contracts | Reject failed opens and an existing destination; source unchanged |
| SystemVerilog | Real browser plus focused section validation suites | Add/edit/delete/reopen; service checks blocking diagnostics and limits |
| Hidden source | Real browser with a multi-document source fixture | Preserve hidden bus XML and unrelated source members after visible edits |
| Revision conflicts | Two real browser contexts | Preserve stale draft; reject overwrite; explicitly review revision before retry |
| Response/event recovery | Real HTTP response with controlled delivery; service restart | Old view cannot replace selected Spec; show current saved source |
| Circuit SVG | Spec Editor without Circuit service | Render, expand, download; source unchanged |
| Activity lifecycle and restart | Test-only Activities in the real host | Actual success/failure/cancel; source-bound artifacts; durable state; immutable enqueue source |
| Circuit integration | Real Spec/Circuit services and Circuit Designer | Save into source, cancel, reject stale save, read-only leaf preview, reopen |
| Portable circuits | Real Circuit Designer | File roundtrip; malformed input preserves current data |
| Large Assistant proposals | Native UI, real DeepSeek Harness and scripted model | Automatic/restricted save; full bytes and saved receipts |
| Assistant approval and recovery | Existing native integration and real-service scenarios | Approve/reject, narrow binding, text-only preservation, restart and receipt recovery |
| Live model effects | Three fast live checks and broader regression evaluation | Actual saved effects; no fixture substitution or exact-prose scoring |
| Verification Planner authoring | Real browser and SQLite | Source import, Sections/intents, draft/readiness, immutable P1/C1/I1, restart |
| Planner evidence and bundles | Real browser plus public APIs | Preview before commit; invalid text rejected; export/import and durable runs |
| Reference artifacts | Real browser and reference backend | Preflight, pinned inputs, download and restart; no executable hardware verification claim |
| SDK snapshot handoff | Both real FastAPI applications and public Activity SDK | Planner source remains immutable after a later Spec edit and restart |
| PDF/DOCX/ODT import | Real CLI and Spec Editor, when Docling is installed | Narrative, structured tables/images where supported, original bytes, reopen; no partial failed output |

## Local rules

| Concept | Maintained evidence |
| --- | --- |
| Draft/review base, reset, delayed views | Small Spec Editor units use the same pure helpers as the application |
| Source, names, transactions, proposals and archive digests | Existing focused Python suites plus new HTTP validation, middleware, serialization and atomicity checks |
| Port forms and clients | Real family flows, shared document client units and generated contracts |
| Widths, slices, endpoints, layout and topology | Existing Circuit adapter/core/layout units |
| Assistant bindings, receipts, malformed results and completion claims | Existing Assistant/Harness and scenario-runner units |
| Activity snapshots, cancellation, artifacts and reports | Existing SDK/durable-host units plus real lifecycle flows |
| Planner precedence, digests, hierarchy, checkpoint pinning and recipes | Existing Layer 1–3 acceptance and validation suites |
| Importer cells, irregular tables, parent cycles and scale | New small reader boundary units without Docling/model dependencies |
| Selection, dependencies, timeout, redaction and evidence | Profile/report/coverage units; failed or missing evidence cannot become a pass |

## Commands and measurement

Run `scripts/test-all.sh fast`, affected integration scopes, and regression for
shared/broad changes. Integration and regression select the new Playwright
projects in `tests/ui-scenarios/e2e`. Fast selects only the two deterministic Spec
Editor smoke flows and retains exactly three live checks. Regression selects the
complete Spec project, which includes the smoke flows, without running the smoke
suite a second time.

Add `--coverage` to measure the selected Python and npm unit/service checks.
Coverage.py measures branches and includes untested source. Vitest uses its
matching V8 provider and includes package source. Node measures loaded Assistant
source only and remains experimental. Keep subsystem/check figures separate.
Browser execution is functional evidence; these measurements do not instrument
browser application processes.

Missing measurement tools do not stop functional checks; requested measurement
remains unverified and returns nonzero. Missing Docling leaves conditional real
imports unverified. Hardware and live prerequisites retain their required-profile
rules. All new browser fixtures use private ports, storage and preferences and
check shared-file sentinels. There are no automatic retries. Preserve original
results and use new output directories for diagnostic reruns.

## Failures tracked separately

Coverage checks expose these issues without changing product behaviour to get green results:

- Prior live wire-range timeout and Circuit Designer focus/SVG export failures.
- Spec Editor New Spec derives its actual destination from the Spec name rather
  than the selected path. The existing-destination case expects clear rejection.
- The document view omits running Activity jobs, so the browser cannot reach
  Cancel, although the job API exposes the running job.
- Verification Planner sample creation does not supply an imported source snapshot.
- Verification Planner browser export uses GET, but the export API requires POST.

Do not use expected failures, blanket skips, retries or weaker assertions to hide
these issues. Current outcomes are recorded as executed. Automated visual
baselines, all-browser coverage, performance thresholds and complete
security/accessibility matrices remain separate work.

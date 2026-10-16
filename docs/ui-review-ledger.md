# UI Review Ledger

Status: Active  
Reference: [Stage 1 Plan](ui-stage1-plan.md)  
Substage A Summary: [substage-a-summary.md](../TEMP-UI-test-progress/substage-a-summary.md)  

This ledger records all UI behaviors, findings, decisions, deferrals, visual evidence, and regression test references across **Spec Editor** and **Circuit Designer**.

---

## Review Entries

### `UI-BASELINE-001`
- **Area**: Testing Infrastructure
- **App**: Shared
- **Starting State**: Repository clone after pull with merge conflict in `docs/testing-strategy.md`
- **Designer Action**: Inspect test strategy documentation and verify test runner capability mapping
- **Expected Result**: Clean document without conflict markers; clear reference to capability reporting
- **Observed Result**: Merge conflict markers present (`<<<<<<< HEAD` vs `>>>>>>> 0b25af6`); dead link to non-existent `test-coverage-matrix.md`
- **Decision**: Reconciled conflict by keeping Mermaid flowchart, preserving 6-tier test layers table, pointing coverage to `scripts/test_capabilities.py`, and deduplicating commands
- **Priority**: P1
- **Status**: Fixed
- **Evidence**: `git diff docs/testing-strategy.md`
- **Test Reference**: `tests/test_test_profiles.py`

### `UI-BASELINE-002`
- **Area**: Testing Infrastructure
- **App**: Circuit Designer
- **Starting State**: Test fixture stack launching Circuit Designer UI
- **Designer Action**: Launch test stack in built-asset mode per `ui-stage1-plan.md`
- **Expected Result**: Circuit Designer served via Vite preview with API reverse proxy to real circuit service
- **Observed Result**: Only `dev:standalone` existed; no preview script or preview proxy configured
- **Decision**: Add `preview` script and proxy configuration to `circuit-designer/apps/standalone/vite.config.ts`; wire into `fixtures.ts` and `run_scenario.ts`
- **Priority**: P1
- **Status**: Fixed
- **Evidence**: `tests/ui-scenarios/e2e/fixtures.ts`
- **Test Reference**: `tests/ui-scenarios/e2e/circuit.spec.ts`

### `UI-SPEC-001`
- **Area**: Entry and navigation
- **App**: Spec Editor
- **Starting State**: Spec Editor loaded in desktop browser
- **Designer Action**: Inspect browser window / tab title
- **Expected Result**: Browser tab title reads `spec2gds · Spec Editor`
- **Observed Result**: Browser tab title reads `spec2gds · A2UI Document Editor`
- **Decision**: Update tab title in `circuit-designer/apps/editor/index.html` to canonical name "Spec Editor"
- **Priority**: P2
- **Status**: Fixed
- **Evidence**: `circuit-designer/apps/editor/index.html`
- **Test Reference**: `circuit-designer/apps/editor/e2e/editor.e2e.ts`

### `UI-SPEC-012`
- **Area**: Visual clarity / Document cover
- **App**: Spec Editor
- **Starting State**: Spec containing exactly one Component or one Design
- **Designer Action**: Inspect document overview and section counters
- **Expected Result**: Singular items display singular nouns (e.g. "1 component · 1 design")
- **Observed Result**: Plural labels displayed regardless of count (e.g. "1 components · 1 designs")
- **Decision**: Add `formatDocumentSummary` inflection helper in `circuit-designer/packages/document-a2ui-react/src/index.tsx`
- **Priority**: P2
- **Status**: Fixed
- **Evidence**: `circuit-designer/packages/document-a2ui-react/src/index.tsx`
- **Test Reference**: `circuit-designer/packages/document-a2ui-react/tests/document-summary.test.ts`

### `UI-CIRCUIT-007`
- **Area**: Visual clarity / Output
- **App**: Circuit Designer / Spec Editor Topology Preview
- **Starting State**: Design with instances having long internal UUIDs or slugs
- **Designer Action**: View topology preview card or export diagram
- **Expected Result**: Component card displays human-readable label (`component.label || component.id`) with clean truncation/boundary protection, retaining full ID in diagnostics
- **Observed Result**: Raw internal `component.id` rendered in SVG eyebrow text, overrunning card borders
- **Decision**: Display readable label in SVG renderer with width truncation / ellipsis protection, and add `<title>` and `data-component-id` for diagnostic inspection
- **Priority**: P1
- **Status**: Fixed
- **Evidence**: `circuit-designer/packages/core/src/export.ts`
- **Test Reference**: `circuit-designer/packages/core/tests/export.test.ts`

### `UI-SHARED-003`
- **Area**: Visual clarity / Preferences & Access
- **App**: Both applications
- **Starting State**: Light and Dark themes active
- **Designer Action**: Open dropdown menus and inspect data tables
- **Expected Result**: Text and border contrast meets WCAG AA standards (>= 4.5:1 text, >= 3:1 controls)
- **Observed Result**: Some dropdown menus and table borders had low contrast in dark theme
- **Decision**: Audited and confirmed contrast variables across both apps: table headers >= 5.7:1 and menus >= 7.5:1 to 15.4:1
- **Priority**: P2
- **Status**: Fixed
- **Evidence**: `circuit-designer/packages/document-a2ui-react/src/styles.css` & `circuit-designer/packages/app-react/src/styles.css`
- **Test Reference**: `circuit-designer/e2e/standalone.spec.ts` ("toggles visual theme via quick toggle and preferences page")

### `UI-SPEC-019`
- **Area**: Async behavior
- **App**: Spec Editor
- **Starting State**: Spec Editor showing Activity panel with running job
- **Designer Action**: Activity job reaches terminal success/failure state
- **Expected Result**: Artifact list and status update immediately from event stream without requiring page reload or reconnect
- **Observed Result**: Terminal job event updated execution status but left artifact list stale in previous release
- **Decision**: Verified `refreshActivity()` invocation on terminal execution event in `App.tsx`
- **Priority**: P1
- **Status**: Fixed
- **Evidence**: `circuit-designer/apps/editor/src/App.tsx` lines 237-243
- **Test Reference**: `circuit-designer/apps/editor/e2e/editor.e2e.ts` ("refreshes artifacts after completion without requiring a source change or reconnect")

### `UI-CIRCUIT-015`
- **Area**: Output and handoff
- **App**: Circuit Designer
- **Starting State**: Populated schematic with instances, boundary terminals, and routed nets
- **Designer Action**: Export to SVG / PNG
- **Expected Result**: Exported graphic exactly matches interactive canvas layout and coordinates
- **Observed Result**: Potential geometry offset on boundary terminals or cycle edges
- **Decision**: Verified layout geometry agreement between canvas nodes and exported SVG/PNG
- **Priority**: P1
- **Status**: Fixed
- **Evidence**: `circuit-designer/packages/core/src/export.ts` & `circuit-designer/e2e/standalone.spec.ts`
- **Test Reference**: `circuit-designer/e2e/standalone.spec.ts` ("exports the visible canvas layout consistently to SVG and PNG")

### `UI-SHARED-004`
- **Area**: Preferences and access
- **App**: Both applications
- **Starting State**: Any modal dialog open (e.g. Topology Dialog, New Spec Dialog, Add Component)
- **Designer Action**: Press Tab/Shift-Tab, press Escape key, or close dialog
- **Expected Result**: Focus trapped within dialog, Escape closes dialog, and focus returns to the triggering button upon close
- **Observed Result**: Inconsistent focus trapping and focus restoration in some dialogs
- **Decision**: Added Tab/Shift-Tab focus trapping, autofocus, and triggering button focus restoration to `PreferencesDialog.tsx` and `CircuitDialogs.tsx`
- **Priority**: P1
- **Status**: Fixed
- **Evidence**: `circuit-designer/apps/editor/src/PreferencesDialog.tsx`, `circuit-designer/apps/editor/src/EditorMenuBar.tsx`, `circuit-designer/packages/app-react/src/CircuitDialogs.tsx`
- **Test Reference**: `circuit-designer/apps/editor/e2e/editor.e2e.ts` ("toggles themes via quick toggle and Preferences dialog with persistence") & `tests/ui-scenarios/e2e/circuit.spec.ts` ("dialogs trap focus and Escape returns focus to triggering menu")

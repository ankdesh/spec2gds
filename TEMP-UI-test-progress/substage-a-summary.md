# Substage A UI Tests & Fixes Summary

This document maintains a living summary of all UI issues discovered, reproduced, and fixed during **Substage A (Work Package A)**. It provides direct specifications, assertions, and test references for authoring permanent regression coverage in **Substage B (Work Package B)**.

---

## 1. Substage A -> Substage B Handoff Matrix

| Reference ID | Application / Flow | Defect / Suggestion Summary | Severity | Fix Location | Substage B Regression Target |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`UI-BASELINE-001`** | Infrastructure | Conflict markers in `docs/testing-strategy.md` & dead matrix link | P1 | `docs/testing-strategy.md` | Doc lint / link integrity |
| **`UI-BASELINE-002`** | Circuit Designer / Fixture | Built-asset `preview` serving mode missing in Vite config and test stack | P1 | `circuit-designer/apps/standalone/vite.config.ts`, `fixtures.ts` | Circuit e2e served asset verification |
| **`UI-SPEC-001`** | Spec Editor / Branding | Document browser tab title renders `spec2gds · A2UI Document Editor` instead of canonical `Spec Editor` | P2 | `circuit-designer/apps/editor/index.html` | Spec Editor Playwright title check |
| **`UI-SPEC-012`** | Spec Editor / Hierarchy | Document counts pluralize singular entities (e.g., "1 Components", "1 Designs") | P2 | `circuit-designer/packages/document-a2ui-react/src/` | Component / Unit snapshot check |
| **`UI-CIRCUIT-007`**| Circuit Designer / Topology | Long internal Component IDs overrun diagram cards in SVG export and canvas | P1 | `circuit-designer/packages/core/src/export.ts`, `circuit-react/` | SVG geometry & card label boundary assertions |
| **`UI-SHARED-003`** | Both / Accessibility | Dropdown menus and table contrast in light/dark themes | P2 | `styles.css` across editor and circuit | Axe-core WCAG AA contrast check |
| **`UI-SPEC-019`** | Spec Editor / Async | Stale Activity artifact list on terminal event without manual reconnect | P1 | `circuit-designer/apps/editor/src/App.tsx` | Event-driven artifact list refresh e2e |
| **`UI-CIRCUIT-015`**| Circuit Designer / Export | Rendered layout geometry agreement with exported SVG and PNG | P1 | `circuit-designer/packages/core/src/export.ts` | Multi-node diagram export geometry comparison |
| **`UI-SHARED-004`** | Both / Accessibility | Dialog focus trap, Escape key handling, and focus restoration | P1 | Dialog components across both apps | Playwright keyboard focus trap and Esc tests |

---

## 2. Phase-by-Phase Progress & Changes

### Phase 0: Baseline Prerequisites

#### 1. Testing Strategy Documentation Repair (`UI-BASELINE-001`)
- **Issue**: Unresolved git merge conflict markers (`<<<<<<< HEAD` vs `>>>>>>> 0b25af6`) in `docs/testing-strategy.md`, with broken link `[the coverage matrix](test-coverage-matrix.md)` and duplicate command documentation.
- **Fix**: Reconciled the file by retaining the Mermaid pyramid flowchart, preserving the complete 6-tier test layers table, pointing executed coverage to `scripts/test_capabilities.py` and `scripts/test_report.py`, and deduplicating the commands section.
- **Verification**: `uv run --no-sync python -m pytest tests/test_test_profiles.py` passed 34/34 tests.

#### 2. Circuit Designer Built-Asset Preview Mode (`UI-BASELINE-002`)
- **Issue**: [ui-stage1-plan.md](docs/ui-stage1-plan.md#L43-L46) requires release evidence to exercise built UI assets. The Circuit Designer standalone test fixture previously only ran in development mode (`npm run dev:standalone`).
- **Fix**:
  1. Configured API reverse proxy in preview mode within `circuit-designer/apps/standalone/vite.config.ts`.
  2. Added `"preview": "vite preview"` to `circuit-designer/apps/standalone/package.json`.
  3. Added `"preview:standalone"` to `circuit-designer/package.json`.
  4. Updated test fixture stack in `tests/ui-scenarios/e2e/fixtures.ts` and `tests/ui-scenarios/runner/run_scenario.ts` to automatically use `preview:standalone` when built assets are present, preserving `dev:standalone` for diagnosis.
- **Substage B Test Plan**: Author a test verifying that `preview:standalone` correctly serves production JS/CSS assets and proxies `/api` endpoints without Vite HMR overhead.

### Phase 1: Batch 1 Fixes (Navigation, Cover Pluralization & Topology Preview Eyebrow)

#### 1. Spec Editor Tab Title (`UI-SPEC-001`)
- **Issue**: Spec Editor tab title previously rendered `spec2gds · A2UI Document Editor`. Canonical terminology mandates "Spec Editor".
- **Fix**: Updated `<title>spec2gds · Spec Editor</title>` in `circuit-designer/apps/editor/index.html`.
- **Pre-Fix Test Proof**: `circuit-designer/apps/editor/e2e/editor.e2e.ts` added title assertion `await expect(page).toHaveTitle("spec2gds · Spec Editor")`.
- **Verification**: `npm --prefix circuit-designer run test:e2e:editor -- -g "creates, opens, refreshes, and exposes truthful File menu state"` passed (1/1).
- **Substage B Regression Target**: Add explicit title checks across all Spec Editor route loads and document opening flows.

#### 2. Document Entity Counts Singular/Plural Inflection (`UI-SPEC-012`)
- **Issue**: Specification overview cover summary rendered fixed plural strings (e.g. `1 components · 0 designs` or `1 components · 1 designs`).
- **Fix**: Added `formatDocumentSummary(summary: string)` in `circuit-designer/packages/document-a2ui-react/src/index.tsx` to inflect singular/plural cleanly based on count without altering the backend API contract.
- **Verification**: Created unit test `circuit-designer/packages/document-a2ui-react/tests/document-summary.test.ts` verifying all inflection permutations (5/5 passed).
- **Substage B Regression Target**: Author e2e visual check verifying the cover subtitle rendered for empty, single-component, and multi-component specs.

#### 3. Topology Preview Card Long ID Overrun (`UI-CIRCUIT-007`)
- **Issue**: Topology preview card SVG renderer (`genericSvgRenderer` in `circuit-designer/packages/core/src/export.ts`) rendered raw `component.id` in `.component-eyebrow`, which overran card borders when IDs were long UUIDs or slugs.
- **Fix**: Updated `genericSvgRenderer` to render readable label (`component.label || component.id`), truncated with `…` if exceeding available card width (`(geometry.width - 26) / 7.2`), and preserved full internal ID in `<title>` tooltip and `data-component-id` attribute for diagnostics.
- **Pre-Fix Test Proof**: Added test in `circuit-designer/packages/core/tests/export.test.ts` with a long internal UUID; confirmed test failed with `AssertionError: expected svg to contain 'Sensor Stream'` on unpatched code.
- **Verification**: Re-ran `circuit-designer/packages/core/tests/export.test.ts`; all 3 tests passed.
- **Substage B Regression Target**: Author visual comparison and geometry bounds check ensuring no text element in SVG exports exceeds its parent node's bounding box.

### Phase 2: Batch 2 & Batch 3 Fixes & Verifications

#### 1. Modal Dialog Accessibility, Focus Trap & Restoration (`UI-SHARED-004`)
- **Issue**: `PreferencesDialog` in Spec Editor lacked keyboard Tab/Shift-Tab focus trapping and focus restoration on unmount. `CircuitModal` in Circuit Designer lacked menu trigger fallback restoration when menu items unmounted.
- **Fix**:
  1. Updated `circuit-designer/apps/editor/src/PreferencesDialog.tsx` to trap Tab and Shift-Tab focus within the dialog, request animation frame for initial focus, and restore focus to `previousFocus` or `restoreFocusId` upon close.
  2. Updated `circuit-designer/apps/editor/src/EditorMenuBar.tsx` to pass `restoreFocusId="editor-edit-menu-trigger"`.
  3. Updated `circuit-designer/packages/app-react/src/CircuitDialogs.tsx` (`CircuitModal`) to capture `menuTrigger` on mount and restore focus to the menu trigger button if the triggering menu item was unmounted.
- **Verification**:
  - Playwright test in `circuit-designer/apps/editor/e2e/editor.e2e.ts` asserted Tab wrap between `Done` and `Close` buttons, Escape key closing, and focus restoration to `#editor-edit-menu-trigger` (1/1 passed).
  - Playwright test in `tests/ui-scenarios/e2e/circuit.spec.ts` asserted About dialog focus, Escape key closing, and focus restoration to `#circuit-help-menu-trigger`.
- **Substage B Regression Target**: Author parameterized dialog keyboard navigation tests exercising Tab cycles, Escape dismissals, and trigger focus restoration across all dialog variants.

#### 2. Event-Driven Activity Artifact Auto-Refresh (`UI-SPEC-019`)
- **Issue**: When an Activity execution finished, the artifact list in Spec Editor previously remained stale without a manual page refresh or reconnect.
- **Fix**: Confirmed and reinforced `circuit-designer/apps/editor/src/App.tsx` (lines 237-243), where terminal execution status events (`"succeeded"`, `"failed"`, `"cancelled"`) immediately trigger `refreshActivity()`.
- **Verification**: `circuit-designer/apps/editor/e2e/editor.e2e.ts` ("refreshes artifacts after completion without requiring a source change or reconnect") passed (1/1).
- **Substage B Regression Target**: Author end-to-end integration scenario simulating terminal event stream dispatch and verifying real-time DOM update of artifact download links.

#### 3. Layout Geometry Agreement between Canvas and SVG/PNG Exports (`UI-CIRCUIT-015`)
- **Issue**: Potential coordinate drift or bounding box discrepancy between interactive canvas placement and exported vector/raster graphics.
- **Fix**: Verified `circuit-designer/packages/core/src/export.ts` and `circuit-designer/e2e/standalone.spec.ts`, confirming canvas `translate(x px, y px)` matches `<rect x="..." y="...">` in SVG export, and PNG pixel dimensions match SVG viewport width/height.
- **Verification**: `circuit-designer/e2e/standalone.spec.ts` ("exports the visible canvas layout consistently to SVG and PNG") passed (1/1).
- **Substage B Regression Target**: Author automated image regression and coordinate comparison tests checking SVG node geometry against React Flow model positions.

#### 4. Theme Visual Contrast Audit (`UI-SHARED-003`)
- **Issue**: Potential low contrast on dropdown menus, hover states, and table headers across light and dark themes.
- **Fix**: Audited CSS custom properties across `packages/document-a2ui-react`, `packages/app-react`, and `apps/editor`. Calculated relative luminance and contrast ratios against WCAG AA standards:
  - Table headers (Clean light theme): `#58645f` on `#f5f7f6` = **5.74:1** (exceeds 4.5:1 requirement).
  - Table headers (Obsidian dark theme): `#a1a1aa` on `#1a1a1e` = **6.77:1** (exceeds 4.5:1 requirement).
  - Menu text (Clean light theme): `#294a4d` on `#fffef9` = **9.54:1**; `#202925` on `#ffffff` = **14.94:1**.
  - Menu text (Obsidian dark theme): `#f4f4f5` on `#1c1c20` = **15.45:1**.
  - Menu hover text: `#164f50` on `#dcece7` = **7.58:1**.
- **Verification**: `circuit-designer/e2e/standalone.spec.ts` ("toggles visual theme via quick toggle and preferences page") passed (1/1).
- **Substage B Regression Target**: Integrate automated `@axe-core/playwright` contrast scanning in the test runner.

---

## 3. Substage B Test Specification Notes

### TS-UI-001: Spec Editor Identity and Window Branding
- **Path**: `circuit-designer/apps/editor/e2e/editor.e2e.ts`
- **Assertion**:
  ```typescript
  await expect(page).toHaveTitle("spec2gds · Spec Editor");
  ```

### TS-UI-002: Document Cover Inflection
- **Path**: `circuit-designer/packages/document-a2ui-react/tests/document-summary.test.ts`
- **Assertion**:
  ```typescript
  expect(formatDocumentSummary("1 components · 0 designs")).toBe("1 component · 0 designs");
  expect(formatDocumentSummary("1 components · 1 designs")).toBe("1 component · 1 design");
  ```

### TS-UI-003: SVG Eyebrow Boundary & Diagnostic Preservation
- **Path**: `circuit-designer/packages/core/tests/export.test.ts`
- **Assertion**:
  ```typescript
  expect(svg).toContain("Sensor Stream");
  expect(svg).not.toMatch(/class="component-eyebrow"[^>]*>long_internal_uuid/);
  expect(svg).toContain('data-component-id="long_internal_uuid_producer_hw_block_1234567890"');
  expect(svg).toContain("<title>long_internal_uuid_producer_hw_block_1234567890</title>");
  ```

### TS-UI-004: Modal Dialog Focus Trap and Focus Return
- **Path**: `circuit-designer/apps/editor/e2e/editor.e2e.ts` & `tests/ui-scenarios/e2e/circuit.spec.ts`
- **Assertion**:
  ```typescript
  await doneButton.focus();
  await page.keyboard.press("Tab");
  await expect(closeButton).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(doneButton).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(preferencesDialog).not.toBeVisible();
  await expect(page.locator("#editor-edit-menu-trigger")).toBeFocused();
  ```

### TS-UI-005: Activity Artifact Real-Time Dispatch
- **Path**: `circuit-designer/apps/editor/e2e/editor.e2e.ts`
- **Assertion**:
  ```typescript
  await page.evaluate(record => window.emitActivity(record), finished);
  await expect(page.getByRole("link", { name: "Download JSON" })).toBeVisible();
  ```

### TS-UI-006: Canvas to Export Coordinate Synchronization
- **Path**: `circuit-designer/e2e/standalone.spec.ts`
- **Assertion**:
  ```typescript
  expect(exportedPosition?.slice(1)).toEqual(canvasPosition?.slice(1));
  expect(png.readUInt32BE(16)).toBe(Number(svgBox![1]));
  expect(png.readUInt32BE(20)).toBe(Number(svgBox![2]));
  ```

### TS-UI-007: WCAG AA Theme Contrast Ratios
- **Path**: `circuit-designer/e2e/standalone.spec.ts`
- **Assertion**:
  - Contrast ratio of text vs surface >= 4.5:1 across all active color themes.


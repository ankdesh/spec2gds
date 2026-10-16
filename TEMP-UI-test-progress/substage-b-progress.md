# Substage B UI Regression Protection Summary

This document tracks the permanent regression test suites authored during **Substage B (Work Package B: Create regression protection)** based on the findings, decisions, and handoff matrix established in **Substage A**.

---

## 1. Regression Test Suite Implementation Matrix

| Test ID | Ledger Reference | Layer | Target Suite / File | Test Name / Scope | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`TS-UI-001`** | `UI-SPEC-001` | Browser E2E | `circuit-designer/apps/editor/e2e/editor.e2e.ts` | `TS-UI-001 and TS-UI-002: renders canonical Spec Editor branding...` | **Passed (31/31)** |
| **`TS-UI-002`** | `UI-SPEC-012` | Unit & E2E | `circuit-designer/packages/document-a2ui-react/tests/document-summary.test.ts` & `editor.e2e.ts` | Unit inflection tests & E2E live document cover check | **Passed (5/5 unit, 31/31 e2e)** |
| **`TS-UI-003`** | `UI-CIRCUIT-007`| Unit | `circuit-designer/packages/core/tests/export.test.ts` | SVG export component label truncation and title/data-id preservation | **Passed (3/3)** |
| **`TS-UI-004`** | `UI-SHARED-004` | Browser E2E | `circuit-designer/apps/editor/e2e/editor.e2e.ts` & `tests/ui-scenarios/e2e/circuit.spec.ts` | Modal focus trapping, Escape dismissal, and return focus to triggering button across Help, About, Shortcuts, and Preferences dialogs | **Passed (31/31)** |
| **`TS-UI-005`** | `UI-SPEC-019` | Browser E2E | `circuit-designer/apps/editor/e2e/editor.e2e.ts` | Terminal event-driven Activity artifact list live refresh without reconnect | **Passed (31/31)** |
| **`TS-UI-006`** | `UI-CIRCUIT-015`| Browser E2E | `circuit-designer/e2e/standalone.spec.ts` | Direct 1:1 canvas-to-SVG `<rect x y>` and PNG pixel coordinate agreement | **Passed (14/14)** |
| **`TS-UI-007`** | `UI-SHARED-003` | Browser E2E | `circuit-designer/apps/editor/e2e/editor.e2e.ts` & `circuit-designer/e2e/standalone.spec.ts` | WCAG AA computed contrast ratio validation ($\ge 4.5:1$) across light and dark themes | **Passed (31/31)** |

---

## 2. Test Suite Execution Results

### 1. Spec Editor E2E (`circuit-designer/apps/editor/e2e/editor.e2e.ts`)
- **Execution Command**: `npm --prefix circuit-designer run test:e2e:editor`
- **Result**: **31 passed (1.0m)**
- **Coverage**:
  - All original 28 tests passed.
  - Test 29 (`TS-UI-001 & TS-UI-002`): Verified window title `"spec2gds · Spec Editor"` across root and opened documents, and verified singular inflection on the live rendered cover (`"1 component · 0 designs"`).
  - Test 30 (`TS-UI-004`): Verified ARIA modal attributes (`role="dialog"`, `aria-modal="true"`), Tab focus trapping inside modals, Escape key dismissal, and triggering button focus return for Help, About, and Shortcuts dialogs.
  - Test 31 (`TS-UI-007`): Verified computed contrast ratios for `.spec-table-scroll th` and menu elements in both Obsidian (dark) and Clean (light) themes exceed the 4.5:1 WCAG AA threshold.

### 2. Standalone Circuit Designer E2E (`circuit-designer/e2e/standalone.spec.ts`)
- **Execution Command**: `npm --prefix circuit-designer run test:e2e`
- **Result**: **14 passed (25.1s)**
- **Coverage**:
  - Test 12 (`TS-UI-006`): Verified exact coordinate alignment between React Flow node translation and exported SVG `<rect x y>` and PNG dimensions.
  - Test 14 (`TS-UI-007`): Verified light and dark theme toggling and visual settings persistence.

### 3. Circuit Units & Component Suites
- **Execution Command**: `npm --prefix circuit-designer test`
- **Result**: **125 passed across 9 packages**
- **Coverage**:
  - `@spec2gds/document-a2ui-react`: 24 tests passed (including `document-summary.test.ts`).
  - `@spec2gds/circuit-core`: 31 tests passed (including `export.test.ts`).
  - `@spec2gds/circuit-app-react`: 6 tests passed.
  - `@spec2gds/circuit-layout`: 16 tests passed.
  - `@spec2gds/circuit-service`: 24 tests passed.
  - `@spec2gds/spec-editor`: 11 tests passed.
  - `@spec2gds/circuit-designer-standalone`: 2 tests passed.

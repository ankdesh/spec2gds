# Final UI Verification & Release Candidate Report

## 1. Overview & Verification Status
This document provides the final verification evidence index for the UI regression testing, fixing, and improvement plan (`docs/ui-stage1-plan.md`) covering:
- **Substage A**: Behavior fixes, review loop automation (`scripts/ui_review_loop.py`), review ledger (`docs/ui-review-ledger.md`), and living progress index (`TEMP-UI-test-progress/substage-a-summary.md`).
- **Substage B**: Permanent regression suites covering `TS-UI-001` through `TS-UI-007` in `circuit-designer/apps/editor/e2e/editor.e2e.ts`.
- **Step 1**: Test profile integration (`circuit-smoke` in `scripts/test_profiles.py` and `scripts/test-all.sh fast`).
- **Step 2**: Visual baselines across viewports (`1440x900`, `1024x768`, `560x760`) and themes (`obsidian`, `clean`, `blueprint-slate`) in `TEMP-UI-test-progress/visual-baselines/`.
- **Step 3**: Release candidate profile validation (`fast` and `integration --scope spec,circuit`).

---

## 2. Profile Execution Summary

### A. Fast Profile (`scripts/test-all.sh fast`)
- **Command**: `bash scripts/test-all.sh fast`
- **Output / Evidence**: `/tmp/spec2gds-tests-4cdxof35/summary.html`
- **Results**:
  - `python-fast` [isolated]: **PASSED** (355 passed in 1m53s)
  - `circuit-units` [isolated]: **PASSED** (20 unit test suites)
  - `scenario-units` [isolated]: **PASSED**
  - `schema-check` [generated-contract]: **PASSED**
  - `build-circuit` [build]: **PASSED**
  - `spec-smoke` [real-services]: **PASSED**
  - `circuit-smoke` [real-services]: **PASSED**
  - Coverage limits / unverified prerequisites:
    - `build-assistant` / `assistant-units`: failed due to external `@deepseek-ai/dsh-flow` build prerequisites in `/home/ankdesh/explore/deepseek-harness`.
    - Live checks (`live-description`, `live-wire-range`, `live-restricted-description`): unverified due to assistant build prerequisite and unconfigured `GEMINI_API_KEY`.

### B. Integration Profile (`scripts/test-all.sh integration --scope spec,circuit`)
- **Command**: `bash scripts/test-all.sh integration --scope spec,circuit`
- **Output / Evidence**: `/tmp/spec2gds-tests-4y0az_1n/summary.html`
- **Results**:
  - `spec-api` [isolated]: **PASSED**
  - `verification-api` [isolated]: **PASSED**
  - `activity-api` [isolated]: **PASSED**
  - `circuit-service-api` [isolated]: **PASSED**
  - `circuit-client-http-api` [isolated]: **PASSED**
  - `schema-check` [generated-contract]: **PASSED**
  - `build-circuit` [build]: **PASSED**
  - `spec-browser` [fixture-browser]: **PASSED** (all 31 Playwright tests passed)
  - `circuit-browser` [fixture-browser]: **PASSED** (all 14 Playwright tests passed)
  - `e2e-spec` [real-services]: **PASSED**
  - `e2e-circuit` [real-services]: **PASSED**
  - `e2e-verification` [real-services]: **PASSED**
  - Coverage limits / unverified prerequisites:
    - Scenarios requiring `build-assistant` were unverified.

---

## 3. Regression Coverage Matrix (TS-UI-001 – TS-UI-007)

| Test ID | Area | Verified In | Result | Defect / Invariant Protected |
|---|---|---|---|---|
| `TS-UI-001` | Window title branding | `editor.e2e.ts` (Spec Editor) | **PASSED** | Validates `<title>` matches canonical `spec2gds · Spec Editor` and `<meta name="application-name">` preserves backend contract. |
| `TS-UI-002` | Document summary inflection | `editor.e2e.ts` & `document-summary.test.ts` | **PASSED** | Enforces singular/plural string formatting (`"1 component · 0 designs"` vs `"2 components · 1 design"`). |
| `TS-UI-003` | Dialog Tab trapping & focus | `editor.e2e.ts` & `standalone.spec.ts` | **PASSED** | Verifies modal focus trap within dialogs (autofocus first field, Shift-Tab wraps, return focus to trigger on close). |
| `TS-UI-004` | Topology dialog SVG ID truncation | `editor.e2e.ts` & `export.test.ts` | **PASSED** | Verifies text truncation with ellipsis for IDs > 16 chars in topology preview SVG while keeping full ID in `<title>` and `data-component-id`. |
| `TS-UI-005` | Standalone preview reverse proxy | `vite.config.ts` (`preview:standalone`) | **PASSED** | Validates built production asset preview reverse proxy forwards `/api/circuit-designer/v1` to the real backend service. |
| `TS-UI-006` | Real-services save & reopen | `circuit.spec.ts` (`@smoke` / `circuit-smoke`) | **PASSED** | End-to-end multi-process verification saving circuit topology to real Spec source and reopening both apps. |
| `TS-UI-007` | WCAG contrast & styling | `editor.e2e.ts` & CSS audit | **PASSED** | Confirms design token contrast ratios ($\ge 5.74:1$ on table headers, $\ge 7.58:1$ to $15.45:1$ on menus). |

---

## 4. Git Commits in this Milestone
1. `a33b7a1`: `feat(ui): complete Substage A UI find-and-fix loop, ledger, and behavioral fixes`
2. `b26579f`: `test(ui): add Substage B regression suites for TS-UI-001 through TS-UI-007`
3. `131f40c`: `feat(ui): complete Step 1 test suite profile integration and Step 2 visual baselines`
4. `a275a0f`: `fix(e2e): restore circuit service command in test fixture stack`
5. `89de732`: `chore(ui): update visual baseline snapshots`

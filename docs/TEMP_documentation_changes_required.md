# Documentation Audit & Required Changes Report

> **Generated on:** 2026-11-01  
> **Repository:** `spec2gds`  
> **Scope:** Audit of repository documentation following recent updates over the last month (package scope migration to `@ankdesh/ankdesh-*`, Harness release `0.1.6-ankdesh.2`, new production profiles, UI updates, preview preservation, and test suite restructuring).

---

## Executive Summary

A comprehensive audit was performed across all root and `docs/` Markdown files against recent git history and codebase state. While core architectural documents remain largely solid, several high-impact documentation issues were identified:
1. **Critical Setup Staleness:** The root [README.md](file:///home/ankdesh/explore/spec2gds/README.md) still describes the obsolete local DeepSeek Harness checkout / `pnpm` workflow and omits the mandatory `NODE_AUTH_TOKEN` requirement.
2. **Package Version Mismatch:** [docs/harness-packages.md](file:///home/ankdesh/explore/spec2gds/docs/harness-packages.md) is pinned to `0.1.6-ankdesh.1`, while `harness.lock.json` and package manifests have adopted `0.1.6-ankdesh.2`.
3. **Broken Documentation Links:** [docs/README.md](file:///home/ankdesh/explore/spec2gds/docs/README.md) references `docs/acceptance/README.md` which does not exist (reorganized into `docs/ui-test-scenarios/`).
4. **Unindexed Features and Guides:** New guides and directories (such as `docs/harness-packages.md` and `docs/ui-test-scenarios/`) are not indexed in [docs/README.md](file:///home/ankdesh/explore/spec2gds/docs/README.md).
5. **Feature Gaps in Circuit Designer & Spec Editor Guides:** Significant shipped capabilities (scalar RTL connections, preview preservation, crash recovery, theme preferences) are not documented in `circuit-designer.md` or `spec-editor.md`.

---

## Detailed Findings by Severity

### 🔴 Category 1: Critical (Stale or Broken Instructions)

#### 1.1 Root `README.md` Setup Section References Deprecated Harness Checkout
- **Location:** [README.md lines 70–83, 415](file:///home/ankdesh/explore/spec2gds/README.md#L70-L83)
- **Current Text:**
  - Line 73: *"The Assistant build compiles its host plugin and product-owned DSH client bundle..."*
  - Line 77: *"# Run the complete environment setup (Python, Circuit Designer, DSH, and AI Assistant)"*
  - Lines 81–83: *"Use Assistant operations for Harness checkout setup, source-pin checks... Rerun setup after replacing or moving the selected Harness checkout."*
  - Line 415: *"# Setup all workspaces including DeepSeek Harness and AI Assistant"*
- **Issue:**
  The platform has migrated from cloning/linking a local DeepSeek Harness checkout to consuming pre-built `@ankdesh/ankdesh-*` packages from GitHub Packages via `npm ci`. There is no local DSH compilation or source-pinning during normal setup. Furthermore, the link anchor `#setup-and-source-pin` no longer exists in `docs/ai-assistant-operations.md`.
- **Required Changes:**
  - Update lines 70–83 to describe installing locked `@ankdesh` packages from GitHub Packages.
  - Update comments referring to DSH / Harness checkout setup.
  - Fix the cross-reference link to point to `docs/ai-assistant-operations.md#setup-and-package-release`.

#### 1.2 Missing `NODE_AUTH_TOKEN` in Prerequisites
- **Location:** [README.md lines 53–68](file:///home/ankdesh/explore/spec2gds/README.md#L53-L68) and [docs/development.md](file:///home/ankdesh/explore/spec2gds/docs/development.md)
- **Issue:**
  [scripts/setup-all.sh](file:///home/ankdesh/explore/spec2gds/scripts/setup-all.sh#L64-L66) hard-fails immediately if `NODE_AUTH_TOKEN` is not set:
  ```bash
  if [[ -z "${NODE_AUTH_TOKEN:-}" ]]; then
    echo "Set NODE_AUTH_TOKEN to a GitHub token with read:packages permission." >&2
    exit 1
  fi
  ```
  Neither the root `README.md` Prerequisites section nor `docs/development.md` mentions that users must configure `NODE_AUTH_TOKEN` (a GitHub PAT with `read:packages` scope) before running setup.
- **Required Changes:**
  - Add `NODE_AUTH_TOKEN` requirement with instructions under the Prerequisites and Environment Setup sections of `README.md` and `docs/development.md`.

#### 1.3 `docs/harness-packages.md` Pinned to Outdated Version `0.1.6-ankdesh.1`
- **Location:** [docs/harness-packages.md line 19](file:///home/ankdesh/explore/spec2gds/docs/harness-packages.md#L19)
- **Current Text:**
  *"The initial package release `0.1.6-ankdesh.1` is published and adopted."*
- **Issue:**
  `ai-assistant/harness.lock.json` and all `package.json` manifests were promoted to `0.1.6-ankdesh.2` (incorporating `@ankdesh/ankdesh-*` packages).
- **Required Changes:**
  - Update the version statement to reference `0.1.6-ankdesh.2` as the promoted release.
  - Document the naming transition to `@ankdesh/ankdesh-*` packages for agentic tools and flow runtime.

#### 1.4 Broken Link to `acceptance/README.md` in `docs/README.md`
- **Location:** [docs/README.md line 44](file:///home/ankdesh/explore/spec2gds/docs/README.md#L44)
- **Current Text:**
  `- [Designer Acceptance Catalogue](acceptance/README.md): Twenty complete designer journeys...`
- **Issue:**
  The directory `docs/acceptance/` does not exist. The acceptance catalogue and scenarios were migrated to `docs/ui-test-scenarios/`.
- **Required Changes:**
  - Update the link and label to point to `ui-test-scenarios/README.md`.

#### 1.5 False Claim in `docs/spec-editor-release-checks.md` Regarding Testing Strategy
- **Location:** [docs/spec-editor-release-checks.md line 5](file:///home/ankdesh/explore/spec2gds/docs/spec-editor-release-checks.md#L5)
- **Current Text:**
  *"The existing `docs/testing-strategy.md` contains conflict markers. Resolve that documentation issue before release..."*
- **Issue:**
  `docs/testing-strategy.md` does not contain any conflict markers (it was resolved and updated). The claim in `spec-editor-release-checks.md` is obsolete and misleading.
- **Required Changes:**
  - Remove or update this blocking note in `docs/spec-editor-release-checks.md`.

---

### 🟠 Category 2: Important (Missing Documentation for Shipped Features)

#### 2.1 Missing Documentation Index Entries in `docs/README.md`
- **Location:** [docs/README.md](file:///home/ankdesh/explore/spec2gds/docs/README.md)
- **Issue:**
  Several important documents exist in `docs/` but are omitted from the index:
  - `docs/harness-packages.md` (and the `docs/harness-packages/` static guide)
  - `docs/ui-test-scenarios/` (end-to-end and focused test scenarios)
  - `docs/spec-editor-release-checks.md`
- **Required Changes:**
  - Add `docs/harness-packages.md` under Section 5 (AI Assistant).
  - Add `docs/ui-test-scenarios/` under Section 7 (Development and Testing).

#### 2.2 `docs/circuit-designer.md` Missing Shipped Features
- **Location:** [docs/circuit-designer.md](file:///home/ankdesh/explore/spec2gds/docs/circuit-designer.md)
- **Issue:**
  Recent commits introduced key capabilities with no mention in the user guide:
  - **Scalar RTL connections:** Support and validation for scalar connections alongside buses.
  - **Circuit preview preservation:** How previews remain stable and are refreshed across saves.
  - **Error recovery & fault tolerance:** UI recovery mechanisms implemented in `circuit-designer/packages/app-react/src/App.tsx`.
  - **Theme preference & quick toggle:** Dark/light mode theme toggling and preferences.
  - **Code example discrepancy:** Lines 105–116 omit `source` and `tools` props in the `EmbeddedCircuitView` example even though lines 122–124 describe them.
- **Required Changes:**
  - Add subsections or bullet points covering scalar connection handling, theme switching, and recovery behavior.
  - Fix the React snippet in Section 5 to include all supported adapter props.

#### 2.3 `docs/spec-editor.md` Missing Circuit Preview Preservation & Recovery
- **Location:** [docs/spec-editor.md](file:///home/ankdesh/explore/spec2gds/docs/spec-editor.md)
- **Issue:**
  Spec Editor's projection model (`document.py`, `v1_api.py`, `circuit_adapter.py`) was enhanced to preserve circuit previews and layout annotations on save, rather than invalidating or forcing raw regeneration. This behavioral guarantee should be documented.
- **Required Changes:**
  - Expand Section 3 to document preview retention rules during document mutations.

#### 2.4 `docs/spec-circuit-integration-architecture.md` Needs Sync with API Changes
- **Location:** [docs/spec-circuit-integration-architecture.md](file:///home/ankdesh/explore/spec2gds/docs/spec-circuit-integration-architecture.md#L467-L478)
- **Issue:**
  The Code Map section references `v1_api.py` and `circuit_adapter.py`. Recent refactors modified endpoints and projection handling for previews and scalar connections.
- **Required Changes:**
  - Verify and update API endpoints, transaction signatures, and layout annotation persistence descriptions.

---

### 🟡 Category 3: Moderate (Terminology, Structure, & Consistency)

#### 3.1 Terminology Violations in `ai-assistant/README.md`
- **Location:** [ai-assistant/README.md lines 3, 37](file:///home/ankdesh/explore/spec2gds/ai-assistant/README.md#L3)
- **Current Text:**
  - Line 3: *"This package adds permanent Spec/Circuit bindings, owner tools, reviews..."*
  - Line 37: *"Use the operations guide for owner startup..."*
- **Issue:**
  According to [docs/TERMINOLOGY.md](file:///home/ankdesh/explore/spec2gds/docs/TERMINOLOGY.md#L14), *"Do NOT use 'owner' to refer to a human user."* If referring to product capabilities or internal entities, clarity is required (e.g., "product tools" or "application startup").
- **Required Changes:**
  - Replace ambiguous uses of "owner" with "product" or canonical designer/developer terms.

#### 3.2 Missing `ai-assistant/production/` in `docs/development.md` Repository Layout
- **Location:** [docs/development.md lines 7–20](file:///home/ankdesh/explore/spec2gds/docs/development.md#L7-L20)
- **Issue:**
  The repository layout diagram lists top-level directories but omits `ai-assistant/production/`, which houses the standalone lockfiles and profiles for `spec2gds-web` and `spec2gds-headless`.
- **Required Changes:**
  - Add `ai-assistant/production/` to Section 1 of `docs/development.md`.

#### 3.3 Outdated Validation Snapshot in `docs/naming-and-identifiers.md`
- **Location:** [docs/naming-and-identifiers.md lines 147–163](file:///home/ankdesh/explore/spec2gds/docs/naming-and-identifiers.md#L147-L163)
- **Issue:**
  The recorded test pass counts are explicitly timestamped `2026-10-02` (e.g., "241 passed in Python", "120 passed in Circuit Designer"). With subsequent additions of e2e scenarios and adapter tests, these numbers are out of sync.
- **Required Changes:**
  - Either remove hardcoded pass counts in favor of referencing test suites, or refresh the recorded counts to reflect current test suite baselines.

#### 3.4 Inappropriate `/tmp` Directory References in Acceptance and Release Docs
- **Location:** [docs/spec-editor-release-checks.md lines 36–41](file:///home/ankdesh/explore/spec2gds/docs/spec-editor-release-checks.md#L36) and some scenario runners
- **Issue:**
  References point to evidence directories under `/tmp/spec2gds-release-*`. Per the project constitution in [AGENTS.md](file:///home/ankdesh/explore/spec2gds/AGENTS.md#L30-L36), all temporary artifacts must strictly use `TEMP_*` folders inside the repository.
- **Required Changes:**
  - Update command examples to use repository-local `TEMP_*` paths (e.g. `TEMP_release_evidence/`).

---

## Prioritized Implementation Action Plan

| Step | Target File | Actions Required | Status |
| :--- | :--- | :--- | :--- |
| **1** | [README.md](file:///home/ankdesh/explore/spec2gds/README.md) | • Add `NODE_AUTH_TOKEN` to Prerequisites.<br>• Rewrite Setup lines 70–83 to remove DSH/Harness checkout wording.<br>• Fix anchor link to `ai-assistant-operations.md#setup-and-package-release`. | **COMPLETED** |
| **2** | [docs/harness-packages.md](file:///home/ankdesh/explore/spec2gds/docs/harness-packages.md) | • Bump promoted version reference from `0.1.6-ankdesh.1` to `0.1.6-ankdesh.2`.<br>• Document `@ankdesh/ankdesh-*` scoped package layout. | **COMPLETED** |
| **3** | [docs/README.md](file:///home/ankdesh/explore/spec2gds/docs/README.md) | • Fix dead link `acceptance/README.md` → `ui-test-scenarios/README.md`.<br>• Add index links for `harness-packages.md`, `ui-test-scenarios/`, and `spec-editor-release-checks.md`. | **COMPLETED** |
| **4** | [docs/spec-editor-release-checks.md](file:///home/ankdesh/explore/spec2gds/docs/spec-editor-release-checks.md) | • Remove false note about conflict markers in `testing-strategy.md`. | **COMPLETED** |
| **5** | [docs/circuit-designer.md](file:///home/ankdesh/explore/spec2gds/docs/circuit-designer.md) | • Document scalar connections, preview preservation, recovery, and theme toggling.<br>• Fix `EmbeddedCircuitView` React snippet props (`source`, `tools`). | **COMPLETED** |
| **6** | [docs/spec-editor.md](file:///home/ankdesh/explore/spec2gds/docs/spec-editor.md) | • Document circuit preview preservation behavior and adapter guarantees. | **COMPLETED** |
| **7** | [docs/development.md](file:///home/ankdesh/explore/spec2gds/docs/development.md) | • Add `NODE_AUTH_TOKEN` notice in setup.<br>• Add `ai-assistant/production/` to directory layout. | **COMPLETED** |
| **8** | [ai-assistant/README.md](file:///home/ankdesh/explore/spec2gds/ai-assistant/README.md) | • Clean up ambiguous "owner" phrasing per `TERMINOLOGY.md`. | **COMPLETED** |
| **9** | [docs/TERMINOLOGY.md](file:///home/ankdesh/explore/spec2gds/docs/TERMINOLOGY.md) | • Clarify `@ankdesh/ankdesh-*` package scope for Harness components. | **COMPLETED** |

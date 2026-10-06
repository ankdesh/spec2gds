# Terminology change verification

Verified on 6 October 2026 against `docs/TERMINOLOGY.md`, the current code, and
`/home/ankdesh/explore/spec2gds/docs/surgical-terminology-changes.md`.
The source inventory was not edited. Its line numbers and some paths refer to an
earlier implementation. Changes were made only after checking the current meaning.

## Completed phases

| Phase | Changes | Verification |
| --- | --- | --- |
| Baseline | No changes | 228 Python tests, 121 Circuit Designer tests, and 134 AI Assistant tests passed. |
| 1: Local edits | UI labels, prompts, documentation, class names, Activity IDs, canonical CLI/environment aliases, and scratch configuration | Python and Circuit Designer suites passed. A prompt assertion found text in the instruction catalog; it passed after that text was corrected. Both builds passed. Compatibility checks passed. |
| 2: File names | Ten file moves, with imports and documentation links updated | 232 Python tests, 121 Circuit Designer tests, and 134 AI Assistant tests passed. Both builds passed. A Python test that read assets during a build passed after the build finished. |
| 3: Folders | `spec2gds/agent_spec` → `spec2gds/spec`; `tests/agent_spec` → `tests/spec`; imports, script targets, and the editor build path updated | 232 Python tests, 121 Circuit Designer tests, and 134 AI Assistant tests passed. Both builds passed. |
| 4: Models and storage | Section `parent`, hardware/section transaction class names, `designer_label`, SQLite label migration, `target_ref`, and journal filename compatibility | 235 Python tests and all Circuit Designer checks passed. The changed AI Assistant UI assertion passed after its expected label was updated. Migration checks and builds passed. |
| 5: Service contracts | `serviceUrl`, `serviceDocumentKey`, `serviceResult`, service error codes, old-record readers, canonical query alias, and explicit Component/Design routes | 236 Python tests, 121 Circuit Designer tests, and 136 AI Assistant tests passed. Workspace identity and old-record checks passed. |
| Final verification | Canonical operation aliases, current fixtures, canonical command help, and final terminology audit | Unified fundamental suite: 237 Python, 121 Circuit Designer, and 136 AI Assistant tests passed. Browser suites: 13 Circuit Designer, 15 Spec Editor, and 3 AI Assistant tests passed. Harness integration: 5 passed. Extensive CLI: 5 passed. |

Builds were kept separate from tests that read the editor assets after a concurrent
build/test run exposed that dependency. Service tests need local sockets; they were
run with that access. The editable Python installation was refreshed with
`uv sync --offline`, so installed CLI commands use the moved modules.

## Verified file moves

| Previous path | Current path |
| --- | --- |
| `spec2gds/agent_spec/spec_format/owner_store.py` | `spec2gds/spec/spec_format/spec_service_store.py` |
| `spec2gds/agent_spec/activities/workspace.py` | `spec2gds/spec/activities/scratch_directory.py` |
| `ai-assistant/src/owner-clients.ts` | `ai-assistant/src/service-clients.ts` |
| `ai-assistant/src/owner-operation-schema.ts` | `ai-assistant/src/service-operation-schema.ts` |
| `ai-assistant/tests/owner-clients.test.ts` | `ai-assistant/tests/service-clients.test.ts` |
| `circuit-designer/packages/document-a2ui-react/src/entity-section-registry.ts` | `circuit-designer/packages/document-a2ui-react/src/section-registry.ts` |
| `docs/testplan-service-architecture.md` | `docs/verification-planner-architecture.md` |
| `docs/entity-sections.md` | `docs/component-sections.md` |
| `tests/agent_spec/spec_format/test_entity_sections.py` | `tests/spec/spec_format/test_component_sections.py` |
| `tests/agent_spec/activities/test_activity_workspace.py` | `tests/spec/activities/test_activity_scratch_directory.py` |

## Verification decisions

| Inventory cases | Decision and reason |
| --- | --- |
| 1.1, 1.5–1.13; 6.2.2 | Applied the verified package, file, and test moves above. The live scratch implementation class was `LocalActivityWorkspace`; it is now `LocalActivityScratchDirectory`. |
| 1.2–1.4; 2.5 | Retained `testplan-service`, `testplan_service`, and legacy data locations. Rule 12 explicitly allows the codebase name `testplan-service`; it does not require a package or folder migration. |
| 2.1–2.4; 3.1–3.11 | Added canonical CLI commands, approval flags, and environment names. Previous commands, flags, and environment names remain accepted. Canonical environment names take precedence. |
| 2.6 | Added `activities.scratch_root`; old `workspace_root` configurations remain readable. The existing SDK attribute and durable job fields remain compatible. |
| 2.7 | The existing registry already separates the Spec service endpoint from the Spec Editor UI endpoint. No structural change was needed. |
| 2.8 | Adding service discovery is a feature change. No terminology rule requires it; the standalone Verification Planner registry integration was not added. |
| 4.1; 4.2; 4.3; 5.1 | Applied the verified UI wording and symbol changes, with current test expectations updated. Retained **Download Draft JSON** and aligned its documentation. Hardware forms use `HardwareCreationForm` and `HardwareMetadataForm`. Terminal and section hierarchy references use `parent`. |
| 5.2.1–5.2.13; 5.2.16–5.2.21 | Applied mismatches at their current source locations. Several cited prompts were already aligned or had moved to `profile/catalog/instructions.json`; that catalog was checked and corrected. Native Harness identifiers and third-party API names remain unchanged. |
| 5.2.14–5.2.15; 6.3.1 | Renamed service client/contract classes and Spec service storage classes, with their callers updated. |
| 5.2.18; 6.3.3–6.3.6; 8.5 | Added canonical service fields and error codes. Kept old SQL storage columns and transport aliases where needed to read existing records. Saved workspace hashes retain their original key vocabulary. Spec queries accept `service_document_key`, which takes precedence over the old query alias. |
| 5.2.22; 7.1–7.3 | Updated the AI Assistant title and Verification Planner service prose/identity. |
| 6.1.1–6.1.4; 6.1.6; 6.1.8; 6.1.10; 6.1.13–6.1.15 | Applied section `parent`, section class names, `UpsertSection`, `DeleteSection`, `SetNarrativeLinks`, containing-Component references, and confirmed messages. Old section indexes still load. |
| 6.1.5 | Kept the V1 annotation namespace and paths. These are persisted format identifiers. Renaming them is a format migration; terminology changes must not hide existing section data. New index entries use `parent`, with `owner` accepted on reads. |
| 6.1.7; 6.1.9 | Used shared internal helpers `CreateHardware` and `SetHardwareMetadata`. Both handle Components and Designs through the existing deterministic implementation. Duplicating that implementation into separate classes was not required to correct the terminology. |
| 6.1.11–6.1.12 | Preserved Design support for SV sections. The live registry, validation, and documentation support both Components and Designs. Removing Design support would change behavior. Hierarchy wording uses `parent`. |
| 6.2.1–6.2.11; 8.6; 8.12 | Applied Activity identifiers, versions, scratch writer/class names, manifests, and containing-Component/interface references. Manifest readers accept old `generator_id` output so existing managed directories remain usable. |
| 6.3.2 | New journals use `spec_service.sqlite3`. Existing `owner.sqlite3` journals remain in use rather than creating a second, empty history. |
| 6.3.7–6.3.10; 6.3.13–6.3.14 | Applied confirmed messages and added explicit Component/Design Activity and action routes. Existing generic routes remain available. Existing shared reference fields and URL parameter names remain transport compatibility identifiers. |
| 6.3.11–6.3.12 | Transaction parsers accept `parent`. Canonical creation/section operation aliases normalize into the validated V1 execution vocabulary. Conflicting kind or parent aliases are rejected. Old operation names remain valid. |
| 7.4 | `LEGACY_STORAGE_DIR` identifies actual old data. Changing that value to a new name would defeat its migration purpose. It remains `.testplans`. |
| 7.5; 7.8–7.13 | Applied `VerificationPlannerService`, `produces_rtl`, human-label prose, `designer_label`, a SQLite column migration, and `SourceLocator.target_ref`. Old request/model/export keys remain accepted where needed. |
| 7.6–7.7 | The cited `routes_export.py` is an explicitly unmounted legacy prototype. The live app uses `routes_exports.py`. Its dead route is not a live terminology defect. |
| 7.14–7.15 | The cited `EntityRef` class and `scope_occurrences` table/columns do not exist in the current Verification Planner implementation. The proposed changes could not be verified. |
| 7.16–7.17 | Applied the matched view/layout CSS and HTML names, with matching selectors updated. |
| 8.1–8.3; 8.7–8.15 | Applied the confirmed helper names, prose, test names, fixtures, and local conversation variable. |
| 8.4 | The cited `ownerUrl` dictionary is input to a stable workspace identity hash, not a protocol handshake. Its hash key must remain unchanged; product binding fields now use `serviceUrl`. |
| 9.1–9.34 | Applied verified wording and link changes. References to retained package paths and persisted/API compatibility identifiers remain accurate. The requested package-path changes follow the decisions above. |

## Compatibility rules

- The canonical commands are `spec2gds-spec-service`, `spec2gds-spec-editor`,
  `spec2gds-ai-assistant`, and `verification-planner`. Previous commands still work.
- Use `--require-designer-approval`, `SPEC_SERVICE_HOST`, `SPEC_SERVICE_PORT`,
  `SPEC2GDS_REQUIRE_DESIGNER_APPROVAL`, `SPEC_SERVICE_URL`, `CIRCUIT_SERVICE_URL`,
  `SPEC_SERVICE_STATE_ROOT`, and `AI_ASSISTANT_UI_TEST_DEPS`. Old names remain aliases.
- Use `parent` for section hierarchy data. Old annotation indexes with `owner` load.
- Use `designer_label` for a Test Plan's human label. Old input and export data
  with `owner_label` load, and the SQLite column migrates without losing its value.
- Use `service_result` for Spec service receipts. The old `owner_result` transport
  field remains available. AI Assistant product objects use `serviceResult`.
- The Spec service accepts `create_component`, `create_design`, `upsert_section`,
  `delete_section`, and `set_narrative_links` as aliases. The published V1 tool
  vocabulary and stored operation forms remain compatible.
- External code that imports the moved Python package must use `spec2gds.spec`.
  The old Python module path was moved; CLI aliases remain supported.

## Checks and limits

The fundamental suite, both builds, generated Circuit contract check, added
compatibility checks, browser suites, Harness integration, and extensive CLI
checks passed. Ruff passed for production Python, scripts, and added compatibility
checks. A broader tests-directory lint scan found three existing import issues;
no unrelated test lint cleanup was made.

The complete extensive Python invocation also attempted five required Verilator
checks. They failed because `verilator` is not installed. Twenty-four optional
toolchain checks skipped because their tools are not available. These checks
remain unverified; they were not changed to pass or silently skipped.

The extensive CLI fixture originally supplied an extra `status` property that
the unchanged architecture schema rejects. That fixture was corrected to the
current schema, then all five CLI flows passed. Browser assertions and mock
section data were updated to the changed UI labels and `parent` field.

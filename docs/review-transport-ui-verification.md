# Review transport and UI scenario verification

All required repair checks passed in `/home/ankdesh/explore/codex-spec2gds/spec2gds`. This report covers the structured architecture decision transport, durable proposal review transport, binding lookup, fixture corrections, and browser scenarios. The presentation capture also passed.

Date: 2026-10-06. Repository baseline: `a02569b51469f754732461e860821cfa41e91e29`. Changes are local and uncommitted.

## Runtime and builds

Node: `v24.13.1`, from `/home/ankdesh/.nvm/versions/node/v24.13.1/bin`.

The sibling Harness checkout is `/home/ankdesh/explore/codex-spec2gds/deepseek-harness`, pinned at `3c98c5108b672280e862a4c85914f5808878aa09`. Its Git working tree remained clean. No Harness code was changed.

The UI scenario dependencies were installed locally with `npm ci --cache /tmp/spec2gds-npm-cache`. The Assistant and Spec Editor were rebuilt from this checkout. Chromium used the existing local Playwright browser installation in `circuit-designer/.playwright-browsers`.

| Working directory | Command | Result | Log |
| --- | --- | --- | --- |
| `ai-assistant` | `npm run build` | Pass | [Assistant build](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/checks/assistant-build.log) |
| `circuit-designer` | `npm run build:editor` | Pass | [Spec Editor build](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/checks/spec-editor-build.log) |
| `ai-assistant` | `npm run typecheck` | Pass | [Typecheck](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/checks/typecheck.log) |
| `ai-assistant` | `npm test` | 146 passed | [Unit tests](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/checks/unit-tests.log) |
| `ai-assistant` | `npm run test:harness` | 7 passed | [Harness integration](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/checks/harness-integration.log) |
| `ai-assistant` | `npm run test:ui` | 3 passed | [Assistant UI](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/checks/assistant-ui.log) |
| `tests/ui-scenarios` | `npm run test:fixture` | 6 passed | [Fixture tests](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/checks/fixture-tests.log) |
| Repository root | `git diff --check` | Pass | No whitespace errors |

Total: 162 test cases passed, plus all six named browser scenarios, the large-proposal run, and the presentation capture. The build reports an existing bundle-size advisory. Node reports its SQLite experimental notice.

## Changes and regression evidence

Architecture decisions now contain an exact review ID, saved decision, and separate feedback. The UI delivers a native queued continuation with a stable message identity and a readable label. The server checks the saved decision and conversation. It checks the durable native event log before it queues a retry. A failed delivery remains on the card with a retry control. Revisions retain the original request. Prose history does not grant approval authority; existing JSON decision messages remain supported.

The architecture tests cover selection of an older review while a newer review exists, repeated refinement, foreign or inconsistent records, and retry after a lost delivery acknowledgement. The native runtime test reads the saved event log and verifies that only one continuation was inserted. Host tests cover transient delivery failure and failure to persist a continuation.

The complete proposal and review remain in product state. Public review responses omit the duplicate `serviceResult.preview` without changing the stored service receipt. A separate valid JSON projection for the model is capped at 40 KiB with field-level reduction. Native `presentationMeta` stores a small review reference with the tool-result event.

The client loads the complete review through a conversation-scoped proposal lookup. Approval controls appear after that load succeeds. Failed lookup has a retry control. The client supports existing full JSON results and recovers older spilled results by the exact tool-call ID through the conversation review list.

The transport integration test forces native text spilling at 512 bytes, reopens persisted metadata, and loads the complete review containing 180,000 bytes of preview text. The client regression test covers metadata recovery, legacy call-ID recovery, failed lookup, and approval gating. The large browser run verifies the complete preview after reload and one initial service submission, then compares the saved IP-XACT description with the full fixture input.

The optional binding lookup returns `200` with `session: null` for a known unbound conversation. Unknown conversations still return `404`. The source-name display uses this optional lookup. Binding errors and review-subresource errors remain fatal in fixture tests and browser failure checks.

The fixture parses output by the matching tool call. Malformed structured output records a fixture failure and emits a terminal model turn. It does not submit another proposal or enter a provider retry loop. It recognizes explicit proposal outcomes, reads architecture identity from structured decisions, and uses authoritative document references.

Document creation now honors an optional supplied `document_id` and validates it through the existing destination helper. IDs with underscores remain exact. Titles remain separate from IDs. The browser tests read the package destination from the saved creation receipt, then compare it with the service snapshot. They verify the requested ID and title. The pinned Harness does not support JSON-schema `pattern`; validation stays in the shared application helper.

## Browser results

| Scenario | Result | Evidence | Artifacts |
| --- | --- | --- | --- |
| architecture | Pass | Reload, revise, cancel, approve; preserve original request. | [Records](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/architecture-final/records.json), [trace](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/architecture-final/trace.zip), [saved Spec](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/architecture-final/packages/architecture-lifecycle.spec) |
| automatic | Pass | Create once; preserve underscore ID and separate title; refine and run the RTL Activity. | [Records](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/automatic-final/records.json), [trace](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/automatic-final/trace.zip), [saved Spec](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/automatic-final/packages/iterative-scenario.spec) |
| restricted | Pass | Review mode; Save to Spec; reject a proposal and reject a stale revision. | [Records](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/restricted/records.json), [trace](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/restricted/trace.zip), [saved Spec](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/restricted/packages/scenario_1791295386536.spec) |
| live | Pass | Preserve an in-progress Spec Editor draft across an AI Assistant update; reject a stale draft save. | [Records](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/live/records.json), [trace](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/live/trace.zip), [saved Spec](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/live/packages/scenario_1791295386543.spec) |
| binding | Pass | Keep the conversation bound to its original Spec while another Spec opens; retain state after a service restart. | [Records](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/binding/records.json), [trace](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/binding/trace.zip), [saved Spec](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/binding/packages/scenario_1791295399691.spec) |
| repeated | Pass | 100 saved receipts; repeat submissions use the same identity; history stays bounded. | [Records](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/repeated/records.json), [trace](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/repeated/trace.zip), [saved Spec](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/repeated/packages/scenario_1791295399861.spec) |
| restricted, large proposal | Pass | Reload a 350,469-byte stored preview, save once, and compare the complete saved IP-XACT description. | [Records](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/restricted-large/records.json), [trace](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/restricted-large/trace.zip), [saved Spec](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/review-transport-verification/verified/restricted-large/packages/scenario_1791295816394.spec) |

Each scenario directory contains `model-requests.json`, `model-fixture-failures.json`, service logs, screenshots, `trace.zip`, and `records.json`. The records retain service receipts, source revisions, and Activity reports. The `packages` directory retains `.spec` files, generated RTL files, and report sidecars. Architecture records also retain saved review lineage; the automatic and architecture runs retain the exact saved creation receipt.

All accepted runs have zero unexpected console, page, process, or network failures, and an empty fixture-failure list. Expected failures are limited to event-stream cancellation, planned service-restart disconnects, and the intentional `409` draft conflict in `live`. No broad binding-error exclusion was added.

The large run stored a 350,469-byte preview. It reloaded the pending card, found the end marker in the full preview, used Save to Spec, and verified exactly one initial history receipt. The saved Component description retained all 79,357 characters, including the final marker.

## Commands to reproduce

Run the build and test commands above from their listed working directories after setting the Node path:

```bash
export PATH=/home/ankdesh/.nvm/versions/node/v24.13.1/bin:$PATH
```

From the repository root, run the browser scenarios with these arguments. The output directories below are the accepted evidence directories.

```bash
artifact_root="$PWD/tests/ui-scenarios/results/review-transport-verification/verified"
bash tests/ui-scenarios/run-test.sh --scenario architecture --output "$artifact_root/architecture-final"
bash tests/ui-scenarios/run-test.sh --scenario automatic --output "$artifact_root/automatic-final"
bash tests/ui-scenarios/run-test.sh --scenario restricted --approval-mode review --output "$artifact_root/restricted"
bash tests/ui-scenarios/run-test.sh --scenario live --output "$artifact_root/live"
bash tests/ui-scenarios/run-test.sh --scenario binding --output "$artifact_root/binding"
bash tests/ui-scenarios/run-test.sh --scenario repeated --output "$artifact_root/repeated"
bash tests/ui-scenarios/run-test.sh --scenario restricted --approval-mode review --large-proposal --output "$artifact_root/restricted-large"
bash tests/ui-scenarios/run-test.sh --scenario automatic --presentation --output "$PWD/tests/ui-scenarios/results/presentation-irq-pipeline/assets"
```

Local servers and Chromium require socket and process access. The test runs used that access and isolated temporary service state. Builds completed before the accepted browser runs.

## Presentation capture

The capture follows architecture approval, Spec creation, an 8-bit to 16-bit interface refinement, a two-instance Design preview, Circuit Designer, a private Circuit draft, and RTL Activity execution. It contains 11 unaltered PNG screenshots at 2400 × 1350 pixels (16:9).

- [Screenshot gallery](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/presentation-irq-pipeline/assets/gallery.html)
- [Captions and suggested slide order](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/presentation-irq-pipeline/assets/screenshots.md)
- [Screenshot ZIP](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/presentation-irq-pipeline/spec2gds-presentation-screenshots.zip)
- [Capture records](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/presentation-irq-pipeline/assets/records.json)
- [Saved example Spec](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/presentation-irq-pipeline/assets/packages/irq-signal-pipeline.spec)
- [Capture trace](/home/ankdesh/explore/codex-spec2gds/spec2gds/tests/ui-scenarios/results/presentation-irq-pipeline/assets/trace.zip)

The screenshots retain the UI's timing and RTL validation warnings. RTL generation succeeded. Verilator was unavailable, so this capture does not establish RTL lint, simulation, or timing closure.

## Scope

These runs use a deterministic model fixture with the real UI and services. The scenario named `live` tests preservation of a live Spec Editor draft. Live-provider generalization is outside this repair.

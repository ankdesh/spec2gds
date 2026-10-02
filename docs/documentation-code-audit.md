# Documentation and code review map

Reviewed against the current source on 2026-10-01. The [documentation index](README.md)
links current behavior separately from remaining design requirements. Python setup
uses `uv` and a local `.venv`; the root and package READMEs contain run instructions.

## Authoritative boundaries

| Documentation family | Implementation and verification evidence |
| --- | --- |
| Architecture, flows, setup, addresses and logging | `config/services.json`, `scripts/setup-all.sh`, `scripts/serve-all.sh`, `spec2gds/service_registry.py`, `runtime/src/spec2gds_runtime/`; launcher/config/logging tests |
| Spec packages, editing, sections and review | `spec2gds/agent_spec/spec_format/`: archive, IR, sections, transactions, owner/review/proposal stores and `v1_api.py`; `tests/agent_spec/spec_format/` |
| Activities and RTL/SystemC examples | `spec2gds/agent_spec/activities/`: contracts, snapshot, registry, workspace and generator packages, plus `tools/systemc-rtl/main.cpp`; Activity tests and `scripts/generate_rtl_examples.py` |
| Spec editor browser | `circuit-designer/apps/editor/src/` and `packages/document-{core,a2ui-react}/`; client unit tests, editor browser fixtures and isolated owner scenarios |
| Circuit semantics, UI, layout and source saves | `circuit-designer/schema/`, `packages/{core,layout,react,app-react,service}/` and `apps/standalone/`; schema consistency, workspace tests/builds and Circuit browser fixtures |
| Assistant owner tools, creation and focused CLI | `ai-assistant/src/`, `scripts/spec2gds_{assistant,spec}.py` and product request/dev scripts; contract, CLI, refinement and Harness integration fixtures |
| Event/goal runtime and reviewed configuration | `ai-assistant/profile/catalog/`, execution policy/configuration, host/client adapters and the pinned Harness native packages; native integration and event-preset browser tests |
| Verification Planner | `testplan-service/src/testplan_service/{api,application,domain,integrations,storage,ui}/`; three layer acceptance modules and independent CLI/OpenAPI |

Read code at the mutation or admission boundary before changing a documented
contract. A test proves its exercised cases; a proposed requirement in a backlog
or preserved research file does not establish current support.

## Consolidation destinations

Completed report plans, event phase plans, the former UI migration, the duplicate
configurable tutorial, the dated Spec evaluation report and the old refinement
test plan have been removed. Their useful content now lives in:

- [Execution design rationale](agentic-systems-architecture-report.md),
  [event/preset reference](event-driven-assistant-system.md),
  [operations](event-driven-assistant-operations.md) and [tutorial](event-driven-assistant-tutorial.md).
- [Assistant UI](assistant-ui.md), [evaluation](ai-assistant-evaluation.md) and
  [acceptance commands](assistant-acceptance-tests.md).
- [Planner architecture](testplan-service-architecture.md), its
  [layer references](README.md#verification-planner) and [remaining requirements](verification-planner-backlog.md).

The former JSON-node Planner prototype document is superseded. Legacy Python
modules remain in the tree but are not mounted by the current application.
Future executable workflows, full Test IR semantics, native result collectors,
Planner browser hardening and recovery requirements remain explicitly proposed.
The [Assistant backlog](ai-assistant-improvement-plan.md),
[integration issues](ai-assistant-integration-issues.md) and
[Circuit gaps](circuit-designer-chipmind-gap-analysis.md) retain unresolved work.
The former root RTL notes are now corrected [language examples](rtl-language-examples.md).
The unimplemented generator-local SystemC timing proposal is retained in a short
[performance-model backlog](systemc-at-performance-backlog.md), distinct from
the structural generator. Historical implementation/test diaries are recoverable through Git.

## Reviewer comments and checks

Module reading guides, public Python docstrings and focused inline comments cover
ownership, revision checks, causal identities, capability ceilings, replay/claim
ordering, crash windows, artifact publication and routing decisions. Comments
also distinguish partial validators, trusted plugins, receipt acceptance and
completed work. Generated bundles/types and copied dependencies are not manually
annotated. See [commenting conventions](code-quality.md).

The source audit compares Python syntax trees with docstrings removed and
TypeScript/JavaScript with comments removed; C++ emitter tokens are compared
with comments excluded. Intentional non-comment corrections
are limited to the durable-wait prompt, the Activity cancellation type import,
import ordering, packaging's script-relative root and a launcher guard for
missing `import.meta.main`. The Assistant engine range is corrected to Node
22.19+ (22.x) or 24.2+; Node 24.0/24.1 can otherwise exit without starting the CLI. Existing tests were aligned with isolated filesystem fixtures and the event
replay cursor.

Validation commands and their limits are in [development](development.md) and
[Assistant acceptance](assistant-acceptance-tests.md). The event browser suite
uses a minimal Harness adapter shell with deterministic owner/model fixtures;
it does not prove full native-shell browser behavior. The Planner reference
backend does not execute DUT verification. Its existing import/unused lint
findings remain outside the root-only Ruff/Vulture gate.

The native SystemC emitter's one-bit arithmetic conversion is an identified
semantic limitation, documented in the [cycle-accurate guide](systemc-cycle-accurate-activity.md).
Comment-only emitter changes preserve its current tokens; optional native
compiler/SystemC tests do not run without their external toolchains.


## Verified results

The audit covers 77 maintained Markdown files, with 194 local link targets and
three heading anchors checked. Eleven superseded or misplaced documents were
removed or consolidated; their current contracts and unresolved requirements
remain in the destinations above. Reviewer annotations were expanded in 79
production files: 45 Python, 33 TypeScript/JavaScript and the C++ emitter.

| Validation on 2026-10-01 | Result and scope |
| --- | --- |
| Root Python and Planner acceptance suites | 201 passed; nine optional native-toolchain cases skipped |
| Activity SDK/workspace checks after the cancellation import fix | 10 passed |
| Circuit workspace tests | 117 passed |
| Assistant unit/contract tests | 94 passed |
| Native Harness integration and event-preset browser suites | Three passed in each suite on Node 24.2; browser scope is the adapter shell described above |
| Schema consistency, workspace builds and Assistant type checking | Passed |
| Root Ruff/Vulture and documentation links | Passed; no broken local targets or heading anchors |
| RTL language examples | All 16 examples passed strict Verilator lint |
| Assistant release packaging | Passed; all packaged checksums verified |
| Source behavior comparison | Python AST, TypeScript/JavaScript syntax and C++ tokens preserve behavior except the explicit corrections above |

Planner's 105 existing lint diagnostics are unchanged. The documented SystemC
one-bit arithmetic limitation and unavailable optional native toolchains remain
limits of the current implementation, rather than claims of completed support.

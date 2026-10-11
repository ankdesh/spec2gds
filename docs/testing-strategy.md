# Software Testing and Verification Strategy

This document defines the software test pyramid, local execution profiles, and coverage matrix across `spec2gds`.

## 1. Test Organization and Pyramid

Software tests validate platform reliability, revision safety, and cross-application boundaries.
Software tests are separate from the hardware **Test Plan** artifact produced by **Verification Planner**.

<<<<<<< HEAD
Use layered, risk-based testing. Put a check at the lowest layer that can detect
the fault reliably. Use integration and browser checks when the fault depends
on communication, persistence, or designer interaction. Do not set fixed test
counts or code-coverage percentages for each layer.

Keep tests near their subsystem. Keep flows that span applications in
`tests/ui-scenarios`. Do not copy tests into a second regression collection.
Regression profiles select the maintained suites. The suite catalogue in
`scripts/test_profiles.py` records the subsystem, layer, evidence type,
dependencies, prerequisites, risk areas, and execution limit beside each command.

| Layer | Method | Main purpose |
| --- | --- | --- |
| Unit and component | Isolated logic and state checks | Fast feedback on local faults |
| Contract and service API | Public interface and validation checks | Compatibility and enforced boundaries |
| Integration | Real services, storage, adapters, and extension execution | Correct interaction between subsystems |
| Browser | Rendered state, controls, keyboard access, and responsive layout | Correct designer interaction |
| End-to-end | Real applications and services, with saved-state assertions | Complete flows and durable results |
| Quality evaluation | Live inference, hardware execution, and measured quality | Evidence beyond fixtures |

Prioritise source integrity, atomic changes, revision control, approval rules,
and separation between Spec and Circuit domains. During detailed test design,
use state-transition, boundary-value, negative-input, and property-based methods
where they fit the risk. Use exploratory review for usability and unexpected
behaviour. See [the coverage matrix](test-coverage-matrix.md) for implemented
flows, local rules, conditional checks and known failures.

## Local commands

Run commands from the repository root after `scripts/setup-all.sh`. Profiles need
Python 3.12+, the root uv environment, Node.js 24.2+, installed npm dependencies,
the linked DeepSeek Harness source, and Playwright Chromium as applicable.
Use `nvm use 24` if the active Node version is older. No CI or scheduled run is
installed by these commands.

For full document-import coverage, run `uv sync --extra document-import` before
the profiles. Their `--no-sync` Python commands retain these optional dependencies.
An import skip caused by missing Docling remains unverified. Live RTL evaluation
records creation, hardware simulation, and saved refinement separately in
`live-generalization/summary.json`; a simulation pass alone is not a complete flow pass.

```bash
scripts/test-all.sh fast
scripts/test-all.sh integration --scope spec
scripts/test-all.sh integration --scope spec,assistant
scripts/test-all.sh regression
scripts/test-all.sh regression --dry-run
scripts/test-all.sh regression --rtl-cases adder_4,adder_8,adder_13
scripts/test-all.sh fast --output /tmp/spec2gds-fast-evidence
scripts/test-all.sh integration --scope spec --coverage
=======
```mermaid
flowchart TD
    E2E["End-to-End Scenarios (Playwright / Real Services)"] --> INT["Subsystem Integration Tests (FastAPI / REST APIs)"]
    INT --> UNIT["Unit & Contract Tests (Python pytest / Vitest)"]
>>>>>>> 0b25af6 (Update docs)
```

### Test Layers

| Test Layer | Framework & Scope | Purpose |
| --- | --- | --- |
| **Unit & Contract** | `pytest`, `vitest` | Fast verification of local algorithms, state machines, and schema models |
| **Service Integration** | Real FastAPI & REST test clients | Enforces revision conflicts, atomic file transactions, and API contracts |
| **Browser End-to-End** | Playwright Chromium | Validates rendered canvas, forms, keyboard shortcuts, and responsiveness |
| **Live Quality Checks** | Real model evaluation & Verilator | Evaluates live model tool calls and hardware compilation |

---

## 2. Test Execution Profiles

Run tests through the unified test runner:

```bash
# 1. Fast profile: Unit tests, schemas, builds, smoke UI, and 3 live model checks
scripts/test-all.sh fast

# 2. Integration profile: Real service interactions for specific scopes
scripts/test-all.sh integration --scope spec,assistant
# Available scopes: spec, circuit, assistant, verification, activities, shared

# 3. Regression profile: Full suite including broad browser scenarios
scripts/test-all.sh regression

# 4. Dry-run inspection: Inspect selected commands without executing
scripts/test-all.sh fast --dry-run
```

### Execution Prerequisites
- Python 3.12+ with root `uv` virtual environment.
- Node.js 24.2+ (or 22.19+ for Assistant alone).
- Playwright Chromium browser binaries (`npx playwright install chromium`).
- Verilator 5.x and GNU Make for RTL Activity verification.

---

## 3. Subsystem Test Coverage Matrix

### Designer Flows and Core Capabilities

| Capability | Primary Test Evidence | Expected Assertion |
| --- | --- | --- |
| **Spec Creation & Drafts** | Spec Editor e2e + Spec service | UI, service, and archive agree; cancelled drafts leave file unchanged |
| **Hardware Port Families** | Spec Editor unit & e2e | Creates wire, transactional, and packed ports; reloads accurately |
| **Revision Conflicts** | Multi-client concurrency tests | Rejects stale writes with HTTP 409; requires refresh before retry |
| **Circuit Projections** | Spec-Circuit adapter tests | Validates bidirectional IP-XACT port to schematic pin translation |
| **Circuit Canvas & Routing** | Circuit Designer unit & e2e | Verifies orthogonal routing, edit leases, and undo/redo stacks |
| **Timing Stages** | Circuit timing engine tests | Accurately calculates path latency across cycle edge markers |
| **Activity Snapshot Handoff** | Activity SDK acceptance tests | Snapshots are immutable; subsequent spec edits do not alter running jobs |
| **RTL Generation** | `rtl.generate` test suite | SystemVerilog compiles cleanly in Verilator without warnings |
| **SystemC Models** | SystemC Activity test suites | Generates valid TLM 2.0 and cycle-accurate MLIR HW dialect code |
| **Verification Planning** | `testplan-service` acceptance tests | Evaluates 3-layer models, P/C/I checkpoints, and reference generation |
| **AI Assistant Flows** | DeepSeek Harness integration tests | Validates architecture review cards, proposal staging, and receipts |

---

## 4. Defect Reporting and Resolution

- Add regression protection at the lowest effective layer when fixing confirmed bugs.
- If a bug depends on browser behavior, add a Playwright browser scenario in `tests/ui-scenarios/`.
- Do not suppress test failures with blanket skips or loose assertions.

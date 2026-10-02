# Project Constitution: spec2gds

This document defines the core principles, coding standards, and architectural guidelines for `spec2gds`. All AI assistants and developers must adhere to these rules in every interaction. Keep this file minimal, high-impact, and action-oriented.

---

## 1. Environment & Dependency Management

* **Package & Virtual Environment Manager**: Strictly prefer `uv` and `uv` virtual environments (`uv venv` / `uv sync` / `uv run`) for Python development. Avoid slow or non-deterministic package managers.
* **JavaScript & Node Engine**: Node.js 24 (or 22.19+) is required for DSH SQLite support and Playwright UI scenario testing. Use `circuit-designer/.playwright-browsers` for browser binaries.

---

## 2. Core Architecture Principles

* **Specification-First Source of Truth**: The `.spec` package (IP-XACT components, designs, ports, and SystemVerilog module bodies) is the semantic source of truth. Changes made in downstream workflows (RTL generation, verification, circuit editing) must reflect back into the specification.
* **Loose Coupling of Flow Stages**: Stages (`Spec -> RTL Code -> Simulation -> Synthesis -> GDS`) remain modular and decoupled. Individual submodules and Activities evolve independently through standard APIs without hard dependencies on proprietary tools.
* **Component and Design RTL Generation**: The `rtl.generate` Activity supports both `design` and `component` scopes. Generating RTL directly for a component compiles its ports, vector ranges, and SystemVerilog module-body section into `rtl/components/<name>.sv` without requiring an artificial top-level wrapper. In multi-component packages, all referenced sub-components are recursively visited and rendered alongside the top-level entity.
* **Hierarchical Hardware Construction & Multi-Turn Refinement**:
  - Complex designs are constructed hierarchically in multi-turn conversations: foundational sub-components (e.g. `full_adder`, `dual_port_RAM`) are created first, followed by top-level designs/components (`adder_8bit`, `asyn_fifo`) that instantiate them in SystemVerilog module bodies.
  - Unitary designs (such as synchronous counters `up_down_counter`) remain unified without artificial decomposition.
* **Resilient Assistant Model Protocol**:
  - The AI Assistant communicates via typed semantic proposals (`create_entity`, `upsert_component_port`, `upsert_entity_section`).
  - Wire ports must specify `family: "wire"`, `direction: "in" | "out"`, and compact range (e.g. `7:0`). The assistant normalizer defaults missing families to `"wire"`.
  - Component creations automatically normalize `instances` to `[]` (`kind: "component"` cannot hold IP-XACT instances; hardware sub-components are instantiated inside the SystemVerilog module body).
  - SystemVerilog code submitted by LLMs is automatically normalized (markdown fences stripped, outer `module ... endmodule` wrappers stripped down to pure module bodies, and illegal compiler directives removed).
  - DSH tool spill envelopes (`(Omitted ... stored at: <path>)`) are transparently resolved by parsing from disk if payload exceeds standard thresholds.

---

## 3. Error Handling & Reliability

* **Fail explicitly and early**: Never swallow exceptions silently. Log structured issues with actionable context.
* **Static Typing & Contracts**: Use strict type hinting (`mypy`, TypeScript strict mode) and Pydantic dataclasses for ASTs, IR models, and service schemas.
* **One Primary Class Per File**: Keep modules lightweight, focused, and maintainable.
* **Better Design Over Legacy**: Do not favor legacy backward compatibility at the expense of sound architectural design.

---

## 4. Testing & Verification Strategy

* **Balanced Testing Pyramid**: Maintain unit tests for core IR/parser algorithms and end-to-end integration tests for user journeys.
* **RTLLM Benchmark Verification**: Validate the end-to-end AI Assistant -> Spec Editor -> RTL Generation flow against standard RTLLM benchmark tasks:
  1. `adder_8bit` (Arithmetic: 8-bit full adder)
  2. `up_down_counter` (Control: 16-bit up-down counter)
  3. `asyn_fifo` (Memory: Dual-clock asynchronous FIFO with 16x8 RAM and gray-code sync)
* **Automated UI Scenario Testing**: Use Playwright (`tests/ui-scenarios/run-test.sh --rtllm`) with 5 visual milestone snapshots (Assistant Home, Proposal Applied, Spec Editor Component View, Activity Launch Dialog, Activity Completion) and Python-based functional verification (`scripts/verify_rtllm_rtl.py`).

---

## 5. Documentation & Constitution Updates

* Check and update `README.md` and this project constitution (`GEMINI.md`) after completing major features, refactors, or benchmark evaluations.

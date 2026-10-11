# Documentation Index

This directory contains the living technical documentation for `spec2gds`.
All documents adhere to the canonical terminology defined in [TERMINOLOGY.md](TERMINOLOGY.md) and Simplified Technical English (ASD-STE100).

## 1. System Overview and Architecture

- [System Architecture](architecture.md): Subsystems, authoritative service boundaries, state containers, and dependency direction.
- [End-to-End Flows](flows.md): System workflows for specification authoring, circuit projection, independent circuit editing, and document import.
- [Names and Identifiers](naming-and-identifiers.md): Hardware identifier rules, display name resolution, and normalization policies.
- [Canonical Terminology](TERMINOLOGY.md): Mandatory terminology rules across code, UI, and documentation.

## 2. Specification System

- [Spec Editor and Spec Service](spec-editor.md): User interface, section registry (text, ports, SystemVerilog), package layout, transactions, and approval modes.

## 3. Circuit Designer

- [Circuit Designer](circuit-designer.md): Canvas gestures, menubar, pipeline timing stages, user preferences, and embedding `@spec2gds/circuit-app-react`.
- [Spec-Circuit Integration Architecture](spec-circuit-integration-architecture.md): Deep-dive into bidirectional projection, edit leases, source-bound drafts, and Save to Spec transactions.

## 4. Verification Planner

- [Verification Planner](verification-planner.md): Architecture of `testplan-service`, 3-layer verification model (Test Plan, Coverage & Evidence, Recipes & Test IR), evaluator precedence, and reference artifact generation.

## 5. AI Assistant

- [AI Assistant Contract](ai-assistant.md): Core behavioral contract, approval gating, document tokens, and boundary invariants.
- [AI Assistant Operations](ai-assistant-operations.md): Setup, configuration, execution commands, diagnostics, and acceptance matrix.
- [Reusable Flows](ai-assistant-flows.md): Published flow tools (`flow_create_empty_spec`, `flow_create_spec_with_component`, `flow_add_component`, `flow_edit_spec`) and execution lifecycles.

## 6. Activities, RTL, and SystemC

- [Activity SDK](activity-sdk.md): Extension SDK, Activity Snapshot v1 format, high/low read APIs, and plugin registration.
- [RTL Generation](rtl-generation.md): Deterministic SystemVerilog generator (`rtl.generate`), supported source profiles, body-only SystemVerilog contract, and Verilator linting.
- [RTL Language Examples](rtl-language-examples.md): Verified SystemVerilog examples for combinational logic, registers, state machines, and arithmetic modules.
- [SystemC Activities](systemc-activities.md): Approximately-Timed TLM 2.0 skeleton generator and cycle-accurate native SystemC generator using CIRCT.

## 7. Development and Testing

- [Development Guide](development.md): Repository layout, port allocations, service configuration (`config/services.json`), unified logging, and launcher commands.
- [Python Code Guide](python-code-guide.md): Reading order, architectural boundaries, code-quality standards, and static analysis commands.
- [Software Testing Strategy](testing-strategy.md): Test pyramid, execution profiles (`fast`, `integration`, `regression`), and capability coverage matrix.
- [Sample Application Methodology](sample-apps.md): Guidelines for developing small, reproducible hardware scenarios through the full platform.

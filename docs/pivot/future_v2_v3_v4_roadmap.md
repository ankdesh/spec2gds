# Future Roadmap — V2, V3, and V4

This roadmap records the agreed direction after V1. It is not a substitute for
a decision-complete implementation plan. Each release requires its own profile,
public contracts, tests, and exit gate before work starts.

## V2 — SystemC and TLM Action Pack

### Objective

Generate and verify SystemC/TLM performance and functional/bit-accurate models
from V1 structure, narrative, and reviewed optional annotations.

### Planned Additions

- Action-defined, target-neutral behavioral annotations for transactions,
  payloads, state, latency, throughput, ordering, queueing, and errors.
- Architect-reviewed extraction of structured behavioral facts from narrative.
- SystemC performance-model and functional/bit-accurate-model generation.
- Compile, execute, trace, compare, and report actions.
- Artifact lineage between generated source, compiled executable, simulation
  results, traces, and verification reports.

### Boundary

SystemC class names, compiler flags, templates, and tool settings remain action
configuration or artifact metadata. They do not become core component fields.

## V3 — RTL and IP Development

### Objective

Support structured IP development and RTL-oriented generation for constrained
but complete IP categories.

### Planned Additions

- Structured ports, arrays, reusable type definitions, detailed clocks, resets,
  and component modes.
- Memory maps, address blocks, registers, fields, access policies, reset
  values, enumerations, register files, and indirect interfaces.
- Optional RTL annotations for state machines, datapaths, pipelines,
  scheduling, storage, handshake behavior, and clock/reset domains.
- SystemVerilog generation, lint, simulation, formal, synthesis, and
  equivalence actions.

### Initial Acceptance Targets

- Register-controlled peripherals
- Streaming datapaths
- Protocol adapters
- DMA-style engines
- Configurable compute blocks

CPU/GPU hierarchy may be represented, but generic full behavioral RTL
generation for CPU/GPU implementations is not implied by this release.

## V4 — SoC Integration

### Objective

Compose reusable IP into full SoC designs and generate integration-level
models, checks, and top-level deliverables.

### Planned Additions

- Address spaces, subspace maps, remaps, CPU regions, and system memory
  topology.
- Power domains, operating modes, clock/reset topology, CDC intent, and
  interrupt topology.
- Mirrored/system interface roles, monitored interconnections, abstractors,
  and design configurations when mixed abstractions are required.
- Hash-locked external dependencies, cached resolution, and reusable catalogs.
- SoC elaboration, address assignment, integration validation, top-level
  SystemC/RTL generation, and platform verification actions.

## Deferred Across All Releases

- Remote queues, authentication, and collaborative real-time editing.
- Arbitrary third-party vendor extensions.
- Using IP-XACT file sets or generator chains as the project action system.
- Automatic acceptance of source changes proposed by actions.

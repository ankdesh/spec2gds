# Spec Catalog Component reference

The Spec Catalog contains reusable Component releases. The runtime inventory is the source for delivery status and release pins. Phase 4 is still planned.

```mermaid
flowchart LR
    C[Component contract] --> D[Component definition]
    D --> V[Verification evidence]
    V --> R[Published release]
    R --> I[Import into Spec]
```

- [Service guide](../../spec_catalog_service/README.md): setup, commands, and import.
- [Runtime inventory](../../spec_catalog_service/catalog/inventory.json): status and release pins.
- [Common hardware and verification rules](common-rules.md).
- Component contracts: [phase 1](contracts/phase-1.md), [phase 2](contracts/phase-2.md), [phase 3](contracts/phase-3.md).
- [Phase 4 plan](phase-4.md): remaining protocol and peripheral work.
- [Interoperability proposal](interoperability-plan.md): reviewed options for cross-phase composition; check its status against the current code before use.

Published `.spec` files and historical evidence are immutable. Some contain the former `docs/TEMP_spec_library_plan/` paths. Use the equivalent contract above when reading those historical records; do not alter published bytes to change a documentation link.

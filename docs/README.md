# Documentation

Use each document's status to distinguish required contracts, current owner
behavior, and proposed work. The Assistant contract defines required behavior;
its TEMP register records current code gaps. Historical plans and release diaries
remain in Git.

## System and development

- [Architecture](architecture.md), [end-to-end flows](flows.md) and
  [development commands](development.md)
- [Code reading guide](python-code-guide.md), [commenting conventions](code-quality.md)
  and [documentation/code audit](documentation-code-audit.md)
- [Service configuration](service-configuration.md) and [logging](logging.md)
- [Sample application method](sample-apps.md)

## Specification editing and Activities

- [Editor UI](editor-ui.md), [entity sections/SystemVerilog](entity-sections.md),
  and [owner refinement, live views, and drafts](spec-editor-iterative-refinement.md)
- [Activity Snapshot v1](activity-snapshot-v1.md) and [Activity SDK](activity-sdk.md)
- [RTL generation](rtl-generation-activity.md), [RTL semantics examples](rtl-semantics-examples.md)
  and [SystemVerilog language examples](rtl-language-examples.md)
- [SystemC AT](systemc-at-activity.md), [performance-model requirements](systemc-at-performance-backlog.md)
  and [cycle-accurate SystemC](systemc-cycle-accurate-activity.md)

## Assistant

- [System contract](ai-assistant.md): required behavior, workflows, tools, and states.
- [Operations and tests](ai-assistant-operations.md): setup, configuration, CLI,
  diagnostics, and acceptance checks.
- [TEMP implementation gaps](TEMP-ai-assistant-implementation-gaps.md): differences
  between the contract and current code. Remove entries after verification.
- [Future work](ai-assistant-future-work.md): proposals, not accepted requirements.

The preserved research and raw evidence are linked from these guides. They do
not grant capabilities or establish current product behavior.

## Circuit Designer

- [Spec/Circuit ownership and flow diagrams](spec-circuit-integration-architecture.md)
  and [specification synchronization](circuit-designer-spec-sync.md)
- [Interactions](circuit-designer-interactions.md), [preferences](circuit-designer-preferences.md)
  and [timing stages](circuit-designer-timing-stages.md)
- [Embedding](circuit-designer-embedding.md), [visual profile](circuit-designer-visual-profile.md)
  and [remaining feature gaps](circuit-designer-chipmind-gap-analysis.md)

## Verification Planner

- [Architecture](testplan-service-architecture.md) and [service operation](verification-service-overall.md)
- [Layer 1: Test Plan](verification-layer-1-test-plan.md)
- [Layer 2: Coverage and Evidence](verification-layer-2-coverage.md)
- [Layer 3: Recipes and reference generation](verification-layer-3-implementation.md)
- [Remaining requirements](verification-planner-backlog.md)

## Maintenance

Update the smallest relevant current reference and run instructions when behavior
changes. Move useful decisions from completed plans into those pages, then remove
the superseded plan. Keep proposed capabilities separate from supported APIs.
Generated samples and dependencies are not authoritative documentation.

- [Names and identifiers](naming-and-identifiers.md): naming policy, exposure inventory, normalization, and acceptance checks.

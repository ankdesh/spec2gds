# Documentation

These pages describe the current source. Future requirements live in explicitly
marked backlogs; completed plans and release diaries live in Git history.

## System and development

- [Architecture](architecture.md), [end-to-end flows](flows.md) and
  [development commands](development.md)
- [Code reading guide](python-code-guide.md), [commenting conventions](code-quality.md)
  and [documentation/code audit](documentation-code-audit.md)
- [Service configuration](service-configuration.md) and [logging](logging.md)
- [Sample application method](sample-apps.md)

## Specification editing and Activities

- [Editor UI](editor-ui.md) and [entity sections/SystemVerilog](entity-sections.md)
- [Activity Snapshot v1](activity-snapshot-v1.md) and [Activity SDK](activity-sdk.md)
- [RTL generation](rtl-generation-activity.md), [RTL semantics examples](rtl-semantics-examples.md)
  and [SystemVerilog language examples](rtl-language-examples.md)
- [SystemC AT](systemc-at-activity.md), [performance-model requirements](systemc-at-performance-backlog.md)
  and [cycle-accurate SystemC](systemc-cycle-accurate-activity.md)

## Assistant

- [Unified hierarchy, explanations and RTL integration](assistant-hierarchical-spec-integration.md)
  and [functional/generalization evaluation evidence](assistant-hierarchical-spec-evaluation.md)
- [Setup and owner boundaries](ai-assistant.md), [UI composition](assistant-ui.md)
  and [native/product architecture](configurable-assistant-architecture.md)
- [Events, presets and configuration](event-driven-assistant-system.md),
  [monitoring/waiting/recovery](event-driven-assistant-operations.md) and
  [hands-on tutorial](event-driven-assistant-tutorial.md)
- [Specification creation](assistant-spec-creation.md),
  [iterative refinement](spec-editor-iterative-refinement.md),
  [acceptance tests](assistant-acceptance-tests.md) and [workspace CLI](spec-workspace-cli.md)
- [Owner operation schemas](assistant-owner-operation-contract.md) and [evaluation](ai-assistant-evaluation.md)
- [Execution design rationale](agentic-systems-architecture-report.md),
  [remaining improvements](ai-assistant-improvement-plan.md) and
  [remaining integration issues](ai-assistant-integration-issues.md)
- [Preserved research input](research/ai-spec-to-rtl-design-research-guide.md)
  is provenance, not current product behavior or task instructions.

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

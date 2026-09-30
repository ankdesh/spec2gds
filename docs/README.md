# Documentation

These are living documents for the current system, plus explicitly labeled
implementation specifications for requested future work. Historical plans,
completed migration notes, generated demos, and benchmark-specific guides are
not kept in this tree.

Read in this order:

1. [Architecture](architecture.md) — ownership, runtime boundaries, and source
   layout.
2. [End-to-end flows](flows.md) — block and sequence diagrams for the main user
   scenarios.
3. [Specification editor UI](editor-ui.md) — menus, shortcuts, section options,
   and intentionally unavailable commands.
4. [Entity sections](entity-sections.md) — extensible content registry,
   SystemVerilog storage, validation, editing, and RTL semantics.
5. [Service configuration](service-configuration.md) — shared IP/port registry,
   discovery, and cross-application launch behavior.
6. [Activity snapshot](activity-snapshot-v1.md) — deterministic full-source
   input boundary for specification consumers.
7. [Activity SDK](activity-sdk.md) — two-level read API, plugin contracts,
   registry, results, and Context Renderers.
8. [SystemC AT Activity](systemc-at-activity.md) — deterministic structural
   SystemC generation, workspace publishing, and supported topology.
9. [Cycle-accurate SystemC Activity](systemc-cycle-accurate-activity.md) —
   native RTL-style modules compiled from stored SystemVerilog behavior.
10. [RTL Generation Activity](rtl-generation-activity.md) — deterministic
   SystemVerilog scaffolding, direct-wire validation, and Verilator checks.
11. [RTL semantics examples](rtl-semantics-examples.md) — body-only component
    behavior, one-/two-cycle samples, and configured output generation.
12. [AI Assistant](ai-assistant.md) — DeepSeek Harness runtime, editor
    integration, review boundary, proposal contracts, setup, and recovery.
    [Create a specification from Assistant chat](assistant-spec-creation.md)
    covers the creation card, save location, continuation, and recovery.
    [Iterative Spec refinement](spec-editor-iterative-refinement.md) covers
    automatic submissions, restricted policy, stable bindings, live drafts,
    event replay, and durable history. Its
    [test plan](spec-editor-iterative-refinement-test-plan.md) lists non-UI
    acceptance and the separately invoked UI scenarios.
    Its [DSH UI migration map](dsh-ui-migration.md) documents the plugin layers
    and retained, extended, and removed UI features.
    The [AI Assistant improvement plan](ai-assistant-improvement-plan.md) is the
    living, topic- and readiness-organized backlog for future assistant work.
    The [AI Assistant integration issues](ai-assistant-integration-issues.md) tracks
    identified decoupling defects and divergences between the Spec Editor, Circuit
    Designer, and AI Assistant.
    The [configurable assistant architecture](configurable-assistant-architecture.md)
    documents the implemented prompt/workflow catalogs, presets, budgets,
    delegation boundary, and service-extension path.
    The [DSH configurable assistant tutorial](dsh-configurable-assistant-tutorial.md)
    explains the DSH plugins, composition layers, execution paths, authority
    boundaries, persistence, and extension process used by that architecture.
    The [agentic systems architecture report](agentic-systems-architecture-report.md)
    assesses fixed workflows and durable event-driven agents, distinguishes
    current support from proposed capabilities, and recommends shared execution
    foundations. Its [report plan](agentic-systems-report-plan.md) records the
    agreed scope and validation approach.
    The proposed [event driven assistant plan](event-driven-assistant-plan.md)
    splits replacement of `orchestrated`, reconsideration of `goal`, external
    triggers, and visual tooling into three delivery phases. Workflow setup
    remains outside that plan.
    The [evaluation guide](ai-assistant-evaluation.md) defines the golden
    corpus, DSH replay checks, raw metrics, and commands.
    Its preserved [Spec-to-RTL research guide](research/ai-spec-to-rtl-design-research-guide.md)
    provides research provenance for refining open questions; it is reference
    material rather than current product behavior.
13. [Unified logging](logging.md) — Info/Debug modes, redaction, retention, and
    browser viewer.
14. [Python code-reading guide](python-code-guide.md) — package ownership,
    request flows, proposal boundaries, and a safe newcomer reading order.
15. [Code quality](code-quality.md) — commenting and unused-code review gates.
16. [Sample application method](sample-apps.md) — how to build one representative
    application through the entire system.
17. [Development guide](development.md) — setup, commands, checks, and where code
    belongs.
18. [Circuit Designer interactions](circuit-designer-interactions.md) — unified
    canvas gestures, configurable action bindings, visible commands, and
    editing constraints.
19. [Circuit Designer preferences](circuit-designer-preferences.md) — shared
    JSON profile, REST endpoints, validation, migration, and persistence.
20. [Circuit Designer specification synchronization](circuit-designer-spec-sync.md)
    — source bindings, Save to Specification, layout annotations, conflicts,
    and recovery.
21. [Circuit Designer timing stages](circuit-designer-timing-stages.md) —
    vertical cycle edges, single-clock defaults, latency analysis, source
    persistence, and export behavior.
22. [Embedding Circuit Designer](circuit-designer-embedding.md) — reusable React
    shell, host adapters, portable service discovery, and ownership rules.
23. [Circuit Designer visual profile](circuit-designer-visual-profile.md) —
    Blueprint Slate tokens, responsive behavior, and theme extension.
24. [Circuit Designer / Chipmind gap analysis](circuit-designer-chipmind-gap-analysis.md)
    — current overlap, missing capabilities, and suggested priorities.
25. [Spec Editor and Circuit Designer integration architecture](spec-circuit-integration-architecture.md)
    — plain-language ownership, projection, launch, save, refresh, conflict,
    and security diagrams.
26. [Verification & Testplan System](verification-testplan-system.md) —
    hierarchical coverage taxonomy, testplan-service architecture, Circuit
    Designer visual alignment, AI Assistant contract, and execution roadmap.
27. [Focused Spec workspace commands](spec-workspace-cli.md) — Python assistant
    and Spec review CLIs, persistence, and evaluation records.

## Proposed Verification Planner

These four documents specify future behavior, not the existing testplan prototype:

1. [Overall service and user experience](verification-service-overall.md) —
   decisions, palette, layout, navigation, independent architecture, shared API,
   persistence, review boundaries, and delivery gates.
2. [Layer 1: Test Plan](verification-layer-1-test-plan.md) — snapshot references,
   sections, manual intent authoring, UI/API workflows, and FIFO fixtures.
3. [Layer 2: Coverage & Evidence](verification-layer-2-coverage.md) — objectives,
   mapping completeness, results, gaps, exact status and aggregation rules.
4. [Layer 3: Implementation](verification-layer-3-implementation.md) — test IR,
   recipe editor, plugin contracts, artifact generation, and result mapping.

## Documentation rule

Documentation describes behavior that exists now, a clearly labeled next
sample application, or a requested implementation specification explicitly
marked as proposed. Put implementation history in version control rather than
an archive folder. Delete a superseded page instead of adding another versioned
page beside it.

When behavior changes, update the smallest relevant document and the root
README in the same change.

- [Event driven assistant Phase 1](event-driven-assistant-phase1.md): preset usage, limits, recovery, and verification.

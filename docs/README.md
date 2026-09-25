# Documentation

These are living documents for the current system. Historical plans, completed
migration notes, generated demos, and benchmark-specific guides are not kept in
this tree.

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
9. [RTL Generation Activity](rtl-generation-activity.md) — deterministic
   SystemVerilog scaffolding, direct-wire validation, and Verilator checks.
10. [RTL semantics examples](rtl-semantics-examples.md) — body-only component
    behavior, one-/two-cycle samples, and configured output generation.
11. [AI Assistant](ai-assistant.md) — DeepSeek Harness runtime, editor
    integration, review boundary, proposal contracts, setup, and recovery.
    Its [DSH UI migration map](dsh-ui-migration.md) documents the plugin layers
    and retained, extended, and removed UI features.
    The [AI Assistant improvement plan](ai-assistant-improvement-plan.md) is the
    living, topic- and readiness-organized backlog for future assistant work.
    The [configurable assistant architecture](configurable-assistant-architecture.md)
    documents the implemented prompt/workflow catalogs, presets, budgets,
    delegation boundary, and service-extension path.
    The [DSH configurable assistant tutorial](dsh-configurable-assistant-tutorial.md)
    explains the DSH plugins, composition layers, execution paths, authority
    boundaries, persistence, and extension process used by that architecture.
    The [evaluation guide](ai-assistant-evaluation.md) defines the golden
    corpus, DSH replay checks, raw metrics, and commands.
    Its preserved [Spec-to-RTL research guide](research/ai-spec-to-rtl-design-research-guide.md)
    provides research provenance for refining open questions; it is reference
    material rather than current product behavior.
12. [Unified logging](logging.md) — Info/Debug modes, redaction, retention, and
    browser viewer.
13. [Python code-reading guide](python-code-guide.md) — package ownership,
    request flows, proposal boundaries, and a safe newcomer reading order.
14. [Code quality](code-quality.md) — commenting and unused-code review gates.
15. [Sample application method](sample-apps.md) — how to build one representative
    application through the entire system.
16. [Development guide](development.md) — setup, commands, checks, and where code
    belongs.
17. [Circuit Designer interactions](circuit-designer-interactions.md) — unified
    canvas gestures, configurable action bindings, visible commands, and
    editing constraints.
18. [Circuit Designer preferences](circuit-designer-preferences.md) — shared
    JSON profile, REST endpoints, validation, migration, and persistence.
19. [Circuit Designer specification synchronization](circuit-designer-spec-sync.md)
    — source bindings, Save to Specification, layout annotations, conflicts,
    and recovery.
20. [Circuit Designer timing stages](circuit-designer-timing-stages.md) —
    vertical cycle edges, single-clock defaults, latency analysis, source
    persistence, and export behavior.
21. [Embedding Circuit Designer](circuit-designer-embedding.md) — reusable React
    shell, host adapters, portable service discovery, and ownership rules.
22. [Circuit Designer visual profile](circuit-designer-visual-profile.md) —
    Blueprint Slate tokens, responsive behavior, and theme extension.
23. [Circuit Designer / Chipmind gap analysis](circuit-designer-chipmind-gap-analysis.md)
    — current overlap, missing capabilities, and suggested priorities.
24. [Spec Editor and Circuit Designer integration architecture](spec-circuit-integration-architecture.md)
    — plain-language ownership, projection, launch, save, refresh, conflict,
    and security diagrams.

## Documentation rule

Documentation describes behavior that exists now or a clearly labeled next
sample application. Put implementation history in version control rather than
an archive folder. Delete a superseded page instead of adding another versioned
page beside it.

When behavior changes, update the smallest relevant document and the root
README in the same change.

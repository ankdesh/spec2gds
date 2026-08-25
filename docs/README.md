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
11. [AI Assistant](ai-assistant.md) — document- and entity-bound editor
    integration, review boundary, and proposal contracts.
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

## Documentation rule

Documentation describes behavior that exists now or a clearly labeled next
sample application. Put implementation history in version control rather than
an archive folder. Delete a superseded page instead of adding another versioned
page beside it.

When behavior changes, update the smallest relevant document and the root
README in the same change.

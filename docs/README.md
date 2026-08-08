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
4. [Service configuration](service-configuration.md) — shared IP/port registry,
   discovery, and cross-application launch behavior.
5. [Activity snapshot](activity-snapshot-v1.md) — deterministic full-source
   input boundary for specification consumers.
6. [Activity SDK](activity-sdk.md) — two-level read API, plugin contracts,
   registry, results, and Context Renderers.
7. [AI Assistant](ai-assistant.md) — entity-bound editor integration, review
   boundary, and proposal contracts.
8. [Unified logging](logging.md) — Info/Debug modes, redaction, retention, and
   browser viewer.
9. [Code quality](code-quality.md) — commenting and unused-code review gates.
10. [Sample application method](sample-apps.md) — how to build one representative
   application through the entire system.
11. [Development guide](development.md) — setup, commands, checks, and where code
   belongs.

## Documentation rule

Documentation describes behavior that exists now or a clearly labeled next
sample application. Put implementation history in version control rather than
an archive folder. Delete a superseded page instead of adding another versioned
page beside it.

When behavior changes, update the smallest relevant document and the root
README in the same change.

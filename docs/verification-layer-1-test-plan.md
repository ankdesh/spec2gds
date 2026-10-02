# Layer 1: Test Plan

Layer 1 records human-reviewed verification intent against an immutable imported
Activity Snapshot. It defines what needs verification; it does not generate
stimulus or infer passing evidence. [Service operation](verification-service-overall.md)
explains setup; [architecture](testplan-service-architecture.md) maps the code.

## Records and source identity

`domain/models.py` defines the current wire fields. A `PlanHeader` pins a snapshot
and root scope, draft edit revision and per-source-section audit. A `SourceLocator`
identifies snapshot, entity, section and digest, with optional quoted text/range
or structured path/value. These are provenance references, not live Spec reads.

Requirements contain an atomic statement, source locators, scope and disposition.
Sections organize intents with parents, ordered child IDs, default priority and
tags. Intents record Given/When/Then text, named observations, linked requirements,
participants/dependencies, priority override and `draft`, `ready` or `blocked`
authoring state. Issues retain ambiguity/contradiction, severity and resolution.
Archiving retains historical records and references.

Readiness validates requirement links and meaningful intent fields; hierarchy
and dependency cycle checks run over the final staged candidate. A batch can
create a requirement and reference its ID in a later operation. Do not confuse
an intent's authoring readiness with downstream evidence satisfaction.

## Author and review

Import a snapshot through `POST /api/verification/v1/source-imports`, create a
plan through `/plans`, then use the source/requirements and outline views.
Audit sections as requirements captured, informational or out of scope;
non-requirement dispositions need a rationale. Capture requirements, organize
sections, and author intents with explicit observable expected behavior.

Use `/plans/{id}/commands?preview=true` to inspect a batch before committing to
`/plans/{id}/commands`. Query `/operation-catalog` for the supported operation
vocabulary rather than using the removed prototype's `add_node` operations.

Checkpoint preview evaluates audits, requirements, intent readiness, source
issues and mappings. Creating a plan checkpoint freezes its payload and returns
a P-series key (the first is P1). A later draft edit does not modify it.
`application/review_engine.py` owns the exact checklist and warning acknowledgement
rules; a successful source import alone does not mean the plan is reviewed.

## Reuse and portability

Duplication and bundle import create independent records; they do not establish
hidden inheritance. `.vplan`, Markdown and CSV exports are implemented in
`application/export_service.py`. Snapshot rebinding must be an explicit command;
review downstream relationships after source changes instead of assuming old
requirements still refer to the same content.

Synthetic synchronous-FIFO and two-FIFO snapshots live in `fixtures/`. Use
`scripts/build_fixtures.py` as the API authoring example; these inputs are
regression fixtures, not measured hardware evidence.

## Verification and remaining work

`testplan-service/tests/test_layer1_acceptance.py` exercises source imports,
audits, readiness, cycles, command replay, checkpoints and bundle portability.
Run it with `uv run python -m pytest testplan-service/tests/test_layer1_acceptance.py -q`.
The remaining UI conflict/draft preservation, large-plan behavior and exact
cross-layer rebase requirements are tracked in [the backlog](verification-planner-backlog.md).

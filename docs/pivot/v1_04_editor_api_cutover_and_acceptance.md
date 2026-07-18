# V1.4 — Editor, API, Cutover, and End-to-End Acceptance

> Status: completed. This file is implementation and acceptance history;
> current architecture and usage are in `docs/agent_spec_architecture.md` and
> `docs/spec_editor_v1.md`.

## Goal

Expose the new source model and generic action platform through a purpose-built
editor and local API, then remove production dependence on ODT and
heading-derived action blocks.

## Non-Goals

- SystemC, RTL, or any target-specific generator.
- Drag-and-drop diagram editing; V1 provides form/list editing plus derived
  topology visualization.
- Multi-user editing, remote execution, PDF/HTML/DOCX publishing, or legacy
  ODT import.

## Public API

Replace heading/block routes with entity-targeted operations for:

- Loading document snapshot and diagnostics.
- Listing, reading, and editing components and designs.
- Managing entry designs and component-to-internal-design mappings.
- Applying validated source edit transactions with source revision checks.
- Reading and editing narrative blocks and assets.
- Listing actions available for an entity.
- Checking action preconditions and creating action executions.
- Reading execution status, events, reports, and artifacts.
- Previewing, accepting, and rejecting change proposals.

Every source-changing API request carries the expected source revision hash and
returns the committed revision or a conflict/validation diagnostic.

## Editor Information Architecture

Provide top-level navigation for:

- Components
- Designs
- Narrative document
- Actions and action executions
- Artifacts and reports
- Diagnostics

V1 component editing supports identity, concise descriptions, parameters,
wire/transactional ports, bus interfaces, channels, and port maps.

V1 design editing supports component instances, configuration values,
interconnections, ad-hoc connections, explicit entry-design selection, and
component-to-internal-design assignment. Render a read-only derived topology
graph from the validated design data.

Narrative editing supports the V1.1 AST blocks, assets, entity links, and live
views. Live views render current SpecIR data; they never duplicate IP-XACT
tables as independently editable narrative data.

Action UI is target-aware and includes schema-driven inputs, execution status,
reports, artifact lineage, and a proposal diff/review flow.

## Cutover

After the new API/editor workflow passes acceptance:

1. Remove ODT archive/session/relations behavior from production paths.
2. Remove heading-derived block graphs and IP-XACT heading attachments.
3. Remove ODT fixtures and active benchmark expectations.
4. Remove the ODF dependency if it is no longer used elsewhere.
5. Replace public “run” terminology with action-execution terminology.
6. Update the root README and all architecture, schema, vocabulary, action,
   diagnostics, benchmark, and UI documentation to describe the new format.
7. Preserve prior ODT rationale only in clearly labelled archived documents.

## End-to-End Acceptance Scenario

1. Create a new `.spec` package.
2. Add leaf components, ports, bus interfaces, and an abstraction definition.
3. Create an internal design and assign it to a composite component.
4. Create two explicit entry designs that reuse the components.
5. Add narrative sections, a table, an image, entity links, and live views.
6. Save, close, reopen, and validate the document without data loss.
7. Execute the snapshot-summary action against an entry design.
8. Inspect the resulting artifact, report, and provenance.
9. Execute the narrative-proposal action.
10. Preview and accept the proposal.
11. Verify the source revision changes while earlier action provenance remains
    valid.
12. Verify old ODT `.spec` files are rejected by the active CLI and API.

## Validation and Tests

- API tests for every entity, transaction, action, artifact, and proposal
  route.
- UI tests for component/design/narrative editing, validation diagnostics,
  action execution, artifact display, and proposal review.
- Playwright test for the complete acceptance scenario.
- Package/open/save tests through UI and CLI.
- Regression test that no production entry point imports or requires ODT
  parsing, ODF manifests, or heading block graphs.

## Assumptions

- V1 is a local single-user application.
- The existing frontend can be evolved or replaced as needed; no visual
  fidelity to office documents is required.
- Historical ODT support is intentionally removed rather than migrated.

## Exit Gate

The full acceptance scenario passes through both CLI and editor. All active
documentation describes the new package, SpecIR, and action execution model,
and no production path depends on ODT or heading-based blocks.

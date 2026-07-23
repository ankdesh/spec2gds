# A2UI Specification Editor — Stage 1

Stage 1 turns one validated `.spec` package into a single human-readable,
read-only document. IP-XACT and JSON/narrative sources stay authoritative in
`SpecRevision`; A2UI is only the transport and presentation layer.

## Runtime Boundary

```text
.spec package
    │ validate and normalize
    ▼
SpecRevision
    │ deterministic presentation projection
    ▼
DocumentProjection
    │ compile to A2UI v0.9 messages
    ▼
Custom A2UI catalog ──► React document components
```

The FastAPI process owns package selection, source snapshots, the A2UI batch,
actions, activity, diagnostics, and proposal review. Native React owns the
package picker and the Document/Activity/Diagnostics shell. A2UI owns only the
document surface.

The projection and A2UI compiler live in
`spec2gds/agent_spec/spec_format/document.py`. `GET /documents/a2ui` returns a
batch containing:

- `createSurface` for `urn:spec2gds:a2ui:document:v1`;
- one adjacency-list `updateComponents`;
- one `updateDataModel` carrying document and source-revision identity.

The renderer-independent projection remains separately testable and can later
feed another A2UI frontend without importing React.

## Document Shape

The generated hierarchy is stable:

1. Overview
2. Designs
3. Components
4. Protocols
5. Cross-cutting Notes, when multi-entity narrative exists

Designs and components form level-two sections. Narrative linked to one entity
is placed in that entity's section. Unlinked narrative stays in Overview.
Narrative referencing multiple entities is placed under Cross-cutting Notes.

Stage 1 emits fixed-column tables for the V1 IP-XACT subset, including
parameters, assertions, choices, component ports, bus interfaces, port maps,
channels, design instances, interface/ad-hoc connections, bus properties, and
abstraction logical ports. Register maps remain outside the current V1 profile
and are explicitly deferred.

Every table column and cell carries an IP-XACT schema path. Each cell also
records whether its value was:

- `explicit`: present in source;
- `defaulted`: supplied by the profile;
- `absent`: not present and not defaulted.

This distinction is part of the data contract, not inferred by CSS.

## A2UI Catalog

`circuit-designer/packages/document-a2ui-react` defines a small semantic
catalog:

- `SpecDocument`
- `SpecSection`
- `SpecTable`
- `NarrativeBlock`
- `EntityLink`
- `LiveView`

These components receive complete semantic props and do not fetch IP-XACT,
interpret XML, or own package state. Components communicate entity-action
intent through one DOM custom event; the native shell performs the API call.
This keeps them portable to another A2UI host.

Shared HTTP and document contracts live in
`circuit-designer/packages/document-core`. The editor composition root lives in
`circuit-designer/apps/editor`.

## Build and Run

Node.js 24 is the supported frontend runtime.

```bash
uv sync
uv run spec2gds-server --reload

# Second terminal, for UI development:
cd circuit-designer
npm install
npm run dev:editor
```

The development URL is `http://127.0.0.1:4190`; Vite proxies `/api` to FastAPI
on port 8000.

Build the production assets that FastAPI serves:

```bash
cd circuit-designer
npm run build:editor
```

The output is
`spec2gds/agent_spec/spec_format/editor_dist/` and is included in the Python
package. Normal users run only `uv run spec2gds-server` and open `/editor`.

## Stage 2 Seam

Stage 2 should add editing without replacing the projection:

1. extend `DocumentCell` with an edit descriptor containing operation type,
   entity identity, field identity, validation rules, and original value;
2. add editable A2UI cell components while retaining `SpecTable`;
3. stage changes client-side as typed operations, never as mutated snapshot
   objects;
4. preview and commit through `/transactions` with
   `expected_source_revision_hash`;
5. rebuild the projection and A2UI surface after each accepted transaction;
6. preserve explicit/defaulted/absent semantics so clearing a value is
   distinguishable from accepting a profile default.

This keeps Stage 2 focused on edit intent and conflict handling. It does not
move source authority into React or the A2UI data model.

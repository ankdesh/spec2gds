# Independent Circuit Designer v1 Protocol

The Circuit Designer owns the schema and semantics of portable
`CircuitDocument` values; it does not own their durable storage. SpecIR and
IP-XACT are not protocol dependencies. Future translators are ordinary REST
clients that supply component definitions and a design, then translate
committed circuit content back to their own model.

The JSON Schema authority is
`circuit-designer/schema/circuit-designer.v1.schema.json`. TypeScript bindings
and the runtime schema copy are generated with `npm run generate` and checked
with `npm run generate:check`.

## Canonical document

A document contains a working component catalog, exactly one design, and one
canonical logical-unit layout. The design owns instances, optional boundary
terminals, and multi-endpoint nets. Net endpoints reference either a boundary
terminal or an instance/component-terminal pair and may include a bus slice.
One terminal slice may belong to only one net.

Component IDs, instance IDs, terminal IDs, and net IDs are stable readable
slugs. Labels are editable and do not rename IDs. Local definitions are
editable; built-in and provider definitions are read-only. Component template
parameters expand terminal structure when a definition is created. Instance
parameters never change terminal structure in v1.

Terminal directions are `input`, `output`, or `inout`. A terminal width is
either a positive integer or non-empty opaque text supplied by the component
owner, such as `[DATA_WIDTH-1:0]`. Circuit Designer displays symbolic width
text but does not evaluate or rewrite it. Whole-terminal connections may use
either form; endpoint slices require a numeric width so their bounds can be
validated. Bidirectional terminals are source- and sink-capable and use the
neutral south side when no placement is stored.

Incomplete nets and unconnected terminals are allowed. Direction and width
problems are warnings. Broken references, overlapping slice ownership, invalid
layout references, and hierarchy incompatibility are errors. Deletion of
connected objects requires an explicit `cascade: true`.

## Mutation paths

- Full desired state uses an explicit `create` or `replace`; merging is never
  inferred. Supplied geometry is preserved and only missing geometry is placed.
- `CircuitConstruction` compiles readable request-local aliases into a
  normalized document and returns an alias map.
- `CircuitOperationBatch` carries a request ID, expected opaque revision, and
  ordered domain operations. Preview and commit are atomic. Request IDs make
  commits idempotent.

Manual editing acquires an exclusive whole-document lease and creates a private
`CircuitDraft`. Draft moves and routes are coalesced. Undo and redo exist only
inside the draft. Save commits its complete operation batch; Cancel discards it.
Warnings permit Save while errors retain the draft. In the browser file
workflow, an accepted Save also downloads the accepted `CircuitDocument`.

## Transport and session outcomes

All external clients communicate through the versioned REST API. The browser
uses `HttpCircuitDesignerBackend`; future SpecIR translators, chat agents, and
automation clients use the same HTTP contracts.

The Node service stores active documents, revisions, leases, proposals, and
idempotency results only in process memory. This state coordinates an editing
session and is discarded on service restart. Durable ownership always remains
with a client, such as a SpecIR system or a downloaded `.circuit.json` file.
There is no SQLite or IndexedDB repository in the v1 runtime.

The active service snapshot is authoritative for concurrent REST activity.
“Client-owned persistence” does not mean each REST request carries the complete
document: the service retains short-lived session state so it can enforce
revisions, leases, proposals, and idempotent retries.

Change results distinguish `accepted`, `rejected`, `conflict`, `locked`, and
`provider_failed`. The REST service maps revision and stale-proposal conflicts
to HTTP 409, edit locks to 423, validation failures to 400, missing objects to
404, and provider failures to 502.

SSE events are invalidations, not state replication. Clients refetch the
authoritative snapshot after `document.changed`, `lock.changed`,
`proposal.changed`, or `provider.requested`.

External proposal authors submit `CircuitProposalCreateRequest`, containing
identity, base revision, descriptive fields, and exactly one construction or
operation batch. They cannot author status, diagnostics, normalized diff, or
creation time; the service previews the request and owns those fields in the
returned `CircuitProposal`.

## Portable file workflow

The web client opens a circuit with a standard HTML file-upload control. The
file must be a canonical `CircuitDocument` encoded as UTF-8 JSON. Invalid JSON,
schema errors, and semantic errors are rejected without changing the live
session.

Saving creates a browser download named `<document_id>.circuit.json`. The web
client never receives filesystem paths and does not overwrite an existing file
in place. A private draft must be committed or cancelled before opening or
exporting another authoritative document.

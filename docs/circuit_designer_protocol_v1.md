# Independent Circuit Designer v1 Protocol

The Circuit Designer owns a portable `CircuitDocument`; SpecIR and IP-XACT are
not protocol dependencies. Future translators are ordinary clients that supply
component definitions and a design, then translate committed circuit content
back to their own model.

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
Warnings permit Save while errors retain the draft.

## Transport outcomes

All backends implement the same `CircuitDesignerBackend` interface. Change
results distinguish `accepted`, `rejected`, `conflict`, `locked`, and
`provider_failed`. The REST service maps revision and stale-proposal conflicts
to HTTP 409, edit locks to 423, validation failures to 400, missing objects to
404, and provider failures to 502.

SSE events are invalidations, not state replication. Clients refetch the
authoritative snapshot after `document.changed`, `lock.changed`,
`proposal.changed`, or `provider.requested`.

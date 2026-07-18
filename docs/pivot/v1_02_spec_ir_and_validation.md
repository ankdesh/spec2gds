# V1.2 — SpecIR, Semantic Queries, and Edit Validation

> Status: completed. This file is implementation and acceptance history; the
> active contract is in `docs/spec_ir_v1.md`.

## Goal

Load the V1 source package into an immutable semantic representation called
`SpecRevision` (also referred to as SpecIR), provide stable entity queries,
and apply source changes through atomic validated edit transactions.

The SpecIR represents source only: components, designs, bus/abstraction
definitions, narrative, assets, and accepted annotations. Action history and
artifact activity are not part of the source graph.

## Non-Goals

- Executing actions, storing artifacts, or applying change proposals.
- Persisting derived lookup indexes as a second source of truth.
- Supporting IP-XACT views, design configurations, or abstractors.
- Multi-user editing or conflict merging.

## Public Contracts

```text
EntityRef
  document_id
  entity_id
  entity_kind

SpecRevision
  document_id
  source_revision_hash
  manifest
  components
  designs
  bus_definitions
  abstraction_definitions
  narrative
  assets
  annotations
  diagnostics

SpecEditTransaction
  base_source_revision_hash
  operations: list[EditOperation]

EditResult
  revision | diagnostics
```

The source revision hash covers only canonical source entries: manifest source
fields, IP-XACT documents, narrative AST, assets, and accepted annotations. It
must not change when future action records, reports, or artifact metadata are
added.

Provide immutable semantic-query methods:

- Resolve an entity by `EntityRef`.
- Resolve a document by VLNV and kind.
- List explicit entry designs.
- Resolve a component's optional internal design.
- Traverse design instances, interfaces, and connections.
- Find narrative blocks linked to an entity.
- Return the transitive dependency closure for a component or design.

Implementation may build dictionaries and graph indexes for speed, but those
are disposable load-time caches and are never persisted independently.

## Required Semantic Rules

- A component is a leaf or has exactly one internal design.
- A design has at most one component owner but can also be an entry design.
- Component-to-internal-design composition is acyclic.
- An internal design's external boundary matches the owning component's
  interfaces and ports.
- Every component instance resolves to an embedded component definition.
- Every connection endpoint exists and is compatible with its peer.
- Connected interfaces use compatible bus and abstraction definitions.
- IDs, VLNVs, component instance names, interface names, port names, and
  connection names are unique in their standard/project scopes.
- Every narrative entity link resolves to a source entity.

## Edit Transactions

Define typed operations for:

- Add, update, or delete components and designs.
- Add, update, delete, or reorder instances and connections.
- Set or clear a component's internal-design composition.
- Add or remove entry designs.
- Edit component, port, interface, bus, and abstraction fields in the V1
  profile.
- Insert, update, delete, and reorder narrative blocks.
- Add and remove source assets and entity links.

Transaction behavior:

1. Verify that `base_source_revision_hash` matches the loaded source.
2. Apply all operations to a working copy.
3. Rebuild the semantic graph and run XSD, profile, referential, hierarchy,
   and narrative validation.
4. Serialize and commit a new source revision only when every check passes.
5. Return diagnostics and preserve the original revision when any check fails.

## Implementation Steps

1. Define typed SpecIR models independently of raw XML parser objects.
2. Implement source loading that maps the V1 package to `SpecRevision` and
   retains enough XML provenance to serialize validated edits.
3. Build entity/VLNV/reference/connection indexes at load time.
4. Implement the query API and dependency-closure algorithm.
5. Implement edit operations and optimistic revision checks.
6. Serialize accepted transactions through the deterministic V1.1 package
   writer.
7. Add a sample hierarchy containing leaf components, a composite component,
   an internal design, and two entry designs.

## Validation and Tests

- Resolve every entity kind by stable ID and VLNV.
- Verify entry-design and component-composition queries.
- Verify dependency closure for leaf, composite, and entry-design targets.
- Reject composition cycles, missing components, duplicate instances, missing
  endpoints, invalid interface mappings, incompatible connections, and broken
  narrative links.
- Verify internal-design boundary compatibility.
- Verify valid transactions create new revisions and preserve stable IDs.
- Verify invalid transactions roll back completely.
- Verify stale base revisions are rejected.
- Verify save/reopen retains source hashes and semantic identities.

## Assumptions

- V1 is local and single-user; optimistic revision checks are sufficient.
- No action or editor code receives direct mutable access to the loaded
  package.
- Raw IP-XACT remains canonical at rest, while SpecIR is the typed working
  representation.

## Exit Gate

The V1.1 sample loads into a validated immutable `SpecRevision`, supports all
defined edit operations atomically, and survives save/reopen with identical
semantic identity and source hashing. All graph and transaction tests pass.

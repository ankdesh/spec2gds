# Development Methodology

The project follows a source-first, invariant-driven vertical-slice method.
Changes move from canonical contract to semantic model to use case to API/UI,
with deterministic evidence at each boundary.

## Principles

### Source before presentation

Hardware and narrative meaning must be representable in canonical source before
the editor renders or changes it. UI-only data models are not a substitute for
source contracts.

### Validate at ownership boundaries

Each layer validates what it owns: archive safety, persisted schema, IP-XACT
protocol, semantic graph, transaction concurrency, action contracts, and
artifact integrity. Higher layers do not weaken lower-layer invariants.

### Immutable reads, atomic writes

Consumers read `SpecRevision`. Writers produce a new validated revision through
`SpecEditTransaction`. This makes failure behavior, concurrency, action
snapshots, and proposal review predictable.

### Generated output is evidence

Reports and artifacts are immutable evidence tied to source revisions and
entities. They are not canonical source. Any suggested source change is a
reviewed proposal.

### One representative sample

The deterministic V1 sample is a living product walkthrough. It should become
richer as capabilities grow instead of being replaced by disconnected toy
fixtures.

## Vertical Slice Workflow

1. **State the invariant.** Identify source authority, stable identity,
   validation, compatibility, and failure behavior.
2. **Change the contract.** Update strict models and format/profile versions if
   persisted compatibility changes.
3. **Project semantics.** Add immutable IR and cross-document validation.
4. **Add the use case.** Implement a typed query, transaction, or action without
   transport dependencies.
5. **Expose the adapter.** Decode/encode values at the FastAPI boundary and map
   conflicts or validation failures to explicit statuses.
6. **Render the view.** Build browser presentation from the API projection; do
   not persist a second model.
7. **Extend evidence.** Update the sample, focused tests, end-to-end acceptance,
   and user documentation.
8. **Audit the cut.** Search for stale terminology, dependencies, paths,
   commands, and historical assumptions.

## Design Review Questions

- What is canonical source, derived state, activity, or artifact content?
- Which stable identity survives rename, reorder, save, and reopen?
- What exact invalid state is rejected, where, and with which diagnostic?
- Does a failure leave active source and artifact metadata unchanged?
- Does the change alter the source hash, package bytes, or compatibility?
- Can an action reproduce its result from the captured snapshot and toolchain
  identity?
- Can the editor render the capability solely from the server projection?
- Which sample screen and automated test prove the behavior?

## Definition of Done

A change is complete only when:

- the canonical contract and invariants are explicit;
- the complete source candidate validates atomically;
- public writes are revision-guarded;
- generated content has provenance and reviewed writeback where applicable;
- the deterministic sample exposes editor-visible behavior;
- focused and full tests pass;
- active docs, commands, vocabulary, and roadmap status match the code;
- removed behavior is not still advertised by tests, dependencies, or docs.

## Planning Future Capability Packs

SystemC, RTL, and physical implementation work should integrate as capability
packs above the V1 action/artifact boundary. They may introduce typed source
annotations and new actions, but they must not couple canonical source to one
tool vendor or write generated content directly into the source package.

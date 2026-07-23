# Architecture Boundary Assessment

This assessment replaces the pre-pivot MVC review. It evaluates the current
V1 implementation against its desired separation of source, application, and
presentation concerns.

## Summary

The current system has a sound dependency direction and a small composition
root. The browser behaves as a view/controller over immutable API projections;
`SpecRevision` and strict persisted models form the domain model; `V1Session`
and FastAPI routes form the local application layer.

The design is closer to hexagonal architecture than classic server-side MVC:
the package/IR/action core is framework-independent, while HTTP and browser
code adapt that core for a local user.

## Boundary Map

| Concern | Owner | Assessment |
| --- | --- | --- |
| Persisted source contract | `models.py`, `archive.py` | Strong: deterministic and framework-independent. |
| Semantic model | `ir.py` | Strong: immutable objects and explicit queries. |
| Write use cases | `transactions.py` | Strong: atomic, optimistic, full revalidation. |
| Execution use cases | `actions.py` | Strong: snapshots and reviewed writeback preserve source authority. |
| Application composition | `v1_api.py` | Appropriate for V1; deliberately single-process and single-session. |
| Document presentation contract | `document.py` | Strong: renderer-neutral projection and deterministic A2UI compilation. |
| Presentation | `circuit-designer/apps/editor/`, `packages/document-*` | Strong: semantic A2UI components and a thin native React shell own only presentation state. |

## What Is Working Well

### Immutable model boundary

The UI and actions consume `SpecRevision` projections rather than mutable XML
or ZIP internals. This prevents accidental cross-layer mutation and makes
optimistic revision checks meaningful.

### One validated write path

Interactive edits and accepted action proposals both use
`SpecEditTransaction`. There is no privileged proposal write path that can
bypass source validation.

### Source/activity split

Execution history is durable without entering the source revision identity.
Artifact bytes are separately content-addressed and verified. This is a clear
separation between model state and operational evidence.

### Thin browser client

The editor renders the server's A2UI document projection and activity routes.
It does not persist a parallel client-side hardware graph or parse IP-XACT.

## Current Tradeoffs

### `v1_api.py` is both adapter and application service

For V1 this keeps the local product understandable. If multiple transports or
multi-document concurrency appear, extract a transport-neutral application
service before duplicating route logic.

### `V1Session` has a single active document

This matches the local single-user boundary. Multi-tab or multi-user support
would require explicit session IDs, lifecycle management, and concurrency
policy rather than a larger global dictionary.

### Reference actions are trusted local subprocesses

Isolation is by temporary directories and strict input/output contracts, not a
security sandbox. Untrusted or remote execution requires a future capability
broker and stronger isolation model.

### Document field editing uses XML upsert

The transaction layer has typed instance, connection, hierarchy, narrative,
and asset operations. Fine-grained component field forms currently serialize a
complete profiled XML document. Add typed component operations only when UI
requirements justify their maintenance cost.

## Methodology

Architecture changes should follow this order:

1. Define or update the persisted contract and invariants.
2. Add immutable semantic projection and validation.
3. Add one typed transaction or action use case.
4. Expose it through the HTTP adapter.
5. Render it in the browser without creating a second source model.
6. Extend the deterministic sample and acceptance tests.

This order keeps protocol and source integrity ahead of presentation
convenience.

## Future Extraction Triggers

Do not add layers speculatively. Extract a new boundary when one of these is
real:

- a second transport needs the same use cases;
- more than one active document must be managed concurrently;
- actions execute outside the trusted local process boundary;
- component/design edits require a stable public fine-grained command API;
- V2/V3 generators introduce capability discovery and scheduling.

## Decision

The current architecture is appropriate for the V1 product boundary. Near-term
work should extend the existing source-first flow rather than reintroduce a
repository abstraction, heading graph, plugin manager, or client-owned model.

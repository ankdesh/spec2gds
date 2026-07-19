# Circuit Designer Completed Roadmap

This document covers Phases 2–5, which complete the roadmap after the Phase 0
foundation and Phase 1 read-only integration.

## Final architecture

All human and agent changes use `CommandBatch`. A batch carries stable element
IDs, one target design, and the source revision hash the caller observed.

```text
React UI / agent client
        |
        v
CircuitDesignerApi (TypeScript)
        |
        v
FastAPI circuit routes
        |
        v
CircuitDesignerSession
   |                 |
   v                 v
SpecIR transaction   layout/proposal sidecars
   |
   v
validated IP-XACT package
```

Source commands are translated to existing typed `SpecEditTransaction`
operations and applied to a private immutable revision. The active package is
replaced only if every operation validates. Layout commands never rewrite
IP-XACT; they use a deterministic renderer-neutral sidecar.

## Phase 2: mutation and coordination

The service implements:

- preview and atomic apply for revision-guarded command batches;
- exclusive renewable human or agent edit leases;
- stale-revision, invalid-command, and lock-conflict diagnostics;
- persisted node geometry, terminal placement, route trees, and layout
  direction;
- in-session undo and redo for source and layout changes;
- source edits through SpecIR for add, duplicate, replace, and delete instance;
- create, rename, extend, disconnect, and delete net operations.

Instance display metadata and configuration values remain disabled because the
current project IP-XACT profile has no persistence semantics for them. Instance
rename is intentionally expressed as duplicate/delete rather than pretending
references were updated incompletely.

## Phase 3: interactive editing

After obtaining a human lease, the canvas enables drag placement and persists
the resulting geometry. The workbench provides add/delete instance, component
replacement, net rename/delete, undo, and redo controls. The complete command
surface—including endpoint manipulation and explicit route changes—is also
available through the programmatic client.

ELK's supported browser worker is used for layout. Persisted overrides are
merged onto fresh automatic layout, and ELK orthogonal edge sections are
converted into the renderer-neutral route tree. The deterministic fallback is
used only when ELK does not return route sections.

## Phase 4: agent collaboration and hierarchy

Agents submit the same command batches as persistable proposals. The UI lists
pending proposals for human acceptance or rejection. Acceptance requires the
active edit lease and revalidates the original revision guard; stale proposals
are marked rather than partially applied.

The catalog includes component-composition hierarchy links. The workbench
shows parent and internal-design navigation without encoding IP-XACT knowledge
in the React renderer.

Proposal state is stored beside the source package in
`<package>.circuit-proposals.json`. Layout is stored in
`<package>.circuit-layout.json`. Neither file becomes a second source of truth
for electrical semantics.

## Phase 5: delivery and hardening

The UI polls immutable revision identity and refreshes when another workflow
commits the active package. The Vite development server proxies to FastAPI,
while a production build can be served by FastAPI at
`/circuit-designer-ui/`.

Build and run the integrated application:

```bash
cd circuit-designer
npm install
npm run generate:check
npm test
npm run build
cd ..
uv run spec2gds-server
```

Open the existing editor to select a package, then use
`http://127.0.0.1:8000/circuit-designer-ui/`. For frontend development, use
`npm run dev` and `http://127.0.0.1:4173` instead.

## HTTP API

Read operations:

```text
GET  /circuit-designer/catalog
GET  /circuit-designer/designs/{design_id}
GET  /circuit-designer/lease
GET  /circuit-designer/history
GET  /circuit-designer/proposals
```

Coordination and mutation:

```text
POST   /circuit-designer/lease
DELETE /circuit-designer/lease/{lease_id}
POST   /circuit-designer/commands/preview
POST   /circuit-designer/commands/apply
POST   /circuit-designer/history/undo
POST   /circuit-designer/history/redo
POST   /circuit-designer/proposals
POST   /circuit-designer/proposals/{proposal_id}/decision
```

The TypeScript `CircuitDesignerApi` mirrors this surface and remains free of
React, ELK, FastAPI, SpecIR, and IP-XACT types.

## Intentional product boundary

The implementation supports the IP-XACT subset already represented by
spec2gds: component instances, component interfaces and ports, interface and
ad-hoc connections, external/hierarchy endpoints, and component composition.
It does not claim full IEEE 1685 coverage. Unsupported profile fields fail with
explicit diagnostics instead of being silently discarded.

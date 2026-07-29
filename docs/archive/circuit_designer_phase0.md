# Historical: Circuit Designer Phase 0

Phase 0 establishes the reusable circuit-diagram boundary and a working,
read-only UI spike. It deliberately does not add FastAPI routes, persistence,
edit execution, lock management, or IP-XACT writes.

The live read-only routes and server-backed UI that followed are documented in
[Circuit Designer Phase 1](circuit_designer_phase1.md).

## Architecture

The dependency direction is one-way:

```text
SpecIR -> Python projection -> versioned JSON contract
                                  |
                                  v
                         TypeScript core package
                                  |
                     +------------+-------------+
                     v                          v
             grid layout/router          React renderer
                     +------------+-------------+
                                  v
                         standalone mock app
```

`spec2gds.agent_spec.circuit_designer.contracts` is transport-only and does
not import SpecIR or IP-XACT code. The projection adapter is the only Phase 0
module that knows the current SpecIR model. This keeps the graph, layout, and
UI packages usable with another electrical-design backend.

The checked-in JSON schema is generated from Pydantic. TypeScript definitions
are then generated from that schema, so Python is the Phase 0 contract source
of truth rather than a parallel handwritten model.

## Packages

- `@spec2gds/circuit-core`: generated contracts, runtime AJV validation,
  indexing/query helpers, command-batch construction, and deterministic
  fixtures.
- `@spec2gds/circuit-layout`: deterministic connectivity-layered grid placement
  plus global obstacle-aware orthogonal routing. It has no worker or external
  layout-engine dependency.
- `@spec2gds/circuit-react`: React Flow canvas with hardware-spec component
  blocks, semantic terminals, orthogonal segments, junction dots, selection,
  zoom, and pan.
- `@spec2gds/circuit-designer-mock`: standalone Vite application with fixture
  selection, graph statistics, and an inspector.

## Contract boundaries

`CircuitGraphSnapshot` carries stable IDs, opaque source references,
capabilities, component definitions, instances, semantic terminals, nets, and
optional layout. It has no React Flow or layout-engine types.

`DiagramLayout` stores node rectangles, terminal side/order, and each net as a
route tree of endpoint, bend, and junction vertices connected by strictly
orthogonal segments. This represents multi-endpoint electrical nets without
forcing them into unrelated pairwise net identities.

The command union defines the future common human/agent manipulation surface.
Commands are grouped in a revision-guarded batch; proposals, previews,
diagnostics, and edit leases are transport contracts only in this phase. All
projected capabilities are `false` until a later adapter implements them.

## Development

Python setup remains managed by `uv`:

```bash
uv sync
uv run python -m pytest tests/agent_spec/circuit_designer -q
```

Regenerate the shared schema after changing a Pydantic contract:

```bash
uv run python -m spec2gds.agent_spec.circuit_designer.schema \
  --output circuit-designer/schema/circuit-designer.v1.schema.json
cd circuit-designer
npm run generate
```

Use Node.js 24 for the standalone workspace:

```bash
cd circuit-designer
npm install
npm run generate:check
npm test
npm run build
npm run dev:specir
```

For the browser smoke test, install Chromium once and run Playwright:

```bash
cd circuit-designer
PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright-browsers" npm exec playwright install chromium
npm run test:e2e
```

Playwright may also request distribution browser libraries; install those with
the package manager appropriate to the development machine.

The mock app is served at `http://127.0.0.1:4173`. The fixtures cover simple
point-to-point wiring, mixed interface/ad-hoc connections, a multi-endpoint
net, hierarchy boundaries, a cycle, and a 200-instance/398-net scale graph.

In WSL environments that inherit an inaccessible Windows temporary directory,
run Vitest or the build with `TMPDIR=/tmp`.

## Phase 0 acceptance boundary

Accepted here: deterministic schema/type generation; current SpecIR read
projection; strict runtime validation; deterministic automatic layout; 90-degree route
trees; multi-endpoint rendering; standalone mock inspection; unit, scale, and
browser smoke tests.

Deferred at the Phase 0 boundary: FastAPI endpoints and live `.spec` loading
(now delivered by Phase 1), topology and layout edits, undo/redo, lock
enforcement, proposal review UI, source writes, semantic validators, hierarchy
navigation behavior, persisted view state, and crossing minimization quality
tuning against real project designs.

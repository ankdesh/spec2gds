# Standalone Circuit Designer

> This long-form document records the earlier standalone canvas iteration.
> The authoritative independent-v1 contracts and run instructions are now
> [`docs/circuit_designer_protocol_v1.md`](../../../docs/circuit_designer_protocol_v1.md)
> and [`docs/circuit_designer_run_v1.md`](../../../docs/circuit_designer_run_v1.md).
> The former SpecIR mock harness and command protocol described later in this
> file have been removed.

The Standalone Circuit Designer is the independent development and usage
environment for the circuit canvas. It runs entirely in the browser with
bundled example circuits and does not require Python, FastAPI, SpecIR, IP-XACT,
or an open `.spec` package.

Use this application to:

- draw components, ports, and interconnects with minimal metadata;
- position components and ports on a 20-pixel grid;
- generate obstacle-aware orthogonal routes;
- manually edit, constrain, and lock route geometry;
- test the shared command API without changing the spec editor;
- export the renderer-independent circuit graph as JSON.

## Quick start

Node.js 24 is the supported runtime.

From the repository root:

```bash
cd circuit-designer
npm install
npm run dev:standalone
```

Open <http://127.0.0.1:4180>.

The shorter `npm run dev` command starts the same standalone application.

## Recommended workflow

1. Choose an example circuit or reset the current example.
2. Create or drag components into their intended positions.
3. Select each component to create, reorder, and position its ports.
4. Create interconnects in **Connect** mode or with the endpoint selectors.
5. Select **Reroute unlocked nets** after the block and port positions are
   stable.
6. Enter **Route** mode to adjust important trunks, bends, or junctions.
7. Lock intentional route geometry so later rerouting preserves it.
8. Use **Export JSON** to save the current renderer-neutral graph.

Changes live only in the current browser tab. **Reset** restores the selected
example; it does not affect a `.spec` package or the spec2gds editor.

## Canvas modes

| Mode | Intended operation | Disabled operations |
|---|---|---|
| **Select** | Select and grid-drag components | Connection handles, route editing, canvas pan/zoom |
| **Connect** | Drag between compatible terminal handles | Component movement, route editing, canvas navigation |
| **Route** | Edit segments, bends, junctions, and locks | Component movement and canvas navigation |
| **Pan** | Pan and zoom without changing the circuit | Component, connection, and route mutations |

Additional navigation:

- Hold `Space` for temporary Pan mode.
- Press `Escape` to return to Select mode.
- Component movement never automatically pans or zooms the canvas.

## Drawing and editing

### Components

Use **Draw component** to create a placeholder component with a name. Select a
component to:

- change its label;
- duplicate or delete it;
- pin or unpin its geometry;
- optimize only its connected nets;
- create and delete ports.

Component origins snap to the visible 20-pixel grid. Dropping a component
reroutes its connected unlocked nets in the same undoable command batch.

### Ports

The selected-component inspector can:

- create input, output, and bidirectional ports;
- assign a port to the north, east, south, or west side;
- move it earlier or later on that side;
- lock the placement or restore automatic placement.

Input ports default to the west side, output ports to the east side, and
bidirectional ports to the south side. Components are enlarged when required
to accommodate the selected port order.

### Interconnects

Create a net either by:

- entering a name and choosing two endpoints in **Connect terminals**; or
- switching to **Connect** mode and dragging between terminal handles.

A physical port can connect to another physical port, and an interface can
connect to another interface. Semantic connectivity is stored separately from
the optional route geometry.

### Manual routes

In **Route** mode:

- drag a horizontal segment vertically;
- drag a vertical segment horizontally;
- drag a bend or electrical junction;
- double-click a segment to insert a bend;
- double-click an unlocked bend to remove it;
- Shift-click a segment, bend, or junction to toggle its lock.

The selected-net inspector can optimize or reset the entire net, lock or unlock
all route geometry, or reset one endpoint branch.

## Placement and routing behavior

The application deliberately separates placement from routing:

- **Arrange unpinned blocks** provides simple deterministic initial placement.
- **Reroute unlocked nets** never moves components or ports.
- Pinned component geometry is preserved by automatic arrangement.
- Any net containing an explicit route lock is preserved during normal
  rerouting.

The router sees all requested nets together. It treats component rectangles,
boundary terminals, unselected routes, and user-locked routes as obstacles. It
prefers short paths with fewer bends and searches for routes without:

- net-to-block intersections;
- shared geometry between independent nets;
- geometric crossovers between independent nets;
- diagonal segments;
- terminal wires initially running along a component edge.

Every terminal begins with a 20-pixel segment perpendicular to its component
side. Junction dots are emitted only for electrically connected route vertices
with degree three or greater; a plain geometric crossing does not imply an
electrical connection.

For ordinary interactive designs, occupied routes are strict obstacles. For a
very dense design where no free channel can be found, the router uses a
congestion-penalized fallback so it can still produce a valid route while
minimizing unavoidable overlap or crossing.

## User-interface layout

The application has four primary regions:

```text
+------------------------------------------------------------------+
| Example picker | Undo | Redo | Reset | Export JSON               |
+----------------+--------------------------------+----------------+
| Design tools   | Canvas and mode toolbar        | Inspector      |
|                |                                |                |
| - layout       | components, ports, and nets    | selected block |
| - components   |                                | or selected net|
| - connections  |                                |                |
+----------------+--------------------------------+----------------+
```

The notice bar reports command results and makes it clear that the application
is operating in independent local mode.

## Architecture

The standalone composition keeps the UI, electrical model, routing, and command
execution as separate packages:

```text
apps/standalone
  App.tsx
    |
    +--> @spec2gds/circuit-client-local
    |      in-memory CircuitDesignerApi, leases, preview/apply,
    |      revision guards, undo/redo, proposals, and reset
    |
    +--> @spec2gds/circuit-core
    |      generated contracts, graph indexes, validation,
    |      fixtures, and renderer-independent route editing
    |
    +--> @spec2gds/circuit-layout
    |      deterministic grid placement and global
    |      obstacle-aware orthogonal routing
    |
    +--> @spec2gds/circuit-react
           React Flow canvas, circuit blocks, terminal handles,
           route rendering, selection, and gestures
```

There is no dependency from the standalone app to:

```text
Python / FastAPI / SpecIR / IP-XACT / .spec packages
```

### State and command flow

```text
Human gesture
    |
    v
Typed DesignerCommand or atomic CommandBatch
    |
    v
LocalCircuitDesignerApi preview/apply
    |
    +--> revision and lease validation
    +--> semantic and route validation
    +--> undo/redo history
    |
    v
New immutable CircuitGraphSnapshot
    |
    +--> placement/routing projection
    |
    v
CircuitDesignerCanvas
```

Both a human UI and a programmatic agent use the same `CircuitDesignerApi` and
the same typed command batches. An exclusive edit lease ensures that only one
owner manipulates a document at a time.

### Data ownership

`CircuitGraphSnapshot` is the renderer-neutral document:

- `nodes`, `terminals`, and `nets` contain semantic topology;
- `layout.node_geometry` contains component presentation geometry;
- `layout.terminal_placements` contains side and order overrides;
- `layout.net_routes` contains optional route vertices and segments;
- route locks constrain automatic geometry without changing connectivity.

React Flow state is derived from this snapshot; it is not the source of truth.
The local client returns a new snapshot after every accepted command batch.

## Included examples

| Example | Primary purpose |
|---|---|
| Processor subsystem | Interface and physical-port nets in one design |
| Producer / consumer | Basic movement, connection, and route editing |
| Broadcast fanout | Multi-endpoint tree and electrical junction behavior |
| Feedback pipeline | Cyclic connectivity and longer orthogonal routes |
| Disconnected crossing | Difference between a crossing and a junction |

## Source map

```text
apps/standalone/
  src/App.tsx             application composition and command workflows
  src/examples.ts         independent example catalog
  src/layout-state.ts     guards asynchronous layout results by graph revision
  src/styles.css          standalone workbench styling
  src/examples.test.ts    example and isolation regression tests

e2e/standalone.spec.ts    workspace-level Playwright interaction tests
```

Shared implementation:

```text
packages/core/            contracts, validation, fixtures, route editor
packages/client-local/    in-memory shared API implementation
packages/layout/          placement and orthogonal router
packages/react/           reusable circuit canvas
schema/                   checked-in shared JSON Schema
```

## Development and verification

From `circuit-designer/`:

```bash
# Verify generated schema-derived TypeScript files
npm run generate:check

# Run all workspace unit tests
npm test

# Build all applications and packages
npm run build

# Run browser interaction tests
npm run test:e2e
```

Run only the standalone package:

```bash
npm run test --workspace @spec2gds/circuit-designer-standalone
npm run build --workspace @spec2gds/circuit-designer-standalone
```

In WSL, use `TMPDIR=/tmp` if a Node tool inherits an inaccessible Windows
temporary directory:

```bash
TMPDIR=/tmp npm test
```

Playwright requires Chromium and its Linux runtime libraries. A missing library
such as `libnspr4.so` prevents the browser from starting before any application
test executes.

## Standalone versus SpecIR integration

The standalone app is the primary place to diagnose canvas and routing issues:

- if a problem reproduces here, inspect core, layout, local-client, React, or
  standalone code;
- if it occurs only with a `.spec` package, inspect the optional HTTP and Python
  projection/persistence adapters.

The optional SpecIR integration harness is a separate application and is
started with `npm run dev:specir`. It does not change the standalone dependency
boundary.

For additional design notes, see
[`docs/circuit_designer_standalone.md`](../../../docs/circuit_designer_standalone.md).

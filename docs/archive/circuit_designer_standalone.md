# Historical: Standalone Circuit Designer

## Purpose

The standalone application isolates the React circuit stack from SpecIR and
the spec editor. It is the default environment for developing and diagnosing
canvas, routing, selection, and mutation behavior.

If a problem reproduces here, it belongs to the circuit contract, local command
engine, grid layout/router, React canvas, or workbench UI. If it occurs only in the
optional SpecIR harness, investigate the HTTP projection and Python source
adapter instead.

## Dependency boundary

```text
apps/standalone
  -> packages/client-local
  -> packages/core
  -> packages/layout
  -> packages/react

No dependency on:
  Python / FastAPI / SpecIR / IP-XACT / .spec packages
```

The local client implements the same `CircuitDesignerApi` consumed by remote
clients. It provides revision-guarded commands, exclusive human/agent leases,
preview/apply, undo/redo, proposals, reset, and graph export entirely in memory.

## Run

Node.js 24 is the supported runtime.

```bash
cd circuit-designer
npm install
npm run dev
```

Open `http://127.0.0.1:4180`.

The independent app contains five examples:

- processor subsystem with interface and interrupt nets;
- producer/consumer datapath;
- multi-endpoint broadcast fanout;
- cyclic feedback pipeline;
- two independent nets that cross without forming an electrical junction.

Edits remain in the current browser tab. Use **Export JSON** to save the
renderer-neutral graph or **Reset** to restore the selected example.

## Minimal drawing workflow

The standalone lab intentionally permits incomplete, externally enrichable
objects:

1. Enter a name under **Draw component** to create a placeholder component and
   instance.
2. Select the component and create input, output, or bidirectional ports in the
   inspector.
3. Drag from one port handle to another to create an automatically named net,
   or use the endpoint selectors when an explicit name is useful.

Component origins snap to the visible 20-pixel grid. Creating or dragging a
component does not automatically pan or zoom the canvas. Existing geometry is
pinned before topology changes so it remains stable.

Every automatically routed terminal has a 20-pixel outward stub. The stub is
normal to the terminal side—left for inputs, right for outputs, and down for
bidirectional ports—before the route joins its orthogonal trunk. This prevents
a net from initially running along or overlapping the component edge.

There is no third-party graph-layout engine or layout worker. Initial placement
uses a small deterministic connectivity-layered grid placer. Final routing is
owned by one rectilinear router that sees the whole design at once. Component
rectangles and locked routes are obstacles; unlocked nets are routed together
with bend, proximity, overlap, and crossing costs. The router first searches
for a crossing-free path and uses a congestion-penalized fallback only when a
design is too dense to provide a free channel.

This separation is deliberate: block placement is optional convenience data,
while route quality depends on the block and port positions the user has fixed.
The normal workflow is to place or drag blocks, arrange ports, lock intentional
route corridors, and then choose **Reroute unlocked nets**.

## Canvas modes

The toolbar makes canvas intent explicit so gestures cannot accidentally move
both a circuit object and the viewport:

- **Select** selects and grid-drags components. Existing routes remain stable
  during the gesture; unlocked connected routes are recomputed atomically on drop.
- **Connect** exposes terminal handles for creating nets. Component dragging,
  route editing, and viewport navigation are disabled.
- **Route** edits saved orthogonal route geometry. Drag a segment perpendicular
  to its direction, drag a bend or junction, double-click a segment to insert a
  bend, double-click a bend to remove it, and Shift-click a route object to
  toggle its lock.
- **Pan** pans and zooms the viewport without changing circuit geometry. Hold
  Space to use this mode temporarily and press Escape to return to Select.

Route edits snap to the same 20-pixel grid as components. Endpoint stubs remain
normal to their component sides, zero-length and diagonal segments are rejected,
and route trees are validated against the net's semantic endpoint set. A dot is
drawn only for a degree-three-or-greater electrical junction. Geometric
crossings between independent nets do not receive a junction dot.

## Placement and routing controls

The selected component can be pinned or unpinned. For each selected terminal,
the inspector can choose NORTH, EAST, SOUTH, or WEST, change its order on that
side, lock the placement, or restore automatic placement. The component is
resized when necessary and affected nets are rerouted atomically.

**Reroute unlocked nets** changes only route geometry; component placement is kept
fixed and locked route segments/vertices are preserved. The selected-net tools
can optimize, reset, lock/unlock all geometry, or reset an individual route
branch. A selected block can optimize only its connected nets, while the layout
panel can optimize every net. **Arrange unpinned blocks** is intentionally
separate: the deterministic grid placer may move unpinned components, preserves
pinned component geometry, and then creates fresh orthogonal routes.

The persisted model keeps semantic connectivity (`nets` and terminal endpoint
IDs) separate from optional presentation geometry (`net_routes`). Stable route
vertex/segment IDs and lock flags are part of the common command contract, so
human UI operations and programmatic/agent operations use the same API.

The shared command protocol includes `add_terminal` and `delete_terminal`.
They are implemented by the local adapter. The current SpecIR adapter returns
an explicit unsupported-profile diagnostic rather than pretending to persist
them into IP-XACT.

## Optional SpecIR integration harness

The old mixed-source workbench is retained only as an explicit integration
harness:

```bash
# Terminal 1
uv run spec2gds-server

# Terminal 2
cd circuit-designer
npm run dev:specir
```

Open `http://127.0.0.1:4173`. The spec editor itself remains at
`http://127.0.0.1:8000/editor` and contains no Circuit Designer controls or
static mount.

## Verification

```bash
cd circuit-designer
npm run generate:check
npm test
npm run build
```

Python API regression tests continue to verify that removing the embedded UI
does not change the spec editor behavior.

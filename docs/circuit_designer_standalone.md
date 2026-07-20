# Standalone Circuit Designer

## Purpose

The standalone application isolates the React/ELK circuit stack from SpecIR and
the spec editor. It is the default environment for developing and diagnosing
canvas, routing, selection, and mutation behavior.

If a problem reproduces here, it belongs to the circuit contract, local command
engine, ELK adapter, React canvas, or workbench UI. If it occurs only in the
optional SpecIR harness, investigate the HTTP projection and Python source
adapter instead.

## Dependency boundary

```text
apps/standalone
  -> packages/client-local
  -> packages/core
  -> packages/layout-elk
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

The independent app contains four examples:

- processor subsystem with interface and interrupt nets;
- producer/consumer datapath;
- multi-endpoint broadcast fanout;
- cyclic feedback pipeline.

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
pinned before topology changes so ELK cannot rearrange already placed blocks.

Every automatically routed terminal has a 24-pixel outward stub. The stub is
normal to the terminal side—left for inputs, right for outputs, and down for
bidirectional ports—before the route joins its orthogonal trunk. This prevents
a net from initially running along or overlapping the component edge.

ELK is used for component ordering and placement, not as the final electrical
net router. ELK emits separate edge sections for the pairwise edges used during
layering; merging those sections into a multi-endpoint circuit net produces
hairpins, reverse segments, and visually duplicated trunks. The circuit router
therefore builds one deterministic route tree per semantic net after ELK has
placed the blocks. Fanout endpoints share one trunk and explicit junctions.

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

# Circuit Designer timing stages

Circuit Designer can divide a design into left-to-right pipeline stages with
vertical **cycle edges**. A path in the same clock domain gains exactly one
cycle for every marker between its source and destination. Edge polarity is
not part of the model or user interface.

The feature starts with one implicit clock domain named `clk`. Components and
design boundaries belong to that domain automatically, so ordinary
single-clock designs need no clock setup or per-object badges. **Timing →
Clock settings** can bind `clk` to a boundary terminal or net. Its Advanced
section can define additional domains and assign the selected component or
boundary when a genuine multi-clock design needs that escape hatch. A path
between different domains is reported as CDC rather than receiving a cycle
count; the stage markers themselves remain global.

## Place and edit markers

Begin an edit draft, then choose **Timing → Add cycle edge** and click empty
canvas. The point snaps to the circuit grid. Empty-canvas context menus expose
the same command and use the clicked position directly. A marker cannot split
a component or boundary terminal.

Select a marker to drag it horizontally. Arrow Left/Right moves it by one grid
step and Shift moves five steps. **Timing**, the marker context menu, and the
Inspector expose Edit, Lock/Unlock, and Delete. Editing changes its coordinate,
optional edge label, and the name of the stage that follows it. The region
before the first marker is Stage 0 by default. Locking protects a marker from
dragging and keyboard movement.

**View → Timing overlay** hides or shows markers and latency labels without
removing timing data. The preference is part of the shared Circuit Designer
profile.

## Placement and automatic layout

Every component must be fully contained in one stage. A direct drag may move a
component to another stage, but a drop that leaves it across an edge is
rejected. Automatic layout preserves each component's existing stage. It may
move unlocked markers rightward to make a stage wide enough; a locked marker
that prevents expansion produces an actionable error. The layout and any
marker movement are one Undo step.

**Timing → Timing analysis** lists directed paths, source and destination
stages, cycle counts, CDCs, backward paths, and paths whose geometry is not
available. Cycle labels are also placed on visible routes.

## Save, source synchronization, and export

Independent circuit files store timing in the optional `timing` member of the
version-1 Circuit document. Existing files without it behave as a one-domain,
zero-marker design and need no migration.

For a specification-owned circuit, **Save to Specification** persists a
source-semantic `DesignCircuitTimingV1` annotation under
`annotations/circuit-timing/<design-id>.json`. Instance, boundary, and net
references use IP-XACT names rather than generated Circuit IDs. The namespace
is `spec2gds.circuit-timing`; annotation ownership, clock and subject
references, finite unique marker positions, and a 2 MiB payload limit are
validated with the rest of the atomic package transaction.

SVG and PNG downloads include full-height markers, stage names, and path cycle
labels. The Specification Editor's derived SVG preview uses the same exporter,
so saved timing appears in the card, expanded view, downloaded SVG, and print
output without storing an image in the `.spec` package. HDL and SystemC
generators are unchanged: timing stages are design metadata, not inferred RTL
behavior.

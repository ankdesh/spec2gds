# Circuit Designer interactions

Circuit Designer uses one direct-manipulation canvas. There are no separate
Select, Connect, Route, or Pan modes. The action bar exposes the same operations
for users who prefer visible commands over mouse or keyboard gestures.

## Action bar

- **Selection** selects every circuit item, clears the selection, or centers the
  viewport on the current selection.
- **Connect…** creates a new two-terminal net. It supports an optional label and
  explicit bus-slice LSB and width; width `0` means the complete terminal.
- **Route** reroutes, locks, or unlocks the selected net, or arranges and routes
  the complete circuit.
- **View** pans in four directions, zooms, centers the selection, or fits the
  complete circuit.

Selection and View remain available for source-owned and locked documents.
Connect and route-changing commands require an unlocked private draft.

## Canvas gestures

| Input | Result |
| --- | --- |
| Click an instance, boundary terminal, or net | Select it |
| Shift/Ctrl/Command-click | Add or toggle selection |
| Drag empty canvas | Select every partially intersecting item |
| Drag a selected instance | Move the selected instances on the grid |
| Arrow / Shift+Arrow | Move selected instances 1 / 10 grid steps |
| Drag one free terminal to another | Create a full-terminal net |
| Select a net, then drag its route | Move an unlocked segment, bend, or junction |
| Double-click a segment or bend | Insert or remove a valid bend |
| Mouse wheel or pinch | Zoom around the pointer |
| Middle-drag or Space+left-drag | Pan |
| Escape | Cancel a keyboard connection, otherwise clear selection |

Ports already used by a net are visibly disabled. Canvas connection gestures
create new two-terminal nets only; extending a fanout, dropping onto a wire,
and merging existing nets are not currently supported. Use **Connect…** for an
explicit bus slice because port-to-port dragging always connects whole ports.

## Route editing

Manual route handles appear only when exactly one net is selected. Locked route
parts remain visible but cannot be dragged. Use the Route action menu to lock or
unlock the complete selected route. Rerouting is disabled until a locked route
is unlocked.

All movement and manual route edits snap to the circuit's grid. Changes remain
in the private draft until **Save**; **Cancel** discards them.

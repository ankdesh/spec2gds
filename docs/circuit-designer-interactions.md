# Circuit Designer interactions

Circuit Designer uses one direct-manipulation canvas. There are no separate
Select, Connect, Route, or Pan modes. A compact traditional menubar exposes
every operation without reserving permanent canvas space.

Use **Edit → Preferences → Actions and shortcuts** to open the shared
configuration page. Every action has a keyboard and mouse binding. Changes are
debounced and saved through the Circuit service. Reusing an input moves it from
the previous action so two commands never compete for the same shortcut.
**Reset defaults** restores the current action contract.

## Menubar

- **File** owns document creation, opening, save/cancel, and JSON/SVG/PNG
  downloads.
- **Edit** owns edit leases, undo/redo, deletion, and preferences.
- **Components** opens the catalog, local-component and proposal dialogs, and
  the selected child design.
- **Selection**, **Connect**, **Route**, **Timing**, and **View** contain the former canvas
  action-strip commands. The View menu also toggles the properties-only
  Inspector, which defaults closed.
- **Tools** opens AI Assistant. **Help** contains Getting Started and About.

Menus use ARIA menu semantics. Arrow keys navigate menus and submenus, Home/End
move to boundaries, Enter or Space activates, Escape dismisses and restores
focus, and clicking elsewhere dismisses the open menu. Unavailable commands
remain visible and disabled. Configured keyboard shortcuts appear beside menu
commands.

Selection and View remain available for source-owned and locked documents.
Connect and route-changing commands require an unlocked private draft. A
writable source-bound design labels the ordinary save action **Save to
Specification** and shows it in the header while the draft is dirty.

SVG and PNG downloads are rendered from the same effective layout currently
shown by the canvas, including automatically computed instance and boundary
positions, terminal placement, route geometry, locked-route styling, and the
canvas color system. Cycle edges, stage labels, and computed path latency are
included when timing markers exist. PNG is rasterized directly from that SVG so both image
formats have identical bounds and content. Save or Cancel an active draft
before downloading an authoritative image.

## Canvas gestures

| Input | Result |
| --- | --- |
| Click an instance, boundary terminal, or net | Select it |
| Shift/Ctrl/Command-click | Add or toggle selection |
| Left-drag empty canvas | Pan without holding Space |
| Shift+left-drag empty canvas | Select every partially intersecting item |
| Drag a selected instance | Move the selected instances on the grid |
| Arrow / Shift+Arrow | Move selected instances 1 / 10 grid steps |
| Drag one free terminal to another | Create a full-terminal net |
| Select a net, then drag its route | Move an unlocked segment, bend, or junction |
| Double-click a segment or bend | Insert or remove a valid bend |
| Mouse wheel or pinch | Zoom around the pointer |
| Space+drag | Temporarily activate panning when a different pan mouse binding is configured |
| Right-click, Context Menu key, or Shift+F10 | Open the target-aware context menu |
| Escape | Cancel a keyboard connection, otherwise clear selection |

Use **Timing → Add cycle edge** to place a grid-snapped vertical stage
boundary. Markers can be selected, dragged, locked, renamed, and deleted, and
cannot bisect a component. See
[Circuit Designer timing stages](circuit-designer-timing-stages.md) for the
single-clock default, path analysis, and source persistence.

Ports already used by a net are visibly disabled. Canvas connection gestures
create new two-terminal nets only; extending a fanout, dropping onto a wire,
and merging existing nets are not currently supported. Use **Connect → New
connection** for an explicit bus slice because port-to-port dragging always
connects whole ports.

## Context menus

Right-click is reserved inside the Circuit Designer canvas and opens a menu at
the pointer. The browser context menu remains available outside the canvas.
Right-clicking an unselected component, boundary terminal, or net selects it;
right-clicking an already selected object preserves a multi-selection. Exact
ports, segments, bends, and junctions retain their specific menus.

Empty canvas exposes editing, creation, selection, Inspector, and fit commands.
Components and selections expose their existing center, open-child, clear, and
delete commands. Nets expose whole-route reroute and lock controls. A segment
can insert a grid-snapped bend at the pointer, and a structurally removable
unlocked bend can be removed.

Free ports open New connection with Endpoint A prefilled. Connected ports can
select their net or disconnect. Disconnecting a port from a two-endpoint net
requires confirmation because it deletes the whole net. The Placement submenu
sets the North/East/South/West side, reorders ports within an owner and side,
locks placement, or resets it to automatic. Boundary deletion is confirmed and
uses explicit connectivity cascade.

The Context Menu key and Shift+F10 use the focused semantic element, current
selection, or canvas center as the anchor. Context menus support the same arrow,
Home/End, Enter/Space, Escape, submenu, disabled, checked, and focus-restoration
behavior as the menubar. Menubar and context menus are mutually exclusive.
Right-drag panning remains assignable; moving beyond the drag threshold
suppresses the context menu released afterward.

## Route editing

Manual route handles appear only when exactly one net is selected. Locked route
parts remain visible but cannot be dragged. Use the Route menu to lock or
unlock the complete selected route. Rerouting is disabled until a locked route
is unlocked.

All movement and manual route edits snap to the circuit's grid. Independent
changes remain in the private draft until **File → Save changes**. A bound
design instead uses **File → Save to Specification**, which commits topology
and the displayed layout to the `.spec` source. **File → Cancel changes**
discards either kind of private draft.

## Default action bindings

| Action | Keyboard | Mouse |
| --- | --- | --- |
| New / Open / Save | Ctrl/Command+N / O / S | — |
| Undo / Redo | Ctrl/Command+Z / Shift+Ctrl/Command+Z | — |
| Delete selected | Delete | — |
| Select all | Ctrl/Command+A | — |
| Clear selection | Escape | — |
| Drag canvas | Space | Left drag |
| Zoom in / Zoom out | — | Wheel up / Wheel down |
| Center selection, New connection, route commands, directional pan, Fit circuit | — | — |

Actions without a shortcut remain available in the menubar. Empty-canvas
click, double-click, and middle-click shortcuts can be assigned to commands.
Right-click is reserved for context menus. Canvas dragging can still be
assigned to the left, middle, or right mouse button.

The same typed executor handles menubar activation, context-menu commands,
keyboard shortcuts, and assignable mouse commands. Context-only commands that
need a precise pointer target are intentionally absent from Actions and
shortcuts. See
[Circuit Designer preferences](circuit-designer-preferences.md) for profile
storage, validation, migration, and API details.

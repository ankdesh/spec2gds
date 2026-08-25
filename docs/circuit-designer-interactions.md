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
- **Selection**, **Connect**, **Route**, and **View** contain the former canvas
  action-strip commands. The View menu also toggles the properties-only
  Inspector, which defaults closed.
- **Tools** opens AI Assistant. **Help** contains Getting Started and About.

Menus use ARIA menu semantics. Arrow keys navigate menus and submenus, Home/End
move to boundaries, Enter or Space activates, Escape dismisses and restores
focus, and clicking elsewhere dismisses the open menu. Unavailable commands
remain visible and disabled. Configured keyboard shortcuts appear beside menu
commands.

Selection and View remain available for source-owned and locked documents.
Connect and route-changing commands require an unlocked private draft.

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
| Escape | Cancel a keyboard connection, otherwise clear selection |

Ports already used by a net are visibly disabled. Canvas connection gestures
create new two-terminal nets only; extending a fanout, dropping onto a wire,
and merging existing nets are not currently supported. Use **Connect → New
connection** for an explicit bus slice because port-to-port dragging always
connects whole ports.

## Route editing

Manual route handles appear only when exactly one net is selected. Locked route
parts remain visible but cannot be dragged. Use the Route menu to lock or
unlock the complete selected route. Rerouting is disabled until a locked route
is unlocked.

All movement and manual route edits snap to the circuit's grid. Changes remain
in the private draft until **File → Save changes**; **File → Cancel changes**
discards them.

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
click, double-click, middle-click, and right-click shortcuts can be assigned to
commands. Canvas dragging can be assigned to the left, middle, or right mouse
button.

The same centralized executor handles menu activation, keyboard shortcuts, and
assignable mouse commands. See
[Circuit Designer preferences](circuit-designer-preferences.md) for profile
storage, validation, migration, and API details.

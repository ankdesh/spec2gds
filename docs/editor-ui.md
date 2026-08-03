# Specification editor UI

The specification editor uses a sticky application bar so document operations
remain available while the unified specification scrolls. The active package
name appears in the bar; hover it to inspect the full server-local path.

## Application menus

- **File** creates or opens a server-local `.spec` package and refreshes the
  active path from disk. Accepted changes save automatically, so Save is shown
  as an informational disabled command. Use `Ctrl/Command+N` and
  `Ctrl/Command+O` for New and Open.
- **Edit** supports copying a selection from the rendered specification and
  selecting the complete document. Undo, Redo, and Find remain unavailable.
  Native Cut and Paste shortcuts work inside explicit edit fields; the menu
  commands remain disabled because there is no document-wide editable buffer.
- **Circuit** groups launchable entry designs, other designs, and components.
  Choosing an item projects it through the existing circuit adapter and opens
  Circuit Designer.
- **Help** contains getting-started guidance, keyboard shortcuts, the FastAPI
  reference, and the source-format identity.

Menus support arrow-key traversal, Home and End within a menu, Escape to close,
click-outside dismissal, and focus restoration. Dialogs trap keyboard focus
until they are dismissed.

## Section options

Every generated document section has a visible **Options** dropdown beside its
heading. Narrative subheadings and table captions do not receive this control.

- Designs and components provide **Open circuit**.
- The Components group provides **Add component** and the Designs group
  provides **Add design**. The name-only workflow uses
  `spec2gds.local:work:<name>:1.0`; new designs become entry designs.
- Component and design entities provide **Edit details** for display name,
  short description, and description. VLNV identity stays read-only.
- Leaf components provide **Add port**. The existing Ports table accepts a
  browser-only draft row and exposes Edit on existing wire ports. Port names
  stay fixed after creation.
- Every section shows disabled **Launch activity — Coming soon** so the planned
  workflow has a stable location without implying that it already runs.
- Entity-backed sections provide **More actions**, which opens the existing
  action and assistant workflow.

Overview contains only the disabled Launch activity placeholder. The Designs
and Components groups add their respective creation command. Protocol entities
keep More actions but do not offer circuit launch.

## Direct editing lifecycle

Only one inline editor can be active at a time. Save submits a typed operation
with the current source revision hash; the server constructs XML, validates the
candidate package, and saves it atomically. Cancel discards the local draft.
Validation failures leave the draft visible. If the source revision is stale,
the editor refreshes the hash and preserves entered values for review and
retry.

“Port” in this editor means an IP-XACT physical wire port. A new or edited port
has an `in`, `out`, or `inout` direction, optional left/right vector bounds,
and an optional description. Both vector bounds are required together.
Transactional ports and ports on components with internal designs are
read-only because their protocol or hierarchy boundaries require a broader
editing workflow.

## Deliberate boundaries

The generated document remains read-only outside explicit inline editors. This
phase does not add VLNV editing, entity deletion, port rename/delete,
transactional-port editing, bus-interface creation, composite-boundary editing,
undo history, Find, Save As, recent-file persistence, session closing, or
activity launching.

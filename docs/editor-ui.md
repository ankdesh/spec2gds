# Specification editor UI

The specification editor uses a sticky application bar so document operations
remain available while the unified specification scrolls. The active package
name appears in the bar; hover it to inspect the full server-local path.

## Application menus

- **File** creates or opens a server-local `.spec` package and refreshes the
  active path from disk. New collects a required human-readable specification
  name separately from the server path. Accepted changes save automatically,
  so Save is shown as an informational disabled command. Use `Ctrl/Command+N`
  and `Ctrl/Command+O` for New and Open.
- **Edit** supports copying a selection from the rendered specification and
  selecting the complete document. Undo, Redo, and Find remain unavailable.
  Native Cut and Paste shortcuts work inside explicit edit fields; the menu
  commands remain disabled because there is no document-wide editable buffer.
- **Circuit** groups launchable entry designs, other designs, and components.
  Choosing an item projects it through the existing circuit adapter and opens
  Circuit Designer. A leaf component opens as one read-only preview instance
  with its wire ports attached; a component with an internal design opens that
  design instead.
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
- Component and design entities provide **Edit text** for the paragraph shown
  directly between the entity heading and its structured definitions. VLNV,
  Vendor, Library, Name, and Version are kept in the source but omitted from
  the normal rendered document.
- Leaf components provide separate **Add wire port**, **Add transactional
  port**, and **Add structured port** commands. Each existing port is rendered
  as its own compact card and exposes Edit when supported. Port names and
  families stay fixed after creation.
- Every section shows disabled **Launch activity — Coming soon** so the planned
  workflow has a stable location without implying that it already runs.
- Entity-backed sections provide **More actions**, which opens the existing
  action and assistant workflow.

Overview contains only the disabled Launch activity placeholder. The Designs
and Components groups add their respective creation command. Protocol entities
keep More actions but do not offer circuit launch.

## Direct editing lifecycle

The human-readable specification name can be edited from the document cover.
It is persisted in `document/document.json` without changing the stable
`document_id` or any entity reference.

Only one inline editor can be active at a time. Save submits a typed operation
with the current source revision hash; the server constructs XML, validates the
candidate package, and saves it atomically. Cancel discards the local draft.
Validation failures leave the draft visible. If the source revision is stale,
the editor refreshes the hash and preserves entered values for review and
retry.

All port families have a required immutable Name plus optional Display name and
Description. Wire ports have an `in`, `out`, or `inout` direction and one
optional Range. Enter `left:right`, such as `DATA_WIDTH-1:0`; a single
expression stores identical left and right bounds, and an empty Range produces
a scalar wire port. Transactional ports have a `requires`, `provides`, or
`both` initiative, optional TLM Kind, optional custom-kind name, and optional
Bus width expression. Structured ports have a direction and are always packed
structs. The required `<port_name>_struct_t` IP-XACT type definition is created
and maintained internally rather than displayed.

The editable source profile is deliberately strict: it rejects multiple wire
dimensions, qualifiers, arrays, advanced wire/electrical fields, detailed TLM
protocol modeling, structured subports, unions, and interfaces. Ports on
components with internal designs remain read-only because changing a composite
boundary requires hierarchy synchronization.

## Deliberate boundaries

The generated document remains read-only outside explicit inline editors. This
phase does not add arbitrary IP-XACT import, VLNV editing, entity deletion,
port rename/delete, port-family conversion, bus-interface creation,
composite-boundary editing, detailed TLM modeling, structured subports, undo
history, Find, Save As, recent-file persistence, session closing, or activity
launching.

Circuit Designer remains a physical-wire view. A launch reports and omits
unused transactional and structured ports. If a design connection references a
non-wire port, launch fails with a precise validation error instead of silently
dropping the connection.

# Spec Editor UI

The Spec Editor uses a sticky application bar so document operations
remain available while the unified specification scrolls. The active package
name appears in the bar; hover it to inspect the full server-local path.
The upper-right **AI Assistant ↗** button uses the shared service registry. With
an active Spec it opens an Assistant chat with a permanent binding to the complete document. It may propose a new top-level component or
design, including initial instances. A new component proposal can include its
initial wire ports and module-body SystemVerilog behavior in the same atomic
create. The same document scope can refine existing supported entities. With no
specification open, the same button opens an
unbound Assistant chat without attaching source context or mutation tools.
Use a Component or Design's **More actions → Explore with AI Assistant** command for a
narrower Component or Design conversation. Each proposal reads fresh Spec service context.

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
  design as a writable source-bound circuit.
- **Help** contains getting-started guidance, keyboard shortcuts, the FastAPI
  reference, and the source-format identity.

Menus support arrow-key traversal, Home and End within a menu, Escape to close,
click-outside dismissal, and focus restoration. Dialogs trap keyboard focus
until they are dismissed.

## Derived circuit previews

Every entry, internal, and other design section places a static circuit preview
before its structured tables. The backend derives a Circuit Designer document
from the same immutable IP-XACT revision used for the tables; the browser then
uses the shared deterministic layout and SVG exporter. The preview is not an
asset in the `.spec` package and does not require the Circuit Designer service,
so it is regenerated automatically after an accepted edit, proposal, disk
refresh, or reopen and cannot become stale independently of the source.

The responsive preview is capped at 420 pixels high. **Expand** opens the same
SVG at its natural dimensions in a scrollable, focus-trapped dialog, while
**Download SVG** saves the exact displayed vector. **Open Circuit Designer**
uses the same validated projection and new-tab launch flow as **Options → Open
circuit**. Eligible designs can be changed there and explicitly saved back to
the specification. Printed documents expand the complete diagram and omit
these controls. The embedded SVG itself remains deliberately read-only.

Unused non-wire ports and interface connections that can be omitted safely are
listed below the diagram. If a connected endpoint or another source condition
cannot be projected without producing a misleading circuit, that design shows
a precise unavailable message instead. Empty designs show an explicit empty
state. In all cases, the design tables remain visible and authoritative.

## Section options

Every generated document section has a visible **Options** dropdown beside its
heading. Narrative subheadings and table captions do not receive this control.

- Designs and components provide **Open circuit**.
- The Components group provides **Add component** and the Designs group
  provides **Add design**. The name-only workflow uses
  `spec2gds.local:work:<name>:1.0`; new designs become entry designs.
- Component and design entities provide **Edit text** for the paragraph shown
  directly between the Component or Design heading and its structured definitions. VLNV,
  Vendor, Library, Name, and Version are kept in the source but omitted from
  the normal rendered document.
- Entry-design entities provide **Add component instance**. The inline form
  collects a unique instance name and selects from components defined at the
  specification’s top level. Saving appends the IP-XACT component instance to
  that design.
- Leaf components provide separate **Add wire port**, **Add transactional
  port**, and **Add structured port** commands. One Ports table contains every
  port as a row and exposes an Edit action per supported row. New-port drafts
  also appear inside this table. Port names and families stay fixed after
  creation.
- Components and designs provide **Add section → SystemVerilog** while their
  optional singleton is absent. Saved source appears inline with validation
  status, source diagnostics, CodeMirror editing, and confirmed deletion.
- Eligible Component and Design sections provide **Launch activity…** through **More actions**.
  The dialog checks Activity availability/preflight, then the Activity tab tracks
  queued/running/terminal jobs and their server-side output.
- Entity-backed sections provide **More actions**, which opens the existing
  action and assistant workflow.

Overview contains narrative content when present; internal document IDs, revision hashes, and entity counts
are intentionally omitted. The Designs and Components groups add their
respective creation command. Bus interfaces, their port maps and channels,
interface connections, and bus/abstraction protocol definitions remain in the
source package but are omitted from the editor document for now.

## Direct editing lifecycle

The human-readable specification name can be edited from the document cover.
It is persisted in `document/document.json` without changing the stable
`document_id` or any entity reference.

Only one inline editor can be active at a time. Save submits a typed operation
with the current source revision hash; the server constructs XML, validates the
candidate package, and saves it atomically. Cancel discards the local draft.
Validation failures leave the draft visible. If the source revision is stale,
the editor preserves entered values and their authored base revision. A retry
requires explicit source review; incoming changes never restamp a stale draft.

SystemVerilog drafts may be empty and are limited to 256 KiB. The server checks
portable module-body rules and runs Verilator 5.x in generated context when
available. Missing-tool and unsupported-profile results are saved as
`unverified`; blocking syntax and safety diagnostics leave the draft intact.

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
protocol modeling, structured subports, unions, and interfaces. Composite
boundaries are edited through the source-bound Circuit Designer, where
hierarchy references and semantic layout keys can be updated atomically.

## Deliberate boundaries

The generated document remains read-only outside explicit inline editors. The editor does not expose arbitrary IP-XACT import, VLNV editing, Component or Design deletion,
port rename/delete, port-family conversion, bus-interface creation,
composite-boundary editing, detailed TLM modeling, structured subports, undo
history, Find, Save As, recent-file persistence, session closing. Activity launching is available separately through
the Component or Design action dialog. Existing bus and protocol content is preserved when a package is
opened or edited even though it is not rendered in the editor.

Circuit Designer remains a physical-wire view. A launch reports and omits
unused transactional and structured ports. If a design connection references a
non-wire port, launch fails with a precise validation error instead of silently
dropping the connection.

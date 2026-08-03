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
  selecting the complete document. Undo, Redo, Cut, Paste, and Find remain
  visible but disabled because this phase does not provide an editable buffer
  or history model.
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
- Every section shows disabled **Launch activity — Coming soon** so the planned
  workflow has a stable location without implying that it already runs.
- Entity-backed sections provide **More actions**, which opens the existing
  action and assistant workflow.

Grouping sections such as Overview can therefore contain only the disabled
Launch activity placeholder. Protocol entities keep More actions but do not
offer circuit launch.

## Deliberate boundaries

The document remains a read-only projection of the validated `.spec` source.
This UI phase does not add direct text editing, undo history, Find, Save As,
recent-file persistence, session closing, or activity launching. Those features
require their own source and lifecycle contracts rather than placeholder data
mutations in the browser.

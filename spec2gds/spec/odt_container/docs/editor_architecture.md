# ODT Viewer/Editor Architecture

## Decision

Build the extended ODT viewer/editor as a local web application contained inside
the `spec2gds.spec.odt_container` package.

The first implementation should use a small, popular stack:

- Python backend: FastAPI with Pydantic models.
- Frontend: React, TypeScript, and Vite.
- Styling: plain CSS first.
- Browser tests: Playwright when UI flows become stable.
- Python tests: pytest through the existing `uv` environment.

Do not start with Electron. Keep the app easy to run and debug in a normal
browser first. If desktop packaging becomes important later, wrap the already
working web app instead of making packaging part of the first milestone.

## Why Not Browser-Only First

Browser-only TypeScript is attractive because it can become a static app and
keeps all file handling local to the user. It is still a valid future direction
for some parts of the viewer.

For this project, the first implementation should prefer a Python backend plus
a browser frontend because the problem is not only UI. The tool must parse,
validate, preserve, and rewrite ODT packages with embedded structured hardware
data. Keeping that document engine behind a typed local API gives us a clearer
place for package integrity checks, IP-XACT validation, export flows, and later
automation.

This decision is based on the problem shape, not on the fact that Python code
already exists.

## Dependency Policy

Keep package usage minimal and understandable.

Use popular frameworks for infrastructure:

- React for UI composition.
- Vite for frontend dev/build.
- FastAPI for local HTTP APIs.
- Pydantic for request and response contracts.

Avoid heavy editor frameworks in the first phase. Do not introduce Tiptap,
Lexical, ProseMirror, Slate, Electron, Tauri, or shadcn by default. Add one only
when a concrete feature proves that the custom code is becoming harder to
maintain than the dependency.

The first editor should be a simple semantic block editor owned by this package.
It should support headings, paragraphs, lists, section version selection, links,
and IP-XACT previews before attempting broad word-processor behavior.

## Package Boundary

All code for this tool should live below:

```text
spec2gds/spec/odt_container/
```

Recommended layout:

```text
spec2gds/spec/odt_container/
  api/              FastAPI app, route handlers, API schemas.
  editor_core/      ODT semantic model, section versions, serializers.
  editor_web/       React/Vite frontend source.
  docs/             Package-level design notes.
```

The repository root can remain a high-level umbrella for future `spec2gds`
components.

## First Milestone

Build a light editor, not a full word processor.

Implemented backend/core capabilities:

- Parse ODT `content.xml` into a semantic document model.
- Represent headings, paragraphs, list items, table placeholders, and links.
- Apply plain-text edits to headings, paragraphs, and list item paragraphs.
- Detect adjacent heading variants named `Title//version`.
- Persist active section choices in manifested editor metadata.
- Read embedded IP-XACT XML and render interface-focused summaries.
- Emit blocking diagnostics for malformed content, unresolved `spec://` links,
  malformed IP-XACT XML, missing IP-XACT component VLNV fields, and missing
  IP-XACT bus interfaces.
- Block save when diagnostics remain.
- Save an ODT while preserving custom files and manifest entries.
- Expose a small FastAPI app factory for local API use.

Implemented browser UI shell capabilities:

- Load an ODT snapshot by local path through the API.
- Render a semantic document view instead of exact page layout.
- Show one selected section version at a time.
- Provide controls for heading, paragraph, and list item text edits.
- Provide controls for active section version choices.
- Display interface-focused IP-XACT tables.
- Preview and save raw IP-XACT XML through backend diagnostics.

Remaining browser UI capabilities:

- Add local file picker/open-save ergonomics.
- Add browser-level build and interaction tests once Node/npm are available in
  the development environment.

Out of scope for the first milestone:

- Exact LibreOffice rendering fidelity.
- Full rich-text editing.
- Advanced table editing.
- In-browser-only operation.
- Electron or Tauri packaging.
- Multi-user collaboration.

## Section Versioning Rule

Versioned sections are identified by headings with a suffix:

```text
Section title//version
```

Only adjacent headings with the same base title and same heading level are one
version group. For example, these are variants of the same section:

```text
Cache behavior//v1
Cache behavior//v2
```

The UI should display the base title, `Cache behavior`, plus a version dropdown.
The underlying ODT can keep the explicit suffixes so the format remains simple
and inspectable.

## IP-XACT Scope

The first table renderer should focus on interfaces before registers:

- component identity and VLNV fields
- bus interfaces
- bus type references
- abstraction type references
- interface mode
- port maps where present

Full IP-XACT schema validation should remain a backend responsibility. The UI
should show diagnostics clearly and prevent saving when the current document has
known unresolved warnings or errors.

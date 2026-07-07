# agent-spec Viewer/Editor Architecture

## Decision

Build the extended agent-spec viewer/editor as a local web application contained
inside `spec2gds.agent_spec.document`, backed by the `.spec` archive services in
`spec2gds.agent_spec.package`.

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
validate, preserve, and rewrite agent-spec archives with embedded structured hardware
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

The editor should remain a semantic document editor owned by this package. It
should support headings, paragraphs, lists, section version selection, links,
tables, images, and IP-XACT previews before attempting broad word-processor
behavior.

## Package Boundary

All code for this tool should live below:

```text
spec2gds/agent_spec/document/
```

Recommended layout:

```text
spec2gds/agent_spec/
  api/              FastAPI app, route handlers, API schemas.
  document/         semantic model, section versions, serializers, web shell.
  package/          .spec archive mechanics and validation.
  plugins/          embedded payload handlers.
  docs/             Package-level design notes.
```

The old `spec2gds.spec` package is not an active compatibility path.

## Current Milestone

Build a light editor, not a full word processor.

Implemented backend/core capabilities:

- Parse agent-spec `content.xml` into a semantic document model.
- Represent headings, paragraphs, list items, read-only tables, read-only
  images, and links.
- Apply plain-text edits to headings, paragraphs, and list item paragraphs.
- Detect adjacent legacy heading variants named `Title//version`.
- Assign stable heading IDs and persist version/IP-XACT relations in
  `spec_data/agent-spec-editor/relations.json`.
- Read embedded IP-XACT XML and render interface-focused summaries.
- Emit blocking diagnostics for malformed content, unresolved `spec://` links,
  malformed IP-XACT XML, missing IP-XACT component VLNV fields, and missing
  IP-XACT bus interfaces.
- Block save when diagnostics remain.
- Save an agent-spec while preserving custom files and manifest entries.
- Expose a small FastAPI app factory for local API use.

Implemented browser UI shell capabilities:

- Load an agent-spec snapshot by local path through the API.
- Render a clean themed document view instead of exact page layout.
- Show one selected section version at a time.
- Provide inline controls for simple heading, paragraph, and list item text
  edits.
- Provide heading-local controls for active section version choices.
- Attach existing embedded IP-XACT files to headings and inspect them in a right
  drawer.
- Save document text, relation metadata, active versions, and optional raw
  IP-XACT XML edits through one explicit endpoint.

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

Legacy versioned sections can be identified by headings with a suffix:

```text
Section title//version
```

Only adjacent headings with the same base title and same heading level are one
version group. For example, these are variants of the same section:

```text
Cache behavior//v1
Cache behavior//v2
```

The UI displays the base title, `Cache behavior`, plus a heading-local version
menu. New phase 2 state is stored in `relations.json`; the suffix form is a
migration path for existing documents and samples.

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

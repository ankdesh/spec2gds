# Agent-Spec Document Editor Architecture

This package-level note describes the current local document editor. The
project-level architecture is in `docs/agent_spec_architecture.md`.

## Current Shape

The editor is a local web application:

- Backend: FastAPI with Pydantic request/response models.
- Frontend: React, TypeScript, and Vite.
- Styling: plain CSS.
- Browser tests: Playwright smoke tests.
- Python tests: pytest through the repository `uv` environment.

All active editor code lives under:

```text
spec2gds/agent_spec/
  api/document_app.py
  document/
  document/editor_web/
  package/
  plugins/
```

`document_app.py` also mounts the action/run API from `api/app.py` at
`/agent-spec`.

## Backend Responsibilities

`EditorSession` in `document/session.py` is the editor facade around
`AgentSpecArchive`.

Implemented backend/core capabilities:

- Load and save `.spec` packages while preserving `spec_data/` custom files.
- Parse `content.xml` into a semantic document model.
- Represent headings, paragraphs, list items, read-only tables, read-only
  images, and links.
- Assign stable heading `xml:id` values when missing.
- Apply plain-text edits to simple headings, paragraphs, and list item
  paragraphs.
- Project section-version groups from explicit editor relation metadata.
- Persist section-version and IP-XACT relation metadata in
  `spec_data/agent-spec-editor/relations.json`.
- Read embedded IP-XACT XML from `spec_data/ipxact/` and render
  interface-focused summaries.
- Report diagnostics for malformed content, unresolved `spec://` links,
  malformed IP-XACT XML, missing component VLNV fields, missing bus interfaces,
  and missing attachment files.
- Block save when blocking diagnostics remain.
- Expose local API endpoints for snapshots, saves, text edits, active section
  choices, IP-XACT preview/editing, image assets, and file browsing.

## Frontend Responsibilities

The React editor currently:

- Browses directories and opens checked-in/generated `.spec` documents.
- Renders a clean document view rather than exact office page layout.
- Shows one selected section version at a time.
- Provides inline controls for simple text edits.
- Provides heading-local controls for section version choices.
- Attaches embedded IP-XACT files to headings.
- Shows IP-XACT component identity, bus interfaces, mode, bus type, abstraction
  type, port maps, diagnostics, and optional raw XML editing in a right drawer.
- Saves text edits, relation metadata, active versions, and IP-XACT XML edits
  through one explicit save flow.
- Shows action controls backed by the mounted `/agent-spec` API.

## Section Versioning Rule

Versioned sections are identified by relation metadata stored in
`spec_data/agent-spec-editor/relations.json`.

The relation group names the user-facing section title, lists the heading IDs
for each variant, and stores the active version choice. The visible heading text
is not parsed for version metadata.

## Editing Scope

The editor is intentionally not a full word processor.

Supported editable blocks:

- simple headings
- simple paragraphs
- simple list item paragraphs

Read-only in the current editor:

- blocks with inline markup, including links or mixed spans
- tables
- images
- broad rich-text formatting

This avoids silently dropping office markup during simple text edits.

## Out Of Scope Today

- exact LibreOffice rendering fidelity
- full rich-text editing
- advanced table editing
- in-browser-only operation
- Electron or Tauri packaging
- multi-user collaboration

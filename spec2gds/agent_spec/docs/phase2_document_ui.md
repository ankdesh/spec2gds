# Document UI Notes

The current editor is a document-first web UI. It runs as a local FastAPI
backend with a React/Vite frontend, and custom agent-spec behavior lives beside
headings instead of only in global side panels.

## Relation Metadata

The editor stores global UI relations at:

```text
spec_data/agent-spec-editor/relations.json
```

The metadata contains:

- `version`: relation schema version, currently `2`.
- `section_groups`: version groups with stable heading IDs, variant labels, and
  active version choices.
- `ipxact_attachments`: a map from heading ID to one or more embedded
  `spec_data/ipxact/*.xml` files.

Section-version groups are read from relation metadata. Heading text is treated
as user-visible prose, so strings such as `Register behavior//v1` are not parsed
as variant metadata. On explicit Save, the relation file is written into the
`.spec` archive.

## Rendering Behavior

The phase 2 renderer favors a clean editor theme over exact LibreOffice page
fidelity. It renders headings, paragraphs, lists, links, tables, and images when
they are present in `content.xml`.

Simple text blocks are editable inline. Blocks with inline markup, such as
links or mixed spans, are read-only in this phase so editing does not silently
drop agent-spec markup. Tables and images are also read-only.

## Heading Widgets

Heading controls are contextual:

- A small chevron appears next to headings that belong to a version group.
- Choosing a version changes the frontend draft immediately.
- An attachment icon opens a compact list of embedded IP-XACT files.
- A right drawer shows IP-XACT component identity, bus interfaces, mode, bus
  type, abstraction type, port maps, diagnostics, and optional raw XML editing.

The UI never exposes raw relation JSON to normal users.

## Save Model

The editor uses explicit Save. Text edits, active section choices, attachment
changes, relation metadata, and raw IP-XACT XML replacements are sent together
to `/documents/save`.

The backend validates blocking diagnostics before writing the `.spec` package.
Office compatibility is preserved by keeping all version sections as normal
document content; the custom editor decides which variant is visible.

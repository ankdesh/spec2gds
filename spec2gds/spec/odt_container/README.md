# ODT Container Spec

This package implements the ODT-based "spec for agent" container for the
`spec2gds` project. It is not the full spec-to-GDS pipeline. Instead, it is the
front-end specification carrier that lets humans edit a normal `.odt` document
while agents and downstream tools read structured hardware specification data
embedded inside that document.

The container is intended to become the shared source of truth for later stages
of the pipeline, such as spec parsing, design generation, verification planning,
RTL generation, and eventual layout/GDS-oriented flows.

## What This Module Provides

- A hybrid ODT package that remains editable in tools such as LibreOffice Writer.
- A `spec_data/` area inside the ODT ZIP archive for machine-readable payloads.
- Manifest registration for embedded payloads so office editors preserve them.
- ODF-compatible ZIP post-processing, including the required uncompressed first
  `mimetype` entry.
- A plugin system for structured spec modalities.
- `spec://` URI resolution for linking prose in the ODT document to embedded
  structured spec nodes.
- A verifier that checks embedded file validity and link consistency.
- A small CLI for listing plugins, injecting payloads, extracting payloads, and
  validating a container.

## Package Layout

```text
spec2gds/spec/odt_container/
  container.py       Core ODT ZIP/package wrapper.
  plugin.py          Modality plugin protocol and config schema.
  manager.py         Plugin registry, payload routing, and spec:// URI resolver.
  json_plugin.py     Simple JSON hardware metadata plugin.
  ipxact_plugin.py   IP-XACT XML plugin using pyEDAA.IPXACT.
  verifier.py        Embedded file and spec:// link consistency checker.
  cli.py             Headless command-line interface.
  api/               Local FastAPI app factory for the planned editor.
  editor_core/       Semantic ODT editor model and v1 save gate.
  editor_web/        Minimal React/Vite frontend shell.
  samples/           Rebuildable sample ODT and hybrid ODT test documents.
  docs/              Package-level design notes and decision records.
```

Future viewer/editor code for this ODT tool should also stay under this package
so the top-level `spec2gds` project can grow other components independently.

## Current Modalities

### `simple-json`

Embeds a constrained JSON metadata payload under:

```text
spec_data/simple-json/<file>.json
```

The current schema expects:

- `title`: non-empty string
- `version`: non-empty string
- `metadata`: list of `{name, value, description?}` items

Example URI:

```text
spec://simple-json/dma.json/metadata/1/value
```

### `ipxact`

Embeds IP-XACT XML under:

```text
spec_data/ipxact/<file>.xml
```

The plugin validates XML with `pyEDAA.IPXACT` and supports both logical object
attribute traversal and XPath fallback.

Example URIs:

```text
spec://ipxact/core.xml/VLNV/Vendor
spec://ipxact/core.xml//ipxact:description
```

## Setup

This project uses `uv.lock` and requires Python 3.12 or newer.

If `uv` is already installed:

```bash
uv sync
```

If this environment cannot write to the default uv cache locations, keep uv
state local to the repository:

```bash
UV_CACHE_DIR="$PWD/.uv-cache" \
UV_PYTHON_INSTALL_DIR="$PWD/.uv-python" \
uv sync
```

If `uv` is not installed but Python/pip is available, a workspace-local
bootstrap install can be used:

```bash
python3 -m pip install --target .uv-bootstrap uv

UV_CACHE_DIR="$PWD/.uv-cache" \
UV_PYTHON_INSTALL_DIR="$PWD/.uv-python" \
.uv-bootstrap/bin/uv sync
```

The planned web editor should keep Python environment management on `uv` and add
only a minimal Node/Vite frontend workspace inside `spec2gds/spec/odt_container/`.

Run the local editor API:

```bash
uv run python -m spec2gds.spec.odt_container.api
```

Run the frontend from another terminal after installing Node.js/npm:

```bash
cd spec2gds/spec/odt_container/editor_web
npm install
npm run dev
```

## Run Tests

Use the module form of pytest from the uv environment:

```bash
UV_CACHE_DIR="$PWD/.uv-cache" \
UV_PYTHON_INSTALL_DIR="$PWD/.uv-python" \
uv run python -m pytest -q
```

With the workspace-local bootstrap:

```bash
UV_CACHE_DIR="$PWD/.uv-cache" \
UV_PYTHON_INSTALL_DIR="$PWD/.uv-python" \
.uv-bootstrap/bin/uv run python -m pytest -q
```

The current test suite covers:

- ODT container creation, injection, extraction, deletion, and ZIP mimetype
  integrity.
- JSON plugin validation, injection, extraction, deep-copy behavior, and URI
  traversal.
- IP-XACT plugin registration, XML validation, extraction, logical traversal,
  and XPath fallback.
- CLI inject, extract, validate, and plugin listing flows.
- Verifier detection of valid and dangling `spec://` links.

At the time the v1 editor core was added, the package suite passed with:

```text
22 passed
```

## CLI Usage

The CLI module registers the default `simple-json` and `ipxact` plugins.

List supported plugins:

```bash
uv run python -m spec2gds.spec.odt_container.cli list-plugins
```

Inject JSON metadata into an ODT container:

```bash
uv run python -m spec2gds.spec.odt_container.cli inject \
  --container spec.odt \
  --modality simple-json \
  --file dma.json \
  --source dma.json
```

Extract JSON metadata:

```bash
uv run python -m spec2gds.spec.odt_container.cli extract \
  --container spec.odt \
  --modality simple-json \
  --file dma.json \
  --output extracted-dma.json
```

Inject IP-XACT XML:

```bash
uv run python -m spec2gds.spec.odt_container.cli inject \
  --container spec.odt \
  --modality ipxact \
  --file core.xml \
  --source core.xml
```

Validate an ODT container:

```bash
uv run python -m spec2gds.spec.odt_container.cli validate \
  --container spec.odt
```

The `validate` command emits a JSON report and exits with a non-zero status when
embedded files are invalid, missing from the manifest, or when `spec://` links in
`content.xml` cannot be resolved.

## Sample Documents

Sample ODT documents live under [`samples/`](samples/). Rebuild the raw/generated
sample corpus and embed the sample IP-XACT component with:

```bash
UV_CACHE_DIR="$PWD/.uv-cache" \
UV_PYTHON_INSTALL_DIR="$PWD/.uv-python" \
uv run python -m spec2gds.spec.odt_container.samples.build_sample_documents
```

Generated hybrid samples are written to:

```text
spec2gds/spec/odt_container/samples/generated/
```

## Design Notes

- All custom files must live under `spec_data/`.
- Each modality owns a subdirectory under `spec_data/<modality-id>/`.
- Plugins are responsible for validation, serialization, extraction, and node
  resolution.
- The core container does not know individual spec schemas.
- The ODT prose can contain hyperlinks with `spec://` targets, allowing visible
  documentation to point at exact structured spec values.
- Extracted payloads are deep-copied at API boundaries to avoid accidental
  mutation of cached container state.

## Planned Viewer/Editor Direction

The next major capability is a local web-based light editor for extended ODT
files. The current decision is documented in
[`docs/editor_architecture.md`](docs/editor_architecture.md).

Summary:

- Use a local Python backend plus a React/TypeScript frontend.
- Keep dependencies minimal and popular: FastAPI, Pydantic, React, Vite, pytest,
  and later Playwright for browser flows.
- Do not start with Electron, Tauri, or a heavy rich-text editor framework.
- Build a small semantic block editor first for headings, paragraphs, lists,
  section-version selection, links, and IP-XACT previews.
- Keep all code for this tool inside `spec2gds/spec/odt_container/`.

The first editor milestone should render ODT semantically, allow limited text
editing, support heading-based section versions such as `Title//v1`, preview
interface-focused IP-XACT tables, edit/import raw IP-XACT XML, and save only
when diagnostics are clean.

Implemented so far:

- `editor_core` parses `content.xml` into headings, paragraphs, list items,
  table placeholders, and links.
- Adjacent headings with the same title and level, written as `Title//version`,
  are grouped as section variants.
- Active section choices are stored as manifested JSON under
  `spec_data/odt-editor/`.
- Embedded IP-XACT XML can be summarized into interface-focused table data.
- The editor session blocks save while diagnostics remain.
- A minimal FastAPI app exposes snapshot, text edit, and active section version
  endpoints.
- A minimal React/Vite shell can load a local ODT path through the API, edit
  semantic text blocks, switch section versions, and display IP-XACT interface
  summaries.
- Raw IP-XACT XML can be previewed for diagnostics and imported only when the
  preview is clean.
- Synthetic tests cover semantic parsing, text edits, section version state,
  IP-XACT interface extraction, IP-XACT XML import gating, save blocking, and
  ODT save/reload.
- API tests cover the local snapshot, text edit, active section version,
  IP-XACT preview, and IP-XACT import route behavior over synthetic ODT files.
- Frontend scaffold tests keep the package scripts, source files, API calls, and
  minimal dependency policy visible to Python CI until Node/npm build checks are
  available in the development environment.

## Known Scope

This package is currently the specification container layer only. It does not yet
implement the downstream agent pipeline that consumes this spec to generate
design artifacts or GDS-related outputs.

The verifier is strongest for the JSON modality. IP-XACT support is present and
tested for direct plugin flows, but end-to-end verifier behavior should continue
to be expanded as the larger pipeline matures.

# spec2gds

`spec2gds` is an umbrella project for specification-driven hardware design
experiments and tooling.

The active implementation is an ODT-free V1 `.spec` workflow: deterministic
IP-XACT source packages, a typed narrative AST, immutable SpecIR snapshots,
entity-targeted action executions, sidecar artifacts, and reviewed proposals.

## Current Components

```text
spec2gds/agent_spec/
```

Key V1 pieces:

- deterministic custom ZIP `.spec` archive and IP-XACT 1685-2022 profile
- typed narrative AST, assets, explicit entry designs, and component composition
- Docling-based PDF, DOC/DOCX, and ODT import with optional table-to-IP-XACT
  extraction through the OpenAI Responses API
- immutable `SpecRevision` semantic queries and atomic edit transactions
- entity-targeted local action executions, content-addressed sidecar artifacts,
  provenance, and reviewed change proposals
- local V1 API and React/A2UI document editor at `/editor`

Start with the docs index:

- [`docs/README.md`](docs/README.md)
- [IP-XACT pivot plans](docs/pivot/README.md) for the approved replacement of
  the ODT-centered `.spec` architecture.

Most-used docs:

- [`docs/agent_spec_architecture.md`](docs/agent_spec_architecture.md)
- [`docs/development_methodology.md`](docs/development_methodology.md)
- [`docs/post_pivot_code_map.md`](docs/post_pivot_code_map.md)
- [`docs/spec_format_v1.md`](docs/spec_format_v1.md)
- [`docs/spec_ir_v1.md`](docs/spec_ir_v1.md)
- [`docs/spec_actions_v1.md`](docs/spec_actions_v1.md)
- [`docs/spec_editor_v1.md`](docs/spec_editor_v1.md)
- [`docs/spec_editor_a2ui_stage1.md`](docs/spec_editor_a2ui_stage1.md)
- [`docs/coding_guidelines.md`](docs/coding_guidelines.md) for uv usage,
  documentation expectations, and Python docstring/comment conventions
- [`docs/circuit_designer_phase0.md`](docs/circuit_designer_phase0.md) for the
  independent React circuit-designer foundation
- [`docs/circuit_designer_phase1.md`](docs/circuit_designer_phase1.md) for live
  read-only SpecIR integration
- [`docs/circuit_designer_standalone.md`](docs/circuit_designer_standalone.md)
  for the independent local app and its SpecIR isolation boundary
- [`docs/circuit_designer_complete.md`](docs/circuit_designer_complete.md) for
  the shared editing contracts and optional SpecIR adapter

## Circuit Designer

The circuit designer is a separate React workspace with its own examples
and an in-browser implementation of the common circuit API. Its default app has
no Python, FastAPI, SpecIR, IP-XACT, or `.spec` package dependency and does not
alter the spec editor interface.

```bash
cd circuit-designer
npm install
npm run generate:check
npm test
npm run dev
```

Open `http://127.0.0.1:4180`. The standalone lab supports bundled example
circuits, minimal component/port/net creation, grid-snapped local topology and
layout edits, explicit select/connect/route/pan modes, manual orthogonal route
editing and locks, port side/order controls, deterministic grid placement,
obstacle-aware rerouting, undo/redo, reset, and JSON export.
Node.js 24 is the supported runtime.

The optional SpecIR integration harness remains separate and is started only
when explicitly requested:

```bash
uv run spec2gds-server
cd circuit-designer
npm run dev:specir
```

Open `http://127.0.0.1:4173` and select **Active SpecIR session**. The optional
programmatic adapter is available under `/circuit-designer`; it is not linked
from or mounted into the spec editor.

## Development Setup

This is a Python project managed with `uv`.

Install dependencies:

```bash
uv sync
```

Install the optional document-import stack:

```bash
uv sync --extra document-import
```

Run tests:

```bash
uv run python -m pytest -q
```

For restricted environments, keep uv state local to the repository:

```bash
UV_CACHE_DIR="$PWD/.uv-cache" \
UV_PYTHON_INSTALL_DIR="$PWD/.uv-python" \
uv run python -m pytest -q
```

## Run the Server and UI Editor

Install/synchronize the environment once:

```bash
uv sync
```

Start the API server and bundled UI:

```bash
uv run spec2gds-server
```

The packaged, prebuilt React/A2UI editor is served by that same process; do not
start a second frontend service for normal use. Open:

```text
http://127.0.0.1:8000/editor
```

For UI-focused work, use the editor-oriented command. It starts the same API
and prints the editor URL:

```bash
uv run spec2gds-editor --reload
```

Both commands accept `--host`, `--port`, and `--reload` options:

```bash
uv run spec2gds-server --host 0.0.0.0 --port 8080 --reload
```

`AGENT_SPEC_HOST` and `AGENT_SPEC_PORT` remain supported as environment
defaults.

The module form remains supported:

```bash
uv run python -m spec2gds.agent_spec.api
```

See [`docs/spec_editor_v1.md`](docs/spec_editor_v1.md) for endpoints and the
editor/API interaction model.

For frontend development, use Node.js 24 and run the Vite app beside the API:

```bash
uv run spec2gds-server --reload
cd circuit-designer
npm install
npm run dev:editor
```

Open `http://127.0.0.1:4190`. Before committing frontend changes, rebuild the
Python-packaged assets with `npm run build:editor`. The Vite app proxies `/api`
to the local FastAPI server; its production bundle calls same-origin routes.

## V1 Source Package

The active `.spec` package stores canonical IP-XACT 1685-2022 source
documents, a typed narrative AST, and assets in a deterministic ZIP package.
The CLI intentionally rejects pre-pivot ODT containers.

```bash
uv run python -m spec2gds.agent_spec.spec_format.cli validate \
  --container spec2gds/agent_spec/spec_format/samples/generated/v1_demo.spec
uv run python -m pytest tests/agent_spec/spec_format -q
```

See [`docs/spec_format_v1.md`](docs/spec_format_v1.md) for the source layout,
CLI, and current V1.1 boundary, and [`docs/spec_ir_v1.md`](docs/spec_ir_v1.md)
for the V1.2 immutable SpecIR and atomic edit API. The full ordered
implementation roadmap is in [`docs/pivot/README.md`](docs/pivot/README.md).
V1.3's generic external-action, artifact, and reviewed-proposal layer is
documented in [`docs/spec_actions_v1.md`](docs/spec_actions_v1.md).

## Import PDF, Word, and OpenDocument Specifications

Install the import extra once, then run the dedicated utility:

```bash
uv sync --extra document-import
uv run spec2gds-import-document path/to/peripheral.odt
uv run spec2gds-import-document path/to/peripheral.docx -o peripheral.spec
uv run spec2gds-import-document path/to/peripheral.pdf -o peripheral.spec
```

The offline path converts Docling text, headings, lists, tables, and images into
the typed narrative document and retains the original file below
`annotations/document_import/`. To additionally turn explicitly supported
hardware table values into validated IP-XACT ports and bus interfaces:

```bash
export OPENAI_API_KEY="..."
uv run spec2gds-import-document path/to/peripheral.pdf \
  --openai \
  --vendor example.org \
  --library peripherals \
  --component-name timer
```

The default API model is `gpt-5.6-sol` and can be changed with `--model`.
Legacy binary `.doc` files require LibreOffice on the host. PDF processing
downloads Docling model artifacts on first use. See
[`docs/document_import.md`](docs/document_import.md) for the conversion
contract, hooks, options, provenance behavior, and limitations.

## Visual Verification Samples

The checked-in V1 demo contains leaf and composite components, an internal
design, two reusable entry designs, a narrative table and architecture image,
an entity link, and a live topology view. Start the API, open `/editor`, and
choose **V1 Demo** from the sample selector. The browser reads the validated
SpecIR projection as an A2UI v0.9 document. Stage 1 keeps document cells
read-only; actions and proposal review still use the V1 API.

The same selector exposes six **Hardware · ...** packages converted from real
APB, HPDcache, and CVFPU HTML/PDF specifications. They exercise larger
narratives, tables, formal ports, and bus-interface mappings.

Rebuild the deterministic sample after changing its builder:

```bash
uv run python -c "from pathlib import Path; from spec2gds.agent_spec.spec_format.samples import write_v1_sample; write_v1_sample(Path('spec2gds/agent_spec/spec_format/samples/generated/v1_demo.spec'))"
```

Rebuild the real-document benchmark after changing its converter:

```bash
uv run python -m benchmarks.agent_spec.hw_docs.build_benchmark
```

The original PDF/HTML, source IP-XACT, deterministic V1 packages, and benchmark
manifest live under
[`benchmarks/agent_spec/hw_docs/`](benchmarks/agent_spec/hw_docs/).

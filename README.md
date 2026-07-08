# spec2gds

`spec2gds` is an umbrella project for specification-driven hardware design
experiments and tooling.

The active implementation in this repository is `agent-spec`: a local workflow
for `.spec` hardware specification documents with embedded structured metadata,
IP-XACT payloads, action runs, generated artifact references, and editor
support.

## Current Components

```text
spec2gds/agent_spec/
```

Key pieces:

- `.spec` archive load/save and `spec_data/` preservation
- semantic document parsing for headings, paragraphs, lists, tables, images,
  links, and simple text edits
- section-version and IP-XACT attachment metadata
- FastAPI editor API plus mounted action/run API
- React/Vite local document editor
- block graph projection from document headings
- Pydantic action, run, artifact, and writeback contracts
- built-in pseudo SystemC actions for exercising the run/writeback flow
- package CLI for listing plugins, injecting/extracting payloads, and validating
  `.spec` files

Start with the docs index:

- [`docs/README.md`](docs/README.md)

Most-used docs:

- [`docs/agent_spec_architecture.md`](docs/agent_spec_architecture.md)
- [`docs/agent_spec_document_schema.md`](docs/agent_spec_document_schema.md)
- [`docs/agent_spec_v1_setup.md`](docs/agent_spec_v1_setup.md)
- [`docs/agent_spec_action_contract.md`](docs/agent_spec_action_contract.md)
- [`docs/agent_spec_vocabulary.md`](docs/agent_spec_vocabulary.md)
- [`docs/ipxact_protocol.md`](docs/ipxact_protocol.md)
- [`docs/coding_guidelines.md`](docs/coding_guidelines.md) for uv usage,
  documentation expectations, and Python docstring/comment conventions

## Development Setup

This is a Python project managed with `uv`.

Install dependencies:

```bash
uv sync
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

## Run The Local API

```bash
uv run python -m spec2gds.agent_spec.api
```

The API entry point starts the editor API and mounts the action/run API at
`/agent-spec`.

## Run The Editor UI Test

```bash
cd spec2gds/agent_spec/document/editor_web
npm install
npx playwright install chromium
npm run test:e2e
```

See [`docs/agent_spec_ui_testing.md`](docs/agent_spec_ui_testing.md) for
restricted-environment notes.

## Benchmarks

Hardware-document benchmarks live under
[`benchmarks/agent_spec/`](benchmarks/agent_spec/). The `hw_docs` benchmark
preserves PDF/HTML inputs, converted ODT/XML artifacts, and generated `.spec`
packages with embedded XML payloads.

Rebuild the benchmark:

```bash
PYTHONPATH=. UV_CACHE_DIR=.uv-cache uv run python -m benchmarks.agent_spec.hw_docs.build_benchmark
```

Run the benchmark test:

```bash
PYTHONPATH=. UV_CACHE_DIR=.uv-cache uv run python -m pytest tests/agent_spec/test_hw_docs_benchmark.py -q
```

See [`docs/agent_spec_benchmarks.md`](docs/agent_spec_benchmarks.md) for
details.

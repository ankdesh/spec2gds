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
- immutable `SpecRevision` semantic queries and atomic edit transactions
- entity-targeted local action executions, content-addressed sidecar artifacts,
  provenance, and reviewed change proposals
- local V1 API and editor shell at `/editor`

Start with the docs index:

- [`docs/README.md`](docs/README.md)
- [IP-XACT pivot plans](docs/pivot/README.md) for the approved replacement of
  the ODT-centered `.spec` architecture.

Most-used docs:

- [`docs/agent_spec_architecture.md`](docs/agent_spec_architecture.md)
- [`docs/mvc_architecture_assessment.md`](docs/mvc_architecture_assessment.md)
- [`docs/agent_spec_document_schema.md`](docs/agent_spec_document_schema.md)
- [`docs/agent_spec_action_execution.md`](docs/agent_spec_action_execution.md)
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

## Run The Local V1 API

```bash
uv run python -m spec2gds.agent_spec.api
```

The API entry point starts the ODT-free V1 editor/API. Open
`http://127.0.0.1:8000/editor` after startup. See
[`docs/spec_editor_v1.md`](docs/spec_editor_v1.md) for the entity-targeted API.

## New V1 Source Package Foundation

The replacement ODT-free `.spec` package is available alongside the legacy
editor/API path while the V1 cutover is implemented. It stores canonical
IP-XACT 1685-2022 source documents, a typed narrative AST, and assets in a
deterministic ZIP package. The new package CLI intentionally rejects legacy
ODT `.spec` containers.

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

## Archived Prototype CLI

The commands below belong to the pre-cutover ODT/heading prototype and are
retained only for historical investigation. They are not part of the production
V1 API or package format.

Print a detailed diagnostic report:

```bash
PYTHONPATH=. UV_CACHE_DIR=.uv-cache uv run python -m spec2gds.agent_spec.package.cli inspect \
  --container benchmarks/agent_spec/hw_docs/generated/apb_timer.spec \
  --format text
```

Write a conservative sanitized copy:

```bash
PYTHONPATH=. UV_CACHE_DIR=.uv-cache uv run python -m spec2gds.agent_spec.package.cli sanitize \
  --container broken.spec \
  --output repaired.spec
```

See [`docs/agent_spec_diagnostics.md`](docs/agent_spec_diagnostics.md) for the
full report contents and sanitization rules.

## Archived Prototype UI Test

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

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

- [`docs/post_pivot_code_map.md`](docs/post_pivot_code_map.md)
- [`docs/spec_format_v1.md`](docs/spec_format_v1.md)
- [`docs/spec_ir_v1.md`](docs/spec_ir_v1.md)
- [`docs/spec_actions_v1.md`](docs/spec_actions_v1.md)
- [`docs/spec_editor_v1.md`](docs/spec_editor_v1.md)
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

## Run the Server and UI Editor

Install/synchronize the environment once:

```bash
uv sync
```

Start the API server:

```bash
uv run spec2gds-server
```

The no-build UI editor is served by that same process. Open:

```text
http://127.0.0.1:8000/editor
```

`spec2gds-editor` is an equivalent convenience command when the editor is your
primary intent:

```bash
uv run spec2gds-editor
```

To bind another address or port:

```bash
AGENT_SPEC_HOST=0.0.0.0 AGENT_SPEC_PORT=8080 uv run spec2gds-server
```

The module form remains supported:

```bash
uv run python -m spec2gds.agent_spec.api
```

See [`docs/spec_editor_v1.md`](docs/spec_editor_v1.md) for endpoints and the
editor/API interaction model.

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

## Visual Verification Sample

The checked-in V1 demo contains leaf and composite components, an internal
design, two reusable entry designs, a narrative table and architecture image,
an entity link, and a live topology view. Start the API, open `/editor`, and
choose **V1 Demo** from the sample selector. The browser reads the validated
SpecIR snapshot and sends every edit or action back through the V1 API.

Rebuild the deterministic sample after changing its builder:

```bash
uv run python -c "from pathlib import Path; from spec2gds.agent_spec.spec_format.samples import write_v1_sample; write_v1_sample(Path('spec2gds/agent_spec/spec_format/samples/generated/v1_demo.spec'))"
```

Original PDF/HTML and converted IP-XACT benchmark inputs remain under
[`benchmarks/agent_spec/hw_docs/`](benchmarks/agent_spec/hw_docs/) as future
import-pipeline source material; they are not active V1 `.spec` fixtures.

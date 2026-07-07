# spec2gds

`spec2gds` is an umbrella project for specification-driven hardware design
experiments and tooling.

## Components

### Agent-Spec Architecture

`agent-spec` is the central `.spec` document architecture for converted
hardware specification documents, versioned sections/subsections, tags,
configurable Python actions, downstream pipeline runs, artifact references, and
reviewable writebacks.

The current plan is documented in:

- [`docs/agent_spec_architecture.md`](docs/agent_spec_architecture.md)
- [`docs/agent_spec_vocabulary.md`](docs/agent_spec_vocabulary.md)
- [`docs/agent_spec_action_contract.md`](docs/agent_spec_action_contract.md)
- [`docs/agent_spec_v1_setup.md`](docs/agent_spec_v1_setup.md)
- [`docs/agent_spec_roadmap_questions.md`](docs/agent_spec_roadmap_questions.md)

The first backend implementation lives in:

```text
spec2gds/agent_spec/
```

It provides the v1 Pydantic contracts, `.spec` metadata repository, Python
module plus YAML action registry, run coordinator, writeback records, pseudo
SystemC performance/bit-accurate actions, and the office-compatible `.spec`
archive/editor layer.

Run the local agent-spec API:

```bash
uv run python -m spec2gds.agent_spec.api
```

The active implementation is organized by responsibility:

```text
spec2gds/agent_spec/
  package/    .spec archive loading, saving, and validation
  document/   semantic document projection and local editor support
  plugins/    payload handlers such as JSON and IP-XACT
  storage/    graph, manifest, run, checkpoint, and artifact persistence
  actions/    action registry and built-in action providers
  runs/       run coordinator and writeback flow
  api/        FastAPI surfaces
  samples/    .spec sample documents and builders
```

The `.spec` archive is currently office-compatible internally, but the public
project extension and user-facing terminology are `.spec` and `agent-spec`.

## Development

This is currently a Python project managed with `uv` and a workspace-local
virtual environment.

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

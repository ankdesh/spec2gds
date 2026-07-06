# spec2gds

`spec2gds` is an umbrella project for specification-driven hardware design
experiments and tooling.

## Components

### Agent-Spec Architecture

The intended architecture is for `agent-spec` to become the central,
ODT-backed source of truth for converted hardware specification documents,
versioned sections/subsections, tags, configurable Python actions, downstream
pipeline runs, artifact references, and reviewable writebacks.

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

It provides the v1 Pydantic contracts, ODT-backed metadata repository, Python
module plus YAML action registry, run coordinator, writeback records, and pseudo
SystemC performance/bit-accurate actions.

Run the local agent-spec API:

```bash
uv run python -m spec2gds.agent_spec.api
```

### ODT Container

The current implemented component is the extended ODT container tool in:

```text
spec2gds/spec/odt_container/
```

It provides a Python API and CLI for embedding structured hardware data inside
ODT files, including custom `spec_data/` artifacts, `spec://` links, IP-XACT
artifact support, and container validation.

See [`spec2gds/spec/odt_container/README.md`](spec2gds/spec/odt_container/README.md)
for setup, tests, CLI usage, and the planned local web viewer/editor direction.

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

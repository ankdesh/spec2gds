# spec2gds

`spec2gds` is an umbrella project for specification-driven hardware design
experiments and tooling.

## Components

### ODT Container

The current implemented component is the extended ODT container tool in:

```text
spec2gds/spec/odt_container/
```

It provides a Python API and CLI for embedding structured hardware data inside
ODT files, including custom `spec_data/` payloads, `spec://` links, IP-XACT
payload support, and container validation.

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

# Agent-Spec V1 Setup

This document captures the current v1 setup: how to install, run, test, and
orient around the implemented local `.spec` workflow.

## Environment

This is a Python project managed with `uv`.

```bash
uv sync
```

For restricted or shared environments, keep caches inside the repository:

```bash
UV_CACHE_DIR="$PWD/.uv-cache" \
UV_PYTHON_INSTALL_DIR="$PWD/.uv-python" \
uv sync
```

## Run The Local API

The API entry point starts the editor API and mounts the action API at
`/agent-spec`:

```bash
uv run python -m spec2gds.agent_spec.api
```

Implementation entry points:

- `spec2gds/agent_spec/api/document_app.py`
- `spec2gds/agent_spec/api/app.py`
- `spec2gds/agent_spec/api/__main__.py`

## Run Tests

Run the Python test suite:

```bash
uv run python -m pytest -q
```

Run focused v1 tests:

```bash
uv run python -m pytest tests/agent_spec/test_v1_setup.py -q
```

Run package/editor tests:

```bash
uv run python -m pytest tests/agent_spec/package -q
```

## Run The Editor UI Smoke Test

```bash
cd spec2gds/agent_spec/document/editor_web
npm install
npx playwright install chromium
npm run test:e2e
```

Restricted-environment notes live in
[`agent_spec_ui_testing.md`](agent_spec_ui_testing.md).

## Current V1 Decisions

| Area | Current decision |
| --- | --- |
| Document artifact | `.spec` is the active document package extension. |
| Package format | `.spec` remains office-compatible internally and stores project metadata under `spec_data/`. |
| Server mode | Local single-user. There is one active document session in the action API. |
| Authentication | None in v1. User identity defaults to `local` or comes from request/config. |
| Write ownership | The API assumes the server owns writes while a document session is open. Saving is rejected if the file changed externally. |
| Editor model | The editor uses a semantic projection of `content.xml`, not full word-processor fidelity. |
| Editable content | Simple headings, paragraphs, and list item paragraphs are editable. Inline-markup blocks, tables, and images are read-only. |
| Section variants | Adjacent legacy headings named `Title//version` are projected into section version groups. |
| IP-XACT | Embedded XML under `spec_data/ipxact/` can be attached to headings and previewed through lightweight summaries. |
| Block model | Every heading becomes an action graph block. |
| Block version | A version hashes the heading section content plus attached artifact IDs. |
| Tags | Supported v1 tags are `systemc-perf`, `systemc-bitaccurate`, `rtl`, `ip`, `interface`, and `configuration`. |
| Action registration | Built-in Python actions are registered in-process; optional module/config loading exists. |
| Action execution | Runs execute synchronously in-process. |
| Run states | `queued`, `running`, `completed`, and `failed`. |
| Events | Run audit events are kept in memory for the session and persisted per run in `events.ndjson`. |
| Large outputs | Current pseudo outputs are sidecar files referenced by artifact metadata. |
| Writeback | Valid artifact metadata auto-attaches to a block. Invalid output records `needs_human_feedback`. |
| Source prose updates | Actions do not directly update source prose. |

## Metadata Paths

```text
spec_data/agent-spec/
  manifest.json
  graph.json
  versions/<block_id>/<version_id>.json
  artifacts/<artifact_id>.json
  runs/<run_id>/input_snapshot.json
  runs/<run_id>/run.json
  runs/<run_id>/events.ndjson
  writebacks/<writeback_id>.json
  checkpoints/<checkpoint_id>.json

spec_data/agent-spec-editor/
  relations.json
  active_section_versions.json
```

The sidecar directory defaults to:

```text
<document>.agent-spec-sidecar/
```

## Pseudo Action Demo

1. Start the local API.
2. Open a `.spec` document through `POST /agent-spec/documents/open` or through
   the web editor.
3. Add `systemc-perf` or `systemc-bitaccurate` to a heading block.
4. Fetch available actions for that block.
5. Trigger `systemc.perf.pseudo` or `systemc.bitaccurate.pseudo`.
6. The runner captures the active block version and parameters in an immutable
   input snapshot.
7. The action writes a fixed text output to the sidecar.
8. The runner validates artifact metadata, appends an attachment, writes the
   run/writeback/checkpoint metadata, and saves the `.spec` package.

## Current Test Coverage

The tests cover:

- `.spec` archive load/save and custom file preservation
- CLI plugin list/inject/extract/validate behavior
- JSON and IP-XACT plugin behavior
- sample document generation
- editor snapshots, text edits, relation metadata, and IP-XACT summaries
- block projection and version persistence
- tag validation and action discovery
- immutable run snapshots
- pseudo SystemC action success paths
- artifact sanity checks and `needs_human_feedback`
- rerun attachment append behavior
- run events, run records, writebacks, checkpoints, and reload behavior
- server-owned write guard behavior

## Not Implemented In V1

- general Word, PDF, Markdown, SystemRDL, CSV, or table import adapters
- remote workers or distributed queues
- browser live event streaming
- multi-user editing
- authentication
- rich-text editing
- action-driven source prose updates
- real SystemC, RTL, UVM, or synthesis generators

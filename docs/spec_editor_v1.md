# V1 Local API and Editor

The production local server is the IP-XACT-centered V1 surface. Synchronize the
environment and start it from the repository root:

```bash
uv sync
uv run spec2gds-server
```

The browser editor is a prebuilt React application using the A2UI v0.9
renderer. It needs no separate frontend process for normal use because its
compiled assets are served by the API process. Open
`http://127.0.0.1:8000/editor`. Do not run both public commands at once because
they bind the same service and port.

For editor development, use the editor-oriented command. It prints the browser
URL, and `--reload` restarts the process after Python changes:

```bash
uv run spec2gds-editor --reload
```

Choose the checked-in **V1 Demo** sample to visually inspect components,
design reuse, typed narrative content, action executions, artifacts, proposals,
and diagnostics. In a source checkout, the package selector also discovers the
generated hardware-document and simple-SystemC benchmark packages. Rebuild a
benchmark and refresh the editor page to update the selector.

Stage 1 presents source data as a unified read-only document. The API remains
the authoritative surface for actions and proposal review.

For frontend source changes, run the Vite development app in a second terminal:

```bash
cd circuit-designer
npm install
npm run dev:editor
```

It opens on `http://127.0.0.1:4190` and proxies `/api` to port 8000. Rebuild the
assets served by FastAPI after a UI change:

```bash
cd circuit-designer
npm run build:editor
```

Override the default local bind address with command-line options:

```bash
uv run spec2gds-server --host 0.0.0.0 --port 8080
```

The `AGENT_SPEC_HOST` and `AGENT_SPEC_PORT` environment variables remain
available as defaults when the matching option is omitted.

The original module command remains available:

```bash
uv run python -m spec2gds.agent_spec.api
```

The browser holds presentation state only. It obtains one immutable editor
snapshot from `/documents/open`, consumes the renderer-neutral document through
`/documents/a2ui`, and uses stable entity references for navigation and
actions. Direct document editing is reserved for Stage 2.

## API Workflow

1. `POST /documents/create` or `POST /documents/open` establishes the active
   custom V1 `.spec` package. ODT containers are rejected.
2. `GET /documents/snapshot` returns the source revision hash, components,
   designs, entry designs, compositions, narrative AST, assets, and diagnostics.
3. `GET /documents/a2ui` returns a batch of A2UI v0.9 `createSurface`,
   `updateComponents`, and `updateDataModel` messages for the custom
   `urn:spec2gds:a2ui:document:v1` catalog.
4. `POST /transactions` accepts an expected source hash plus typed operations,
   such as `upsert_document_xml`, `upsert_instance`, `upsert_connection`,
   `set_internal_design`, `add_entry_design`, or narrative operations.
5. `GET /entities/{kind}/{entity_id}/actions` lists compatible actions. Execute
   with `POST /entities/{kind}/{entity_id}/actions/{action_id}/executions`.
6. Inspect `GET /executions`, `/artifacts`, and `/proposals`. Preview, accept,
   or reject proposals through their dedicated endpoints.

Every source-changing request includes `expected_source_revision_hash`. A stale
hash returns HTTP 409; invalid transactions return diagnostics without changing
source. Action activity is persisted under `activity/` and does not change the
source revision hash.

The API intentionally uses **action execution** terminology. It has no
heading/block routes, ODT loading, or external executor completion callback.

Run the API and document-projection acceptance checks with:

```bash
uv run python -m pytest \
  tests/agent_spec/spec_format/test_document_projection.py \
  tests/agent_spec/spec_format/test_v1_api.py -q
```

See [V1.4 — Editor, API, Cutover, and End-to-End Acceptance](pivot/v1_04_editor_api_cutover_and_acceptance.md)
for the completed cutover criteria and
[`agent_spec_architecture.md`](agent_spec_architecture.md) for the current
system boundary.

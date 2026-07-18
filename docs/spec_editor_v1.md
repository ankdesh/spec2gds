# V1 Local API and Editor

The production local server is the IP-XACT-centered V1 surface. Synchronize the
environment and start it from the repository root:

```bash
uv sync
uv run spec2gds-server
```

The browser editor needs no separate frontend build or development server; it
is served by the API process. Open `http://127.0.0.1:8000/editor`.

For an editor-oriented command, use the equivalent alias:

```bash
uv run spec2gds-editor
```

Choose the checked-in **V1 Demo** sample to visually inspect components,
design reuse, derived topology, typed narrative content, action executions,
artifacts, proposals, and diagnostics. The API is the authoritative editing
surface; source changes are submitted as validated entity-targeted
transactions.

Override the default local bind address with environment variables:

```bash
AGENT_SPEC_HOST=0.0.0.0 AGENT_SPEC_PORT=8080 uv run spec2gds-server
```

The original module command remains available:

```bash
uv run python -m spec2gds.agent_spec.api
```

The browser holds presentation state only. It obtains one immutable editor
snapshot from `/documents/open`, uses stable entity references for navigation
and actions, derives topology from the design projection, and commits narrative
edits through `/transactions` with the last observed source revision hash.

## API Workflow

1. `POST /documents/create` or `POST /documents/open` establishes the active
   custom V1 `.spec` package. ODT containers are rejected.
2. `GET /documents/snapshot` returns the source revision hash, components,
   designs, entry designs, compositions, narrative AST, assets, and diagnostics.
3. `POST /transactions` accepts an expected source hash plus typed operations,
   such as `upsert_document_xml`, `upsert_instance`, `upsert_connection`,
   `set_internal_design`, `add_entry_design`, or narrative operations.
4. `GET /entities/{kind}/{entity_id}/actions` lists compatible actions. Execute
   with `POST /entities/{kind}/{entity_id}/actions/{action_id}/executions`.
5. Inspect `GET /executions`, `/artifacts`, and `/proposals`. Preview, accept,
   or reject proposals through their dedicated endpoints.

Every source-changing request includes `expected_source_revision_hash`. A stale
hash returns HTTP 409; invalid transactions return diagnostics without changing
source. Action activity is persisted under `activity/` and does not change the
source revision hash.

The API intentionally uses **action execution** terminology. It has no
heading/block routes, ODT loading, or external executor completion callback.

Run the V1.4 acceptance checks with:

```bash
uv run python -m pytest tests/agent_spec/spec_format/test_v1_api.py -q
```

See [V1.4 — Editor, API, Cutover, and End-to-End Acceptance](pivot/v1_04_editor_api_cutover_and_acceptance.md)
for the completed cutover criteria and
[`agent_spec_architecture.md`](agent_spec_architecture.md) for the current
system boundary.

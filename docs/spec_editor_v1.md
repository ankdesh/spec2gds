# V1.4 Local API and Editor

The production local server is now the IP-XACT-centered V1 surface. Start it
from the repository root with:

```bash
uv run python -m spec2gds.agent_spec.api
```

Open `http://127.0.0.1:8000/editor` for the lightweight V1 editor shell. Its
navigation exposes Components, Designs, Narrative, Actions, Artifacts, and
Diagnostics. The API is the authoritative editing surface; source changes are
submitted as validated entity-targeted transactions.

## API Workflow

1. `POST /documents/create` or `POST /documents/open` establishes the active
   custom V1 `.spec` package. ODT containers are rejected.
2. `GET /documents/snapshot` returns the source revision hash, components,
   designs, entry designs, compositions, narrative AST, assets, and diagnostics.
3. `POST /transactions` accepts an expected source hash plus typed operations,
   such as `upsert_document_xml`, `upsert_instance`, `upsert_connection`,
   `set_internal_design`, `add_entry_design`, or narrative operations.
4. `GET /entities/{kind}/{id}/actions` lists compatible actions. Execute with
   `POST /entities/{kind}/{id}/actions/{action_id}/executions`.
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
for the full cutover criteria.

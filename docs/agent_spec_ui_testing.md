# Agent-Spec V1 UI Testing

The V1 editor is a prebuilt React/A2UI v0.9 client served by the FastAPI
process. End users need no Node process. Frontend development uses the shared
`circuit-designer/` npm workspace and emits a generated bundle into the Python
package.

## Start the Editor

```bash
uv sync
uv run spec2gds-editor --reload
```

Open `http://127.0.0.1:8000/editor` and select **V1 Demo**. The equivalent
server-oriented command is `uv run spec2gds-server`. Both commands start the
same FastAPI process, so run one or the other, not both.

## Manual Acceptance Walkthrough

1. Confirm the sample picker lists `V1 Demo` and opens without diagnostics.
2. In **Document**, verify the contents navigation and the Overview, Designs,
   Components, Protocols, and optional Cross-cutting Notes hierarchy.
3. Inspect fixed-column ports, interfaces, port maps, instances, connections,
   bus-property, and abstraction-port tables. Hover headings/cells to see their
   IP-XACT schema paths.
4. Verify absent values show an em dash and profile-supplied values show a
   `default` badge.
5. Verify narrative sections, paragraphs, lists, tables, images, entity links,
   and live-view references appear beside their linked entities.
6. Open an entity's **Actions** control and run
   `reference.snapshot_summary`; verify a successful execution, report,
   artifact, and downloadable content.
7. Run `reference.narrative_proposal`; accept or reject the pending
   proposal.
8. On **Activity**, confirm executions, artifacts, and proposals persist.
9. On **Diagnostics**, confirm source and artifact health are reported
   independently.
10. Stop and restart the server, reopen the package, and verify source and
    activity persist.

## Automated Coverage

Run all tests:

```bash
uv run python -m pytest -q
```

`tests/agent_spec/spec_format/test_v1_api.py` calls the actual route functions
and covers create/open, snapshot editing, action execution, artifact lineage,
proposal preview/acceptance, persistence, stale-write rejection, legacy-format
rejection, editor HTML, and bundled sample discovery.

`tests/agent_spec/spec_format/test_document_projection.py` verifies the stable
document hierarchy, fixed profile table kinds, schema-path metadata,
explicit/defaulted/absent cell states, and the A2UI adjacency-list batch.

`tests/agent_spec/spec_format/test_spec_format.py` verifies that the visual
sample includes every supported narrative type, a real SVG asset, explicit
entry designs, composition, deterministic bytes, and no diagnostics.

## Live HTTP Smoke Check

With the server running:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/samples
curl -fsS http://127.0.0.1:8000/editor
curl -fsS http://127.0.0.1:8000/documents/a2ui
```

Rebuild and type-check frontend assets with Node.js 24:

```bash
cd circuit-designer
npm run build:editor
```

## UI Design Constraint

The browser owns only transient presentation state: selected view, active
snapshot, source path, and cached activity lists. The A2UI surface is a
presentation adapter over SpecIR, not a second data model. Every mutation and
action goes through the API. Tests should fail if the UI begins persisting an
independent hardware graph or bypassing revision checks.

## Future Browser Automation

Browser automation should point at the same FastAPI-served production bundle.
Cover the manual walkthrough as one end-to-end scenario.

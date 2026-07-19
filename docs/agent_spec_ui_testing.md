# Agent-Spec V1 UI Testing

The V1 editor is a no-build HTML/CSS/JavaScript client served by the FastAPI
process. There is no Node dependency, frontend development server, or generated
bundle.

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
2. On **Overview**, verify three components, three designs, two entry designs,
   one composite component, and the source revision badge.
3. On **Components**, inspect leaf/composite status, ports, bus interfaces, and
   entity-targeted action controls.
4. On **Designs**, verify entry badges and derived instance/connection topology.
5. On **Narrative**, verify section, paragraphs, list, table, SVG image, entity
   link, and live topology view.
6. Add an architect note and confirm the source revision changes.
7. Run `reference.snapshot_summary`; verify a successful execution, report,
   artifact, and downloadable content.
8. Run `reference.narrative_proposal`; preview and accept or reject the pending
   proposal.
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

`tests/agent_spec/spec_format/test_spec_format.py` verifies that the visual
sample includes every supported narrative type, a real SVG asset, explicit
entry designs, composition, deterministic bytes, and no diagnostics.

## Live HTTP Smoke Check

With the server running:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/samples
curl -fsS http://127.0.0.1:8000/editor
curl -fsS http://127.0.0.1:8000/editor-assets/app.js >/dev/null
```

## UI Design Constraint

The browser owns only transient presentation state: selected view, active
snapshot, source path, and cached activity lists. Every source mutation and
action goes through the API. Tests should fail if the UI begins persisting an
independent hardware graph or bypassing revision checks.

## Future Browser Automation

If browser automation is reintroduced, keep it optional and point it at the
same FastAPI-served editor. Cover the manual walkthrough as one end-to-end
scenario and avoid creating a second frontend build pipeline solely for tests.

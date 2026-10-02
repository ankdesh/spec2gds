# Verification Planner service and operation

`testplan-service` is a standalone Python/FastAPI service with a static browser
UI. It imports immutable Activity Snapshot v1 containers and owns verification
plans, checkpoints, evidence and generated reference artifacts. It does not
modify live specifications or run simulators. Read [architecture](testplan-service-architecture.md),
[Test Plan](verification-layer-1-test-plan.md), [Coverage & Evidence](verification-layer-2-coverage.md)
and [Implementation](verification-layer-3-implementation.md) for each boundary.
Outstanding design requirements are in [the backlog](verification-planner-backlog.md).

## Run independently

From the repository root, use its uv-managed `.venv`:

```bash
uv sync
uv run testplan-service --host 127.0.0.1 --port 6016 --storage-dir verification-data
uv run python -m pytest testplan-service/tests -q
```

Alternatively, run `uv sync` and `uv run testplan-service` inside
`testplan-service/` to use a service-local environment. Defaults come from
`VERIFICATION_HOST`, `VERIFICATION_PORT` and `VERIFICATION_STORAGE_DIR`.
The browser is served at `/` and `/ui`, static files at `/static`, and REST
routes at `/api/verification/v1`. `/docs` exposes the actual OpenAPI contract.
No Spec, Circuit or Assistant process is required. The combined launcher does
not currently start this service.

This is a local service with no built-in account or trusted-proxy actor system.
Do not infer authentication or a public multi-user contract from CORS settings.

## State and revisions

The selected storage directory contains `verification.db` (SQLite WAL),
`blobs/<first-two-hash-characters>/<hash>` and `staging/`. Back up SQLite
consistently with its referenced blobs. Plans pin imported snapshot identities;
opening a newer live Spec does not replace their source automatically.

Authoring commands carry `base_edit_revision`, `request_id` and `operations`.
Committed batches stage a candidate in memory, validate it, then write records,
revision, replay response and event in one repository transaction. Exact
operation-payload retries reuse their stored response; reusing an identity with
a different operation payload fails. Preview is a dry run, not a reservation;
commit checks the revision again. Missing revisions return 428, conflicts 409,
and domain validation errors 422. The API's actual request models and routes
are authoritative; not all proposed pagination, strict unknown-field,
If-Match and actor rules have been implemented.

P1, C1 and I1 are immutable reviewed checkpoints for plan, coverage and
implementation respectively. Later draft edits leave previous checkpoint
payloads unchanged. Evidence campaigns select a frozen coverage checkpoint;
generation reads an implementation checkpoint, not the live recipe draft.

## Browser and integration boundary

The static UI uses Blueprint Slate styling, a scope hierarchy, layer-specific
center views and an inspector. It offers source audit and intent authoring,
coverage matrices/gaps/runs, recipe and binding forms, checkpoint review and
reference artifact generation. It is a single-page application; the earlier
proposed per-layer browser routes are not implemented routes.

SSE invalidates projections through the plan event stream. Its current behavior
is defined in `api/routes_events.py`; bounded event retention, fully replayable
cursors and hidden-tab fallback polling remain backlog requirements.

The service exposes its own operation catalog and command preview/commit API.
It is not registered as an Assistant owner. The former `/api/v1/testplans`,
JSON node repository, sample seeder and `/assistant/proposals/*` prototype are
not the current contract. Future Assistant integration must preserve owner
revision checks and reviewed command boundaries.

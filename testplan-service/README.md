# Verification Planner

A standalone FastAPI/static-browser service for snapshot-bound requirements,
verification intents, coverage/evidence and implementation recipes. It owns
SQLite records and content-addressed blobs independently of Spec/Circuit services.
P1/C1/I1 checkpoints preserve reviewed plan, coverage and implementation inputs.

The bundled `spec2gds.reference.bundle` backend emits reference artifacts and
synthetic fixture result templates. It does not generate executable tests or
run simulators. See the authoritative
[Verification Planner architecture and guide](../docs/verification-planner.md).

## Run and test

From the repository root, use the uv-managed root `.venv`:

```bash
uv sync
uv run testplan-service --host 127.0.0.1 --port 6016 --storage-dir verification-data
uv run python -m pytest testplan-service/tests -q
```

For an independent environment, run `uv sync` and `uv run testplan-service`
inside this directory. Use `--service-config PATH`, `--host`, `--port`, and
`--public-host` for addresses, with precedence CLI → file → defaults. The
`verification_planner.service/ui` entries use one listener. `VERIFICATION_HOST`
and `VERIFICATION_PORT` have no effect. `VERIFICATION_STORAGE_DIR` remains
supported. Open `http://127.0.0.1:6016/`;
OpenAPI is at `/docs`, API routes at `/api/verification/v1`. No Node build or
other service is needed. The combined root launcher does not start this service.

## Use

1. Import an Activity Snapshot v1 and create a plan for its root scope.
2. Audit source sections, capture requirements and author atomic intents.
3. Preview command batches with the observed draft revision, commit, and review
   a plan checkpoint.
4. Add objectives/policies, review coverage, select a profile/campaign and import
   normalized evidence. Synthetic runs remain fixture evidence.
5. Author target bindings and recipes, review implementation, generate and
   inspect reference artifacts. External simulation is a separate operation.

Read the [Verification Planner guide](../docs/verification-planner.md)
for architecture, command operations, coverage schemas, and implementation recipe boundaries.
`src/testplan_service/application/service.py` composes the domain services;
`api/app.py` mounts HTTP/UI; `storage/` owns persistence; `ui/static/` owns the
browser. API field shapes come from Pydantic/OpenAPI and `/operation-catalog`.

Back up `verification.db` consistently with `blobs/`. Use local/trusted deployment;
the service has no built-in account system or public multi-user guarantees.

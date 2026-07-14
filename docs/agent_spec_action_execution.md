# Agent-Spec Action Execution Contract

Agent-spec uses a small action/executor contract for generated hardware work.
An action is the user-visible capability, an executor performs the external
work, and a run is one immutable invocation.

## Lifecycle

1. The editor loads all enabled actions for a heading.
2. The user supplies `ActionSpec.input_schema` fields and checks preconditions.
3. Trigger creates a run, captures an immutable `InputSnapshot`, and records a
   `run.executor.dispatched` event. The built-in dispatcher does not start a
   command.
4. An executor calls `POST /agent-spec/runs/{run_id}/completion` with its
   outcome, artifacts, and report data.
5. The server validates the action report, artifacts, and postconditions. A
   successful executor result with invalid output is a completed run whose
   report requires review; an executor-declared failure is a failed run.
6. The server persists `report.json` and a read-only A2UI message stream at
   `report.a2ui.jsonl`. The editor opens it in the report drawer.

## Action Definition

`ActionSpec` includes action identity and presentation metadata, `executor_id`,
an input JSON Schema, a report JSON Schema, a restricted report catalog ID, and
allowed artifact roles. Inputs are stored in the `inputs` member of an
immutable snapshot; document hashes, selected versions, and prior artifacts are
always server-owned.

## API

| Route | Purpose |
| --- | --- |
| `GET /agent-spec/actions` | Enabled action definitions. |
| `GET /agent-spec/blocks/{block_id}/context` | Read-only action context. |
| `POST /agent-spec/blocks/{block_id}/actions/{action_id}/preconditions` | Evaluate supplied inputs without creating a run. |
| `POST /agent-spec/blocks/{block_id}/actions/{action_id}/runs` | Recheck, snapshot, and dispatch a run. |
| `GET /agent-spec/runs/{run_id}` | Run, snapshot, events, report, and A2UI messages. |
| `POST /agent-spec/runs/{run_id}/completion` | Executor completion callback. |

The query envelope version is `agent-spec.actions.v1`.

## Report Catalog

`agent-spec.report.v1` is read-only. Its current components are `Column`,
`ReportSummary`, `CheckList`, and `ArtifactList`. Executors submit structured
report data only; trusted server-side code produces the A2UI surface. External
command execution, queues, authentication, retries, cancellation, and
multi-user coordination are intentionally out of scope.

`Delayed report demo` is the one local test action: it waits five seconds in a
background worker, then completes with a pseudo report so the Runs sidebar and
A2UI report drawer can be exercised without an external executor.

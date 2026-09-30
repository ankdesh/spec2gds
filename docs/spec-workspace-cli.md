# Focused Spec workspace commands

The Python commands in `scripts/spec2gds_assistant.py` and `scripts/spec2gds_spec.py` run focused assistant turns and manage package decisions/history. They work on a workspace directory or an exact `.spec` file. This phase does not run the RTLLM benchmark.

## Setup

From the repository root, use `uv` to create and populate `.venv`, then build the internal Node/Harness product:

```bash
uv sync
scripts/setup-all.sh
export OPENAI_API_KEY="..."
```

`spec2gds-assistant` needs Node.js 22.19+ or 24+, the built `ai-assistant` product, and its DeepSeek Harness checkout. `scripts/setup-all.sh` prepares those dependencies. A compatible endpoint can be selected with `OPENAI_BASE_URL` and `OPENAI_MODEL`. The installed Python commands run from the root `.venv` through `uv run`; the same files can be invoked directly with `uv run python scripts/spec2gds_assistant.py` and `uv run python scripts/spec2gds_spec.py`. The internal Node review bridge is `scripts/spec2gds_review_bridge.mjs`.

## Automatic turns and restricted decisions

```bash
uv run spec2gds-assistant ./work/timer --preset focused -- "Propose a timer component."
# A restricted turn leaves its proposal pending:
uv run spec2gds-assistant ./work/timer --require-human-approval -- "Refine the timer."
uv run spec2gds-spec reviews ./work/timer
uv run spec2gds-spec approve ./work/timer proposal_...
# Or reject a proposal without changing the package:
uv run spec2gds-spec reject ./work/timer proposal_...
uv run spec2gds-spec history ./work/timer --limit 25
```

The assistant command accepts only the `focused` preset in this phase. It starts a private loopback Spec owner, binds one headless turn to the exact package, prints the answer and proposal IDs, and exits. Valid submissions save automatically; `--require-human-approval` makes them pending. The Spec command never prompts a model. `reviews` emits proposal IDs, session IDs, state, complete artifacts, previews, diagnostics, and receipts. `approve` reopens the package and revalidates the stored artifact against its current revision. `reject` records a discarded decision without changing source. When multiple proposals remain pending, pass an ID. `history --limit N --before CURSOR` paginates durable submissions.

For a directory, the command uses its sole direct-child `.spec` file. It creates `<directory-name>.spec` if there is none, and reports all candidates if there are several. An explicit path such as `./work/timer/custom.spec` always selects that file; the assistant creates it if absent. `spec2gds-spec reviews`, `approve`, and `reject` require an existing package.

The browser editor and CLI may open the same package. Idle browser views follow disk updates. Drafts retain their original revision and require source review before a stale save can be retried. Package saves preserve disk conflict detection. If an application saved the package but stopped before updating review state, a later read or retry reconciles the same proposal ID without applying it twice. Proposals carry the revision actually read by the model; older context produces a stale result.

## Records for future evaluation scripts

Each package has its own state directory at `<workspace>/.spec2gds/assistant/<package-path-hash>/`. The hash separates multiple explicit `.spec` paths in one workspace. The stable entry points for scripts are:

- `last-run.json`: latest run metadata, including `schema_version`, `spec_path`, `document_id`, `session_id`, `preset`, `approval_policy`, `exit_code`, `answer`, proposal IDs/states, and `events_path`.
- `runs/<session-id>.json` and `runs/<session-id>.jsonl`: metadata and the raw JSON event stream for each completed assistant invocation.
- `uv run spec2gds-spec reviews <target>`: versioned JSON proposal and decision records for the selected package.

The Harness transcript, review database, and owner submission/event journal remain under that state directory. Use command output and run JSON for evaluation scripts. A future `BaseAgentAdapter.solve()` can capture automatic saved receipts, or request restricted mode and decide with the Spec CLI, then map those records into trajectory/token fields. Backend execution such as RTL generation belongs in separate scripts. See the [iterative refinement test plan](spec-editor-iterative-refinement-test-plan.md) for deterministic acceptance commands and deferred UI coverage.

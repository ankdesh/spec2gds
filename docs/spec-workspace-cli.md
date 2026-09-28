# Focused Spec workspace commands

The Python commands in `scripts/spec2gds_assistant.py` and `scripts/spec2gds_spec.py` divide one focused assistant turn from a human review decision. They work on a workspace directory or an exact `.spec` file. This phase does not run the RTLLM benchmark.

## Setup

From the repository root, use `uv` to create and populate `.venv`, then build the internal Node/Harness product:

```bash
uv sync
scripts/setup-all.sh
export OPENAI_API_KEY="..."
```

`spec2gds-assistant` needs Node.js 22.19+ or 24+, the built `ai-assistant` product, and its DeepSeek Harness checkout. `scripts/setup-all.sh` prepares those dependencies. A compatible endpoint can be selected with `OPENAI_BASE_URL` and `OPENAI_MODEL`. The installed Python commands run from the root `.venv` through `uv run`; the same files can be invoked directly with `uv run python scripts/spec2gds_assistant.py` and `uv run python scripts/spec2gds_spec.py`. The internal Node review bridge is `scripts/spec2gds_review_bridge.mjs`.

## One turn, then a decision

```bash
uv run spec2gds-assistant ./work/timer --preset focused -- "Propose a timer component."
uv run spec2gds-spec reviews ./work/timer
uv run spec2gds-spec approve ./work/timer proposal_...
# Or reject a proposal without changing the package:
uv run spec2gds-spec reject ./work/timer proposal_...
```

The assistant command accepts only the `focused` preset in this phase. It starts a private loopback Spec owner, binds the one headless turn to the selected document, prints the answer and proposal IDs, and exits. It never approves. The Spec command never prompts a model. `reviews` emits JSON containing each proposal's ID, session ID, state, complete artifact, owner preview, diagnostics, and apply result. `approve` reopens the package, validates its current revision, applies the owner-previewed operations, and records the decision. `reject` records a discarded decision and leaves the package source untouched. When multiple proposals remain pending, pass an ID to `approve` or `reject`.

For a directory, the command uses its sole direct-child `.spec` file. It creates `<directory-name>.spec` if there is none, and reports all candidates if there are several. An explicit path such as `./work/timer/custom.spec` always selects that file; the assistant creates it if absent. `spec2gds-spec reviews`, `approve`, and `reject` require an existing package.

The browser editor and CLI may open the same package. A browser session with an older disk snapshot receives a save conflict and must refresh from disk. Approvals serialize per package. If an approval saved the package but stopped before updating review state, the next `approve` reconciles the same proposal ID without applying the operations twice. A proposal whose base source revision changed is marked stale.

## Records for future evaluation scripts

Each package has its own state directory at `<workspace>/.spec2gds/assistant/<package-path-hash>/`. The hash separates multiple explicit `.spec` paths in one workspace. The stable entry points for scripts are:

- `last-run.json`: latest run metadata, including `schema_version`, `spec_path`, `document_id`, `session_id`, `preset`, `exit_code`, `answer`, proposal IDs/states, and `events_path`.
- `runs/<session-id>.json` and `runs/<session-id>.jsonl`: metadata and the raw JSON event stream for each completed assistant invocation.
- `uv run spec2gds-spec reviews <target>`: versioned JSON proposal and decision records for the selected package.

The Harness conversation transcript and review database also remain under that state directory. Their internal schemas are owned by Harness and the assistant product; use the command output and run JSON for scripts. A future `BaseAgentAdapter.solve()` implementation under `/home/ankdesh/explore/RTLLM/agent_eval` can launch one turn for a `DesignMeta` fixture workspace, capture the run record, inspect the proposal and preview, and make an explicit decision with the Spec CLI. It can then map those records into `FrameworkTrajectory.steps` and token fields. Backend execution such as RTL generation belongs in separate scripts; this workflow stops at the saved Spec and review record.

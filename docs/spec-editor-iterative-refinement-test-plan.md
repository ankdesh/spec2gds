# Iterative refinement test plan

Use scripted proposals and a deterministic model fixture. No external model key
is required for correctness coverage. The implementation does not add a
long-running agent. UI execution is deferred; all non-UI correctness checks are
required before accepting this phase.

## Non-UI acceptance commands

Run from the repository root using the root `.venv` managed by `uv`:

```bash
uv sync
npm --prefix ai-assistant run typecheck
npm --prefix ai-assistant test
npm --prefix ai-assistant run build
uv run python -m pytest tests/agent_spec/spec_format -q
npm --prefix ai-assistant run test:harness
npm --prefix circuit-designer run build
```

The owner directory includes `test_workspace_clis.py` for private-owner CLI
coverage.
The workspace CLI fixtures use the compiled assistant, so build it before the
Python acceptance suite.
`scripts/setup-all.sh` prepares the pinned Harness and Node dependencies when
needed. Do not treat existing generated bundles as verification of source
changes.

| Coverage | Fixtures and required result |
| --- | --- |
| Owner policy | Automatic submission saves; restricted submission stays ready; explicit approval saves once; rejection leaves source unchanged; reload/restart preserves policy; imported old reviews stay pending. |
| Document refinement | Create and refine ports, parameters, supported sections, instances, connections, and narratives. Invalid references, forbidden composite ports, and entity-boundary violations leave source unchanged. |
| Authored revision | Read A, commit B, submit against A: stale diagnostic, no mutation, and no revision restamping. |
| Package binding | A remains writable while B is active; equal internal document IDs have distinct keys; restart reopens the pinned package; missing or changed identity fails. |
| Writers | Ten local writers sharing one base revision yield one success. Mix assistant, editor, and CLI application; retain disk conflict detection and locked activity finalization. |
| Retry and interrupted save | Identical retry returns one receipt; changed artifact under the same ID fails. Interrupt after package save, restart, and reconcile from accepted decisions without another save. |
| Assistant adapter | Explicit policy discovery, missing policy/service failure, automatic saved results, defaults versus missing inputs, stale context, same-chat contract refresh, uncertain application, and retained pending reviews. |
| CLI | Private owner's default automatic behavior and restricted flag; review/reject/approve and package history; saved run metadata. |
| Repeated refinement | 100 submissions produce valid packages, complete paginated history, ordered event replay, stable contracts, and bounded view history. |

Primary fixtures are `tests/agent_spec/spec_format/test_iterative_refinement.py`,
the workspace CLI tests, `ai-assistant/tests/iterative-refinement.test.ts`, and
owner-client/source-creation tests. Harness integration exercises the real
assistant transport against local owner/model fixtures.

## Deferred UI pass

Build the assistant and editor first. Install the scenario workspace's
dependencies and use the cached Circuit Designer Playwright browser:

```bash
npm --prefix tests/ui-scenarios install
# If Chromium has not been installed yet:
cd circuit-designer
PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright-browsers" npm exec -- playwright install chromium
cd ..
bash tests/ui-scenarios/run-test.sh --scenario automatic
bash tests/ui-scenarios/run-test.sh --scenario restricted --approval-mode review
bash tests/ui-scenarios/run-test.sh --scenario live
bash tests/ui-scenarios/run-test.sh --scenario binding
bash tests/ui-scenarios/run-test.sh --scenario repeated
```

The runner allocates temporary package/state/config directories and dedicated
ports. It stops only its own processes. It never deletes a developer package or
stops a shared stack. Every scenario asserts owner API results, package bytes
read through Python, rendered editor content, and assistant state. Readiness
and transitions use observable polling. A failed editor assertion fails the
scenario.

| Scenario | Required result |
| --- | --- |
| automatic | Create and refine a specification with zero confirmation clicks. Check exact component IDs, port ranges, SystemVerilog contents, saved revision, and applied history. Idle rendering converges within five seconds after the saved owner result. |
| restricted | Source is unchanged before approval and after rejection; approval saves once; approving after a newer edit fails stale. |
| live | Idle view follows assistant changes. An inline draft retains exact text and authored base revision; stale save requires source review, and cancellation reveals current source. |
| binding | A chat still refines A while B with the same document ID is visible. Owner restart/reconnect restores the pinned document and rendered source. |
| repeated | 100 accepted submissions and identical retries preserve complete history and bounded rendered rows. |

Also run `npm --prefix circuit-designer run test:e2e:editor`. Its fixtures
exercise coherent views, scoped requests, document switching, and explicit
review before stale-draft retries. Extend the later UI pass with delayed view
responses, CLI updates during subscriptions, connection gaps, and focused
scroll/expanded-section assertions; these remain runtime acceptance work.

`--output /absolute/path` selects artifacts; `--headed` shows the browser.
The runner captures screenshots, traces, service logs, console/network failures,
model fixture requests, proposal/revision records, and a copy of saved packages.
Its temporary working data is removed after artifact capture.

The live-model smoke is separate and explicitly invoked:

```bash
OPENAI_API_KEY=... bash tests/ui-scenarios/run-test.sh --scenario automatic --live-model
```

It is supplementary and must never replace deterministic coverage. This
session could not execute checks because the tool process launcher failed
before starting commands; no passing results or built artifacts are claimed.

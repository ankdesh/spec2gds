# Hierarchical assistant evaluation and evidence

Portable requirements/testbenches live in `tests/evaluation/rtl/cases.json` and
`tests/evaluation/rtl/benches`. Production prompts use general rules with no
benchmark dispatch or canned RTL. Deterministic fixtures measure plumbing; repeated
live-model runs measure inference. Neither lint nor fixture success establishes
live-model quality.

| Family | Concrete configurations | Checks |
| --- | --- | --- |
| Adder | 8, 4, 13 bits | Carry propagation, final carry, corner/random operands |
| Counter | 16, 5, 9 bits | Reset, direction, wrap-around |
| Asynchronous FIFO | 8×16, 12×4, 16×8 | Single transfers, ordering, full/empty boundaries, pointer wrap, unequal clocks, concurrent traffic |
| Unseen priority encoder | 8 requests | Exhaustive valid/highest-priority index |
| Registered pipeline | Two 8-bit stages | Structured child reuse, latency, reset/data |

Negative controls cover an XOR adder, constant counter and the reviewed FIFO's
single-write Gray-pointer defect. They compile but must fail simulation. Benches
specialize concrete widths/depths and expected public interfaces; adaptations are
recorded in reports. `--benchmark-root` optionally records original RTLLM bench
provenance. Full original parameterized benchmark compatibility remains unverified.

## Reproduce the gates

Install Verilator 5.x, Make and a C++ compiler; use uv with the root `.venv`:

```bash
uv run --no-sync python -m pytest tests/agent_spec/spec_format tests/agent_spec/activities/rtl -q
npm test --prefix ai-assistant
npm run typecheck --prefix ai-assistant
npm run test:harness --prefix ai-assistant
ASSISTANT_UI_TEST_DEPS="$PWD/circuit-designer" \
  PLAYWRIGHT_BROWSERS_PATH="$PWD/circuit-designer/.playwright-browsers" \
  npm run test:ui --prefix ai-assistant
npm test --prefix circuit-designer
```

Check an already published UI activity project without regenerating it:

```bash
uv run --no-sync python scripts/rtl_evaluation.py \
  --project /absolute/published/project --case adder_8 \
  --source-revision sha256:SOURCE_REVISION --output /tmp/adder-check
```

Inventory hashes and revision are checked before separate generation, lint,
compilation and simulation outcomes. Missing tools yield `unverified`; errors yield
`failed`. Logs and `evaluation-report.json` remain in the output folder. Explicit
`--spec PACKAGE --target EXACT_ID_OR_VLNV` generates a separate CLI project and
cannot serve as evidence of UI execution.

Browser scenarios isolate ports, owner state, packages and output directories:

```bash
npm ci --prefix tests/ui-scenarios
cd tests/ui-scenarios
PLAYWRIGHT_BROWSERS_PATH=../../circuit-designer/.playwright-browsers npx playwright install chromium
npm test -- --scenario automatic --output /tmp/spec2gds-ui-automatic
npm test -- --scenario architecture --output /tmp/spec2gds-ui-architecture
npm test -- --scenario restricted --output /tmp/spec2gds-ui-restricted
npm test -- --scenario live --output /tmp/spec2gds-ui-draft
npm test -- --scenario binding --output /tmp/spec2gds-ui-binding
npm test -- --scenario repeated --output /tmp/spec2gds-ui-repeated
```

Here `live` means editor refresh/draft preservation; it uses deterministic responses
unless `--live-model` is supplied. The five generation scenarios verify the actual
UI-queued activity's terminal success, artifacts, report and source revision; the
architecture scenario checks review lifecycle and package creation. They retain
traces/screenshots, history/disk snapshots and process logs. Repeated history checks
100 submissions, idempotent retries and pagination.

For real generalization, from `tests/ui-scenarios`:

```bash
export OPENAI_API_KEY=...
node --import tsx runner/run_generalization.ts --output /tmp/spec2gds-generalization
node --import tsx runner/run_generalization.ts --case registered_pipeline --repeats 3 \
  --output /tmp/pipeline-live --benchmark-root /path/to/RTLLM
```

The default is three runs of all 11 short prompts with no RTL, IDs or tool
instructions. Capture reviewed architecture, authored packages, actual UI generation,
simulation and explanation refinement. Apply the manifest's document-quality rubric
to linked requirements/assumptions/verification, hierarchy, explanations, authority
and refinement. Manual document review remains separate from functional results.
Missing credentials produce an unverified report; canned responses never substitute.

Live runs default to 8192 output tokens and 12 model steps per turn so compound
hierarchy/SV proposals fit. Override these with `ASSISTANT_MAX_OUTPUT_TOKENS` and
`ASSISTANT_MAX_STEPS_PER_TURN`; model, endpoint and limits are recorded with each run.
For complex authoring in the normal app, configure the same limits before launching
the services. Deployment limits and owner approval policies still apply.

## Implementation evidence (2026-10-02)

The functional suite passed all 11 concrete configurations using test-only reference
implementations emitted by the production generator. All three expected-failure
mutants compiled and failed simulation; the FIFO mutant failed the single-write
assertion. Its 15 tests also cover legacy/stale reports. These verify generation and
the evaluator, not live-model inference.

| Gate | Result |
| --- | --- |
| Spec-format Python suite | 105 passed, including 13 unified integration cases and 9 focused CLI cases |
| RTL Python suite | 35 passed, including the 15 functional evaluation cases |
| Shared API/activity Python regressions | 31 passed, 9 skipped for unavailable external dependencies |
| Assistant unit tests/typecheck | 110 passed; typecheck passed |
| Native harness integration | 3 passed |
| Native preset browser lifecycle | 3 passed |
| Circuit/editor workspace tests | 117 passed |
| Isolated product browser scenarios | All six passed: automatic, restricted, draft, binding, repeated, architecture |
| Source builds and changed Python lint | Passed |

The unified cases include compound creation, explanations, rollback, text-only SV
stability, reachability, deterministic output, V2 reading, ownership and bounded
context. Numeric slice hookups also passed exhaustive 256-input simulation.
Architecture browser coverage includes reload, revise, cancel, creation only after
approval and continuation into the correct document. The five generation scenarios
check the UI-launched activity's terminal success, published report/artifacts and
matching source revision. Automatic and architecture scenarios were rerun after the final
editor build and receipt/freshness fixes.

Runtime evidence used uv with Python 3.12.3, Node 22.23.1 and Verilator 5.020.
Circuit's declared Node requirement is 24+, although its builds/tests passed on this
host's Node 22; use the documented requirement for reproducible setup. One existing
Python fixture emits a Pydantic serialization warning; build output also reports
the editor bundle size warning.

Durable results and UI activity reports are in
[implementation evidence](evidence/hierarchical-spec-implementation.json).
`OPENAI_API_KEY` was unavailable: no live inference runs or document-quality rubric
review were performed. The planned three runs per case remain explicitly
[unverified](evidence/hierarchical-spec-live-evaluation.json). Original parameterized
RTLLM compatibility remains unverified; generated configurations are concrete.

# Software testing and regression strategy

This strategy covers the complete spec2gds environment. Use **Spec Editor** for
the frontend and **Spec service** for its backend. A **Spec** is the logical
document. A **`.spec` file** is the saved archive. Follow [the terminology
rules](TERMINOLOGY.md) in code, reports, and documentation.

Software regression checks are separate from the hardware **Test Plan** artifact
produced by **Verification Planner**. A software test pass does not establish
hardware verification or model quality.

## Method and organisation

Use layered, risk-based testing. Put a check at the lowest layer that can detect
the fault reliably. Use integration and browser checks when the fault depends
on communication, persistence, or designer interaction. Do not set fixed test
counts or code-coverage percentages for each layer.

Keep tests near their subsystem. Keep flows that span applications in
`tests/ui-scenarios`. Do not copy tests into a second regression collection.
Regression profiles select the maintained suites. The suite catalogue in
`scripts/test_profiles.py` records the subsystem, layer, evidence type,
dependencies, prerequisites, risk areas, and execution limit beside each command.

| Layer | Method | Main purpose |
| --- | --- | --- |
| Unit and component | Isolated logic and state checks | Fast feedback on local faults |
| Contract and service API | Public interface and validation checks | Compatibility and enforced boundaries |
| Integration | Real services, storage, adapters, and extension execution | Correct interaction between subsystems |
| Browser | Rendered state, controls, keyboard access, and responsive layout | Correct designer interaction |
| End-to-end | Real applications and services, with saved-state assertions | Complete flows and durable results |
| Quality evaluation | Live inference, hardware execution, and measured quality | Evidence beyond fixtures |

Prioritise source integrity, atomic changes, revision control, approval rules,
and separation between Spec and Circuit domains. During detailed test design,
use state-transition, boundary-value, negative-input, and property-based methods
where they fit the risk. Use exploratory review for usability and unexpected
behaviour. See [the coverage matrix](test-coverage-matrix.md) for implemented
flows, local rules, conditional checks and known failures.

## Local commands

Run commands from the repository root after `scripts/setup-all.sh`. Profiles need
Python 3.12+, the root uv environment, Node.js 24.2+, installed npm dependencies,
the linked DeepSeek Harness source, and Playwright Chromium as applicable.
Use `nvm use 24` if the active Node version is older. No CI or scheduled run is
installed by these commands.

```bash
scripts/test-all.sh fast
scripts/test-all.sh integration --scope spec
scripts/test-all.sh integration --scope spec,assistant
scripts/test-all.sh regression
scripts/test-all.sh regression --dry-run
scripts/test-all.sh regression --rtl-cases adder_4,adder_8,adder_13
scripts/test-all.sh fast --output /tmp/spec2gds-fast-evidence
scripts/test-all.sh integration --scope spec --coverage
```

`--output` must identify a new or empty directory. The default is a private
directory under `/tmp`. `--dry-run` prints the selected commands, requirements,
dependencies, and evidence types. It does not build, write reports, or call a
provider. The existing `fundamental`, `extensive`, and `all` tiers retain their
previous selection and behaviour; `all` is not the new full regression profile.

| Profile | Required checks |
| --- | --- |
| `fast` | Fast Python suites, Circuit Designer and Assistant units, scenario-runner units, schema consistency, required builds, two deterministic real-service Spec Editor smoke flows, and exactly three short live model end-to-end checks |
| `integration` | Selected service/API suites, interface consumers, Harness checks, fixture browsers and real-service Playwright projects for Spec Editor, Circuit Designer, AI Assistant and Verification Planner; hardware checks for the Activities scope |
| `regression` | All fast checks once, remaining Python CLI and hardware suites, all browser suites, real-service scenarios, Spec/Circuit save-back, catalogue validation, and repeated live RTL evaluation |

Scopes are `spec`, `circuit`, `assistant`, `verification`, `activities`, `shared`,
and `all`. Combine scopes with commas. Integration defaults to `all`.
Spec changes include Circuit clients, Assistant integration, and Verification
Planner snapshot consumers. Shared changes expand to all integration scopes.
Integration uses deterministic model fixtures; live inference belongs to fast
and regression. Each invocation runs a prerequisite build once.

### Live checks

Set `OPENAI_API_KEY` in the process environment. `OPENAI_MODEL` and
`OPENAI_BASE_URL` select the model and endpoint; product defaults apply when
they are absent. The runner does not load credential files or print their
contents. A local `.env` used by the product does not replace the profile's
explicit credential prerequisite.

Fast includes three checks: automatic Component description saving, a wire-range
change, and restricted description saving. Each check starts isolated real
services, uses Chromium and the live model, and checks the visible and saved
result. These checks do not compile hardware. Each uses a 180-second execution
limit, six model steps per turn, and 4,096 output tokens per model request.
It permits at most two distinct architecture decisions.
They cannot substitute fixture responses or raise these limits through product
environment overrides.

Full regression runs these three checks once and then the existing portable RTL
evaluation catalogue with its configured repeats. Each broader run has a
600-second limit; the aggregate has a six-hour limit. This evidence includes
UI-launched Activity execution and hardware simulation. It needs Verilator 5.x,
GNU Make, and a C++ compiler. Document quality still requires rubric review.

Use `regression --rtl-cases <case-ids>` to focus live RTL evaluation during a
case-specific investigation. It retains all other regression suites and the
three short live checks. It uses the catalogue's original repeat count. The
report identifies the selected cases and states that other RTL cases were not
rerun. This is a scoped result; the default full regression still runs all cases.

The Assistant `npm run eval` command checks its catalogue. It does not execute
the requests in that catalogue. Reports label this as `catalogued-only`; it
cannot substitute for live execution or semantic assertions.

## Current coverage inventory

This is a map of evidence sources, not a claim that every capability is tested.
Use the capability matrix and each run's report for case coverage and unresolved
results. No fixed percentage is required for acceptance.

| Subsystem | Existing evidence | Main risks and remaining gaps |
| --- | --- | --- |
| Spec service and `.spec` format | Python model/archive suites and HTTP request, transaction, projection, refinement and SDK handoff checks | Source integrity, compatibility, atomic changes and binding boundaries; large-input measurements remain separate |
| Spec Editor and shared document packages | Focused revision/port units, fixture browser checks and real-service browser flows | Save/reopen, conflicts, hidden source, keyboard access and events; selected-path and running-job UI failures remain visible |
| Circuit Designer and Circuit service | Package units, service/client tests, browser suite, and real Spec save-back flow | Projection, temporary drafts, source authority, and topology/layout separation |
| AI Assistant and Harness | Units, native integration, fixture browsers, real-service scenarios, three live checks, and repeated live RTL evaluation | Approval and binding rules, model outcomes, completion claims; Assistant catalogue requests are not all executed and full native-shell coverage remains partial |
| Verification Planner | Python acceptance and real-browser authoring, evidence, checkpoint, bundle and recipe suites | Snapshot identity and durable review state; sample creation and browser export failures remain visible |
| Activities and importers | SDK/preflight, controlled browser jobs, restart, scratch-directory, RTL, SystemC and real-import cases | Deterministic execution and source boundaries; missing Docling/toolchains leave relevant checks unverified |
| Shared infrastructure | Service registry, observability, terminology, runner tests, and generated-contract checks | Configuration, failure propagation, process isolation, and compatibility |

System-wide performance thresholds, resilience measurements, automated visual
baselines, and complete accessibility/security matrices remain gaps. Extend this
map when evidence is added. Do not infer coverage from a filename or a pass count.

## Evidence and failure rules

- Keep isolated checks, fixture-browser checks, real-service flows, live
  inference, compilation, and simulation as separate evidence types.
- Use temporary storage and configuration. Browser profiles use distinct local
  ports and do not reuse a designer's running server. Stop only test processes.
- Build products before checks that consume their output. Continue independent
  checks after a failure; report blocked consumers as unverified.
- Wait for observable readiness and state changes. Avoid fixed delays.
- Missing required credentials or tools makes the profile incomplete and returns
  nonzero. Product failures also return nonzero. Available checks still run.
- Record optional skips and their reasons. Unconfigured SystemC/CIRCT coverage
  is outside the declared result. Never label skipped or unverified checks passed.
- Keep original outcomes. The profile runner does not retry a failing suite.
  Diagnostic reruns must have a separate output directory.
- Version fixtures and expected results. Review baseline updates as behaviour
  changes; do not update expected output solely to remove a failure.
- For each confirmed defect, add protection at the lowest effective layer. Add
  browser protection when the fault depends on browser behaviour.

Each run presents `summary.html`, a standalone report with tables for check groups,
individual recorded behaviours, capability coverage, results, times and known
failures. `--coverage` adds line and branch diagnostics for supported unit/service
suites without selecting extra functional checks. The report updates as checks
finish. It contains no commands, source hashes, stack traces, or raw metadata.
The final console message links to this HTML report. `summary.json` remains
available for automated diagnostics, with per-suite `command.log` files. Python suites
also write JUnit XML, including skips. Existing browser and scenario runners
retain their traces, screenshots, saved Specs, and functional reports.
Fixture browser failures retain screenshots and traces under the suite's
`playwright` directory, so later runs do not replace their evidence. The summary
records the source revision and dirty state, selected scope, tool versions, model
configuration, durations, and pass/fail/unverified counts. Configured secret
values and authentication query tokens are removed from text logs and summaries. Keep the private evidence
directory private: browser traces can include application content.

Review coverage gaps, duration, unstable results, defect recurrence, live
evaluation outcomes, and token usage from available native reports. Code coverage
can support this review; it is not the sole acceptance criterion. A successful
command proves only the checks listed as executed, not the unresolved gaps.

## Coding-agent and developer instructions

After implementation, run `fast` and relevant `integration` scopes. Use
`--dry-run` first if selection or prerequisites are uncertain. Run `regression`
for broad or high-risk changes: cross-application contracts, persistence, shared
runtime, Activity SDK, model/prompt releases, and release preparation.

Use configured credentials for the three live checks. If a prerequisite is
unavailable, report the incomplete profile and its available results. Do not
replace live checks with fixtures or omit checks to obtain a passing profile.
Report the commands run, results, missing coverage, and evidence directory.

Maintain adoption in four stages: inventory existing evidence; maintain profile
execution and reports; close gaps through separately designed tests; then review
speed, stability, and regression protection as part of development.

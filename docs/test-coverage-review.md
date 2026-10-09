# Software coverage review

Review date: 9 October 2026.

The coverage implementation adds 109 cases: 47 Python cases, 23 TypeScript unit
cases, and 39 browser cases. It adds isolated real-service fixtures, four browser
projects, optional coverage measurement, and human-readable HTML tables.
The [capability matrix](test-coverage-matrix.md) maps maintained checks to behaviour.

## Executed evidence

| Check | Result | Evidence directory |
| --- | --- | --- |
| Focused Python contracts, importer boundaries and test infrastructure | 74 passed | Local focused pytest execution |
| `scripts/test-all.sh fast --coverage` | 10 groups passed; live wire-range group failed | `/tmp/spec2gds-coverage-fast-final-20261009` |
| `scripts/test-all.sh integration --scope spec,circuit,assistant,verification,activities,shared --coverage` | 24 groups passed; two browser groups failed | `/tmp/spec2gds-coverage-integration-final-20261009` |
| `scripts/test-all.sh regression --coverage`, with continued browser checks | 25 groups passed; four groups failed; document imports remain unverified | `/tmp/spec2gds-coverage-regression-combined-20261009` |
| All 39 new browser cases, three isolated executions, no retries | 93 passed; 12 failed; 12 unverified | `/tmp/spec2gds-deterministic-stability-final-20261009` |

The browser totals represent 31 passing, four failing and four unverified cases
in each execution. Passing cases passed all three executions. The four import
cases require Docling, which is not installed. They do not count as verified
coverage. Tests use independent files, storage, ports and preferences.

The original regression runner ended with signal 143. Its live evaluation
subprocess continued and completed all 33 planned checks. The continuation
therefore added six duplicate live executions before that was discovered.
All 33 planned checks and all six additional executions failed. The combined
report labels additional executions separately. Original evidence remains in
`/tmp/spec2gds-coverage-regression-20261009`; continuation evidence remains in
`/tmp/spec2gds-coverage-regression-continuation-20261009`. No failure was changed
to a pass. The runner now handles termination and writes an incomplete report.

## Coverage diagnostics

These figures describe the named checks only. They are separate measurements,
not a combined percentage or a measure of browser execution.

| Subsystem | Measured checks | Lines | Branches |
| --- | --- | --- | --- |
| Spec service | Spec HTTP/service integration | 77.0% | 59.1% |
| Verification Planner | Planner service integration | 82.1% | 60.7% |
| Circuit service | Circuit service package | 72.77% | 73.84% |
| AI Assistant | Assistant units; loaded files only | 89.1% | 76.2% |

Python and Vitest include untested source. Node coverage measures loaded source
only and is experimental. Small UI unit measurements cover local rules; their
line coverage does not measure the complete browser flows. See each HTML report
for all subsystem rows and measurement limits.

## Remaining evidence gaps

The new browser checks expose four failures:

- Spec Editor derives the new destination from the Spec name instead of using
  the selected destination. The existing-destination rejection check fails.
- Spec Editor document views omit running Activity jobs. The UI cannot reach
  Cancel for the controlled running job.
- Verification Planner sample creation does not provide an imported source
  snapshot.
- Verification Planner browser export uses GET for a POST-only interface.

The existing live wire-range saving timeout also fails. These results retain
normal assertions and remain failed. Earlier Circuit Designer focus and SVG
export checks passed in the final integration run; their historical failures
remain identified separately.

The live RTL evaluation did not confirm its required results. Its model attempts
do not count as successful hardware verification. Existing toolchain-dependent
hardware regression checks passed independently.

Docling-dependent imports remain unverified. Automated visual baselines,
additional browsers, broad accessibility/security matrices and performance
thresholds remain outside this effort. Required failing capabilities cannot be
accepted as completed coverage until the product behaviour passes the checks.

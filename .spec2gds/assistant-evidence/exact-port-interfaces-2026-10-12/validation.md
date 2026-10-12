# Exact port interfaces — implementation evidence

The changes are in project code. Native Harness sources were not changed.

- Assistant reviews omit the Configuration section and remove duplicate facts. Interfaces show Port ID, Definition, and Description. Numeric and symbolic bounds remain visible.
- Ports use their case-sensitive ID as the single identifier. Component and Design display names remain supported. New Assistant interfaces need descriptions.
- Approved interfaces include ranges, descriptions, parameter declarations, and required local constants and constant functions. Authoring cannot change approved interface values.
- The read-only Spec elaboration operation uses Verilator for symbolic constant expressions. It reports evaluated bounds, widths, parameter values, and diagnostics. Numeric bounds and scalars use direct calculation. Source expressions remain in the Spec and generated RTL.
- Stored parameter declarations supply generated module declarations. Parameter defaults and explicit overrides are checked. Negative signed parameter values use the compiler's declared type when decoded.
- Flow and instruction catalog release: 3.0.0. Historical records remain readable. Pending reviews with old width-only interfaces need a new review. Approval, revision, and receipt guards remain in place.

## Cleanup

`uv run python scripts/cleanup-port-labels.py --output /tmp/spec2gds-port-label-preview-20261012`

`uv run python scripts/cleanup-port-labels.py --apply --output /tmp/spec2gds-port-label-cleanup-20261012`

Cleanup removed 51 physical port labels from 10 Specs in this checkout. No labels were copied into descriptions. Each replacement was atomic and each original has a backup. A repeat preview found no labels to remove.

- [Preview](/tmp/spec2gds-port-label-preview-20261012/report.json)
- [Changes and durable backups](/home/ankdesh/explore/codex-spec2gds/spec2gds/.spec2gds/port-label-cleanup/2026-10-12/report.json)
- [Repeat preview, including durable backups](/tmp/spec2gds-port-label-final-recheck-20261012/report.json)

The saved `cla_4bit` in `/home/ankdesh/explore/codex-spec2gds/spec_samples/adder-1-spec.spec` was not changed. Its vector ports still use `3:0` and its supplied RTL still uses `4:1`. Its file modification time remains 2026-10-12 16:54:51 +0530. The defect was reproduced and corrected in a separate test fixture.

## Direct checks

- `.venv/bin/python -m pytest tests/spec/spec_format/test_rtl_interface.py -q`: 19 passed. Includes offset, ascending, negative, scalar, indexed one-bit, formulas, constant functions, dependent defaults, signed values, overrides, missing dependencies/defaults/compiler, read-only API, cleanup, creation, and Verilator simulation. [Log](/tmp/ports-interface-final.log).
- `node --test --test-name-pattern 'parameterized Component creation' tests/spec-flows.integration.test.mjs`: passed through the real Harness and Spec service. The full Harness profile also runs this check. [Log](/tmp/ports-native-parameterized.log).
- `.venv/bin/python -m pytest tests/spec/spec_format/test_rtl_interface.py -k label_cleanup -q`: passed after adding an in-checkout backup repeatability check. Durable backups use `.spec.bak` names so later cleanup runs leave them unchanged. [Log](/tmp/ports-cleanup-repeatability.log).
- `.venv/bin/python -m pytest tests/spec/spec_format/test_rtl_interface.py -k carry_lookahead -q`: passed after adding explicit reproduction of the `3:0` warning. [Log](/tmp/ports-cla-defect-fixture.log).
- The carry-lookahead adder fixture checks all 512 combinations of the two operands and carry input. Parameterized generated RTL is simulated and linted with an override.
- Browser checks cover review content, exact interface definitions, one identifier field, descriptions, reloads, comparisons, keyboard access, themes, narrow screens, and approval/recovery guards. [Review image](/tmp/spec2gds-exact-ports-integration-complete-20261012/spec-circuit-flow/01_ai_assistant_architecture.png).

## Profile results

- `scripts/test-all.sh fast --output /tmp/spec2gds-exact-ports-fast-complete-20261012`: passed, 11/11 suites. All three required live model checks passed: description edit, wire-range edit, and restricted description approval. [Report](/tmp/spec2gds-exact-ports-fast-complete-20261012/summary.html).
- `scripts/test-all.sh integration --scope assistant,shared --output /tmp/spec2gds-exact-ports-integration-complete-20261012`: passed, 26/26 suites. Includes the real Harness, public APIs, browser tests, end-to-end application flows, RTL Activities, and extended checks. [Report](/tmp/spec2gds-exact-ports-integration-complete-20261012/summary.html).
- `scripts/test-all.sh regression --output /tmp/spec2gds-exact-ports-regression-final-20261012`: failed, 28 passed suites and one failed suite (`live-generalization`). All deterministic, real-service, browser, end-to-end, and three live smoke suites passed. [Report](/tmp/spec2gds-exact-ports-regression-final-20261012/summary.html).

The broad live RTL evaluation attempted all 33 runs without substituting fixtures or retrying failed cases. It recorded three complete creation/simulation/refinement passes. [Stage report](/tmp/spec2gds-exact-ports-regression-final-20261012/live-generalization/summary.json), [full command log](/tmp/spec2gds-exact-ports-regression-final-20261012/live-generalization/command.log).

| Stage | Passed | Failed | Unverified |
| --- | ---: | ---: | ---: |
| Creation | 7 | 20 | 6 |
| Simulation | 5 | 2 | 26 |
| Saved refinement | 3 | 2 | 28 |

Creation failures include malformed or inconsistent architecture results, incorrect interface widths, invalid arithmetic widths, missing RTL variables, and multiple clocked drivers. Two simulations failed. Two refinements did not preserve the required source revision and were rejected by the existing guard. Six runs did not obtain a verified creation outcome; their traces and command diagnostics remain available. Stages after a failed creation were not treated as passed. Broad live-model creation and refinement reliability remain unverified as a general capability; this release does not claim a passing quality evaluation.

Earlier attempts and their original outcomes remain in their evidence directories. They have not been replaced with fixtures or rewritten as passes. The first complete regression report is [here](/tmp/spec2gds-exact-ports-regression-20261012/summary.html). It reported 26 passed and 3 failed suites. Adapter metadata mismatches caused its early Harness and Assistant browser failures; the final integration run passes both. The broad live evaluation recorded 8 complete passes out of 33 runs. The evaluation helper, cosmetic range comparison, and content prompt faults found in that run were corrected before the final runs. Some later profile commands stopped with exit 143 before they wrote final reports; the completed reports above are the final fast and integration evidence.

## Coverage limits

No required credentials or tools were missing for the completed fast and integration profiles. Node.js 24.13.1, Verilator 5.020, Playwright Chromium, the real Harness, and configured model credentials were used. Docling is installed in the test environment.

The complete parameterized creation check uses the real Harness and Spec service with scripted model responses. Generated parameterized RTL is also compiled and simulated. These checks establish the implementation behavior; they do not establish reliable live-model parameterized authoring. The broad live-model evaluation above failed.

SystemC and CIRCT are not configured. Nine optional hardware checks were skipped; those toolchains are not claimed as verified. The browser checks cover selected keyboard and responsive behavior, with screenshot evidence. Automated visual baselines and system-wide performance and accessibility thresholds remain outside this coverage.

The final in-checkout backup naming change was checked separately with the cleanup repeatability test and a new preview. Core Assistant, service, and RTL code did not change after the final profile runs.

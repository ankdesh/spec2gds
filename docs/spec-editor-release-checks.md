# Spec Editor release checks

The agreed UI cleanup and diagnostic sample Activity are implemented. Full
release clearance remains blocked by live model evaluation failures and the
existing conflict markers in `docs/testing-strategy.md`.

## Implemented behavior

- Options lists AI Assistant exploration, registered actions, and compatible
  Activities directly. Empty menus show a disabled No options available entry.
- Existing transaction and structured ports remain visible and read-only. Wire
  ports retain creation and editing. Hardware IDs and readable names have
  distinct labels.
- The document view omits Technical details. Jobs, artifacts, and reviews retain
  their diagnostic panels. Inactive Save, Undo, Redo, and Find entries are removed.
- Cut and Paste retain field selections and update native and SystemVerilog
  editor state. Empty clipboard text and clipboard failures preserve the draft.
  Hidden fields cannot be edited through the menu.
- `reference.spec_summary` version `2.0.0` exports selected-target and dependency
  Section data as JSON. The export includes hidden protocol tables, nested
  narrative, SystemVerilog content, relative source paths, and Section digests.
  It uses public SDK reads and does not run a compiler or change source.
- Command requests and downloads use the displayed Spec binding. Artifact lists
  refresh after job completion. Proposal review preserves an active draft and
  its authored revision.

## Commands and evidence

Profiles use the installed Node.js 24.13.1 runtime and the configured uv runtime.
The sandboxed uv command failed because of Snap permissions; the same configured
runtime worked outside the sandbox. An initial fast run with Node.js 22 was
incomplete. No required live checks were replaced or omitted.

| Command | Outcome | Evidence directory |
| --- | --- | --- |
| `scripts/test-all.sh fast` with Node.js 22 | Incomplete: Node.js 24.2+ required | `/tmp/spec2gds-release-fast` |
| `scripts/test-all.sh fast` with Node.js 24 | 10 suites passed; live wire-range failed | `/tmp/spec2gds-release-fast-node24` |
| `scripts/test-all.sh integration --scope spec,assistant,activities` | 23 suites passed; one outdated Circuit menu selector failed | `/tmp/spec2gds-release-integration` |
| `bash tests/ui-scenarios/run-test.sh --scenario automatic --presentation` after the selector fix | Passed | `/tmp/spec2gds-release-circuit-flow-recheck` |
| `scripts/test-all.sh regression` | 27 suites passed; export browser race and live generalization failed | `/tmp/spec2gds-release-regression` |
| Final `scripts/test-all.sh integration --scope spec,assistant,activities` | Passed: all 24 suites | `/tmp/spec2gds-release-integration-final` |

The focused Python SDK, projection, and service API run passed 33 tests. The
final Spec Editor browser suite passed all 26 checks. The final real-service Spec
suite passed all 23 checks, including JSON download and service restart. Browser
checks cover clipboard access denial, empty clipboard text, late command
responses, hidden fields, draft revision preservation, and artifact completion
without a reconnect. The final integration profile rebuilt the packaged assets. The bundle was
checked for the new controls and the absence of the More actions label.
`git diff --check` passed.

## Failure findings and coverage limits

The fast wire-range live check failed with `structured output already recorded`.
All three short live checks passed in the later regression profile. Both results
are retained; the earlier failure is not treated as a pass.

The regression export test exposed a confirmed UI race: terminal job events
updated execution status but left the artifact list stale. The UI now refreshes
authoritative Activity state on terminal events. A deterministic browser check
covers completion without a source change or reconnect. The corrected real-service
export test passed in the final integration profile.

The broader live RTL evaluation completed 33 runs. Creation had 23 passes and
10 failures. Simulation had 20 passes, 3 failures, and 10 unverified runs.
Refinement had 17 passes, 3 failures, and 13 unverified runs. Failures include
invalid generated widths, undriven signals, and authored revision preservation.
These remain release evaluation failures; this change does not alter model
prompts or generated hardware behavior.

SystemC and CIRCT checks remain outside executed coverage where `SYSTEMC_PREFIX`
or `CIRCT_PREFIX` is not configured. The profile evidence records these skips.
There are no automated visual baselines or system-wide performance and
accessibility thresholds. A real-flow screenshot was reviewed manually.

## API compatibility and remaining checks

The command controller is an optional document-surface interface. The edit
controller remains separate. Activity discovery, launches, cancellation, and
artifact downloads use the displayed Spec binding. Legacy calls without a
binding parameter retain their behavior. The SDK adds read-only
`context.spec.low.document_projection()` access. The sample Activity changes
from text output to diagnostic JSON at version `2.0.0`; existing stored artifacts
remain available.

Full regression was executed and its failures were retained. The broader live
model evaluation was not rerun to replace failures with passing results. The
final integration pass verifies the artifact-refresh and selector corrections;
it does not make the earlier fast or regression profiles pass.

## Other UI findings for a later decision

- The topology preview displays long internal Component IDs above instance
  labels. These can overrun the diagram cards. Prefer readable names and retain
  IDs in diagnostics when this renderer is revised.
- Document counts use plural labels for a single Component or Design.
- The browser tab title uses the rendering-layer name A2UI Document Editor.
  Use Spec Editor in a later naming cleanup.

The existing editor bindings database change was present before this work and
was not part of the implementation.

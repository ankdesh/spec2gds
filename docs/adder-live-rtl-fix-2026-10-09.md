# Live adder flow: cause and fixes

The current changes were committed as `461ad28` before this investigation.
The investigation covers the unsigned 4-, 8-, and 13-bit combinational adders.
The previous 33-run RTL result and each diagnostic result remain unchanged.

## Confirmed causes

- The architecture tool returned a pending review but let the model continue.
  Some turns opened a second approval question before the architecture card
  became available. The tool now ends the turn after its durable result.
- The initial content proposal required the model to reconstruct approved
  interfaces and references. Failed calls omitted the review ID, used architecture
  `width` fields instead of wire `range`, and mixed Component behavior with
  Design composition. A fresh context now supplies a canonical authoring
  template. Initial proposal admission requires the saved approval ID and the
  supported creation envelope. The requirement clears when the source changes.
- Scalar wire shorthand matched both wire and structured schema branches.
  Native admission now requires explicit discriminators for the other families,
  so valid wire shorthand reaches its existing formatter.
- Generic authoring errors did not identify the failed operation. Errors now
  include the operation number and target. Explicitly empty initial RTL bodies
  are rejected. Interface-only creation still permits omitted or null RTL.
- Safety lint found arithmetic width expansion. Rejected previews told the model
  to explain the failure and stop. The instructions now require correction of
  authoring and RTL errors through a new proposal, with explicit width sizing.
  The safety lint checks remain enabled.
- The browser evaluation read an unscoped active Spec. It now follows the exact
  creation receipt, checks document identity, and compares saved archive content
  before launching the Activity.
- The adder refinement request asked for an explanation, while the assertion
  required a saved revision change. The request now explicitly asks to append
  and save the explanation. The check preserves the original text verbatim,
  and retains the assertions for unchanged SV, interfaces, IDs, and wiring.

## Authority and evidence

The template supplies structure from an already approved architecture. It does
not infer RTL behavior or apply edits. The model must author the RTL and its
explanation. The Spec service still checks the source revision, approved
architecture, typed operations, preview, and durable application receipt.
The `rtl.generate` Activity consumes the saved SV and structured interfaces.
No model fixture replaces a live check.

The runner retains generated projects and model records for diagnosis. The
functional bench remains unchanged. It checks 512 inputs per adder run, including
carry propagation and overflow cases. Document quality still needs rubric review.

The first complete 8-bit diagnostic passed generation, lint, compilation,
simulation, and saved explanation refinement:
`/tmp/spec-editor-adder8-diagnostic-11-20261009/summary.html`.

## Verification commands

- `scripts/test-all.sh fast --output /tmp/spec-editor-adder-fix-fast-20261009`
- `scripts/test-all.sh integration --scope shared --output /tmp/spec-editor-adder-fix-integration-20261009`
- `scripts/test-all.sh regression --rtl-cases adder_4,adder_8,adder_13 --output /tmp/spec-editor-adder-fix-regression-20261009`

The selected regression retains all non-RTL suites and the three short live
checks. It uses the original three repeats for each adder. Other RTL families
are outside this run's declared live coverage. The default full regression still
runs all 33 RTL cases.

Final results are recorded below when the profiles finish.

# Layer 3: Recipes, Test IR and reference generation

Layer 3 links reviewed coverage to recipes, target bindings and trusted backend
configurations. The current built-in backend generates reference artifacts;
it does not generate executable cocotb/UVM/SVA tests or run a simulator.

## Records and checkpoints

`domain/recipes.py` defines recipes, oracle provenance, target bindings, backend
configurations and producer manifests. Bindings map semantic observation names
to physical targets and permissions. Recipes link intents/objectives and a
coverage checkpoint, with Test IR or external implementation metadata.

An implementation checkpoint freezes the reviewed recipes, bindings and backend
configuration with upstream coverage identity. Partial implementation is distinct
from coverage closure. Generation builds its inputs from the frozen checkpoint;
changing a draft does not silently alter a prior generation request.

## Current Test IR boundary

`domain/test_ir.py` declares clocks in femtoseconds, reset polarity/domain,
port width/direction, variables, reference models, properties and execution
limits. Setup/body/teardown and several expressions remain dictionary-shaped
payloads rather than a fully discriminated, recursively validated AST.
The declarations therefore describe portable intent; they do not implement its
execution semantics.

`RecipeValidator` currently checks recipe links/oracle rationale and selected
IR cases: output/read-only drives, sample-before-check references, identical
comparison operands, direct parallel driver/model conflicts, checks inside
zero-count repeats and declared checks that are never evaluated. It walks
selected top-level constructs; it is not a complete type checker, recursive
control-flow analyser, clock scheduler or reachability proof. Do not describe
acceptance as proof that every unknown nested construct is rejected.

The remaining portable semantics—typed expression rules, checked/wrapping
arithmetic, timing phases, bounded waits/loops, independent oracles and property
quality—are retained in [the backlog](verification-planner-backlog.md).

## Plugin and artifact flow

`BackendPlugin` has `describe`, `validate`, `lower` and `generate` methods.
`ResultAdapterPlugin` defines an extension interface, but no native tool-result
adapter is bundled. The default registry contains
`spec2gds.reference.bundle` version 1.0.0.

The reference plugin emits `test-ir.json`, `target-bindings.json`, `recipe.md`,
`producer-manifest.json`, `synthetic-result-template.json` and
`validation-report.json`. Its manifest says `executable: false` and
`produces_rtl: false`. The synthetic template must remain fixture evidence.

`OutputWriter` holds bytes in memory, refuses absolute/traversing or duplicate
artifact paths and limits total bytes. It is an artifact capability, not an
OS-level sandbox for trusted plugin code. `GenerationRunner` validates, lowers,
generates synchronously, stores artifacts in the content-addressed blob store,
and records the producer manifest/result. Matching successful jobs are reused.
Job cancellation updates status; it does not cooperatively interrupt plugin
execution. Restart recovery of running jobs is not implemented.

## Use and verify

Use `/plugins` for installed capabilities, `/recipes/{id}/validate` for current
preflight, `/generations/preview` for reviewed inputs and `/generations` for
reference generation under `/api/verification/v1/plans/{plan_id}` (the plugin
catalog itself is `/api/verification/v1/plugins`). Generated artifact endpoints
return their stored bytes. External simulation must occur outside this service.

Run `uv run python -m pytest testplan-service/tests/test_layer3_acceptance.py -q`.
These tests cover the reference backend and selected validators, not executable
backend correctness, isolation, asynchronous job recovery or complete IR semantics.

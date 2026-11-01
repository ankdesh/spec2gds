# Fix plan for issues #5 and #6

## Summary

Fix [Generate RTL in Spec Editor](https://github.com/ankdesh/spec2gds/issues/5)
and [child Design navigation in Circuit Designer](https://github.com/ankdesh/spec2gds/issues/6).
Use the published Harness release `0.1.6-ankdesh.2` for all checks.

The designer selected these behaviors:

- Generate RTL validates the saved target when clicked. A separate Verify action
  remains available. Saving source does not start lint.
- Open selected child design navigates in the same view. A Back control returns
  to the parent.

## Generate RTL

- Remove the Spec Editor's requirement for an existing passed verification receipt.
  Keep Generate RTL available for a saved Component or Design when no command is
  running. Activity discovery must not start Verilator or elaborate interfaces.
- In the Spec service, validate the requested source revision before enqueueing
  `rtl.generate`. Share the existing explicit target verification code. Check the
  selected target and its reachable implementations. Store the resulting receipt.
- Enqueue only after verification passes. Retain HTTP 409 for a stale source
  revision. Return HTTP 422 with the existing verification result for failed
  validation. Return HTTP 503 with that result when the required tool is unavailable
  and verification cannot finish. Failed checks must not enqueue a job or publish
  output.
- Refresh the document view after either outcome. Show the verification state and
  diagnostics beside the target. Remove the message that tells the designer to
  verify separately before retrying generation.
- Keep the successful launch response and the Activity output format unchanged.
  Keep generation deterministic and use the same source revision for verification
  and the Activity snapshot.

## Child Design navigation

- Complete the existing open-child handler in the reusable Circuit Designer app.
  Its current implementation resolves a child and only displays a message.
- For a source-bound parent, route component resolution through its authenticated
  Spec service binding. Add an internal `POST /circuit-designer/source/children`
  callback with `component_id` and `base_source_revision_hash`. Resolve the Circuit
  Component ID through the parent's current source map. Reject stale revisions.
- Require an explicit Component-to-internal-Design relationship in the Spec.
  Reuse the existing Circuit launch publication and binding logic to register the
  child under its stable document ID. Return the existing `ResolvedComponentDesign`
  shape. Keep callback credentials inside the services.
- Keep generic Component providers working through their existing interface.
  Register an available child document before opening it. Generic provider child
  views remain read-only in this change. Source-bound children retain their normal
  Save to Spec behavior and revision checks.
- Load the registered child through the normal document-loading path. Reset the
  parent selection, layout cache, proposals, and source binding. Load the child's
  saved layout and update the active document URL.
- Keep a parent document ID stack in the app and show Back when it is nonempty.
  Back loads the parent's current saved document. Block navigation while any
  private draft or edit lease is active. Do not release or discard it implicitly.
- Keep the current view when the child is unavailable or resolution fails. Show
  the returned reason. Reject a child already present in the navigation ancestry.
  A leaf Component must show that it has no internal Design.

## Tests and acceptance

- Use the checked-in one-cycle and two-cycle RTL samples, `rtl-test-2`, and
  `rtl-test-4` as positive cases. Both Component and entry Design verification
  passed during inspection. Generate RTL must work without a prior Verify action.
- Keep `single_component.spec` as a missing-implementation case. Keep
  `rtl-test-1` and `rtl-test-3` as negative cases: they currently reference a
  missing `mux` module and an undeclared `add` signal. Show those diagnostics and
  preserve the saved source. Do not infer implementations or rewrite the samples.
- Cover current, failed, stale, and missing verification receipts; unavailable
  Verilator; a stale source revision; repeated clicks; and output atomicity at
  the Spec service and Activity layers.
- Use the existing programmatic composite Spec fixture for hierarchy tests.
  Check child instances, nets, and boundary terminals; nested navigation; Back;
  leaf Components; provider failures; cycle prevention; and active drafts.
- Add real-browser protection for both reported behaviors. Check that child edits
  save to the correct internal Design and leave parent topology unchanged.
- Run `scripts/test-all.sh fast`,
  `scripts/test-all.sh integration --scope spec,circuit,activities,shared`, and
  `scripts/test-all.sh regression`. Keep evidence in a new ignored repository
  `TEMP_` directory. Report unavailable prerequisites and incomplete checks.

The exact `u_block` / `add_invert8` issue sample is not in the available files.
The existing composite fixture supplies an explicit equivalent hierarchy.
The Back stack is local to the current app view; reloading opens the active child
from its URL and starts a new stack. No Spec archive migration is required.

# Harness assistant architecture

The implementation is a layered DSH product with two profiles:

- `spec2gds-web` composes `dsh-base`, `dsh-web-app`, the spec2gds host bundle,
  and the spec2gds client bundle;
- `spec2gds-headless` composes `dsh-base`, `dsh-headless`, and the same host
  bundle for one-off terminal requests.

`harness.product.json` is the profile recipe. The two product-owned Cordis
patches are deliberately separate: `profile/cordis.patch.yml` defines shared
agent policy and host behavior, while `bundles/web/cordis.patch.yml` defines
browser-only UI policy.

## Ownership

DSH owns session creation after the product reserves an ID, JSONL persistence,
the agent/model loop, tool call/result pairing, streaming, cancellation,
reconnect, rename, archive/restore, export, and conversation rendering. The web
profile disables DSH coding presets so a session cannot silently regain shell,
filesystem, web, workflow, subagent, or skill tools from the default `standard`
preset.

The host plugin in `src/index.ts` owns:

- immutable Spec/Circuit bindings and SQLite review metadata;
- exact owner allowlists and owner clients;
- `get_bound_context`, `prepare_spec_proposal`, and
  `prepare_circuit_proposal`;
- reservation, activation, review-action, launch, health, and readiness routes;
- binding the domain tools and editing contract to the DSH agent lifecycle.

The browser plugin in `client/index.js` owns only product presentation:

- brand slots;
- the new-session binding dialog;
- the reserve → DSH create → activate transaction;
- keyed tool views for the two proposal tools;
- Spec before/after field diffs and Circuit before/after topology diagrams;
- explicit discard, apply, send, and reconcile actions.

It does not rebuild the transcript or pair tool events. DSH's
`ui-conversation` and `ui-tool` plugins remain authoritative, and the product
registers keyed replacements through `tool.call.toolview`.

## Binding transaction

For a fresh browser session, the product validates the existing owner document
and writes a `creating` binding, asks DSH to create a session with the reserved
ID and scratch directory, then activates the binding and attaches the tools. A
failed DSH creation abandons the reservation. On startup, creating bindings
whose DSH transcript exists are activated; orphan reservations are removed.

The headless profile carries the same binding as `SPEC2GDS_BINDING_JSON` for a
fresh request. The host plugin validates and attaches it when DSH publishes the
agent. A resumed `--session-id` uses the existing persisted binding.

## Proposal safety

Model-visible tools are non-mutating. `get_bound_context` reads current owner
state. Proposal tools normalize typed operations, bind them to the current
revision, request an owner preview, and persist the exact artifact plus a digest.
The model cannot call apply or send.

Review-card actions reload the server-stored artifact, validate its digest and
revision, atomically claim the review state, and then call the owner. Uncertain
mutation outcomes enter `reconcile`; later actions query owner history using the
stable proposal ID before retrying. Browser requests never supply replacement
artifact content.

Circuit Designer remains process-local. Conversation and review metadata survive
its restart, but a bound document must be reopened before an old Circuit review
can be reconciled.

## State boundaries

DSH JSONL is the durable transcript. SQLite stores bindings and proposal review
records only. Scratch directories exist because DSH sessions require a working
directory, but the product exposes no filesystem or shell tools. Permanent
transcript deletion is not added because DSH persistence is append-only;
archive/restore is retained.

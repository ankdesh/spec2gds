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

## Prompt composition

The shared profile contributes only the deployment identity. A bound agent then
adds four typed, agent-scoped sections in deterministic order:

1. domain persona (`100`);
2. immutable binding and fresh-context rule (`150`);
3. Spec or Circuit operation constraints (`200`); and
4. output and unsupported-request contract (`300`).

Bound sections are composable and do not use Harness's `complete` flag. This
allows the deployment persona and any deliberately enabled Harness sections to
coexist with the product contract. Tool descriptions remain the authoritative
schema-level call guidance and are not duplicated into new prompt sections.

An unbound agent is the deliberate exception. It receives one `complete: true`
fail-closed section, no domain tools, and instructions to open a new bound
conversation. In the pinned Harness, an effective complete section becomes the
entire system prompt after assembly, suppressing every other prompt section.

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

Proposal preparation is divided into stable product-owned stages:

1. the DSH tool schema admits model arguments;
2. domain semantic checks and normalization build an immutable owner artifact;
3. the owner validates and previews that artifact;
4. the product persists the review, normalized error, and artifact digest;
5. deterministic presentation is derived from the stored artifact and owner
   preview; and
6. only an explicit HTTP review action can enter the owner mutation path.

The direct path remains active. A future optional plan-review state can be
inserted between artifact construction and owner preview without changing the
Spec/Circuit operation schemas or apply/send contracts. Harness plan mode is
not enabled by this seam.

Review-card actions reload the server-stored artifact, validate its digest and
revision, atomically claim the review state, and then call the owner. Uncertain
mutation outcomes enter `reconcile`; later actions query owner history using the
stable proposal ID before retrying. Browser requests never supply replacement
artifact content.

Circuit Designer remains process-local. Conversation and review metadata survive
its restart, but a bound document must be reopened before an old Circuit review
can be reconciled.

## Results and errors

Both proposal tools return one product envelope. Accepted previews use
`success: true`; unsupported, invalid, stale, rejected, locked, unavailable,
contract, and internal failures use `success: false` plus a stable error code.
Owner diagnostics remain nested unchanged and are also normalized into issues.
Suggested actions are propagated only when supplied by an owner.

Every public review includes a change summary derived from the operation list
and owner diff. Model-authored title, summary, and rationale remain visible as
request context but are not treated as evidence of a change. DSH continues to
own pre-execution JSON-schema failures; the product view falls back to the
generic Harness tool error when execution never begins.

## Evaluation and replay

The versioned corpus under `evals/` records Spec and Circuit intents, allowed
outcomes, expected operation families, and safety assertions. `npm run eval`
validates the corpus and can aggregate an uncompressed DSH Session JSONL into
raw results and metrics.

The Harness integration test records a real headless Session and replays it
through the pinned `@deepseek-ai/dsh-llm-replay` adapter with a dead provider
endpoint. The replay profile and uncompressed persistence setting are generated
only for tests; neither changes the production profiles or their zstd storage.

## State boundaries

DSH JSONL is the durable transcript. SQLite stores bindings and proposal review
records only. Scratch directories exist because DSH sessions require a working
directory, but the product exposes no filesystem or shell tools. Permanent
transcript deletion is not added because DSH persistence is append-only;
archive/restore is retained.

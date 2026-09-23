# AI Assistant

The optional `ai-assistant/` application is a focused DeepSeek Harness product.
DSH supplies the complete chat shell and runtime; spec2gds augments it with
permanent document bindings, owner-aware tools, and proposal review cards. The
former Python/FastAPI/A2A service and custom assistant-ui application have been
removed.

Each conversation is immutably bound to one Spec document, Spec entity, or
Circuit document. The model can read fresh owner context and prepare typed
previews. It has no owner mutation, source creation, filesystem, shell, browser,
or skill tools. The selected `focused`, `goal`, or `orchestrated` preset controls
whether bounded workflow, goal, and read-only delegation capabilities are
present. Spec apply and Circuit send happen only from an explicit review-card
action using the artifact persisted by the server.

See [DSH UI migration and extension map](dsh-ui-migration.md) for the plugin
architecture and the retained/extended/dropped feature table.

## Editor integration

The editor launch paths remain stable:

- `/launch/spec-document` binds a complete Spec document;
- `/launch/spec` binds one Spec entity;
- `/launch/circuit` binds a Circuit document.

The Spec Editor continues to own semantic context, preview, validation, revision
checks, and atomic application. Circuit Designer continues to own snapshots,
operation preview, diagnostics, revisions, and submitted proposals. Discussion
and model output alone never mutate either source.

For a bound conversation, the model prompt composes the shared product identity
with four ordered sections: the domain persona, immutable binding and mandatory
fresh-context rule, owner-specific operation constraints, and output contract.
These sections coexist with deliberately enabled Harness prompt content. An
unbound conversation instead receives a single complete fail-closed prompt and
no domain tools, so it cannot make design claims or prepare proposals.

Document-scoped Spec conversations can propose only `create_entity`. Entity
scope supports the complete Spec assistant operation vocabulary and enforces
the owner's writable boundary. Circuit scope supports the complete logical
operation vocabulary for components, instances, boundary terminals, nets, and
endpoints; geometry, routes, labels, and layout remain outside AI operations.

## Run the browser profile

Use Node.js 22.19+ or Node.js 24+ and the pinned built Harness fork.

```bash
cd ai-assistant
npm install
npm run build
export OPENAI_API_KEY="..."
HARNESS_SOURCE=/home/ankdesh/explore/deepseek-harness npm run dev
```

Open `http://127.0.0.1:6013`. The combined `scripts/serve-all.sh start`
launcher uses the same profile and port. The browser new-session button opens a
design-source chooser for configured Spec and Circuit services. It can connect
another service for the current process or create a new Spec or empty Circuit.
Editor launch links bypass the chooser with an already validated exact target.
After rebuilding either the product bundle or the pinned Harness checkout, run
`scripts/serve-all.sh restart`; `start` deliberately refuses a stale or partial
stack already occupying the default ports.

The browser profile omits DSH's generic Models settings/onboarding
plugin. Configure the OpenAI provider through `OPENAI_API_KEY`,
`OPENAI_BASE_URL`, and `OPENAI_MODEL`; the conversation model selector remains
available for configured models.

The new-conversation dialog offers three immutable execution presets:

| Preset | Behavior |
| --- | --- |
| `focused` | One-shot Q&A and ordinary typed proposals; no goal or delegation tools |
| `goal` | A durable, review-aware workflow plus DSH's bounded goal loop |
| `orchestrated` | Goal behavior plus one-shot, depth-one, read-only analysis children |

Service instructions remain identical across presets and come from exact,
versioned YAML prompt bundles. The generic `prepare-reviewed-change` workflow
is specialized by exact Spec/Circuit adapter manifests. Its full snapshots,
catalog digests, budgets, draft, checkpoint, and pending human decision are
durable DSH Session events. The browser dock exposes human pause, resume,
cancel, and answer controls. Proposal apply/send is the completion approval;
discard cancels the workflow.

Focused turns default to three model steps. Goal and orchestrated turns allow
eight steps while the workflow adds round, request, token, time, child,
concurrency, and depth budgets. Each model response remains capped at 1,200
output tokens. Orchestrated children inherit the immutable binding but can use
only `get_bound_context`; they cannot propose, ask the user, mutate workflow
state, or delegate again.

## Design-source workspaces

A Workspace represents a logical design source, not an arbitrary directory.
One `.spec` package owns one Workspace. Circuit documents projected from that
specification join the same Workspace through their source binding; an
independent Circuit document owns its own Workspace. The stable private path
under `SPEC2GDS_SCRATCH_ROOT` is only a DSH grouping identity.

Opening the Assistant from an editor always starts a new conversation focused
on the launch target. Starting from a Workspace offers only that Spec and its
source-derived Circuits. Starting globally can browse configured services or
create a design source. A conversation never changes target after creation.

## Submit one request from the command line

```bash
cd ai-assistant
npm run request -- \
  --domain circuit \
  --service-url http://127.0.0.1:6011/api/circuit-designer/v1 \
  --document-id my-circuit \
  -- "Explain the clock and reset topology."
```

This starts `spec2gds-headless`, submits one prompt, prints the answer, and
exits. Add `--json` for event output. Use `--session-id <id>` instead of binding
arguments to continue an existing conversation. Native releases expose the
same interface as `node deployment/request.mjs`.

## Configuration and trust

| Variable | Default |
| --- | --- |
| `ASSISTANT_HOST` | `0.0.0.0` |
| `ASSISTANT_PORT` | `6013` |
| `ASSISTANT_STATE` | `ai-assistant/.dev` in development |
| `SPEC2GDS_SCRATCH_ROOT` | `<state>/workspaces` |
| `SPEC_DOCUMENT_ROOT` | `<state>/spec-documents` |
| `SPEC2GDS_CATALOG_ROOT` | Product package's `profile/catalog` (set by launch scripts) |
| `OPENAI_MODEL` | `gpt-4o-mini` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| `SPEC_SERVICE_ALLOWLIST` | `http://127.0.0.1:6010` |
| `CIRCUIT_SERVICE_ALLOWLIST` | `http://127.0.0.1:6011/api/circuit-designer/v1` |
| `ASSISTANT_MAX_STEPS_PER_TURN` | `3` |
| `ASSISTANT_MAX_OUTPUT_TOKENS` | `1200` |

Owner allowlists accept comma-separated exact URLs and are rechecked on every
owner-backed operation. The web routes enforce same-origin requests. This is a
trusted single-user service and must not be treated as an authenticated public
multi-user application.

## State and recovery

DSH JSONL is the transcript source of truth. `assistant.sqlite3` stores immutable
bindings, Workspace identities, and review metadata. Back up the complete state root together. DSH
provides rename, archive/restore, and export. Permanent deletion is not exposed
because the current persistence contract is append-only.

The removed Python assistant's SQLite files are preserved under
`generated/legacy-ai-assistant-state/` and are not loaded. A2A and the former
chat REST/SSE API are intentionally unsupported.

Circuit documents and pending owner proposals remain process-local to Circuit
Designer. A Harness conversation survives a Circuit restart, but the bound
document must be reopened before an old review can reconcile.

## Verification and packaging

```bash
cd ai-assistant
npm run typecheck
npm test
npm run build
npm run test:harness
npm run eval -- --output /tmp/spec2gds-assistant-eval
npm run package -- /tmp/spec2gds-assistant-release
```

The unit suite protects the catalog prompt/domain rules, preset capability
boundaries, workflow controls, and complete
operation vocabularies. The integration test boots the real headless profile
against local owner/model fixtures and verifies context dispatch, proposal
preview, and durable SQLite state. Packaging refuses a dirty Harness checkout
or a commit different from `harness.lock.json`.

Proposal failures use one structured Spec/Circuit envelope, and review cards
lead with a deterministic summary derived from owner preview rather than model
prose. The Harness test records and keylessly replays the model trajectory; the
versioned corpus and metric definitions are documented in
[AI assistant evaluation](ai-assistant-evaluation.md).

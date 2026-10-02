# AI Assistant

The optional `ai-assistant/` application is a focused DeepSeek Harness product.
DSH supplies the complete chat shell and runtime; spec2gds augments it with
permanent document bindings, owner-aware tools, and proposal review cards. The
former Python/FastAPI/A2A service and custom assistant-ui application have been
removed.

Design conversations are immutably bound to one Spec document, Spec entity, or
Circuit document. An unbound conversation is also available for general
discussion when no specification is open, but it receives no design context or
proposal tools. A browser root chat can stage a new Spec package through an
editable creation card, whether it is bound or unbound. A bound model can read
fresh owner context and prepare typed previews. The model has no direct owner
mutation, filesystem, shell, browser, or skill tools. The selected `focused`,
`goal`, or `orchestrated` preset controls
whether native goals and persistent read-only event agents are present. Spec submissions follow the owner's approval policy: automatic by
default, or explicit review with `--require-human-approval`. Circuit send keeps
its explicit review action. The latest proposal card is
kept in the completed turn footer, independent of the collapsible tool-call
trace, so its actions remain available after the response finishes.

See [DSH UI migration and extension map](assistant-ui.md) for the plugin
architecture and the retained/extended/dropped feature table.

Use Node 24.2+ or 22.19+ in the 22.x line. The pinned Harness CLI uses
[`import.meta.main`](https://nodejs.org/api/esm.html#importmetamain), added in
Node 24.2 and backported to Node 22.18. Node 24.0/24.1 cannot launch the CLI;
the product launcher reports that incompatibility before creating runtime state.
For the combined stack, use Node 24.2+ to meet both workspace requirements.

## Editor integration

The editor launch paths remain stable:

- `/launch` opens an authenticated, unbound conversation;
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
no domain tools, so it cannot make design claims or prepare proposals. The
browser root creation tool is its one source-creation exception.

Document-scoped Spec conversations can create and refine entities throughout
their bound package with the supported operation vocabulary. Entity scope
enforces the narrower owner's writable boundary. A component `create_entity`
may carry its initial profiled ports and one module-body SystemVerilog section so the
change is applied atomically. Circuit scope supports the complete logical
operation vocabulary for components, instances, boundary terminals, nets, and
endpoints; geometry, routes, labels, and layout remain outside AI operations.

## Run the browser profile

Use Node.js 22.19+ in the 22.x line or 24.2+ for the Assistant (Circuit Designer alone declares Node 24+).
Prepare the selected Harness source checkout and product bundles from the repository
root. The new native event packages are not published; use source linking:

```bash
scripts/setup-all.sh
cd ai-assistant
export OPENAI_API_KEY="..."
npm run dev
```

The setup script clones/builds `DSH_BRANCH` (default `spec2gds/integration`)
and links local native packages. `HARNESS_SOURCE=/absolute/path` selects the
checkout; `DSH_REPO` and `DSH_REPO_HTTPS` select clone origins. It currently
follows a branch rather than enforcing `harness.lock.json` during setup. Check
that the checkout matches the lock before native testing or packaging;
packaging enforces a clean matching revision. There is no `setup:harness` npm
script or `--update-harness` option. Do not use `npm ci` for the unpublished
package baseline. Clone/fetch/install need network access.

Rerunning setup repairs stale package and developer-tool links, including dangling
links from a deleted checkout. The linker uses the Harness `typescript` and `tsx`
packages and their actual executable files; pnpm's shell wrappers are not copied.
Existing installed package directories and executable files are backed up under
`ai-assistant/node_modules/.harness-links-*`. Setup always saves the canonical
Harness path in `ai-assistant/.env` while retaining other settings, comments and
permissions. Relative destinations resolve from the repository root, and nested
checkouts and symlinked destinations persist their actual checkout path. See
[Harness setup troubleshooting](harness-setup-troubleshooting.md) for verification
and recovery commands.

Open `http://127.0.0.1:6013`. The combined `scripts/serve-all.sh start`
launcher uses the same profile and port, prints the URL, and does not open a
browser automatically. The browser new-session button opens a
design-source chooser for configured Spec and Circuit services. It can connect
another service for the current process or create a new Spec or empty Circuit.
Alternatively, request a new Spec document directly in any browser root chat.
Automatic owners create `SPEC_DOCUMENT_ROOT/<documentId>.spec` and continue
in a separate document chat with the original request. Restricted owners show
the editable creation card. Package creation activates the new Spec document;
existing conversations remain bound to their exact package. See
[specification creation from chat](assistant-spec-creation.md) for the flow,
retry behavior and persistent package bindings.
Editor launch links bypass the chooser with an already validated exact target.
After rebuilding either the product bundle or the Harness checkout, run
`scripts/serve-all.sh restart`; `start` deliberately refuses a stale or partial
stack already occupying the default ports.

The browser profile omits DSH's generic Models settings/onboarding
plugin. Configure the OpenAI provider through `OPENAI_API_KEY`,
`OPENAI_BASE_URL`, and `OPENAI_MODEL`; the conversation model selector remains
available for configured models. The OpenAI route always adds `gpt-5.6-luna`
to that selector while retaining `OPENAI_MODEL` as the default; the configured
endpoint and API key must have access to the selected model.

The new-conversation dialog offers three immutable execution presets:

| Preset | Behavior |
| --- | --- |
| `focused` | One-shot Q&A and ordinary typed proposals; no goal or delegation tools |
| `goal` | Native goal continuation with shared host accounting and review holds |
| `orchestrated` | Persistent event-driven analyst/reviewer reactions; primary owns proposals |

Service instructions come from exact YAML prompt bundles. Event rosters, typed
payload schemas, subscriptions, and Markdown prompts are validated against trusted deployment capabilities
and pinned to the conversation. The execution dock supplies
pause/resume/stop, spending, failures, and acknowledged manual retry. Restart
requires human Resume. Owner apply/send/discard records a review event without
automatically completing a goal. See [event configuration](event-driven-assistant-system.md) and
[operations](event-driven-assistant-operations.md).

Every browser root preset also exposes DSH's structured `ask_user_question`
tool. Fully specified automatic Spec proposals skip confirmation cards and
record defaults as assumptions. Restricted component proposals retain the
details card. Either domain may request a card for genuinely missing required
fields. **Continue proposal** stores confirmed values as structured state
and sends them into the same Session. The model authors the typed operations
using those values; the Assistant does not synthesize ports or SystemVerilog.
Automatic Spec submissions await validation and save, then display **Applied
automatically** with the saved revision. Restricted owners show the
owner-previewed approve/apply card. Non-proposal questions use the Harness composer
takeover. The goal/orchestrated primary can also wait durably for a correlated
human answer, declared event or owner review through `wait_for_event`. Headless
mode and specialist agents do not expose browser question/details cards.

The proposal tool's operation shape is fetched from the selected owner at
agent attachment. The owner publishes a binding-specific JSON Schema and
validates against it before preview. The Assistant checks it before calling
the owner. Changed Spec contracts refresh on a context read in the existing
conversation. Spec preparation requires the model's authored
`base_source_revision_hash`; stale context cannot be silently advanced. See the
[owner operation schema contract](assistant-owner-operation-contract.md).

Focused turns default to three model steps and receive one extra step only
after a visible structured-question call in that turn. Goal and orchestrated
turns allow eight steps, with aggregate round, request, token, active-time,
member, concurrency, queue, event, byte, and causal-depth bounds. Responses
remain capped at 1,200 output tokens. Specialist agents inherit the immutable
owner binding and may read context, inspect execution, and publish permitted
events; proposal tools belong to the primary.

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
bindings, Workspace identities, creation progress, review metadata, event
template revisions and exact conversation pins. Back up the complete state root together. DSH
provides rename, archive/restore, and export. Permanent deletion is not exposed
because the current persistence contract is append-only.

The removed Python assistant's SQLite files are preserved under
`generated/legacy-ai-assistant-state/` and are not loaded. A2A and the former
chat REST/SSE API are intentionally unsupported.

Circuit documents and pending owner proposals remain process-local to Circuit
Designer. A Harness conversation survives a Circuit restart, but the bound
document must be reopened before an old review can reconcile.

Spec bindings include a persistent `owner_document_key` for the canonical
package path. They survive visible-document switches and owner restarts;
copied packages with equal document IDs are distinct. The owner stores pending
submissions and events durably, and reconciles interrupted saves from atomic
package decisions. Existing pending reviews still require a decision after an
upgrade. See [iterative refinement](spec-editor-iterative-refinement.md) for
live views, drafts, history, and restricted launch commands.

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

The unit suite protects Harness bootstrap safety, catalog prompt/domain rules,
preset capability boundaries, execution controls, and complete operation
vocabularies. Native setup/bootstrap reproducibility remains a separate hardening task;
there is no dedicated bootstrap test script in this checkout. The integration test boots the real headless
profile against local owner/model fixtures and verifies context dispatch,
proposal preview, and durable SQLite state. Packaging refuses a dirty Harness
checkout or a commit different from `harness.lock.json`.

Proposal failures use one structured Spec/Circuit envelope, and review cards
lead with a deterministic summary derived from owner preview rather than model
prose. The Harness test records and keylessly replays the model trajectory; the
versioned corpus and metric definitions are documented in
[AI assistant evaluation](ai-assistant-evaluation.md).

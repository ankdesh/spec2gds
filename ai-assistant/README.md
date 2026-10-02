# spec2gds Harness assistant

This package is a DeepSeek Harness product, not a standalone chat server. DSH
owns the browser shell, conversation transport, model loop, cancellation,
session navigation, archive/restore, rename, export, and durable transcript.
The spec2gds layers add immutable editor bindings, versioned prompt/event
catalogs, three execution presets, domain tools, proposal reviews, product
branding, and Spec/Circuit diff cards.

There is no Python/FastAPI/A2A assistant and no compatibility API for the old
custom UI. The only product HTTP routes are the small `/spec2gds-api` extension
used for bindings, explicit review actions, monitoring, and reviewed event-template configuration, plus the stable
editor launch URLs.

Use Node 24.2+ or 22.19+ in the 22.x line. The pinned Harness CLI uses
[`import.meta.main`](https://nodejs.org/api/esm.html#importmetamain), added in
Node 24.2 and backported to Node 22.18. Node 24.0/24.1 cannot launch the CLI;
the product launcher reports that incompatibility before creating runtime state.
For the combined stack, use Node 24.2+ to meet both workspace requirements.

## Requirements

- Node.js `^22.19.0` or Node.js 24.2+
- network access when preparing DSH or installing dependencies
- `OPENAI_API_KEY` for model turns
- a running Spec Editor or Circuit Designer owner for a new bound conversation

Prepare the entire workspace, including Harness and product bundles, with:

```bash
# From workspace root
scripts/setup-all.sh
```

The script manages the sibling `../deepseek-harness` checkout by default.
Set `HARNESS_SOURCE` to select another destination. Source development links
native packages and the toolchain from that checkout; use this setup path
instead of installing the unpublished event packages from npm.

## Browser development

```bash
# Run the complete environment setup (first time or after dependency changes)
scripts/setup-all.sh

cd ai-assistant
export OPENAI_API_KEY="..."
npm run dev
```

Open `http://127.0.0.1:6013`. New conversation opens a browse-only target
chooser for configured Spec and Circuit services. The global chooser can
connect another service for this process or create a new Spec or empty Circuit;
a Workspace-row action stays within that logical design source. The same dialog
chooses an immutable `focused`, `goal`, or `orchestrated` preset. Focused is
one-shot; goal adds bounded native continuation; orchestrated uses persistent
read-only analyst and reviewer agents. Valid Spec submissions save automatically
by default. Start the owner with `--require-human-approval` for component details
and explicit review cards. Fully specified automatic requests skip confirmation;
defaults become assumptions. Missing required values still request clarification.
Initial wire ports and module-body SystemVerilog can be saved in one atomic
create operation. Automatic cards display the saved revision and **Applied
automatically** after the owner responds.
Other immediate questions use Harness's structured question surface. Headless
requests remain noninteractive.
In any browser root chat, including an unbound chat, ask to create a new
specification and include its design requirements if desired. Automatic owners
create it and continue without confirmation; restricted owners show the editable
creation card and **Create specification and continue**. The package
is saved under `SPEC_DOCUMENT_ROOT/<documentId>.spec`, and a separate chat
continues the original request. Existing chat bindings stay attached to their
original package even when another package opens. Circuit changes retain their
approval and save behavior. For retry and package binding behavior, see the
[specification creation guide](../docs/assistant-spec-creation.md).
The existing editor links also work:

- `/launch` for an authenticated conversation without attached design context
- `/launch/spec-document?service_base_url=...&document_id=...`
- `/launch/spec?service_base_url=...&document_id=...&entity_kind=...&entity_id=...`
- `/launch/circuit?service_base_url=...&document_id=...`

Proposal review cards remain in the completed turn footer after Harness
collapses the tool-call trace, so approve, discard, reconcile, and send actions
stay available.

## Event templates and execution inspection

For `goal` and `orchestrated`, the new-conversation dialog offers **Event template** and **Configure event template**. Edit agents, prompts, approved routes/capabilities, payload contracts, subscriptions and limits in the visual form or its canonical JSON text. Validate and review the diff before saving. Built-in edits create named templates; saved edits advance a revision. Conversations pin their selected revision and never adopt later changes silently.

The execution dock's **Inspect configuration and execution** shows pinned configuration, causal event ancestry, matched subscriptions, deliveries/activations/retries, request charges and external source state. Native session-history controls open the participating agent transcripts. See [events, presets and plugins](../docs/event-driven-assistant-system.md) and [the tutorial for both presets](../docs/event-driven-assistant-tutorial.md). The tutorial also gives the isolated browser-tool setup and `npm run test:ui` command for the three keyless Chromium tests.

## Focused Spec command-line workflow

The two user-facing workspace commands live in the root `scripts/` folder as
`spec2gds_assistant.py` and `spec2gds_spec.py` and are installed as Python
entry points in the root `uv`/`.venv` environment. Node and Harness run internally for the assistant
turn:

```bash
# From the repository root, after scripts/setup-all.sh
export OPENAI_API_KEY="..."
uv run spec2gds-assistant ./work/timer --preset focused -- "Propose a timer."
uv run spec2gds-assistant ./work/timer --require-human-approval -- "Refine the timer."
uv run spec2gds-spec reviews ./work/timer
uv run spec2gds-spec approve ./work/timer proposal_...
```

The assistant command prompts once and automatically saves valid submissions.
Its `--require-human-approval` flag leaves them pending. The Spec command lists,
approves, rejects, and paginates history; it does not run a model turn. See the
[focused Spec workspace guide](../docs/spec-workspace-cli.md) for path selection,
retry behavior, and run/proposal records intended for later `agent_eval` scripts.
The lower-level `scripts/request.mjs` remains an internal Harness test and
integration entry point.

## Configuration

| Variable | Default |
| --- | --- |
| `ASSISTANT_HOST` | `0.0.0.0` |
| `ASSISTANT_PORT` | `6013` |
| `ASSISTANT_STATE` | `ai-assistant/.dev` in development |
| `ASSISTANT_PROFILE` | `spec2gds-web` |
| `SPEC2GDS_SCRATCH_ROOT` | `<state>/workspaces` |
| `SPEC_DOCUMENT_ROOT` | `<state>/spec-documents` |
| `OPENAI_MODEL` | `gpt-4o-mini` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| `SPEC_SERVICE_ALLOWLIST` | `http://127.0.0.1:6010` |
| `CIRCUIT_SERVICE_ALLOWLIST` | `http://127.0.0.1:6011/api/circuit-designer/v1` |
| `SPEC2GDS_CATALOG_ROOT` | Product package's `profile/catalog` (normally set by the launcher) |

The OpenAI route always offers `gpt-5.6-luna` in the conversation model
selector in addition to the `OPENAI_MODEL` value. `OPENAI_MODEL` remains the
default, so adding Luna does not change existing sessions or deployments.
The configured API key and compatible endpoint must grant access to the model.

Owner allowlists are comma-separated exact URLs. Stored owner URLs are checked
against the current allowlist before every owner-backed operation. This is a
trusted single-user application; it is not an authenticated multi-user server.

One `.spec` package maps to one DSH Workspace. Source-bound Circuit documents
join the source Spec Workspace; independent Circuits receive their own. Each
conversation retains its exact document or entity binding permanently.

Prompt bundles and event-system templates load from strict startup YAML, with
Markdown prompts pinned to each conversation. Both updated presets have
aggregate host-owned budgets and pause/resume/stop controls. A process restart
requires human Resume; uncertain deliveries require acknowledged manual retry.
The owner review boundary remains in force. See the
[execution operations](../docs/event-driven-assistant-operations.md).

For a guided explanation of the DSH components and how these layers compose,
read the [current assistant architecture](../docs/configurable-assistant-architecture.md).

The [agentic systems architecture report](../docs/agentic-systems-architecture-report.md)
explains the delivered event/goal execution boundary and the requirements for
a future workflow policy. It does not introduce a workflow loader format.

## Verify and package

```bash
npm run typecheck
npm test
npm run build
npm run test:harness
npm run eval -- --output /tmp/spec2gds-assistant-eval
npm run package -- /tmp/spec2gds-assistant-release
```

The integration test uses local owner and OpenAI-compatible fixtures. Packaging
requires the Harness checkout to be clean and at the commit in
`harness.lock.json`.

The integration suite records its successful Session and replays it through
the pinned DSH keyless replay adapter, proving that replay does not contact the
provider. The evaluation command validates the versioned corpus and writes raw
results and metrics; see `docs/ai-assistant-evaluation.md` in the repository.

Harness JSONL is the transcript source of truth. `assistant.sqlite3` stores
bindings, creation requests, review metadata, event template revisions and
conversation configuration pins. Creation requests retain
their original prompt and package/chat progress across reloads and restarts.
The native event-system domain stores members, deliveries, and spending. Back up the complete state root together. Old Python
assistant data is preserved under `generated/legacy-ai-assistant-state/` for
manual inspection and is never loaded by this product.

HTTP condition monitoring, durable waiting, and controlled retries are documented in [operations](../docs/event-driven-assistant-operations.md).

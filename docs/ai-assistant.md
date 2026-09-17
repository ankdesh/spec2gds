# AI Assistant

The optional `ai-assistant/` application is a focused DeepSeek Harness product.
DSH supplies the complete chat shell and runtime; spec2gds augments it with
permanent document bindings, owner-aware tools, and proposal review cards. The
former Python/FastAPI/A2A service and custom assistant-ui application have been
removed.

Each conversation is bound to one existing Spec document, Spec entity, or
Circuit document. The model can read fresh owner context and prepare typed
previews. It has no owner mutation, source creation, filesystem, shell, browser,
workflow, skill, or subagent tools. Spec apply and Circuit send happen only from
an explicit review-card action using the artifact persisted by the server.

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
binding dialog; editor launch links bypass the dialog with an already validated
binding.

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
| `OPENAI_MODEL` | `gpt-4o-mini` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| `SPEC_SERVICE_ALLOWLIST` | `http://127.0.0.1:6010` |
| `CIRCUIT_SERVICE_ALLOWLIST` | `http://127.0.0.1:6011/api/circuit-designer/v1` |

Owner allowlists accept comma-separated exact URLs and are rechecked on every
owner-backed operation. The web routes enforce same-origin requests. This is a
trusted single-user service and must not be treated as an authenticated public
multi-user application.

## State and recovery

DSH JSONL is the transcript source of truth. `assistant.sqlite3` stores immutable
bindings and review metadata. Back up the complete state root together. DSH
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
npm run package -- /tmp/spec2gds-assistant-release
```

The unit suite protects the transferred prompt/domain rules and complete
operation vocabularies. The integration test boots the real headless profile
against local owner/model fixtures and verifies context dispatch, proposal
preview, and durable SQLite state. Packaging refuses a dirty Harness checkout
or a commit different from `harness.lock.json`.

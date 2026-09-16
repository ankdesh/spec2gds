# AI Assistant

The optional `ai-assistant/` application is a focused DeepSeek Harness product.
It owns model execution, durable conversations, cancellation, streaming, and a
small React review UI without becoming part of either editor's critical path.
The former Python/FastAPI/A2A and assistant-ui implementation has been removed.

Each conversation is permanently bound to one existing Spec document, Spec
entity, or Circuit document. The model can read fresh owner context and prepare
typed previews, but it has no apply, send, source-creation, filesystem, shell,
browser, or general code-execution tools. A Spec apply or Circuit proposal send
is available only through an explicit browser review action.

## Editor integration

The existing launch URLs remain stable:

- `/launch/spec-document` creates a document-scoped Spec conversation;
- `/launch/spec` creates an entity-scoped Spec conversation;
- `/launch/circuit` creates a Circuit conversation.

Spec Editor continues to own semantic context, preview, validation, revision
checks, and atomic application. Circuit Designer continues to own snapshots,
operation preview, diagnostics, revisions, and submitted proposals. Discussion
and model output never mutate either source.

Document-scoped Spec conversations may only propose `create_entity` for a new
component or design. Entity-scoped conversations stay inside the owner's
writable boundary and support metadata, parameters, ports, interfaces,
instances, connections, internal designs, bus/abstraction definitions,
narrative blocks, and SystemVerilog sections. The complete 28-operation Spec
vocabulary is represented by closed discriminated schemas.

Circuit conversations receive complete component/instance/net values, an exact
endpoint catalog, and metadata from the deterministic SVG export. They support
the complete 14-operation logical vocabulary for definitions, instances,
boundary terminals, nets, and endpoints. Geometry, routes, labels, and layout
remain outside AI-authored operations.

## Run locally

Use Node.js 22.19+ or Node.js 24+ and a built checkout of the pinned Harness
fork. The combined product expects the Harness checkout at
`/home/ankdesh/explore/deepseek-harness` unless `HARNESS_SOURCE` is set.

```bash
cd ai-assistant
npm install
npm run build
export OPENAI_API_KEY="..."
HARNESS_SOURCE=/home/ankdesh/explore/deepseek-harness npm run dev
```

Open `http://127.0.0.1:6013`. The combined `scripts/serve-all.sh start`
launcher uses the same workspace and port.

Important settings:

| Variable | Default |
| --- | --- |
| `ASSISTANT_HOST` | `0.0.0.0` |
| `ASSISTANT_PORT` | `6013` |
| `ASSISTANT_STATE` | `ai-assistant/.dev` |
| `OPENAI_MODEL` | `gpt-4o-mini` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| `SPEC_SERVICE_ALLOWLIST` | `http://127.0.0.1:6010` |
| `CIRCUIT_SERVICE_ALLOWLIST` | `http://127.0.0.1:6011/api/circuit-designer/v1` |

Owner allowlists accept comma-separated exact URLs. Stored owner URLs are
rechecked before every owner-backed use. This is a trusted single-user service
with same-origin browser checks; do not expose it as a public multi-user API.

## State and recovery

Harness JSONL is the transcript source of truth. `assistant.sqlite3` stores
immutable bindings and review metadata in the same state root. Back up the
complete state root as one unit. The UI supports rename and archive/unarchive;
permanent deletion is not exposed because the current Harness persistence
contract is append-only.

The removed Python assistant's local SQLite files were not migrated. They are
preserved under `generated/legacy-ai-assistant-state/` and are not loaded by the
Harness application. A2A endpoints and old REST/chat compatibility are gone.

Circuit documents and pending Circuit proposals remain process-local to
Circuit Designer. Harness conversations survive a Circuit restart, but the
document must be reopened before a stale or interrupted review can reconcile.

## Verification and packaging

```bash
cd ai-assistant
npm run typecheck
npm test
npm run build
npm run test:harness
```

The integration test boots the real Harness profile against local owner and
OpenAI-compatible fixtures. It covers context dispatch, proposal preview,
browser-only apply, restart/resume, rename, archive, and unarchive without a
live API key.

Native release assembly additionally requires the Harness checkout to be clean
and at the commit recorded in `harness.lock.json`:

```bash
npm run package -- /tmp/spec2gds-assistant-release
```

The package command intentionally refuses dirty or unpinned Harness input.

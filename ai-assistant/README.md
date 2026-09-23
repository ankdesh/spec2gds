# spec2gds Harness assistant

This package is a DeepSeek Harness product, not a standalone chat server. DSH
owns the browser shell, conversation transport, model loop, cancellation,
session navigation, archive/restore, rename, export, and durable transcript.
The spec2gds layers add immutable editor bindings, versioned prompt/workflow
catalogs, three execution presets, domain tools, proposal reviews, product
branding, and Spec/Circuit diff cards.

There is no Python/FastAPI/A2A assistant and no compatibility API for the old
custom UI. The only product HTTP routes are the small `/spec2gds-api` extension
used to create bindings and perform explicit review actions, plus the stable
editor launch URLs.

## Requirements

- Node.js `^22.19.0` or Node.js 24+
- the pinned, built Harness fork at `/home/ankdesh/explore/deepseek-harness`, or
  a different checkout named by `HARNESS_SOURCE`
- `OPENAI_API_KEY` for model turns
- a running Spec Editor or Circuit Designer owner for a new bound conversation

## Browser development

```bash
cd ai-assistant
npm install
npm run build
export OPENAI_API_KEY="..."
HARNESS_SOURCE=/home/ankdesh/explore/deepseek-harness npm run dev
```

Open `http://127.0.0.1:6013`. New conversation opens a browse-only target
chooser for configured Spec and Circuit services. The global chooser can
connect another service for this process or create a new Spec or empty Circuit;
a Workspace-row action stays within that logical design source. The same dialog
chooses an immutable `focused`, `goal`, or `orchestrated` preset. Focused is
one-shot; goal adds a bounded durable loop; orchestrated additionally permits
depth-one read-only analysis children.
The existing editor links also work:

- `/launch/spec-document?service_base_url=...&document_id=...`
- `/launch/spec?service_base_url=...&document_id=...&entity_kind=...&entity_id=...`
- `/launch/circuit?service_base_url=...&document_id=...`

## One-off command-line requests

The headless profile sends one request and exits; it does not start an
interactive chat UI. Start a fresh bound session with:

```bash
npm run request -- \
  --domain spec \
  --service-url http://127.0.0.1:6010 \
  --document-id my-spec \
  -- "Summarize this specification and identify missing reset behavior."
```

Use `--scope entity --entity-kind component --entity-id <id>` for an
entity-scoped Spec request, or `--domain circuit` with the Circuit service URL.
Add `--json` for machine-readable DSH events. Continue a durable conversation
with `--session-id <id> -- "Follow-up question"`; binding arguments are omitted
when resuming.

An assembled release exposes the same syntax through:

```bash
node deployment/request.mjs --domain spec --service-url ... --document-id ... -- "request"
```

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

Owner allowlists are comma-separated exact URLs. Stored owner URLs are checked
against the current allowlist before every owner-backed operation. This is a
trusted single-user application; it is not an authenticated multi-user server.

One `.spec` package maps to one DSH Workspace. Source-bound Circuit documents
join the source Spec Workspace; independent Circuits receive their own. Each
conversation retains its exact document or entity binding permanently.

Prompt bundles, the generic `prepare-reviewed-change` workflow, and Spec/Circuit
service adapters are strict startup YAML with exact versions and SHA-256
identities. They are loaded before the product becomes ready and sealed for the
process lifetime. Model workflow tools can report progress and request review,
but lifecycle, budget raises, completion approval, and owner mutation remain
human/host authority. The browser workflow dock handles pause, resume, cancel,
and required answers; review-card apply/send completes the workflow.

For a guided explanation of the DSH components and how these layers compose,
read the [DSH configurable assistant tutorial](../docs/dsh-configurable-assistant-tutorial.md).

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

Harness JSONL is the transcript source of truth. `assistant.sqlite3` stores only
bindings and review state. Back up the complete state root together. Old Python
assistant data is preserved under `generated/legacy-ai-assistant-state/` for
manual inspection and is never loaded by this product.

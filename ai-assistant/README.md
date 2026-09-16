# spec2gds Harness assistant

This is the spec2gds assistant service built on DeepSeek Harness. It owns the
canonical assistant port `6013`. It binds each conversation to one existing Spec Editor
or Circuit Designer document, streams durable Harness sessions, and keeps
bindings and proposal-review decisions in a small SQLite database.

The model can read owner context and request non-mutating proposal previews. It
cannot apply, send, or create owner data. Spec apply and Circuit send are
available only through explicit browser review actions.

The domain layer ports the former assistant's deterministic Spec writable/read-
only context and Circuit endpoint catalog. Proposal tools expose discriminated,
closed operation schemas, reject unknown fields and invalid supported/unsupported
shapes, and preserve complete-replacement and revision rules. Circuit context
also includes metadata from the owner's deterministic SVG export.

## Requirements

- Node.js `^22.19.0` or Node.js 24+
- a built local Harness checkout on `codex/product-distribution`
- `OPENAI_API_KEY` for model turns
- the existing Spec and/or Circuit owner service for bound conversations

## Development

```bash
cd ai-assistant
npm install
npm run build
HARNESS_SOURCE=/home/ankdesh/explore/deepseek-harness npm run dev
```

Open `http://127.0.0.1:6013`. The service itself boots without either editor;
new bindings and owner-backed actions require the selected owner to be running.

Useful overrides:

| Variable | Default |
| --- | --- |
| `ASSISTANT_HOST` | `0.0.0.0` |
| `ASSISTANT_PORT` | `6013` |
| `ASSISTANT_STATE` | `ai-assistant/.dev` |
| `OPENAI_MODEL` | `gpt-4o-mini` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| `SPEC_SERVICE_ALLOWLIST` | `http://127.0.0.1:6010` |
| `CIRCUIT_SERVICE_ALLOWLIST` | `http://127.0.0.1:6011/api/circuit-designer/v1` |

Comma-separate allowlist values when the owner is advertised through both a
loopback address and a configured LAN address. Stored owner URLs are checked
against the current allowlist before every owner-backed use.

## Verify

```bash
npm test
npm run typecheck
npm run build
npm run test:harness
```

The Harness integration test uses a local OpenAI-compatible fixture and does
not require a live API key. Native packaging additionally requires a clean
Harness checkout whose `HEAD` matches `harness.lock.json`:

```bash
npm run package -- /tmp/spec2gds-assistant-release
```

Empty owner-document creation, legacy Python-assistant chat migration, and A2A
compatibility are not supported. The removed service's last local SQLite state
is preserved under `generated/legacy-ai-assistant-state/` for manual recovery;
the Harness service does not read it.

The focused UI supports rename, archive/unarchive, owner/model status, explicit
review actions, structured diagnostics, Spec field diffs, and Circuit diff
summaries. Permanent transcript deletion is not exposed because the current
Harness persistence contract is append-only and has no safe delete operation.

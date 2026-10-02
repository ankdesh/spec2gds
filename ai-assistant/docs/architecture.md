# Harness Assistant code map

The maintained system references are [product architecture](../../docs/configurable-assistant-architecture.md),
[event execution](../../docs/event-driven-assistant-system.md),
[operations](../../docs/event-driven-assistant-operations.md) and
[UI composition](../../docs/assistant-ui.md). This page maps those contracts to
this package without duplicating a second runtime specification.

## Composition

`harness.product.json` selects `spec2gds-web` or `spec2gds-headless`.
`profile/cordis.patch.yml` supplies shared native services, deployment limits,
model routes and the host adapter. `bundles/web/cordis.patch.yml` supplies browser
slots and UI policy. Headless is focused and noninteractive.

`src/index.ts` is the host composition root: readiness, bindings, native agent
attachment, event/goal integration, owner review routes and controls.
`src/tools.ts` supplies read/proposal tools and interaction policy. The primary
receives proposal capability; standing specialists receive read-only context
and their pinned event tools/publications. Unbound browser roots can discuss
general topics or stage Spec creation but receive no existing-design capabilities.

## Boundaries to review

| Code | Review focus |
| --- | --- |
| `src/owner-clients.ts` | Exact approved owner URLs, immutable package identity and authoritative reads |
| `src/owner-operation-schema.ts` | Owner-published schema admission; semantic validity still belongs to the owner |
| `src/proposal-pipeline.ts` | Authored revision, exact artifact and owner preview/submission policy |
| `src/state.ts` | Review claims, uncertainty, creation receipts and immutable bindings |
| `src/source-creation.ts` | Reserved package/chat progress and recoverable uncertain creation |
| `src/event-configuration.ts` | Deployment capability ceiling, canonical text, reviewed revision and pins |
| `src/execution-policy.ts` | Host bounds and causal review of the latest orchestrated input |
| `client/index.js` | Template visual/text round-trip, revision-carrying controls and causal inspector |
| `client/host.js` | Native UI integration rather than a replacement transcript runtime |

JSONL belongs to native sessions. Product `assistant.sqlite3` stores bindings,
creation progress, reviews, template revisions and conversation pins. Native
storage domains separately own event execution and HTTP sources. Back up the
whole state root, and run one process per root. Restore does not grant fresh
budget or automatic model execution.

## Verification and packaging

See [the package README](../README.md) for commands. Unit tests protect product
contracts; native integration boots actual Loader/goals/event services; product
browser tests use real React with a minimal shell and deterministic owner/model
fixtures. These are different proof scopes. Packaging requires a clean Harness
checkout matching `harness.lock.json`; unified setup currently follows a branch,
so verify the checkout explicitly before release preparation.

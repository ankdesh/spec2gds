# Event-driven execution operations

HTTP condition polling, durable waiting, and bounded recovery are available for `goal` and `orchestrated`. Preset names, immutable owner bindings, and aggregate budgets remain in force. Visual configuration and causal inspection are described in [the current event/plugin reference](event-driven-assistant-system.md); executable workflows remain deferred.

## Start and use monitoring

Use the source setup path in [the Assistant README](../ai-assistant/README.md), then start the owners and Assistant. In a new bound `goal` or `orchestrated` conversation, open the execution dock's HTTP monitoring form. Its suggested URL reads the bound document; its suggested JSON pointer selects the Spec source revision or Circuit revision. Choose **changed**, or **equals** with a valid JSON value, and a check interval in seconds. **Start monitoring** adds an immutable source. The UI uses a five-second debounce; equality monitoring can emit an initial matching observation. Disable or re-enable the source through its row.

Checks use bounded HTTP GET requests. Unchanged values make no model requests. A stable change produces one typed `source.changed` event: `orchestrated` routes it through its persistent analyst and reviewer before the primary may prepare a proposal; `goal` delivers it to its primary. Every resulting model request uses the remaining conversation allowance. Endpoint content is untrusted observation data and cannot change permissions or approve owner mutations.

The form accepts only this conversation's bound owner origin and path prefix. The deployment also requires that origin in its monitoring allowlist. URLs with credentials, redirects, invalid JSON/pointers, oversized bodies, and incompatible event schemas are rejected or reported as source errors. HTTP monitoring is polling: the Assistant checks an existing endpoint at intervals. A webhook would require the external service to push an event to a reachable authenticated receiver; the current runtime implements polling only.

## Waiting and owner review

The primary can use `wait_for_event` for a human answer, a declared event, or an owner review. A wait records an exact string field and value for a future response; events already in history do not resolve it. Human waits receive a host-generated identity and an **Answer** button. The answer must refer to the observed execution revision and current waiting identity; stale answers cannot wake another activation. Waiting consumes no further model rounds for that member. Other configured agents may still work.

A goal proposal awaiting review now blocks native continuation while keeping execution available for its owner's review action. Applying, sending, or discarding that same proposal resolves its wait and resumes the same blocked native goal revision if rounds remain. A review decision alone does not mark the goal complete. Unrelated proposals cannot resolve the wait. The dock distinguishes waiting, goal blocked, goal complete, paused, stopped, restart recovery, and exhaustion. Pause prevents checks and new admissions; Stop is terminal and cancels waits. Resolve a pending owner review before manually resuming.

## Recovery and bounds

Source definitions, cursors, debounce candidates, and pending publications persist in the `event_http_sources` SQLite domain alongside the event ledger. The outbox commits before event publication, and cursor acknowledgement follows the event commit. A crash between publication and acknowledgement reuses the same source sequence and dedupe identity. On process restart, execution requires human Resume; monitors remain inactive until then. Resume retains cursors, spending, waits, and pending work.

The supplied analyst and reviewer subscriptions declare replay-safe retries: at most three attempts, with one-second initial backoff and ten-second maximum backoff. Proposal preparation is not automatically retried. Failed replay-safe deliveries append separate attempts and receipts. Interrupted or uncertain attempts require **Acknowledge uncertainty and retry**. These retries use remaining requests, rounds, tokens, time, and queue capacity. Exactly-once mutation in independent owner storage is not promised.

After five consecutive HTTP failures, the source disables itself. Correct the endpoint and use **Enable** to reset its failures while preserving its cursor and outbox. A source row reports failures and the latest bounded error. Sources remain retained when disabled; editing and deletion are deferred.

## Deployment configuration

The shared profile supplies exact monitoring origins from `ASSISTANT_HTTP_MONITOR_ORIGINS` (comma-separated), or the configured Spec/Circuit service allowlists. Source admission remains restricted to the immutable bound owner even if the deployment approves additional origins. A newly connected owner outside the startup monitoring allowlist requires an updated allowlist and restart before monitoring.

| Bound | Shipped value |
| --- | --- |
| Scheduler tick | 1 second |
| Source interval | 5 seconds to 1 hour; UI starts at 60 seconds |
| Request deadline / complete response | 5 seconds / 64 KiB |
| Sources per conversation / process | 2 / 100 |
| Concurrent checks / suspension threshold | 2 / 5 consecutive failures |

Trusted host/API configuration may set `authorizationEnv` to the name of a bearer credential variable. Only the variable name is persisted. The UI does not accept credential values. Startup revalidates saved origins and credential availability; restoring approved configuration may be required after policy changes. Run one process per state root. No model key is needed for polling itself; activated agents use the normal configured model route.

Member provider/model choices and tool allowlists remain pinned in trusted YAML/native preset compositions. The browser does not grant models roster editing, arbitrary skills/MCP configuration, or budget top-up. Existing conversations retain their definition; start a new conversation to use changed templates. Older records remain readable because wait and backoff fields are optional; downgrading extended records to older binaries is not supported.

## Verification and packaging

Native Loader tests cover polling isolation, debounce/equality, bad and oversized responses, source capacity, restart gating, the publication/acknowledgement crash window, correlated native waiting/completion, bounded retry, and invariant disposal/re-registration. A committed native-session fixture covers human waiting and goal continuation without API keys. Product tests exercise source admission and owner isolation through the HTTP API, analyst/reviewer proposal causation, review-discard resumption, and the existing focused recorded-session replay. Unit tests and type/build checks cover the product adapter and browser bundle.

The implementation is available through local Harness source linking. Verify that the checkout matches `harness.lock.json`; the setup script does not enforce that pin. Registry publication is still separate: the new native packages are not published, and the product npm lockfile requires regeneration after publication. Use source setup rather than `npm ci` for this checkout. Repository-wide Harness documentation checks also contain existing failures outside these packages; the focused native package checks are reported separately.

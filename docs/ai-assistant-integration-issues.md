# Remaining Assistant integration issues

This is a current-source defect/backlog reference. Completed gate-library,
owner-schema, service-link, multi-tool and domain-neutral clarification changes
are documented in the maintained owner/UI references rather than repeated as
open remediation plans. Original issue IDs are retained where useful.

## ISSUE-CD-02: Source-bound proposal preview has a narrower validation scope

`CircuitService` routes `/operations/preview` to the Circuit backend, which
validates logical circuit semantics. Source-specific IP-XACT constraints are
checked by the explicit `/source/preview` and `/source/commit` path. Assistant
Circuit preview does not call that source preview, so a proposal can pass its
initial Circuit preview and later fail **Save to Specification**.

A future change should expose these validation scopes honestly and, where a
source binding exists, request source preview without committing. Preserve
independent Circuit operation behavior and the user's explicit save decision.
Acceptance should include a Circuit-valid but source-invalid candidate and
unchanged package bytes after rejected preview/save.

## ISSUE-CD-03: Sent is not a downstream owner decision

The Assistant records `sent` when it hands a proposal to Circuit Designer.
Circuit Designer accepts/rejects it separately. A goal review wait resolves on
the product's send receipt; that receipt does not prove Circuit acceptance or
saved Spec source. The Assistant does not continuously reconcile later Circuit
decisions into its sent card.

A future decision-status adapter needs durable identity, polling/event policy,
restart reconciliation and clear distinction between sent, accepted draft,
rejected and saved source. It must not mark goals successful solely from a send
receipt. Test send, reject, source-save failure and Circuit restart independently.

## Source-bound acceptance is an explicit draft, not a save defect

The earlier ISSUE-CD-01 remediation proposed automatically saving on Accept.
That conflicts with the delivered ownership contract: `App.tsx` stages a private
leased draft for a source-bound proposal; **Save to Specification** invokes the
source adapter and owner commit. `server.ts` rejects direct source-bound accept
with `validation_failed` and a Save-to-Specification diagnostic. Preserve this behavior and its tests; do not add
an automatic save merely to satisfy the superseded issue checklist.

## Setup reproducibility

`scripts/setup-all.sh` follows `DSH_BRANCH`, may switch an existing checkout,
and falls back from frozen pnpm installation. It does not enforce the origin,
cleanliness and commit in `ai-assistant/harness.lock.json`. The packager does
enforce the clean pin. Future bootstrap hardening should validate existing
checkouts before mutation and make an explicit pin update path; until then,
inspect `git -C "$HARNESS_SOURCE" rev-parse HEAD` against the lock before tests
and packaging. Removed `setup:harness` scripts must not remain in run guides.

## Future owner extension

Verification Planner is not currently an Assistant owner domain. Its operation
catalog and command preview are useful extension seams, but the required owner
schema/context, approval and receipt adapter must be designed before adding it
to the chooser. See [Planner remaining requirements](verification-planner-backlog.md).

# Spec Editor support for iterative assistant refinement

Valid Spec assistant submissions apply and save automatically by default. The
owner validates package identity, scope, references, supported operations, and
the revision read by the assistant before saving. Circuit proposal approval
and **Save to Specification** retain their existing behavior.

## Approval policy

Start a restricted owner with any of these commands:

```bash
uv run spec2gds-server --require-human-approval
uv run spec2gds-editor --require-human-approval
bash scripts/serve-all.sh start --require-human-approval
uv run spec2gds-assistant ./work/timer --require-human-approval -- "Refine the timer."
```

The entrypoints preserve the setting through reloads. Owner capabilities expose
`approval_policy: automatic | review`. The assistant discovers it before
submission; failed discovery never authorizes automatic application. Legacy
owners without this capability retain review behavior.

`POST /assistant/proposals/submit` validates and saves in automatic mode. Its
receipt includes the saved revision and proposal ID. The Assistant awaits this
receipt before displaying **Applied automatically**. Review mode stores the
artifact and returns `approval_required`; explicit stored-ID `/approve` and
`/reject` actions decide it. Approval revalidates the exact stored artifact.
The legacy `/apply` route cannot bypass restricted approval. Pending proposals
imported through `/stage` remain subject to review even on an automatic owner.

Fully specified components and automatic package creation continue without
confirmation cards. Proposed defaults become recorded assumptions. Genuinely
missing required inputs still request clarification. Restricted owners retain
the details and creation cards. Creation request IDs and reserved continuation
receipts prevent a completed creation from creating a second package.
Owners advertise `creation_receipts` for recovery after an uncertain response;
retries carry the same request ID and exact saved inputs.

## Persistent package bindings

Opening or creating a package returns `owner_document_key`. The opaque key
identifies a canonical package path and document ID in the owner's persistent
catalog. Assistant bindings and owner requests carry this key. Opening B does
not redirect an existing conversation bound to A. Copies with identical
internal document IDs receive different keys. Missing files, mismatched
document identities, and ambiguous legacy document-ID lookups fail explicitly.

Document conversations can use the existing supported operation vocabulary
throughout their package: entities, ports, parameters, supported sections,
instances, connections, and narratives. Entity conversations keep their
narrower ownership boundaries. Composite port restrictions and reference
validation still apply.

Proposal preparation requires `base_source_revision_hash` from the context
actually read by the model. Preparation never stamps older operations with a
freshly fetched revision. A mismatch returns structured stale diagnostics and
requires another context read. Schemas stay stable during ordinary content
changes; a genuinely changed contract is refreshed in the existing conversation
before another submission.

## Transactions, retries, and recovery

The package lock covers validation, mutation, source save, and activity
finalization within the owner process. Disk comparison at save prevents an
external writer from overwriting a newer package. This remains a single-user
workflow; multi-user coordination is outside this phase.

Accepted decisions are saved atomically with package source. Owner submission
state and events are durable SQLite records next to the package; the binding
catalog defaults to `.spec2gds/editor` or `SPEC_EDITOR_STATE_ROOT`. Back up the
package and these state directories together.

An identical proposal-ID retry returns the original receipt without a second
save or source event. Changing the artifact under that ID fails. Replays check
package identity, scope, target, authored base revision, and operations. After
an interruption following source save, the owner reconciles its journal from
the package's accepted decision before answering reads or retries. Existing
packages and decision records remain readable; existing pending reviews do
not become automatic submissions during upgrade.

## Live views, drafts, and history

`GET /documents/view` captures snapshot, A2UI, activity, revision, approval
policy, and event cursor together. Document-specific durable event streams
support cursor replay, reconnect, and authoritative resynchronization. Owners
detect valid CLI or external package changes on reads, writes, and subscriptions.

The editor coalesces updates and refreshes while idle, retaining the mounted
view and ignoring obsolete responses after document switches. While an inline
draft is open, incoming changes update the synchronization indicator but leave
the draft text and original base revision intact. **Review current source**
shows the latest snapshot. Selecting **Use reviewed revision for next save**
explicitly acknowledges that revision before retrying; cancellation loads the
current source. Dirty drafts cannot be discarded by a document switch.

The editor shows approval mode, synchronization state, and paginated assistant
history. History details include summaries, diffs, diagnostics, proposal/session
IDs, and base/result revisions. Restricted proposals remain pending until an
explicit decision; stale approval cannot change the source. There are no
restore controls in this phase.

## Verification

[Assistant acceptance tests](assistant-acceptance-tests.md) lists deterministic
owner, CLI, native integration and isolated UI commands. Event-preset browser
coverage is described separately in [the event tutorial](event-driven-assistant-tutorial.md).
Run the relevant source/build checks for a change; a historical release result
or existing generated bundle is not verification of the current worktree.

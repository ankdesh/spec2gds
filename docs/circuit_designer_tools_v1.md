# Circuit Designer v1 Tool and Proposal Contracts

v1 exposes structured capabilities for an external agent host but contains no
model SDK, prompt execution, chat panel, natural-language evaluator, or A2UI
runtime.

An agent host is an ordinary REST client. The SDK-neutral declarations in
`packages/core/src/tools.ts` describe:

- document/design summary;
- component lookup;
- selected neighborhood/subgraph query;
- deterministic JSON, SVG, and PNG export;
- construction validation;
- operation preview;
- immutable proposal submission.

The declarations are tool metadata, not a second transport. The agent host maps
them to the versioned Circuit Designer REST endpoints.

## Recommended agent flow

1. Read the document summary and current opaque revision.
2. Look up relevant components and request a focused subgraph if needed.
3. Choose compact construction for complete desired state or an operation batch
   for a targeted edit.
4. Preview the structured change.
5. Submit an immutable proposal for human Accept or Reject.

The Circuit Designer service remains authoritative for IDs, normalization,
validation, revision checks, leases, proposals, and the active session
snapshot.

## Proposal lifecycle

A proposal create request has a title, summary, optional rationale and
assumptions, exactly one structured construction or operation batch, and a base
revision. Circuit Designer calculates status, diagnostics, normalized canvas
diff, and creation time when it stores the complete proposal.

- It is immutable after submission.
- Accept applies it atomically to the active service session.
- Reject discards it.
- Any intervening document revision marks it stale.
- Reject deletes it; a successful Accept deletes it after applying the change.
- A failed Accept caused by an active edit lease retains it for a later retry.
- It disappears if the ephemeral service restarts.

Acceptance is not durable persistence. The owning client must read/export the
accepted document and save it to its own source, such as a circuit file or
future SpecIR package.

Direct trusted commits are also supported, but they fail while a manual canvas
lease is active. Natural-language interpretation and durable proposal history
belong to the external agent host, not Circuit Designer v1.

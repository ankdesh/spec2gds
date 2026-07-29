# Circuit Designer v1 Tool and Proposal Contracts

v1 exposes structured capabilities for an external agent but contains no model
SDK, prompt execution, chat panel, natural-language evaluator, or A2UI runtime.

The backend exposes:

- document/design summary;
- component lookup;
- selected neighborhood/subgraph query;
- deterministic JSON, SVG, and PNG export;
- construction validation;
- operation preview;
- immutable proposal submission.

A proposal has a title, summary, optional rationale, structured construction or
an operation batch, base revision, diagnostics, and a normalized canvas diff.
It is immutable after submission. Accept applies it atomically; Reject discards
it. Any intervening document revision marks it stale. Proposals are deleted
after either decision.

An NL-to-circuit agent should first query the summary and relevant components,
then choose either compact construction for a complete desired state or an
operation batch for a targeted edit. It should preview before submitting a
proposal. The Circuit Designer remains the authority for IDs, normalization,
validation, revision checks, locks, and final persistence.

# Harness assistant architecture

Harness owns the agent loop, OpenAI-compatible model adapter, tool dispatch,
cancellation, session event log, and JSONL persistence. The product plugin owns
the focused REST/SSE API, immutable document bindings, owner clients, review
state machine, React UI, prompt, and scoped tools.

The model-visible tools are deliberately non-mutating:

- `get_bound_context` reads the current owner revision and semantic context;
- `prepare_spec_proposal` creates and previews a revision-bound Spec artifact;
- `prepare_circuit_proposal` creates and previews a Circuit operation batch.

Each bound agent receives the full domain editing contract as a scoped system-
prompt section. `get_bound_context` validates binding identity and emits a
canonical, deterministic model context. Spec context separates writable and
read-only data; Circuit context includes complete replacement values, a valid
endpoint catalog, list-form map projections, and deterministic SVG metadata.
Proposal operations use closed `oneOf` schemas plus cross-field semantic checks.

Apply and send routes load the server-stored artifact by proposal ID, compare
the current owner revision, atomically claim the review state, and then call the
owner. A browser never supplies replacement artifact content during approval.

Harness JSONL is the transcript source of truth. SQLite stores only binding and
review metadata. A tool call ID connects a review to its durable transcript
event, and an artifact digest protects the reviewed content. SQLite state
transitions use a version compare-and-swap to reject concurrent actions.

Circuit Designer remains process-local. Assistant sessions and review records
survive its restart, but Circuit documents and pending owner proposals do not.
Those reviews become unavailable or stale when the bound Circuit document is
not recreated. This milestone does not claim end-to-end Circuit durability.

Harness persistence is append-only and does not expose deletion. The product
therefore supports archive/unarchive and rename, but intentionally does not
pretend that deleting only the SQLite binding would permanently delete the
conversation transcript.

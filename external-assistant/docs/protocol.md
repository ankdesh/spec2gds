# External Assistant Protocol

## Circuit context

Before each A2A send, the browser requests:

```text
GET /api/threads/{thread_id}/circuit/context
```

The response contains:

```json
{
  "snapshot": {
    "revision": "1",
    "document": {}
  },
  "svg": "<svg>...</svg>",
  "png_base64": null
}
```

The SVG and semantic snapshot are always sent to the A2A agent. `png_base64`
is present only when the chat's **Include PNG context** option is enabled.
The semantic document is authoritative; SVG and PNG are visual aids.

## A2A surface

The service publishes:

- `GET /.well-known/agent-card.json`
- HTTP+JSON routes under `/a2a`
- JSON-RPC at `/a2a/jsonrpc`

The `propose_circuit_changes` skill accepts text and a data part:

```json
{
  "kind": "circuit_context",
  "snapshot": {},
  "svg": "<svg>...</svg>",
  "png_base64": null
}
```

It returns an artifact with media type:

```text
application/vnd.spec2gds.circuit-proposal+json
```

The artifact shape is:

```json
{
  "kind": "circuit_change_proposal",
  "schema_version": "1",
  "proposal_id": "proposal_...",
  "document_id": "fixture_simple",
  "base_revision": "1",
  "title": "Add a consumer",
  "summary": "Add and connect one consumer.",
  "rationale": "The request needs another sink.",
  "assumptions": [],
  "batch": {
    "request_id": "request_...",
    "expected_revision": "1",
    "operations": []
  }
}
```

The first agent supports instance and net operations only. It deliberately
rejects component-definition, boundary-terminal, geometry, route, and layout
changes.

The `explore_and_propose_spec_changes` skill accepts `spec_context`, including the selected
entity, current source hash, semantic writable state, rendered sections,
read-only relationships, legal references, recent messages, and the optional
`proposal_requested` flag. Ordinary requests return conversational text. A
proposal request returns `application/vnd.spec2gds.spec-proposal+json` with
`schema_version: "1.0"`, a canonical target, base source hash, and typed
operations. It never returns replacement XML.

## Proposal review routes

The assistant service uses:

- `POST /api/threads/{thread_id}/circuit/preview`
- `GET /api/threads/{thread_id}/reviews`
- `PATCH /api/threads/{thread_id}/reviews/{proposal_id}`
- `POST /api/threads/{thread_id}/circuit/proposals`

Review state progresses as follows:

```text
artifact -> ready | invalid | stale
ready -> discarded | sent
```

`ready` means Circuit Designer successfully previewed the batch at its stated
base revision. `sent` means Circuit Designer accepted the proposal into its
pending proposal queue; it does not mean the document was committed.

Spec uses these additional routes:

- `GET /api/threads/{thread_id}/spec/context`
- `POST /api/threads/{thread_id}/spec/preview`
- `POST /api/threads/{thread_id}/spec/proposals`

Its lifecycle is `draft -> invalid | ready | stale`, then
`ready -> discarded | stale | applied`. `applied` means the Spec API
revalidated and atomically saved the source and accepted-decision record.

## Circuit Designer proposal creation

The canonical schema now exposes `CircuitProposalCreateRequest`. The caller may
provide:

- proposal ID, document ID, and base revision
- title, summary, optional rationale and assumptions
- exactly one operation batch or construction

The caller cannot provide status, diagnostics, diff, or creation time. Circuit
Designer calculates those fields and returns a complete `CircuitProposal`.

## Stale and locked behavior

- The assistant marks a review stale when its base revision is no longer
  current and will not submit it.
- Circuit Designer rejects stale proposal creation.
- If acceptance inside Circuit Designer is blocked by an edit lease, the
  proposal remains pending and may be retried after the lease is released.

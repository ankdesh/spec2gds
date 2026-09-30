# Owner operation schemas for the AI Assistant

Spec Editor and Circuit Designer publish the assistant operation vocabulary for a selected binding. The Assistant reads that vocabulary through its allowlisted owner client when it attaches an agent. Context reading remains available if the contract cannot be loaded, but proposal preparation is disabled with an owner-contract error.

## Read-only endpoint

`GET /assistant/operation-schema?document_id=ID&scope=document` returns a contract for a selected document. Spec requests carry `owner_document_key` to select the exact package independently of the visible document. Spec Editor also accepts `scope=entity&entity_kind=KIND&entity_id=ID`. Circuit Designer supports document scope only, under its `/api/circuit-designer/v1` base path. The service checks that the selected document and, for Spec, entity exist.

The JSON response is:

```json
{
  "schema_version": 1,
  "digest": "sha256:<64 lowercase hex characters>",
  "operation_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "oneOf": [{
      "type": "object",
      "required": ["operation_id", "type", "net_id"],
      "properties": {
        "operation_id": { "type": "string" },
        "type": { "const": "delete_net" },
        "net_id": { "type": "string" }
      },
      "additionalProperties": false
    }]
  }
}
```

The digest is SHA-256 of the canonical JSON operation schema (sorted keys, no extra whitespace). It changes when the exposed operation shape changes. The schema describes **one operation**; the proposal tool accepts a nonempty array of these operations and checks unique `operation_id` values. The owner remains responsible for semantic validation, references, revision checks, and preview or commit.

Spec Editor publishes the complete supported editing vocabulary at document scope. Entity scope selects operations by entity kind and retains semantic ownership boundaries. Component schemas remain stable when internal composition changes; compiler validation enforces composite port restrictions. The published schema lives beside the Spec operation compiler and validates the proposal before transaction preview. Circuit Designer selects the logical assistant operations from its canonical protocol schema. Geometry, routes, labels, layout, and timing operations are excluded from its assistant contract.

## Constructs and refresh

The Assistant converts JSON Schema 2020-12 local `$defs`/`$ref`, `oneOf`, object `allOf`, object properties and `required`, `additionalProperties`, arrays and `items`, primitive types, `const`, `enum`, string length and pattern, numeric bounds, `minItems`, and `uniqueItems`. Arbitrary object maps become a general JSON tool argument and are still checked against the owner schema before preview. Unsupported constructs fail closed; no bundled schema is used. Owners adding a construct must first extend the converter and its tests.

Before every proposal preview, the Assistant fetches the contract again. A retrieval or conversion error prevents preview. A changed Spec digest requires a fresh `get_bound_context` call, which refreshes the registered schema in the same conversation before another submission. Ordinary content changes do not change the schema digest. Spec preparation requires the `base_source_revision_hash` actually read by the model. The owner validates again at save. Its published approval policy determines automatic application or a stored-ID review decision.

## Review and save boundary

For a source-bound Circuit, the Assistant completes its handoff when Circuit Designer receives the proposal. **Accept** acquires an edit lease and stages its operation batch in a private Circuit draft. **Save to Specification** invokes Circuit preview, Spec preview, Spec commit, and authoritative Circuit re-projection. The source save carries `proposal_id` when a proposal was staged, so the Circuit service resolves it only after a successful save. Cancel discards the draft; a failed save retains the draft and proposal. A source reload that returns the same Spec revision and Circuit projection also preserves the proposal for staging again. Direct proposal acceptance and ordinary Circuit document write routes reject source-bound writes. Independent Circuits keep their existing acceptance behavior.

Spec validation occurs at Save to Specification. Assistant preview checks Circuit rules only. This contract covers Spec and Circuit bindings; another owner needs its own binding, context, preview, and review implementation in addition to the endpoint.

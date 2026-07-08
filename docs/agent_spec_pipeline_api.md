# Agent-Spec Pipeline API

The pipeline API lets tools consume selected information from a `.spec`
document and write generated artifact metadata back through explicit, validated
writeback routes.

The API is mounted under `/agent-spec/pipeline/` by the local FastAPI server.
It uses the active document session opened by `POST /agent-spec/pipeline/documents/open`.

## Read APIs

Read endpoints are intentionally read-only. They must not save graph metadata,
add heading IDs, repair manifest entries, or mutate IP-XACT payloads.

Responses use a v1 envelope:

```json
{
  "schema_version": "agent-spec.pipeline.v1",
  "document_hash": "sha256:...",
  "loaded_at": "2026-07-08T00:00:00Z",
  "data": {},
  "diagnostics": []
}
```

Useful endpoints:

| Endpoint | Purpose |
| --- | --- |
| `POST /agent-spec/pipeline/documents/open` | Open a `.spec` document for pipeline queries. |
| `GET /agent-spec/pipeline/document` | Document identity, hash, counts, and diagnostics. |
| `GET /agent-spec/pipeline/blocks` | Block summaries with active versions and attachment counts. |
| `GET /agent-spec/pipeline/blocks/{block_id}/context` | Pipeline-ready section bundle for the active version. |
| `GET /agent-spec/pipeline/blocks/{block_id}/context?version_id=...` | Same bundle for an explicit version. |
| `GET /agent-spec/pipeline/ipxact` | Embedded IP-XACT summaries. |
| `GET /agent-spec/pipeline/ipxact/raw?file_path=...` | Raw embedded IP-XACT XML bytes. |
| `GET /agent-spec/pipeline/artifacts` | Artifact refs and block attachments. |
| `GET /agent-spec/pipeline/runs` | Persisted run and writeback summaries. |
| `GET /agent-spec/pipeline/links` | Visible document links and link diagnostics. |

The section context bundle joins the information most pipelines need: selected
block, selected version, semantic blocks, links, relevant relations, attached
IP-XACT summaries, artifacts, attachments, and diagnostics.

## Writeback APIs

Pipeline output is written back through explicit mutation routes. Pipelines
should not edit the `.spec` archive directly.

Start a run:

```http
POST /agent-spec/pipeline/runs
```

Request body:

```json
{
  "pipeline_id": "pipeline.systemc.perf",
  "block_id": "h2-performance-model-1",
  "version_id": null,
  "parameters": {}
}
```

Submit output artifact metadata:

```http
POST /agent-spec/pipeline/runs/{run_id}/outputs
```

Request body:

```json
{
  "artifacts": [
    {
      "artifact_id": "artifact_1",
      "artifact_kind": "systemc",
      "media_type": "text/plain",
      "summary": "Generated performance model.",
      "sha256": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "external_uri": "artifact-store://local/run/model.txt",
      "producer": "pipeline.systemc.perf",
      "source_trace": {
        "block_id": "h2-performance-model-1",
        "version_id": "v-abc123",
        "artifact_refs": [],
        "spec_refs": []
      },
      "role": "systemc.perf.model",
      "created_at": "2026-07-08T00:00:00Z"
    }
  ],
  "diagnostics": [],
  "allowed_output_roles": ["systemc.perf.model"]
}
```

The server accepts an artifact only when the hash, URI, role, source block,
source version, and required metadata pass the writeback checks. Accepted
artifacts are attached to the source block and persisted under
`spec_data/agent-spec/`. Malformed artifacts produce diagnostics and a
`needs_human_feedback` writeback.

Pipeline writeback stores metadata and traceability. It does not automatically
rewrite the human-readable document prose.

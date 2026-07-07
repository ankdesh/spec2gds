# Agent-Spec Hardware-Document Benchmark

This benchmark captures hardware documentation inputs from
`/home/ankdesh/temp/temp_hw_docs` and the current conversion artifacts used by
the agent-spec editor pipeline.

## Layout

- `inputs/pdf/`: original PDF source documents.
- `inputs/html/`: original HTML source documents.
- `converted/odt/`: office-compatible converted documents.
- `converted/ipxact/`: extracted XML interface/component payloads.
- `generated/`: `.spec` packages built from the converted ODT files with XML
  embedded under `spec_data/ipxact/`.
- `benchmark_manifest.json`: generated manifest with file paths, hashes,
  attachment metadata, semantic extraction status, and strict IP-XACT validation
  status.

## Rebuild

From the repository root:

```bash
PYTHONPATH=. UV_CACHE_DIR=.uv-cache uv run python -m benchmarks.agent_spec.hw_docs.build_benchmark
```

The XML files currently embed and summarize component VLNV fields, but strict
IP-XACT schema validation fails and no `busInterface` entries are extracted.
Those current limitations are recorded in the manifest so future spec2gds
progress can be measured against this dataset.

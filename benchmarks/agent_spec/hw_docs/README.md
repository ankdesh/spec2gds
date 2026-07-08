# Agent-Spec Hardware-Document Benchmark

This benchmark captures hardware documentation inputs from
`/home/ankdesh/temp/temp_hw_docs` and the current conversion artifacts used by
the agent-spec editor pipeline.

## Layout

- `inputs/pdf/`: original PDF source documents.
- `inputs/html/`: original HTML source documents.
- `converted/odt/`: office-compatible converted documents.
- `converted/ipxact/`: strict IP-XACT XML component payloads with formal
  `busInterfaces/busInterface` records.
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

The XML files embed and summarize component VLNV fields and formal IP-XACT bus
interfaces. The PDF/HTML files are the benchmark ground truth; converted ODT/XML
and generated `.spec` files may be regenerated to keep the benchmark
protocol-correct.

# Agent-Spec Benchmarks

The repository keeps agent-spec benchmark datasets under `benchmarks/agent_spec/`.

The first dataset is `benchmarks/agent_spec/hw_docs`, which preserves hardware
documents as original PDF/HTML inputs, converted ODT/XML artifacts, and generated
`.spec` packages. The generated packages embed the XML payloads under
`spec_data/ipxact/` and include editor relation metadata so the web editor can
show each payload as an attachment.

Run the benchmark builder and tests with:

```bash
PYTHONPATH=. UV_CACHE_DIR=.uv-cache uv run python -m benchmarks.agent_spec.hw_docs.build_benchmark
PYTHONPATH=. UV_CACHE_DIR=.uv-cache uv run python -m pytest tests/agent_spec/test_hw_docs_benchmark.py -q
```

The current XML payloads are intentionally tracked even though strict IP-XACT
schema validation fails. This makes the benchmark useful for measuring future
improvements in XML normalization, bus-interface extraction, and document-to-
artifact traceability.

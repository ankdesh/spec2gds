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

The PDF and HTML files are the benchmark ground truth. Converted ODT/XML and
generated `.spec` files can be regenerated to keep the benchmark loadable and
protocol-correct. IP-XACT payloads must use formal `busInterfaces/busInterface`
records; the editor should report missing bus interfaces instead of inventing
them from component-level ports.

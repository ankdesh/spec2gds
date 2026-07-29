# Simple SystemC ODT Import Benchmark

The source corpus at `benchmarks/agent_spec/simple_spec_systemc/` contains four
hardware specifications authored as ODT documents:

- `fifo_backpressure_hw_spec.odt`
- `pipelined_alu_hw_spec.odt`
- `simple_pipeline_hw_spec.odt`
- `switch_arbitration_hw_spec.odt`

Each source has been converted with the Docling-based
`spec2gds-import-document` utility. Generated packages and their audit manifest
are stored below `benchmarks/agent_spec/simple_spec_systemc/generated/`.

## Build

Install the document-import dependencies and rebuild all packages:

```bash
uv sync --extra document-import
uv run python -m benchmarks.agent_spec.simple_spec_systemc.build_benchmark --openai
```

The builder uses the same `DocumentToSpecConverter` API as the CLI and disables
OCR because ODT content is already structured text. The enriched build requires
`OPENAI_API_KEY` in the environment and uses `gpt-5.6-sol` by default. Select a
different available model with `--model MODEL`.

Omit `--openai` for a no-cost narrative-only build. That mode preserves the
tables and images but does not generate IP-XACT ports.

## Verify

Run the read-only corpus verifier:

```bash
uv run python -m benchmarks.agent_spec.simple_spec_systemc.build_benchmark --check
```

The verifier checks:

- every ODT source has one generated `.spec`;
- source and package SHA-256 values match the manifest;
- every package passes the complete V1 validation pipeline;
- the ODT bytes embedded in each package are byte-identical to the source;
- each package's logical source revision hash matches the manifest.

The checked-in corpus is OpenAI-enriched. It preserves headings, paragraphs,
four tables, and four images per document, and each package contains an IP-XACT
component with source-grounded physical ports. Bus interfaces are emitted only
when the source tables explicitly identify protocol membership and role.

The audit manifest makes one enriched run reproducible and verifiable, but
independent API rebuilds need not be byte-identical because model output can
vary.

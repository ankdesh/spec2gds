# Hardware-Document V1 Benchmark

This corpus is the real-document correctness and usage benchmark for the V1
format. It converts six public hardware specifications into deterministic,
self-contained `.spec` packages while retaining every original source byte for
audit and comparison.

## Layout

- `inputs/pdf/`: original PDF source documents.
- `inputs/html/`: original HTML source documents.
- `converted/ipxact/`: strict IP-XACT XML component payloads with formal
  `busInterfaces/busInterface` records from the earlier 1685-2014 conversion.
- `build_benchmark.py`: deterministic V1 converter and manifest builder.
- `generated/`: six V1 `.spec` packages plus `benchmark_manifest.json`.

## Conversion Contract

HTML is converted into the typed narrative AST with heading hierarchy, lists,
tables, paragraphs, figure labels, and a stable link to the formal component.
PDF and HTML bytes are embedded as registered `benchmark_source` annotations.
The original 2014 XML is also retained there as provenance.

Formal component XML is migrated to IEEE 1685-2022, implementation views are
removed because they are outside the V1 profile, and role names are updated to
`initiator`/`target`. Minimal bus and abstraction definitions are derived from
the component's explicit port maps, so every output package is self-contained
and validates as a `SpecRevision`. The converter does not infer interfaces from
port names.

## Build and Verify

From the repository root:

```bash
uv sync
uv run python -m benchmarks.agent_spec.hw_docs.build_benchmark
uv run python -m pytest tests/agent_spec/spec_format/test_hw_docs_benchmark.py -q
```

The tests load every package, verify semantic references and exact embedded
source bytes, and require a fresh build to match the checked-in files byte for
byte.

For visual review:

```bash
uv run spec2gds-editor --reload
```

Open `http://127.0.0.1:8000/editor` and select any **Hardware · ...** entry.

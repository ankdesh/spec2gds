# Agent-Spec V1 Samples and Benchmark Material

V1 has two complementary benchmark layers: a compact feature-complete visual
fixture and six packages converted from public hardware specifications. Both
layers are deterministic, checked in, selectable in the editor, and exercised
by acceptance tests.

## Canonical V1 Sample

Builder:
`spec2gds/agent_spec/spec_format/samples.py`

Checked-in package:
`spec2gds/agent_spec/spec_format/samples/generated/v1_demo.spec`

The sample contains:

- one bus definition and abstraction definition;
- two leaf components and one composite component;
- one internal design mapped to the composite component;
- two explicit entry designs that reuse source definitions;
- wire ports, bus interfaces, instances, and connections;
- every V1 narrative block type;
- an SVG architecture asset, entity link, and live topology view.

Rebuild it deterministically:

```bash
uv run python -c "from pathlib import Path; from spec2gds.agent_spec.spec_format.samples import write_v1_sample; write_v1_sample(Path('spec2gds/agent_spec/spec_format/samples/generated/v1_demo.spec'))"
```

The checked-in bytes must match a fresh build. The test suite unpacks and
repacks the archive and requires byte-for-byte equality.

## Visual Review

```bash
uv run spec2gds-editor --reload
```

Open `http://127.0.0.1:8000/editor`, select **V1 Demo**, and follow
[`agent_spec_ui_testing.md`](agent_spec_ui_testing.md).

## Real Hardware-Document Benchmark

The active corpus is under `benchmarks/agent_spec/hw_docs/`. It contains paired
HTML/PDF sources for APB GPIO, APB I2C slave, APB timer, two CV-HPDcache
documents, and CVFPU. The converter emits one package per pair into
`generated/` and records hashes, sizes, source URLs, formal entity counts, and
narrative block counts in `benchmark_manifest.json`.

Each package contains:

- the typed narrative derived from authored HTML content;
- a migrated IEEE 1685-2022 component with explicit ports and interfaces;
- self-contained bus and abstraction definitions for every referenced VLNV;
- exact HTML, PDF, and original 2014 XML bytes as registered annotations;
- stable component/entity links usable by the editor and action layer.

Rebuild and verify:

```bash
uv run python -m benchmarks.agent_spec.hw_docs.build_benchmark
uv run python -m pytest tests/agent_spec/spec_format/test_hw_docs_benchmark.py -q
```

For visual comparison, run the editor and select any **Hardware · ...** entry.
The package index is available through `GET /samples` alongside **V1 Demo**.

## Adding Samples

Extend `build_v1_sample()` for compact editor-feature coverage. Add real source
documents to the hardware corpus only when they broaden protocol, narrative,
or scale coverage. Every package must remain deterministic, self-contained,
auditable against its original sources, visually meaningful, and tested.

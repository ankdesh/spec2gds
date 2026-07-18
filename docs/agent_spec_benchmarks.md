# Agent-Spec V1 Samples and Benchmark Material

V1 uses one deterministic `.spec` sample as both a regression fixture and a
visual acceptance document. Historical hardware-document inputs are preserved
separately as future import-pipeline material.

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
uv run spec2gds-editor
```

Open `http://127.0.0.1:8000/editor`, select **V1 Demo**, and follow
[`agent_spec_ui_testing.md`](agent_spec_ui_testing.md).

## Archived Source Corpus

`benchmarks/agent_spec/hw_docs/` retains original PDF/HTML documents and useful
IP-XACT conversions from the pre-pivot experiment. It deliberately does not
contain ODT conversions, generated legacy `.spec` packages, an active manifest,
or an executable builder.

The corpus is not a current acceptance benchmark. A future importer may use it
only after defining explicit conversion quality metrics and emitting the
current V1 package contract.

## Adding Samples

Prefer extending `build_v1_sample()` over accumulating narrow fixture files.
Add another checked-in package only when it represents a materially different
profile or scale boundary. Every sample must be deterministic, valid, visually
meaningful, documented, and exercised by tests.

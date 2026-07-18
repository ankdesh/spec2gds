# Archived Hardware-Document Source Corpus

This directory preserves source material collected for the pre-pivot import
experiment. It is not an active V1 `.spec` benchmark or editor fixture. The
original documents and useful IP-XACT conversions remain available for a
future import pipeline without keeping the ODT runtime alive.

## Layout

- `inputs/pdf/`: original PDF source documents.
- `inputs/html/`: original HTML source documents.
- `converted/ipxact/`: strict IP-XACT XML component payloads with formal
  `busInterfaces/busInterface` records.

The removed ODT conversions, generated prototype packages, manifest, and
builder are recoverable from Git history if their historical behavior needs to
be studied.

## V1 Samples

The active deterministic visual fixture is built by
`spec2gds.agent_spec.spec_format.samples` and checked in at
`spec2gds/agent_spec/spec_format/samples/generated/v1_demo.spec`.

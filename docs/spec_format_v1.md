# V1 `.spec` Source Package

V1.1 introduces the replacement source-format foundation described in the
[IP-XACT pivot plan](pivot/v1_01_spec_package_and_schema.md). It is a custom,
deterministic ZIP package; it is deliberately not an ODT container.

## Status and Boundary

The implementation is available at
`spec2gds.agent_spec.spec_format`. It currently provides package creation,
loading, validation, inspection, and pack/unpack commands. It is not wired
into the legacy editor or action APIs until the later V1 plans are complete.

The legacy ODT-oriented package implementation remains available only for the
existing product path while cutover work is in progress. The new V1 CLI rejects
ODT packages and does not provide migration or import support.

## Source Layout

```text
<name>.spec
  mimetype                                      # first ZIP entry; stored
  manifest.json                                 # typed source manifest
  document/document.json                        # typed narrative AST
  ipxact/components/<vlnv>.xml
  ipxact/designs/<vlnv>.xml
  ipxact/bus-definitions/<vlnv>.xml
  ipxact/abstraction-definitions/<vlnv>.xml
  assets/<sha256>.<extension>
  annotations/                                  # optional source inputs
  activity/                                     # reserved for V1.3
```

The package uses the mimetype
`application/vnd.spec2gds.spec+zip`. Its JSON and XML serialization is
canonicalized, ZIP metadata is fixed, and non-mimetype entries are sorted, so
re-saving unchanged source produces the same bytes. `activity/` is reserved
and excluded from the source hash; V1.1 does not assign it a payload schema.

The checked-in representative package is
[`v1_demo.spec`](../spec2gds/agent_spec/spec_format/samples/generated/v1_demo.spec).
It contains leaf and composite components, one bus/abstraction pair, an
internal design mapping, two entry designs, a narrative tree, and a PNG asset.

## CLI

Use the module directly while the project CLI surface is being cut over:

```bash
uv run python -m spec2gds.agent_spec.spec_format.cli create \
  --output demo.spec --document-id spec_demo
uv run python -m spec2gds.agent_spec.spec_format.cli validate --container demo.spec
uv run python -m spec2gds.agent_spec.spec_format.cli inspect --container demo.spec --format text
uv run python -m spec2gds.agent_spec.spec_format.cli unpack \
  --container demo.spec --output demo-unpacked
uv run python -m spec2gds.agent_spec.spec_format.cli pack \
  --input demo-unpacked --output demo-repacked.spec
```

Run the focused foundation tests with:

```bash
uv run python -m pytest tests/agent_spec/spec_format -q
```

## V1.1 IP-XACT Boundary

Embedded IP-XACT XML is validated against IEEE 1685-2022 and the narrower V1
profile. The only document roots are component, design, bus definition, and
abstraction definition. V1.1 permits source-level component composition and
explicit entry designs, but excludes implementation views, instantiations,
design configurations, abstractors, generators, memory/register data,
structured ports, power intent, and vendor extensions. See the pivot plan for
the complete allowlist and exit gate.

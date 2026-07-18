# V1.1 — Canonical Spec Package and Source Schemas

> Status: completed. This file is implementation and acceptance history; active
> contracts are in `docs/spec_format_v1.md` and
> `docs/agent_spec_document_schema.md`.

## Goal

Replace the ODT-centered container with a deterministic, self-contained
`.spec` ZIP package whose source of truth is IP-XACT 1685-2022 structure plus
a project-owned narrative document and assets.

This plan establishes the new source format only. It does not implement the
editor, SpecIR, actions, artifact execution, SystemC, or RTL generation.

## Non-Goals

- Reading, writing, importing, or migrating old ODT-based `.spec` packages.
- Supporting arbitrary IEEE 1685-2022 XML outside the V1 profile.
- Supporting IP-XACT views, design configurations, abstractors, file sets,
  generators, memory maps, registers, address spaces, or power intent.
- Generating code or retaining generated artifacts.

## Canonical Package Contract

Use a custom ZIP package rather than an ODT-compatible archive.

```text
<name>.spec
  mimetype
  manifest.json
  ipxact/
    components/<vlnv-safe-name>.xml
    designs/<vlnv-safe-name>.xml
    bus-definitions/<vlnv-safe-name>.xml
    abstraction-definitions/<vlnv-safe-name>.xml
  document/document.json
  assets/<sha256>.<extension>
  annotations/                         optional, schema-owned inputs
  activity/                            reserved for V1.3 metadata
```

`mimetype` contains `application/vnd.spec2gds.spec+zip`. Store it first and
uncompressed. Sort every other ZIP entry lexically, use fixed ZIP timestamps,
and use deterministic compression settings. JSON is UTF-8 with LF line
endings and sorted keys. IP-XACT XML is emitted by one project serializer with
stable namespace prefixes, attribute order, indentation, and line endings.

The package is self-contained in V1. Every component, design, bus definition,
and abstraction definition referenced by source must be embedded in the
package.

## Source Interfaces

Define typed Pydantic contracts for the manifest and source metadata.

```text
SpecManifest
  format_version
  profile_version
  document_id
  ipxact_version = "1685-2022"
  documents: list[DocumentEntry]
  entry_designs: list[EntityRef]
  component_compositions: list[ComponentComposition]
  narrative_path
  assets: list[AssetEntry]
  annotation_schemas: list[AnnotationSchemaEntry]

DocumentEntry
  kind: component | design | bus_definition | abstraction_definition
  vlnv
  entity_id
  path
  sha256

ComponentComposition
  component: EntityRef
  internal_design: EntityRef
```

Use immutable opaque project IDs and IP-XACT `xml:id` values for references.
Names and VLNVs may change without changing entity identity. Reject duplicate
IDs, duplicate VLNVs within the same document kind, duplicate entry-design
references, and more than one composition mapping for a component.

Define a versioned narrative AST in `document/document.json`.

```text
NarrativeDocument
  version
  document_id
  blocks: list[NarrativeBlock]

NarrativeBlock
  block_id
  type: section | paragraph | list | table | image | entity_link | live_view
  children or typed content
  entity_refs
```

The V1 AST supports sections, paragraphs, inline formatting, ordered and
unordered lists, tables, image assets, entity links, and live-view blocks.
Live-view blocks store only a renderer ID, a target entity reference, and
typed options; their visible table or figure is derived at read time.

## V1 IP-XACT Profile

Validate all XML against IEEE 1685-2022 XSDs and then validate the narrower
project profile. The public in-memory model must not expose unprofiled XML as
editable state.

Allowed root documents:

- `component`
- `design`
- `busDefinition`
- `abstractionDefinition`

Allowed component data:

- VLNV, display name, short description, description, and `xml:id`.
- Parameters, choices, and assertions.
- `model/ports` with wire or transactional scalar/vector ports.
- Bus interfaces, one abstraction definition per bus interface, compatible
  port maps, and channels.
- Initiator, target, system, and monitor roles.

Allowed design data:

- Component instances and instance configuration values.
- Bus-interface interconnections, hierarchical interfaces, and ad-hoc port
  connections.
- Parameters, choices, and assertions.

Allowed bus and abstraction data:

- Identity and descriptions.
- Bus properties needed by the selected interface roles.
- Logical wire/transactional ports, directions, widths, qualifiers, packet
  metadata, and mapping constraints.
- Parameters, choices, and assertions.

Reject the following in V1:

- `model/views`, all model instantiations, and IP-XACT design configurations.
- Abstractors and abstraction-conversion chains.
- File sets, builders, generators, executable images, and clearbox metadata.
- Structured ports, arrays, reusable type definitions, field maps, and power
  constraints.
- Memory maps, address spaces, registers, CPUs, and indirect interfaces.
- Component modes, reset types, power domains, and arbitrary vendor
  extensions.
- Mirrored interface roles.

Connected interfaces must use compatible bus-definition and abstraction-
definition VLNVs because V1 has no abstractors.

## Implementation Steps

1. Add a new package-format subsystem alongside the legacy implementation;
   do not route existing editor/API entry points to it yet.
2. Implement ZIP creation, loading, deterministic serialization, and strict
   path validation. Reject path traversal, duplicate entries, missing
   `mimetype`, and unexpected top-level source entries.
3. Add manifest, narrative AST, entity-reference, asset, and profile models.
4. Add IP-XACT XSD validation plus project-profile validation. Use a typed
   profile parser rather than treating raw XML nodes as the public API.
5. Add source CLI commands: `create`, `validate`, `inspect`, `pack`, and
   `unpack`. New commands accept only the new package format.
6. Add a checked-in sample with leaf components, one bus/abstraction pair,
   one internal design, multiple entry designs, narrative blocks, and an image
   asset.
7. Document the format and mark ODT support as legacy pending the cutover in
   V1.4.

## Validation and Tests

- Repeated saves of the same logical package produce byte-identical output.
- Pack/unpack/pack preserves source hashes and ZIP bytes.
- Every manifest path, hash, ID, VLNV, entry design, composition, narrative
  block, and asset is validated.
- Profile tests accept every listed V1 construct and reject every excluded
  category with a targeted diagnostic.
- Invalid ZIPs, corrupt XML, missing files, bad hashes, duplicate entries,
  duplicate VLNVs, invalid `xml:id`, and malformed narrative JSON fail safely.
- Existing ODT-based `.spec` fixtures are rejected clearly by the new CLI.

## Assumptions

- The product prioritizes its own deterministic workflow over compatibility
  with office editors or arbitrary IP-XACT tools.
- No ODT migration path is provided.
- The `activity/` directory is excluded from source-format validation until
  V1.3 defines its contents.

## Exit Gate

The new sample can be created, inspected, validated, unpacked, repacked, and
reopened with byte-identical serialization. All format/profile tests pass, and
no new package API accepts ODT input.

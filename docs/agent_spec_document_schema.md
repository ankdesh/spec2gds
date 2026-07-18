# Agent-Spec V1 Document Schema and Interfaces

This document describes the current persisted `.spec` format and the stable
interfaces that operate on it. The source of truth is the strict models in
`spec2gds/agent_spec/spec_format/models.py`.

## Container Contract

A `.spec` file is a deterministic custom ZIP archive with media type
`application/vnd.spec2gds.spec+zip`.

```text
design.spec
├── mimetype
├── manifest.json
├── document/document.json
├── ipxact/
│   ├── components/*.xml
│   ├── designs/*.xml
│   ├── bus-definitions/*.xml
│   └── abstraction-definitions/*.xml
├── assets/<sha256>.<extension>
├── annotations/<registered-namespace>/...
└── activity/v1/actions.json
```

`mimetype` is the first uncompressed ZIP member. Remaining entries are sorted,
timestamps and permissions are fixed, JSON is canonicalized, and IP-XACT XML
is normalized. Saving identical content therefore produces identical bytes.

Paths are relative, slash-separated, and constrained to the allowlisted V1
subtrees. Absolute paths, traversal segments, backslashes, duplicate ZIP
members, and unexpected top-level entries are rejected.

## Manifest

`manifest.json` is a strict `SpecManifest` containing:

| Field | Meaning |
| --- | --- |
| `format_version` | Container contract generation; V1 requires `1`. |
| `profile_version` | Project IP-XACT profile generation; V1 requires `1`. |
| `document_id` | Stable XML-ID-compatible identity of the package. |
| `ipxact_version` | Required external schema version, `1685-2022`. |
| `documents` | Canonical index of IP-XACT documents and their hashes. |
| `entry_designs` | Explicit local design references exposed as top-level entries. |
| `component_compositions` | Component-to-owned-internal-design mappings. |
| `narrative_path` | Fixed at `document/document.json`. |
| `assets` | Source asset IDs, paths, hashes, and media types. |
| `annotation_schemas` | Registered extension namespaces and path prefixes. |

Each IP-XACT `DocumentEntry` records `kind`, four-part `vlnv`, stable
`entity_id`, canonical `path`, and `sha256`. Document IDs, paths, and
kind/VLNV pairs are unique.

## Stable Entity References

An `EntityRef` contains `document_id`, `entity_id`, and `entity_kind`. Supported
kinds are component, design, bus definition, abstraction definition, narrative
block, and asset.

Persisted relationships use `EntityRef` when identity and kind matter together:
entry designs, component compositions, narrative links, action targets, and
artifact provenance. VLNVs remain the protocol-native reference between
IP-XACT documents and instances.

## Narrative AST

`document/document.json` is a strict `NarrativeDocument` with the same
`document_id` as the manifest and globally unique stable block IDs.

| Block type | Required or meaningful fields |
| --- | --- |
| `section` | `text`, nested `children` |
| `paragraph` | `text`, optional `inlines` and `children` |
| `list` | non-empty `children`, optional `ordered` |
| `table` | non-empty string `rows` |
| `image` | `asset_id`, `alt_text`, optional `caption` |
| `entity_link` | one or more `entity_refs`, optional display `text` |
| `live_view` | exactly one `entity_ref`, `renderer_id`, optional `options` |

Inline nodes support text, emphasis, strong text, code, and links. A link may
use an external `href` or a stable entity reference.

Live views are derived projections. They do not duplicate IP-XACT tables or
topology as editable narrative source.

## IP-XACT Source

V1 accepts IEEE 1685-2022 component, design, bus definition, and abstraction
definition roots. XML is parsed with entity resolution and network access
disabled, validated against the bundled XSD set, normalized, and checked
against the narrower V1 profile.

Components own ports and bus interfaces. Designs own component instances,
interface interconnections, and ad-hoc port connections. Project-level
component composition and entry-design selection live in the manifest because
they are source relationships not represented by the selected IP-XACT subset.

## Assets and Annotations

Assets are source content addressed by SHA-256. Narrative image blocks refer to
the stable asset ID; the manifest binds that ID to bytes and media type.

Annotations are optional source inputs below registered namespace prefixes.
Unknown annotation paths are rejected. Accepted annotation bytes are part of
the source hash and action snapshot.

## Activity and Artifact Sidecar

`activity/v1/actions.json` stores execution records, ordered events, report
objects, artifact metadata, and change proposals. Activity is durable package
data but is excluded from the source revision hash.

Generated artifact bytes are not ZIP members. `ArtifactSidecar` stores them at
`sha256/<64-hex>` below an explicit filesystem root. `ArtifactRef` records the
content hash, size, media type, producing action/execution, source revision,
source entities, normalized inputs, selected input artifacts, and parent
artifact lineage.

## Source Revision Hash

The source revision hash covers the canonical manifest, narrative, IP-XACT
documents, assets, and accepted annotations. It excludes `activity/` so reports
and historical executions do not masquerade as source changes.

Every source-changing API request carries the expected hash. A mismatch is a
conflict, not a best-effort merge.

## Public Interfaces

| Interface | Purpose |
| --- | --- |
| `SpecPackage.create/load/save` | Construct, validate, and persist deterministic packages. |
| `SpecPackage.add_document/add_asset` | Populate a package through validated source boundaries. |
| `SpecPackage.diagnostics/require_valid` | Inspect or enforce structural and protocol validity. |
| `SpecPackage.source_hash` | Compute the canonical source identity. |
| `SpecRevision.load/from_package` | Build an immutable semantic source view. |
| `SpecEditTransaction.apply` | Apply atomic source operations to a private copy. |
| V1 HTTP API | Translate JSON requests into the same package, IR, transaction, and action contracts. |

## Validation Layers

1. ZIP safety and deterministic layout.
2. Strict manifest and narrative schema validation.
3. Embedded file set and SHA-256 agreement.
4. Safe XML parsing, IEEE XSD validation, and project profile validation.
5. Manifest and narrative reference integrity.
6. SpecIR semantic validation of hierarchy, endpoints, compatibility, and
   composition cycles.
7. Transaction revision checks and complete candidate revalidation.

See [`agent_spec_diagnostics.md`](agent_spec_diagnostics.md) for operational
diagnostics and [`ipxact_protocol.md`](ipxact_protocol.md) for protocol rules.

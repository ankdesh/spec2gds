# Agent-Spec Document Schema And Interfaces

## Purpose

This document explains what a `.spec` document is made of, why each piece
exists, and how the pieces refer to each other. It is written for contributors
who need to change the document model without first reverse-engineering ODT,
the editor, the plugin layer, and the action graph from code.

The short version: a `.spec` file is an office-compatible document package with
extra project-owned data. The visible specification remains normal ODT
`content.xml`; structured payloads and app metadata live under `spec_data/`.

This document focuses on the document contract itself. It does not cover import
executor integrations, benchmark rebuild workflows, or external execution systems.

## Mental Model

Think of a `.spec` file as five related layers stored in one package:

```text
ODT package
  visible prose and layout
    content.xml, styles.xml, images

semantic projection
  an in-memory/API view of content.xml
    headings, paragraphs, tables, images, links, editability

editor relations
  UI-owned relationships not suitable for visible prose
    section variant groups, active variant choices, IP-XACT attachments

structured payloads
  formal machine-readable hardware data
    IP-XACT XML, simple JSON examples, future modalities

agent-spec graph metadata
  server-owned action/run state
    document identity, heading blocks, versions, artifacts, runs
```

The layers are deliberately separated. `content.xml` stays readable by office
tools. `relations.json` records editor choices without changing visible text.
`spec_data/ipxact/*.xml` stores protocol data without flattening it into prose.
`graph.json` records action-oriented metadata without becoming the editor's
source of truth for text layout.

## How The Layers Connect

Most cross-layer relationships use a few stable identifiers:

| Identifier | Where it comes from | Used by |
| --- | --- | --- |
| Heading `xml:id` | `text:h` elements in `content.xml`; generated when missing | Semantic heading `block_id`, editor relation `heading_id`, action graph `block_id` |
| Positional `block-N` ID | Semantic parser assigns it to non-heading blocks | Editor text edits and section variant contents |
| `spec_data/...` path | Archive path for custom package parts | Relations, plugins, verifier, manifest registration |
| `spec://...` URI | Visible document hyperlink target | Plugin manager and verifier resolve payload nodes |
| Artifact ID | Action/run metadata | Graph attachments and persisted artifact records |

The heading ID is the most important bridge. A heading in `content.xml` becomes
a semantic heading block, can have editor-owned attachments, and becomes an
action graph block. If a heading ID changes, relations and graph metadata may no
longer point at the intended section.

Changing the visible heading text does not by itself break those connections.
The links between layers depend on the heading's hidden `xml:id`, not on the
title string a user sees. For example, this heading:

```xml
<text:h xml:id="h2-register-interface-1">Register Interface</text:h>
```

can be renamed to:

```xml
<text:h xml:id="h2-register-interface-1">APB Register Interface</text:h>
```

and still refer to the same semantic block, editor relation target, and action
graph block. Connections become invalid only when the `xml:id` is changed or
removed, or when the heading itself is deleted. That is most likely to happen
if an external ODT editor rewrites document structure or if project code
intentionally regenerates heading IDs.

## Package Layout

A `.spec` file is an ODT-style ZIP package. The core package still looks like a
text document, while agent-spec-owned data is stored below `spec_data/`.

```text
<document>.spec
  mimetype
  content.xml
  styles.xml
  META-INF/manifest.xml
  Pictures/...                         optional ODT image assets
  spec_data/
    ipxact/*.xml                       structured IP-XACT payloads
    simple-json/*.json                 simple JSON payloads used by tests/examples
    agent-spec/
      manifest.json
      graph.json
      versions/<block_id>/<version_id>.json
      artifacts/<artifact_id>.json
      runs/<run_id>/input_snapshot.json
      runs/<run_id>/run.json
      runs/<run_id>/events.ndjson
      writebacks/<writeback_id>.json
      checkpoints/<checkpoint_id>.json
    agent-spec-editor/
      relations.json
      active_section_versions.json
```

The `mimetype` entry is normalized to
`application/vnd.oasis.opendocument.text`. Custom entries must be under
`spec_data/` so the project can preserve and validate them consistently. They
should also be registered in `META-INF/manifest.xml`; some ODT-aware tools may
drop unknown package entries that are not listed there.

## Archive Layer

`AgentSpecArchive` is the lowest project-owned layer. It knows how to load,
save, inject, extract, and delete bytes under `spec_data/`. It does not know
what IP-XACT, relations, runs, or graph metadata mean.

That split is intentional. The archive wrapper protects the package mechanics,
while higher layers own schema validation.

| Method | Contract |
| --- | --- |
| `AgentSpecArchive(path=None)` | Opens an existing `.spec`/ODT package or creates a blank text document. On load, all `spec_data/` parts are cached as `bytes` in `custom_files`. |
| `inject_file(full_path_in_container, content, media_type)` | Stores bytes at a `spec_data/...` path, updates the ODT package part, and registers the path/media type in the manifest. |
| `extract_file(full_path_in_container)` | Returns a defensive byte copy from the custom-file cache. |
| `delete_file(full_path_in_container)` | Removes a custom part from the cache, package, and manifest on a best-effort basis. |
| `save(path=None)` | Saves the package and reorders the `mimetype` ZIP entry for ODT compatibility. |

Implementation: `spec2gds.agent_spec.package.archive`.

## Visible Document Body

The human-authored specification lives in ODT `content.xml`. The editor does
not expose raw XML to the frontend. Instead, `document/semantic.py` parses it
into a small model that contains only what the current editor needs.

This is why the project has a "semantic document" schema. It is not another
file inside the `.spec` package. It is an in-memory/API view derived from
`content.xml`.

Supported visible content:

| ODT element | Semantic `block_type` | Editable | Notes |
| --- | --- | --- | --- |
| `text:h` | `heading` | Yes, unless inline markup is present | Heading `xml:id` is the stable ID used by editor relations and the action graph. Missing IDs are generated. |
| `text:p` | `paragraph` | Yes, unless inline markup is present | Paragraph block IDs are positional, such as `block-3`. |
| `text:list/text:list-item/text:p` | `list_item` | Yes, unless inline markup is present | List items are flattened into editable text blocks. |
| `table:table` | `table` | No | Projected as rows and cells for display. |
| `draw:frame` with `draw:image` | `image` | No | Projected as an asset reference. Bytes are read from the ODT package. |
| `text:a` | `DocumentLink` on the containing block | N/A | `spec://` links are validated through the plugin manager. Other links are ignored by agent-spec validation. |

Section variant relationships are stored in `relations.json`, not inferred from
visible heading text. A heading that contains characters such as `//` is treated
as ordinary prose unless an explicit relation group points at that heading.

## Semantic Document Schema

The semantic document is what the editor receives from the backend and sends
text edits against. It sits between raw ODT XML and the UI.

```text
SemanticDocument
  blocks: list[SemanticBlock]
  section_groups: list[SectionVariantGroup]
  links: list[DocumentLink]
  diagnostics: list[Diagnostic]
```

`blocks` are the ordered editor projection of the document body. `links` is the
same link information gathered across all blocks. `section_groups` describes
mutually exclusive section variants. `diagnostics` records parser or validation
issues that may block saving.

`SemanticBlock` fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `block_id` | `str` | Stable heading ID for headings, positional ID for other blocks. |
| `block_type` | `str` | `heading`, `paragraph`, `list_item`, `table`, or `image`. |
| `text` | `str` | Raw visible text collected from the block. |
| `display_text` | `str` | Text displayed by the UI. Currently this matches `text` for parsed text blocks. |
| `level` | `int or null` | ODT outline level for headings. |
| `heading_id` | `str or null` | Heading `xml:id`; present only for heading blocks. |
| `editable` | `bool` | Whether plain-text editing can be safely applied. |
| `editable_reason` | `str` | Reason a block is read-only, when applicable. |
| `links` | `list[DocumentLink]` | Links contained in this block. |
| `table_rows` | `list[TableRow]` | Table projection for table blocks. |
| `image` | `ImageRef or null` | Image asset reference for image blocks. |
| `style_name` | `str or null` | ODT text style name, when present. |

`DocumentLink` fields are `href`, `text`, and `block_id`.

`SectionVariantGroup` fields are `group_id`, `title`, `level`, `variants`, and
`active_version`. Each `SectionVariant` has `version`, `heading_block_id`, and
`block_ids`.

Implementation: `spec2gds.agent_spec.document.semantic`.

## Editor Relations

Some relationships are real document state but do not belong in visible prose.
For example, "this IP-XACT XML belongs to this heading" is useful editor
metadata, but it should not be encoded by changing the heading text or mutating
the IP-XACT payload. Those relationships live in
`spec_data/agent-spec-editor/relations.json`.

```text
spec_data/agent-spec-editor/
  relations.json
  active_section_versions.json         compatibility copy of active selections
```

`relations.json` uses media type
`application/vnd.spec2gds.spec-editor-relations+json`.

```json
{
  "version": 2,
  "section_groups": [
    {
      "group_id": "h2-cache-behavior-0",
      "title": "Cache behavior",
      "level": 2,
      "variants": [
        {
          "version": "v1",
          "heading_id": "h2-cache-behavior-0",
          "block_ids": ["h2-cache-behavior-0", "block-4"]
        }
      ],
      "active_version": "v1"
    }
  ],
  "ipxact_attachments": {
    "h2-register-interface-1": [
      {
        "file_path": "spec_data/ipxact/component.xml"
      }
    ]
  }
}
```

Important relation rules:

- `section_groups` describes editor section variants without requiring variant
  metadata in visible heading text.
- `ipxact_attachments` maps heading IDs to embedded XML payload paths.
- IP-XACT attachment paths are normalized to `spec_data/ipxact/<name>.xml`.
- Invalid or missing relations should not make a document unreadable; the
  loader falls back to empty relation state when needed.

`active_section_versions.json` is an older compatibility copy of active
selection state. The source of truth is `active_version` on each
`SectionVersionGroup` in `relations.json`.

```json
{
  "version": 1,
  "active_section_versions": {
    "h2-cache-behavior-0": "v1"
  }
}
```

Implementation: `spec2gds.agent_spec.document.relations`.

## Structured Payloads And Plugins

Structured payloads are formal data embedded beside the prose. They are grouped
by modality under `spec_data/<modality_id>/...`. The archive layer stores
bytes, but a modality plugin owns the meaning of those bytes.

This keeps the `.spec` package open-ended. Adding a new structured data type
should not require changing `AgentSpecArchive`; it should require a plugin that
can validate, store, extract, and resolve that modality.

### Plugin Interface

Plugins implement `spec2gds.agent_spec.plugins.base.ModalityPlugin`.

| Member | Contract |
| --- | --- |
| `config.modality_id` | Unique route segment used in `spec_data/<modality_id>/` and `spec://<modality_id>/...`. |
| `config.file_extensions` | Supported suffixes, such as `.xml` or `.json`. |
| `config.media_type` | Manifest media type for injected package parts. |
| `validate_data(data)` | Raises or returns `True` when payload data conforms to the modality schema. |
| `inject_data(container, file_path, data)` | Serializes and writes payload data to the archive. |
| `extract_data(container, file_path)` | Reads archive bytes and returns a plugin-native parsed value. |
| `resolve_path(container, file_path, node_path)` | Resolves a node selector inside the payload. |

`PluginManager` registers plugins, delegates payload injection/extraction, and
resolves `spec://` links.

Implementation:

- `spec2gds.agent_spec.plugins.base`
- `spec2gds.agent_spec.plugins.manager`

### IP-XACT Payloads

IP-XACT is treated as an external standard, not as an agent-spec-invented data
shape. The `.spec` package may embed IP-XACT, attach it to headings, preview it,
and validate it, but it should not reinterpret IP-XACT semantics for UI
convenience.

Path pattern:

```text
spec_data/ipxact/<file>.xml
```

Media type:

```text
application/xml+ipxact
```

Payload data is raw XML bytes. Validation is performed by the IP-XACT plugin
through `pyEDAA.IPXACT`, which parses the document against the schema implied by
the XML namespace.

The editor uses a lighter summary so people can inspect component identity and
bus interfaces without reading raw XML:

```text
IpxactComponentSummary
  file_path: str
  component: IpxactVLNV
  interfaces: list[IpxactInterfaceSummary]
  diagnostics: list[Diagnostic]
```

`IpxactVLNV` has `vendor`, `library`, `name`, and `version`.
`IpxactInterfaceSummary` has `name`, `mode`, `bus_type`,
`abstraction_type`, and `port_maps`. Each port map has `logical_port` and
`physical_port`.

The editor treats missing component VLNV fields or missing formal
`busInterfaces/busInterface` elements as blocking diagnostics. Component
`model/ports` are not displayed as synthetic bus interfaces.

Implementation:

- `spec2gds.agent_spec.plugins.ipxact`
- `spec2gds.agent_spec.document.ipxact_view`
- `docs/ipxact_protocol.md`

### Simple JSON Payloads

The simple JSON modality exists mostly for tests, examples, and plugin plumbing
demos. It shows how a small schema-backed payload can live under `spec_data/`
and be addressed by `spec://`.

Path pattern:

```text
spec_data/simple-json/<file>.json
```

Media type:

```text
application/x-spec-json
```

Schema:

```json
{
  "title": "Component name",
  "version": "1.0",
  "metadata": [
    {
      "name": "key",
      "value": "string, integer, or boolean",
      "description": "optional text"
    }
  ]
}
```

Implementation: `spec2gds.agent_spec.plugins.json_payload`.

## `spec://` Links

`spec://` links connect visible prose to embedded structured payloads. A user
can see a hyperlink in the document, while the verifier and editor can resolve
that link to a specific payload node.

Syntax:

```text
spec://<modality_id>/<file_path>/<node_path>
```

Examples:

```text
spec://simple-json/registers.json/metadata/0/value
spec://ipxact/component.xml//*[local-name()='busInterface']
```

Resolution rules:

- `<modality_id>` selects a registered plugin.
- `<file_path>` is interpreted by that plugin and may accept friendly names
  without an extension.
- `<node_path>` is plugin-specific.
- Simple JSON node paths use slash-separated dict keys and list indexes.
- IP-XACT node paths first try pyEDAA object traversal, then fall back to lxml
  XPath with common `spirit` and `ipxact` namespace prefixes.

Only links whose `href` starts with `spec://` are part of this contract. Normal
web or file links remain ordinary document links.

Implementation: `spec2gds.agent_spec.plugins.manager`.

## Agent-Spec Graph Metadata

The graph metadata is the action-facing view of the document. It answers
questions like: which headings are runnable blocks, what version of a section is
active, what generated artifacts are attached, and what runs have occurred?

It is stored under `spec_data/agent-spec/` because it is project-owned metadata,
not visible document prose and not editor UI-only state.

```text
spec_data/agent-spec/
  manifest.json
  graph.json
  versions/<block_id>/<version_id>.json
  artifacts/<artifact_id>.json
  runs/<run_id>/input_snapshot.json
  runs/<run_id>/run.json
  runs/<run_id>/events.ndjson
  writebacks/<writeback_id>.json
  checkpoints/<checkpoint_id>.json
```

All JSON entries use media type
`application/vnd.spec2gds.agent-spec+json`.

`manifest.json` gives the document a durable identity:

| Field | Type |
| --- | --- |
| `document_id` | `str` |
| `schema_version` | `int`, default `1` |
| `created_at` | `str` |
| `updated_at` | `str` |
| `user_identity` | `str` |
| `sidecar_root` | `str` |

`graph.json` stores the current block/artifact graph:

| Field | Type |
| --- | --- |
| `version` | `int`, default `2` |
| `blocks` | `dict[str, BlockRecord]` |
| `active_versions` | `dict[str, str]` mapping block ID to active version ID |
| `artifact_refs` | `dict[str, ArtifactRef]` |
| `attachments` | `dict[str, list[AttachmentRecord]]` |

`BlockRecord` fields are `block_id`, `heading_id`, `title`, `level`, and
`versions`.

`BlockVersionRecord` fields are `version_id`, `block_id`, `content_hash`,
`block_ids`, `artifact_ref_ids`, and `created_at`. A version covers the heading
block and following semantic blocks until the next heading at the same or higher
level. The content hash includes section text and attached artifact IDs.

`ArtifactRef` fields are `artifact_id`, `artifact_kind`, `media_type`,
`summary`, `sha256`, `external_uri`, `producer`, `source_trace`, `role`, and
`created_at`.

`AttachmentRecord` fields are `attachment_id`, `block_id`, `artifact_id`,
`role`, `run_id`, and `created_at`.

Run, report, artifact-application, and checkpoint records are part of the persisted document schema
because they live inside the package. Their runtime lifecycle is described in
`docs/agent_spec_action_execution.md`.

Implementation:

- `spec2gds.agent_spec.models`
- `spec2gds.agent_spec.storage.repository`

## Editor Session Interface

`EditorSession` is the main document-level facade used by the local editor API.
It hides the lower-level mechanics: load the archive, ensure heading IDs, parse
the semantic document, load relations, summarize IP-XACT, apply edits, and save
the package.

```text
EditorSnapshot
  document: SemanticDocument
  ipxact_components: list[IpxactComponentSummary]
  relations: EditorRelations
  active_section_versions: dict[str, str]
  diagnostics: list[Diagnostic]
```

The snapshot is the editor's joined view of several package layers: visible
content, embedded IP-XACT payloads, editor relations, active section choices,
and diagnostics.

| Method | Document contract |
| --- | --- |
| `from_path(path)` | Opens a `.spec` document as an editor session. |
| `snapshot()` | Returns `EditorSnapshot`. |
| `apply_text_edits(edits)` | Applies plain-text edits keyed by semantic `block_id` to editable headings, paragraphs, and list items. |
| `persist_active_versions(active_versions)` | Persists active section-version choices in relation and compatibility formats. |
| `persist_relations(relations)` | Normalizes and stores `relations.json`. |
| `preview_ipxact_xml(file_path, xml_text)` | Returns an IP-XACT summary for unsaved XML text. |
| `update_ipxact_xml(file_path, xml_text)` | Replaces an embedded IP-XACT XML part after blocking diagnostics are clear. |
| `asset_bytes(asset_id)` | Reads image bytes referenced by a semantic image block. |
| `save(path)` | Persists editor metadata and saves the `.spec` package if no blocking diagnostics remain. |

Implementation: `spec2gds.agent_spec.document.session`.

## HTTP Document Interfaces

The local editor API exposes document operations as HTTP endpoints. These are
thin wrappers over `EditorSession`; they do not define a separate document
model.

| Endpoint | Interface |
| --- | --- |
| `GET /documents/snapshot?path=...` | Returns `EditorSnapshot`. |
| `POST /documents/active-section-versions?path=...` | Body is `dict[str, str]`; persists active section versions and returns `EditorSnapshot`. |
| `POST /documents/text-edits?path=...` | Body is `dict[block_id, text]`; applies edits and returns `EditorSnapshot`. |
| `POST /documents/save?path=...` | Body is `EditorSaveRequest`; applies text, relation, and IP-XACT edits together. |
| `POST /ipxact/preview` | Body is `{ "file_path": str, "xml_text": str }`; returns `IpxactComponentSummary`. |
| `POST /documents/ipxact-xml?path=...` | Body is `{ "file_path": str, "xml_text": str }`; updates one embedded XML payload. |
| `GET /documents/assets/{asset_id}?path=...` | Returns embedded image bytes. |
| `GET /files?directory=...` | Returns directories and `.spec` files for the local file browser. |

`EditorSaveRequest` schema:

```text
text_edits: dict[str, str]
relations: EditorRelations or null
ipxact_xml_edits: dict[str, str]
```

The mounted action API under `/agent-spec` also reads and writes the same
document package, especially `manifest.json`, `graph.json`, versions,
artifacts, runs, and writebacks.

Action context endpoints under `/agent-spec/` use a shared read/query service
rather than the editor-only response shape. They are read-only and
return versioned response envelopes with document hash, loaded timestamp, data,
and diagnostics. The section context endpoint is the primary executor input
shape: it joins block metadata, the active or explicit version, covered
semantic blocks, section links, relevant relations, attached IP-XACT summaries,
artifact attachments, and diagnostics.

Executor completion is an explicit mutation route. It validates returned
`ArtifactRef` metadata and report data, attaches accepted artifacts, and records
report/audit metadata under `spec_data/agent-spec/`. It does not automatically
rewrite visible document prose.

Implementation:

- `spec2gds.agent_spec.api.document_app`
- `spec2gds.agent_spec.api.app`
- `spec2gds.agent_spec.query`

## Verification Interface

`ContainerVerifier` checks whether the package is internally consistent without
running import flows or action execution.

It validates:

- every cached `spec_data/` file has a manifest entry when possible
- modality-owned payloads can be parsed and validated by their plugin
- editor-owned JSON metadata is parseable JSON
- visible `spec://` links in `content.xml` resolve through `PluginManager`

The report schema is:

```text
ContainerVerificationReport
  container_path: str
  timestamp: datetime
  files: list[FileVerification]
  links: list[LinkVerification]
  is_fully_consistent: bool
```

Implementation: `spec2gds.agent_spec.package.verifier`.

## What To Change Where

Use this table when deciding where a document-model change belongs.

| Change | Likely owner |
| --- | --- |
| Package load/save behavior or custom file preservation | `package/archive.py` |
| How visible ODT content becomes editable blocks | `document/semantic.py` |
| Relationships between headings, section variants, and IP-XACT files | `document/relations.py` and `document/session.py` |
| IP-XACT protocol parsing or summary behavior | `plugins/ipxact.py`, `document/ipxact_view.py`, and `docs/ipxact_protocol.md` |
| New structured payload modality | `plugins/base.py`, `plugins/manager.py`, and a new plugin |
| Action graph blocks, versions, artifacts, and persisted run metadata | `models.py` and `storage/repository.py` |
| Editor HTTP request/response shape | `api/document_app.py` |
| Action context APIs | `query.py` and `api/app.py` |
| Executor completion APIs | `runs/runner.py` and `api/app.py` |
| Package consistency checks | `package/verifier.py` |

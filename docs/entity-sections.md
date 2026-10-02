# Entity sections and SystemVerilog bodies

Components and designs expose typed content through one central section
registry. The built-in registry currently contains:

| Type | Owners | Cardinality | Storage | Editable |
| --- | --- | --- | --- | --- |
| `text` | component, design | singleton | IP-XACT `description` adapter | yes |
| `ports` | component | singleton | IP-XACT port adapter | yes |
| `sv` | component, design | optional singleton | annotation `.sv` file | yes; deletable |

Each definition supplies its stable type/version, title, supported owners,
cardinality, presentation order, persistence behavior, and edit/delete
capabilities. Backend projections expose present sections plus the singleton
types still available to add. The frontend dispatches persisted content through
a renderer registry keyed by section type. Add a future built-in type to both
registries and their completeness tests; do not add another feature-specific
branch to package loading or the editor shell.

## Package layout

The `.spec` format and profile remain V1. Persisted sections use the existing
forward-compatible annotation area:

```text
annotations/entity-sections/index.json
annotations/entity-sections/sv/<section-id>.sv
```

The manifest registers `annotations/entity-sections` under the
`spec2gds.entity-sections` annotation namespace while at least one persisted
section exists. The registration and index disappear when the last section is
deleted. An index entry contains the stable section ID, type and version,
owner `EntityRef`, media type, safe relative path, and SHA-256 digest. Loading
validates the index, paths, hashes, owner existence, type support, and
cardinality. Deleting an owner also deletes its section content.

SystemVerilog text is normalized to UTF-8 with LF line endings. NUL bytes and
content above 256 KiB are rejected; empty and whitespace-only bodies are valid.
Packages without this annotation remain valid and need no migration.

## Editing and API

Use revision-guarded `upsert_entity_section` and `delete_entity_section`
operations. An SV upsert uses this shape:

```json
{
  "type": "upsert_entity_section",
  "owner": {"document_id": "example", "entity_kind": "component", "entity_id": "alu"},
  "section_type": "sv",
  "type_version": 1,
  "payload": {"content": "assign result = a + b;\n"}
}
```

An existing singleton keeps its section ID. A new singleton derives a stable ID
from its owner unless the caller supplies one. Transaction responses and the V2
snapshot/document projection include `verified`, `warnings`, `unverified`, or
`errors` status and source-located diagnostics.

In the editor, choose **Options → Add section → SystemVerilog**. CodeMirror 6
provides line numbers, indentation, and the official legacy
Verilog/SystemVerilog mode. Saved source renders inline with Edit and Delete;
Delete asks for confirmation. Rejected and stale saves keep the browser draft.

## Body contract and validation

An SV section is IEEE 1800-2017 module-body content. Declarations, assigns,
procedural blocks, tasks, functions, and assertions are accepted. A section may
not declare `module`/`endmodule`, use external `` `include``, or supply its own
`` `line`` directive.

When Verilator 5.x is available, save and open validation lint the generated
module context. Syntax errors and safety warnings such as undriven or multiply
driven signals, width mismatches, inferred latches, incomplete/overlapping
cases, and combinational loops are blocking. Style and unused warnings are
reported but do not block. A missing tool, timeout, or unsupported surrounding
RTL profile yields `unverified` and keeps the source editable.

Active bodies require plain, non-keyword SystemVerilog identifiers for ports,
design instances, and connection nets because snippets reference those names
unchanged. Module names and filenames retain the generator's existing stable
normalization.

## RTL behavior

`rtl.generate` 1.2.0 inserts generated nets and instances first, then the
component body, then the owned/design body. Generated `` `line`` mappings point
tool diagnostics at the stored section path. Active modules use `input logic`,
`output logic`, and `inout wire`. A non-empty leaf body removes automatic
output/inout tie-offs; an empty or missing body retains the existing scaffold.
Generation manifests and reports use V3 (with saved V2 reading support) and record each consumed section ID,
digest, source path, and generated output path.

The one-cycle and two-cycle component examples, their generated projects, and
the fixture regeneration command are documented in
[RTL semantics examples](rtl-semantics-examples.md).

Owned designs inherit their owning component's ports. Entry and otherwise
unowned designs remain portless. Storing a section does not expand the RTL
generator's wire-only topology profile.

## Verification

Use the repository environments and rebuild the packaged editor:

```bash
uv sync
uv run python -m pytest -q

cd circuit-designer
npm install
npm test
npm run build:editor
```

Install Verilator 5.x for verified save-time and generated-project lint.

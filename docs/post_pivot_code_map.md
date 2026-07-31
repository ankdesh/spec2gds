# Post-Pivot V1 Code Map

This is the short navigation map for the retained implementation. For design
rationale and runtime flows, read
[`agent_spec_architecture.md`](agent_spec_architecture.md).

| Path | Ownership |
| --- | --- |
| `spec2gds/agent_spec/spec_format/models.py` | Strict persisted source and identity contracts. |
| `spec2gds/agent_spec/spec_format/archive.py` | Deterministic package I/O and structural validation. |
| `spec2gds/agent_spec/spec_format/ipxact.py` | Safe IEEE 1685-2022 parsing and V1 profile. |
| `spec2gds/agent_spec/spec_format/ir.py` | Immutable semantic model, queries, and diagnostics. |
| `spec2gds/agent_spec/spec_format/transactions.py` | Atomic revision-guarded edits. |
| `spec2gds/agent_spec/spec_format/actions.py` | Snapshots, execution, artifacts, activity, proposals. |
| `spec2gds/agent_spec/spec_format/reference_actions.py` | Generic acceptance executors. |
| `spec2gds/agent_spec/spec_format/document.py` | Unified document projection and A2UI v0.9 compiler. |
| `spec2gds/agent_spec/spec_format/v1_api.py` | Local application/API composition root. |
| `circuit-designer/packages/document-core/` | Renderer-independent editor HTTP and document contracts. |
| `circuit-designer/packages/document-a2ui-react/` | Semantic React A2UI document catalog. |
| `circuit-designer/apps/editor/` | Native React editor shell and Vite composition root. |
| `spec2gds/agent_spec/spec_format/editor_dist/` | Prebuilt editor assets served by FastAPI. |
| `spec2gds/agent_spec/spec_format/samples.py` | Deterministic visual acceptance package. |
| `spec2gds/agent_spec/spec_format/cli.py` | Package create/validate/inspect/pack/unpack commands. |
| `spec2gds/agent_spec/api/__main__.py` | `spec2gds-server` and `spec2gds-editor` entry point. |

## Independent Circuit Designer

Circuit Designer is not part of the Python/SpecIR runtime. Its external
boundary is REST.

| Path | Ownership |
| --- | --- |
| `circuit-designer/schema/` | Authoritative portable JSON Schema. |
| `circuit-designer/packages/core/` | Circuit model, generated types, validation, operations, drafts, hierarchy, queries, and exports. |
| `circuit-designer/packages/client-http/` | REST client and response validation. |
| `circuit-designer/packages/service/` | REST/SSE service, ephemeral session state, PNG rendering, and provider callbacks. |
| `circuit-designer/packages/layout/` | Placement and orthogonal-routing worker. |
| `circuit-designer/packages/react/` | Canvas rendering and interaction gestures. |
| `circuit-designer/apps/standalone/` | Human React client and portable file upload/download. |

Start with
[`circuit_designer_architecture_v1.md`](circuit_designer_architecture_v1.md)
for system ownership and runtime flows.

## Spec System Runtime Sequence

```text
load package → validate → immutable SpecRevision
                         ├─ document projection → A2UI batch → browser rendering
                         ├─ transaction → validate candidate → save revision
                         └─ action snapshot → executor → artifact/proposal review
```

## Navigation by Task

- Format and schema: [`agent_spec_document_schema.md`](agent_spec_document_schema.md)
- Semantic reads/writes: [`spec_ir_v1.md`](spec_ir_v1.md)
- Actions and provenance: [`agent_spec_action_execution.md`](agent_spec_action_execution.md)
- Server/editor: [`spec_editor_v1.md`](spec_editor_v1.md)
- Circuit Designer: [`circuit_designer_architecture_v1.md`](circuit_designer_architecture_v1.md)
- Implementation workflow: [`development_methodology.md`](development_methodology.md)
- Future work: [`agent_spec_roadmap_questions.md`](agent_spec_roadmap_questions.md)

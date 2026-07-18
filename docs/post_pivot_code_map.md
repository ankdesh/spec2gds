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
| `spec2gds/agent_spec/spec_format/v1_api.py` | Local application/API composition root. |
| `spec2gds/agent_spec/spec_format/editor/` | No-build browser presentation. |
| `spec2gds/agent_spec/spec_format/samples.py` | Deterministic visual acceptance package. |
| `spec2gds/agent_spec/spec_format/cli.py` | Package create/validate/inspect/pack/unpack commands. |
| `spec2gds/agent_spec/api/__main__.py` | `spec2gds-server` and `spec2gds-editor` entry point. |

## Runtime Sequence

```text
load package → validate → immutable SpecRevision
                         ├─ query → API snapshot → browser rendering
                         ├─ transaction → validate candidate → save revision
                         └─ action snapshot → executor → artifact/proposal review
```

## Navigation by Task

- Format and schema: [`agent_spec_document_schema.md`](agent_spec_document_schema.md)
- Semantic reads/writes: [`spec_ir_v1.md`](spec_ir_v1.md)
- Actions and provenance: [`agent_spec_action_execution.md`](agent_spec_action_execution.md)
- Server/editor: [`spec_editor_v1.md`](spec_editor_v1.md)
- Implementation workflow: [`development_methodology.md`](development_methodology.md)
- Future work: [`agent_spec_roadmap_questions.md`](agent_spec_roadmap_questions.md)

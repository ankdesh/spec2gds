# Historical Documents

Files in this directory are retained only to explain earlier decisions and
migrations. They are not current contracts, run instructions, or implementation
plans.

For the current Circuit Designer, use:

- [Design and Architecture](../circuit_designer_architecture_v1.md)
- [Protocol](../circuit_designer_protocol_v1.md)
- [Provider Boundary](../circuit_designer_provider_v1.md)
- [Agent Tools and Proposals](../circuit_designer_tools_v1.md)
- [Run Guide](../circuit_designer_run_v1.md)

## Archived Circuit Designer material

| Document | Historical subject |
| --- | --- |
| [Phase 0](circuit_designer_phase0.md) | SpecIR-to-canvas read-only projection |
| [Phase 1](circuit_designer_phase1.md) | Former FastAPI Circuit Designer routes |
| [Completed roadmap](circuit_designer_complete.md) | Former command protocol and SpecIR persistence plan |
| [Standalone design](circuit_designer_standalone.md) | Removed local backend and earlier canvas workbench |
| [UI feature selection](circuit_designer_ui_feature_selection.md) | Pre-v1 feature-selection worksheet |
| [Interactive feature worksheet](circuit_designer_ui_feature_selection.html) | HTML form corresponding to the archived worksheet |

The current implementation is REST-only, keeps sessions in service memory, and
has no SQLite, IndexedDB, local-backend package, or active SpecIR integration.

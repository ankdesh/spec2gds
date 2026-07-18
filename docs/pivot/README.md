# Completed IP-XACT-Centered `.spec` Pivot Plans

These documents preserve the approved, gated migration from the retired
ODT-centered prototype to the current IP-XACT-centered `.spec` format. All four
V1 plans are implemented and their exit gates are covered by the active test
suite. Read them as design and acceptance history, not pending instructions.

## Completed V1 Sequence

1. [V1.1: Spec Package and Schema](v1_01_spec_package_and_schema.md)
2. [V1.2: SpecIR and Validation](v1_02_spec_ir_and_validation.md)
3. [V1.3: Actions, Artifacts, and Change Proposals](v1_03_actions_artifacts_and_change_proposals.md)
4. [V1.4: Editor, API, Cutover, and Acceptance](v1_04_editor_api_cutover_and_acceptance.md)

## Future Roadmap

- [V2, V3, and V4 Roadmap](future_v2_v3_v4_roadmap.md)

## Current V1 Product Boundary

V1 provides the new format and generic action platform. It does not generate
SystemC or RTL. Those capability packs begin in V2 and V3 on top of the stable
format, SpecIR, artifact provenance, and reviewed writeback paths.

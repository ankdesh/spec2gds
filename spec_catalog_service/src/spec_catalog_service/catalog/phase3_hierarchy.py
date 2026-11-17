"""Hierarchical 3-Tier Design Builder for Phase 3 Components.

Constructs:
- Level 1: Root composite Component and its internal Design.
- Level 2: Subsystem Components and their internal Designs.
- Level 3: Leaf behavioral Components (SystemVerilog body sections with provenance metadata).
"""

from __future__ import annotations

from typing import Any

from spec2gds.spec.spec_format.ir import (
    ConnectionIR,
    ExternalPortEndpointIR,
    InstanceIR,
    PortEndpointIR,
)
from spec2gds.spec.spec_format.models import EntityRef
from spec2gds.spec.spec_format.transactions import (
    CreateHardware,
    InitialComponentPort,
    SetInternalDesign,
    UpdateParameter,
    UpsertConnection,
    UpsertInstance,
    UpsertSection,
    WirePortInput,
)
from spec_catalog_service.catalog.components.models import ComponentDef


def build_phase3_hierarchy_ops(comp_def: ComponentDef, doc_id: str) -> list[Any]:
    """Generate all atomic transaction operations for the 3-tier hierarchy of a Phase 3 component."""
    top_comp_ref = EntityRef(document_id=doc_id, entity_id=f"component_{comp_def.id}", entity_kind="component")
    top_des_ref = EntityRef(document_id=doc_id, entity_id=f"design_{comp_def.id}", entity_kind="design")

    # Common Level 3 leaf units with Phase 1 / Phase 2 provenance
    # MUX leaf (Provenance: Phase 1 logic/mux/1.0.0)
    mux_ref = EntityRef(document_id=doc_id, entity_id=f"component_{comp_def.id}_leaf_mux", entity_kind="component")

    # Subsystem 0 (u_sub0)
    sub0_comp_ref = EntityRef(document_id=doc_id, entity_id=f"component_{comp_def.id}_sub0", entity_kind="component")
    sub0_des_ref = EntityRef(document_id=doc_id, entity_id=f"design_{comp_def.id}_sub0", entity_kind="design")

    # Level 3 Leaf 0 (for sub0)
    leaf0_ref = EntityRef(document_id=doc_id, entity_id=f"component_{comp_def.id}_leaf0", entity_kind="component")

    ops: list[Any] = []

    # 1. Author Level 3 Leaf Components
    # Leaf 0
    ops.append(
        CreateHardware(
            kind="component",
            name=f"{comp_def.id}_leaf0",
            entity_id=leaf0_ref.entity_id,
            vlnv=f"spec2gds.local:{comp_def.category}:{comp_def.id}_leaf0:{comp_def.version}",
            systemverilog=comp_def.systemverilog,
            ports=tuple(
                InitialComponentPort(
                    name=p.name,
                    port=WirePortInput(direction=p.direction, range=p.range_expr, description=p.description),  # type: ignore[arg-type]
                )
                for p in comp_def.ports
            ),
        )
    )
    for param in comp_def.parameters:
        ops.append(
            UpdateParameter(
                leaf0_ref,
                {"name": param.name, "rtl_type": param.rtl_type, "value": param.default_value, "description": param.description},
            )
        )
    ops.append(
        UpsertSection(
            parent=leaf0_ref,
            section_type="text",
            type_version=1,
            payload={"content": f"Level 3 Leaf Primitive for {comp_def.id}. Behavioral computation unit."},
        )
    )

    # Leaf Mux (Provenance: Phase 1 logic/mux/1.0.0)
    ops.append(
        CreateHardware(
            kind="component",
            name=f"{comp_def.id}_leaf_mux",
            entity_id=mux_ref.entity_id,
            vlnv=f"spec2gds.local:logic:{comp_def.id}_leaf_mux:1.0.0",
            systemverilog="    assign data_o = sel_i ? data1_i : data0_i;\n",
            ports=(
                InitialComponentPort("sel_i", WirePortInput(direction="in", range=None)),
                InitialComponentPort("data0_i", WirePortInput(direction="in", range="W-1:0")),
                InitialComponentPort("data1_i", WirePortInput(direction="in", range="W-1:0")),
                InitialComponentPort("data_o", WirePortInput(direction="out", range="W-1:0")),
            ),
        )
    )
    w_param = next((p for p in comp_def.parameters if p.name in {"W", "IW", "WIDTH", "DATA_W"}), None)
    w_val = w_param.default_value if w_param else "32"
    ops.append(
        UpdateParameter(
            mux_ref,
            {"name": "W", "rtl_type": "int unsigned", "value": w_val, "description": "Data width in bits"},
        )
    )
    ops.append(
        UpsertSection(
            parent=mux_ref,
            section_type="text",
            type_version=1,
            payload={"content": "Level 3 Leaf Unit: 2-to-1 Multiplexer. Provenance: Copied from Phase 1 logic/mux/1.0.0."},
        )
    )

    # 2. Author Level 2 Subsystems
    # Subsystem 0: Core calculation subsystem
    ops.append(
        CreateHardware(
            kind="component",
            name=f"{comp_def.id}_sub0",
            entity_id=sub0_comp_ref.entity_id,
            vlnv=f"spec2gds.local:{comp_def.category}:{comp_def.id}_sub0:{comp_def.version}",
            ports=tuple(
                InitialComponentPort(
                    name=p.name,
                    port=WirePortInput(direction=p.direction, range=p.range_expr, description=p.description),  # type: ignore[arg-type]
                )
                for p in comp_def.ports
            ),
        )
    )
    for param in comp_def.parameters:
        ops.append(
            UpdateParameter(
                sub0_comp_ref,
                {"name": param.name, "rtl_type": param.rtl_type, "value": param.default_value, "description": param.description},
            )
        )
    ops.append(
        CreateHardware(
            kind="design",
            name=f"{comp_def.id}_sub0_design",
            entity_id=sub0_des_ref.entity_id,
            vlnv=f"spec2gds.local:{comp_def.category}:{comp_def.id}_sub0_design:{comp_def.version}",
            entry_design=False,
        )
    )
    ops.append(SetInternalDesign(sub0_comp_ref, sub0_des_ref))
    ops.append(
        UpsertInstance(
            sub0_des_ref,
            InstanceIR(name="u_core", component_vlnv=f"spec2gds.local:{comp_def.category}:{comp_def.id}_leaf0:{comp_def.version}",
                       parameter_values={p.name: p.name for p in comp_def.parameters}),
        )
    )
    # Wire sub0 boundary ports to leaf0 instance ports
    for p in comp_def.ports:
        ops.append(
            UpsertConnection(
                sub0_des_ref,
                ConnectionIR(
                    name=f"net_{p.name}",
                    kind="ad_hoc",
                    port_endpoints=(PortEndpointIR(instance_name="u_core", port_name=p.name),),
                    external_ports=(ExternalPortEndpointIR(port_name=p.name),),
                ),
            )
        )
    ops.append(
        UpsertSection(
            parent=sub0_comp_ref,
            section_type="text",
            type_version=1,
            payload={"content": f"Level 2 Subsystem for {comp_def.id}: Encapsulates computation logic."},
        )
    )

    # 3. Author the root Component and its internal Design
    ops.append(
        CreateHardware(
            kind="component",
            name=comp_def.id,
            entity_id=top_comp_ref.entity_id,
            vlnv=f"spec2gds.local:{comp_def.category}:{comp_def.id}:{comp_def.version}",
            ports=tuple(
                InitialComponentPort(
                    name=p.name,
                    port=WirePortInput(direction=p.direction, range=p.range_expr, description=p.description),  # type: ignore[arg-type]
                )
                for p in comp_def.ports
            ),
        )
    )
    for param in comp_def.parameters:
        ops.append(
            UpdateParameter(
                top_comp_ref,
                {"name": param.name, "rtl_type": param.rtl_type, "value": param.default_value, "description": param.description},
            )
        )
    ops.append(
        CreateHardware(
            kind="design",
            name=f"{comp_def.id}_top_design",
            entity_id=top_des_ref.entity_id,
            vlnv=f"spec2gds.local:{comp_def.category}:{comp_def.id}_top_design:{comp_def.version}",
            entry_design=False,
        )
    )
    ops.append(SetInternalDesign(top_comp_ref, top_des_ref))
    ops.append(
        UpsertInstance(
            top_des_ref,
            InstanceIR(name="u_calc_stage", component_vlnv=f"spec2gds.local:{comp_def.category}:{comp_def.id}_sub0:{comp_def.version}",
                       parameter_values={p.name: p.name for p in comp_def.parameters}),
        )
    )
    # Connect top boundary to u_calc_stage
    for p in comp_def.ports:
        ops.append(
            UpsertConnection(
                top_des_ref,
                ConnectionIR(
                    name=f"net_{p.name}",
                    kind="ad_hoc",
                    port_endpoints=(PortEndpointIR(instance_name="u_calc_stage", port_name=p.name),),
                    external_ports=(ExternalPortEndpointIR(port_name=p.name),),
                ),
            )
        )
    ops.append(
        UpsertSection(
            parent=top_comp_ref,
            section_type="text",
            type_version=1,
            payload={"content": f"Level 1 Root Composite Component: {comp_def.summary}"},
        )
    )

    return ops

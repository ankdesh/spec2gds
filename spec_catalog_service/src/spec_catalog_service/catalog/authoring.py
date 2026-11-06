"""Authoring helpers for creating canonical Spec Component packages and documentation."""

from __future__ import annotations

from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.models import EntityRef
from spec2gds.spec.spec_format.transactions import (
    AddAsset,
    CreateHardware,
    InitialComponentPort,
    SpecEditTransaction,
    UpdateParameter,
    WirePortInput,
)
from spec_catalog_service.catalog.components.models import ComponentDef
from spec_catalog_service.catalog.phase3_hierarchy import build_phase3_hierarchy_ops
from spec_catalog_service.catalog.schemas import CatalogueAssetV1


def build_component_spec(comp_def: ComponentDef) -> SpecPackage:
    """Build and strictly validate one self-contained .spec package for a component."""
    pkg = SpecPackage.create(title=comp_def.summary or comp_def.id)
    rev = SpecRevision.from_package(pkg)
    doc_id = pkg.manifest.document_id
    comp_ref = EntityRef(document_id=doc_id, entity_id=f"component_{comp_def.id}", entity_kind="component")

    is_hierarchical = comp_def.implementation == "composite"

    cat_meta = CatalogueAssetV1(
        schema_version=1,
        root=comp_ref,
        id=comp_def.id,
        category=comp_def.category,
        version=comp_def.version,
        summary=comp_def.summary,
        tags=sorted(set(comp_def.tags)),
        licence=comp_def.licence,
        implementation="composite" if is_hierarchical else "body_sv",
        contracts=f"docs/TEMP_spec_library_plan/plans/phase-{comp_def.phase}.md#{comp_def.contract_anchor or comp_def.id}",
        presets=comp_def.presets,
        timing=comp_def.timing,
        limitations=comp_def.limitations,
        dependencies=[],
    )

    if is_hierarchical:
        ops = build_phase3_hierarchy_ops(comp_def, doc_id)
    else:
        initial_ports = tuple(
            InitialComponentPort(
                name=port.name,
                port=WirePortInput(
                    direction=port.direction,  # type: ignore[arg-type]
                    range=port.range_expr,
                    description=port.description,
                ),
            )
            for port in comp_def.ports
        )

        ops = [
            CreateHardware(
                kind="component",
                name=comp_def.id,
                entity_id=comp_ref.entity_id,
                vlnv=f"spec2gds.local:{comp_def.category}:{comp_def.id}:{comp_def.version}",
                systemverilog=comp_def.systemverilog,
                ports=initial_ports,
            )
        ]

        for param in comp_def.parameters:
            ops.append(
                UpdateParameter(
                    comp_ref,
                    {
                        "name": param.name,
                        "rtl_type": param.rtl_type,
                        "value": param.default_value,
                        "description": param.description,
                    },
                )
            )

    cat_bytes = cat_meta.model_dump_json(indent=2).encode("utf-8")
    ops.append(
        AddAsset(
            asset_id="library_catalogue_v1",
            data=cat_bytes,
            media_type="application/json",
            extension="json",
        )
    )

    res = SpecEditTransaction(rev.source_revision_hash, tuple(ops), validation_mode="strict").apply(rev)
    if not res.succeeded or res.revision is None:
        raise ValueError(
            f"Failed to author component {comp_def.id}: {'; '.join(res.diagnostics)}"
        )
    return res.revision.to_package()


def build_component_usage_markdown(comp_def: ComponentDef, saved_pkg: SpecPackage) -> str:
    """Generate usage.md derived from the saved Spec and component contract."""
    rev = SpecRevision.from_package(saved_pkg)
    expected_vlnv = f"spec2gds.local:{comp_def.category}:{comp_def.id}:{comp_def.version}"
    comp = next((c for c in rev.components if c.vlnv == expected_vlnv), rev.components[0])

    port_rows = []
    for port in comp.ports:
        range_str = f"[{port.width[1:-1]}]" if isinstance(port.width, str) else "1 (scalar)"
        port_rows.append(f"| `{port.name}` | `{port.direction}` | `{range_str}` | {port.description or '-'} |")

    param_rows = []
    for param in comp.parameters:
        param_rows.append(f"| `{param.name}` | `{param.rtl_type}` | `{param.value}` | {param.description or '-'} |")

    preset_lines = []
    for name, p_map in comp_def.presets.items():
        assignments = ", ".join(f"`{k}={v}`" for k, v in sorted(p_map.items()))
        preset_lines.append(f"- **`{name}`**: {assignments if assignments else 'default parameters'}")

    limitations_lines = [f"- {lim}" for lim in comp_def.limitations] if comp_def.limitations else ["- None recorded."]

    return f"""# {comp_def.id}

{comp_def.summary}

- **VLNV**: `spec2gds.local:{comp_def.category}:{comp_def.id}:{comp_def.version}`
- **Category**: `{comp_def.category}`
- **Implementation**: `body_sv`
- **Licence**: `{comp_def.licence}`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
{chr(10).join(port_rows)}

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
{chr(10).join(param_rows) if param_rows else '| - | - | - | No configurable parameters |'}

## Timing Characteristics

- **Latency**: {comp_def.timing.latency}
- **Throughput**: {comp_def.timing.throughput}
- **Reset**: {comp_def.timing.reset}

## Parameter Presets

{chr(10).join(preset_lines)}

## Implementation Limits & Notes

{chr(10).join(limitations_lines)}
"""

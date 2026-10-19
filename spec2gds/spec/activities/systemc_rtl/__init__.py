"""Cycle-accurate SystemC generation from immutable Spec snapshots."""

from __future__ import annotations

import typing

import pydantic

from spec2gds.spec.activities.contracts import (
    ActivityAvailability,
    ActivityContext,
    ActivityResult,
    ActivityScopes,
    ActivitySelectionContext,
    WorkspaceFile,
)
from spec2gds.spec.activities.registry import SpecExtensionRegistry, activity
from spec2gds.spec.activities.systemc_rtl.codegen import (
    ACTIVITY_ID,
    ACTIVITY_VERSION,
    generate_project,
    validate_project,
)
from spec2gds.spec.spec_format.models import EntityRef

REPORT_ROLE = "systemc.cycle_accurate_generation_report"


class CycleAccurateGenerationReport(pydantic.BaseModel):
    """Provenance and inventory for one published native SystemC project."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    schema_version: typing.Literal["spec2gds.systemc-cycle-accurate-report.v1"] = (
        "spec2gds.systemc-cycle-accurate-report.v1"
    )
    activity_id: str
    activity_version: str
    document_id: str
    source_revision_hash: str
    design: EntityRef
    design_vlnv: str
    target_name: str = ""
    document_name: str = ""
    output_path: str
    top_module: str
    component_count: int
    instance_count: int
    connection_count: int
    source_sections: tuple[dict[str, str], ...]
    tool_versions: dict[str, str]
    tree_sha256: str
    files: tuple[WorkspaceFile, ...]


def _availability(context: ActivitySelectionContext) -> ActivityAvailability:
    if context.target is None or context.target.entity_kind != "design":
        return ActivityAvailability(
            available=False,
            diagnostics=("Cycle-accurate SystemC generation requires a selected design.",),
        )
    diagnostics = validate_project(context.spec, context.target, check_compiler=False)
    return ActivityAvailability(available=not diagnostics, diagnostics=diagnostics)


@activity(
    activity_id=ACTIVITY_ID,
    version=ACTIVITY_VERSION,
    title="Generate cycle-accurate SystemC",
    description="Compile Spec ports and SystemVerilog bodies into native SystemC modules.",
    scopes=ActivityScopes(entity_kinds=("design",)),
    report_model=CycleAccurateGenerationReport,
    artifact_roles=(REPORT_ROLE,),
    requires_workspace_output=True,
    availability=_availability,
)
def generate_cycle_accurate(context: ActivityContext) -> ActivityResult:
    """Compile and atomically publish one design-scoped SystemC project."""
    context.cancellation.raise_if_cancelled()
    if context.target is None or context.workspace is None:
        raise RuntimeError("Cycle-accurate SystemC generation requires a design and workspace.")

    project = generate_project(context.spec, context.target)
    context.cancellation.raise_if_cancelled()
    relative_path = context.spec.high.project_path(context.target, "systemc-rtl")
    published = context.workspace.replace_directory(
        relative_path=relative_path,
        files=project.files,
        activity_id=ACTIVITY_ID,
        document_id=context.target.document_id,
        design_id=context.target.entity_id,
    )
    report = CycleAccurateGenerationReport(
        activity_id=ACTIVITY_ID,
        activity_version=ACTIVITY_VERSION,
        document_id=context.snapshot.source.document_id,
        source_revision_hash=context.snapshot.source.source_revision_hash,
        design=context.target,
        design_vlnv=project.design_vlnv,
        target_name=context.spec.high.entity(context.target).display_name,
        document_name=context.spec.high.document["title"],
        output_path=published.relative_path,
        top_module=project.top_module,
        component_count=project.component_count,
        instance_count=project.instance_count,
        connection_count=project.connection_count,
        source_sections=project.source_sections,
        tool_versions=project.tool_versions,
        tree_sha256=published.tree_sha256,
        files=published.files,
    )
    source_entities = tuple(
        item.ref
        for item in context.spec.high.related(context.target, "dependencies").all()
    ) + (context.target,)
    artifact = context.outputs.add_json(
        role=REPORT_ROLE,
        name="generation-report.json",
        value=report.model_dump(mode="json"),
        source_entities=source_entities,
    )
    return ActivityResult(
        summary=f"Generated cycle-accurate SystemC at {published.relative_path}.",
        report=report.model_dump(mode="json"),
        artifacts=(artifact,),
    )


def register_extensions(registry: SpecExtensionRegistry) -> None:
    """Register only the cycle-accurate generator."""
    registry.register_activity(generate_cycle_accurate)

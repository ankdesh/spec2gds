"""Design-scoped deterministic SystemC TLM 2.0 AT skeleton Activity."""

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
from spec2gds.spec.activities.systemc_at.codegen import (
    ACTIVITY_ID,
    ACTIVITY_VERSION,
    generate_project,
    validate_project,
)
from spec2gds.spec.spec_format.models import EntityRef

REPORT_ROLE = "systemc.generation_report"


class SystemCGenerationReport(pydantic.BaseModel):
    """Stable report describing one published SystemC project."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    schema_version: typing.Literal["spec2gds.systemc-generation-report.v1"] = (
        "spec2gds.systemc-generation-report.v1"
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
    top_class: str
    component_definition_count: int
    component_instance_count: int
    design_module_count: int
    connection_count: int
    tree_sha256: str
    files: tuple[WorkspaceFile, ...]


def _availability(context: ActivitySelectionContext) -> ActivityAvailability:
    if context.target is None or context.target.entity_kind != "design":
        return ActivityAvailability(
            available=False,
            diagnostics=("SystemC AT generation requires a selected design.",),
        )
    diagnostics = validate_project(context.spec, context.target)
    return ActivityAvailability(available=not diagnostics, diagnostics=diagnostics)


@activity(
    activity_id=ACTIVITY_ID,
    version=ACTIVITY_VERSION,
    title="Generate SystemC AT skeleton",
    description="Generate deterministic structural SystemC TLM 2.0 AT modules and bindings.",
    scopes=ActivityScopes(entity_kinds=("design",)),
    report_model=SystemCGenerationReport,
    artifact_roles=(REPORT_ROLE,),
    requires_workspace_output=True,
    availability=_availability,
)
def generate_systemc_at_skeleton(context: ActivityContext) -> ActivityResult:
    """Generate and publish one deterministic structural simulation project."""
    context.cancellation.raise_if_cancelled()
    if context.target is None or context.workspace is None:
        raise RuntimeError("SystemC AT generation requires a design target and workspace.")

    target = context.spec.high.entity(context.target)
    dependencies = context.spec.high.related(context.target, "dependencies").all()
    provenance_by_key = {
        (item.ref.entity_kind, item.ref.entity_id): item.ref
        for item in (target, *dependencies)
    }
    source_entities = tuple(provenance_by_key[key] for key in sorted(provenance_by_key))

    project = generate_project(context.spec, context.target)
    relative_path = context.spec.high.project_path(context.target, "systemc-at")
    published = context.workspace.replace_directory(
        relative_path=relative_path,
        files=project.files,
        activity_id=ACTIVITY_ID,
        document_id=context.target.document_id,
        design_id=context.target.entity_id,
    )
    report = SystemCGenerationReport(
        activity_id=ACTIVITY_ID,
        activity_version=ACTIVITY_VERSION,
        document_id=context.snapshot.source.document_id,
        source_revision_hash=context.snapshot.source.source_revision_hash,
        design=context.target,
        design_vlnv=target.vlnv,
        target_name=target.display_name,
        document_name=context.spec.high.document["title"],
        output_path=published.relative_path,
        top_class=project.top_class,
        component_definition_count=project.component_definition_count,
        component_instance_count=project.component_instance_count,
        design_module_count=project.design_module_count,
        connection_count=project.connection_count,
        tree_sha256=published.tree_sha256,
        files=published.files,
    )
    artifact = context.outputs.add_json(
        role=REPORT_ROLE,
        name="generation-report.json",
        value=report.model_dump(mode="json"),
        source_entities=source_entities,
    )
    return ActivityResult(
        summary=f"Generated SystemC AT skeleton at {published.relative_path}.",
        report=report.model_dump(mode="json"),
        artifacts=(artifact,),
    )


def register_extensions(registry: SpecExtensionRegistry) -> None:
    """Register the deterministic SystemC AT generator."""
    registry.register_activity(generate_systemc_at_skeleton)


def _path_segment(value: str) -> str:
    """Use validated Spec identity as a safe workspace path segment."""
    return value

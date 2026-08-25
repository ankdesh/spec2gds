"""Design-scoped deterministic SystemVerilog generation Activity."""

from __future__ import annotations

import typing

import pydantic

from spec2gds.agent_spec.activities.contracts import (
    ActivityAvailability,
    ActivityContext,
    ActivityResult,
    ActivityScopes,
    ActivitySelectionContext,
    WorkspaceFile,
)
from spec2gds.agent_spec.activities.registry import SpecExtensionRegistry, activity
from spec2gds.agent_spec.activities.rtl.codegen import (
    GENERATOR_ID,
    GENERATOR_VERSION,
    generate_project,
    validate_project,
)
from spec2gds.agent_spec.spec_format.models import EntityRef

REPORT_ROLE = "rtl.generation_report"


class RtlNameMapping(pydantic.BaseModel):
    """One deterministic source-to-SystemVerilog identifier mapping."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    kind: str
    scope: str
    source_name: str
    rtl_name: str


class RtlSourceSection(pydantic.BaseModel):
    """One persisted SV body consumed into a generated module."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    section_id: str
    sha256: str
    source_path: str
    output_path: str


class RtlGenerationReport(pydantic.BaseModel):
    """Stable report describing one published RTL project."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    schema_version: typing.Literal["spec2gds.rtl-generation-report.v2"] = (
        "spec2gds.rtl-generation-report.v2"
    )
    generator_id: str
    generator_version: str
    document_id: str
    source_revision_hash: str
    design: EntityRef
    design_vlnv: str
    output_path: str
    top_module: str
    wrapper_generated: bool
    module_count: int
    component_module_count: int
    instance_count: int
    net_count: int
    unconnected_port_count: int
    warnings: tuple[str, ...]
    name_mappings: tuple[RtlNameMapping, ...]
    source_sections: tuple[RtlSourceSection, ...]
    tree_sha256: str
    files: tuple[WorkspaceFile, ...]


def _availability(context: ActivitySelectionContext) -> ActivityAvailability:
    if context.target is None or context.target.entity_kind != "design":
        return ActivityAvailability(
            available=False,
            diagnostics=("Error: RTL generation requires a selected design.",),
        )
    diagnostics = validate_project(context.spec, context.target)
    return ActivityAvailability(
        available=not diagnostics.errors,
        diagnostics=diagnostics.messages,
    )


@activity(
    activity_id=GENERATOR_ID,
    version=GENERATOR_VERSION,
    title="Generate RTL",
    description="Generate deterministic SystemVerilog from IP-XACT structure and stored module bodies.",
    scopes=ActivityScopes(entity_kinds=("design",)),
    report_model=RtlGenerationReport,
    artifact_roles=(REPORT_ROLE,),
    requires_workspace_output=True,
    availability=_availability,
)
def generate_rtl(context: ActivityContext) -> ActivityResult:
    """Generate and publish one deterministic RTL project."""
    context.cancellation.raise_if_cancelled()
    if context.target is None or context.workspace is None:
        raise RuntimeError("RTL generation requires a design target and workspace.")

    target = context.spec.high.entity(context.target)
    dependencies = context.spec.high.related(context.target, "dependencies").all()
    provenance = {
        (item.ref.entity_kind, item.ref.entity_id): item.ref
        for item in (target, *dependencies)
    }
    source_entities = tuple(provenance[key] for key in sorted(provenance))

    project = generate_project(context.spec, context.target)
    relative_path = f"rtl/{context.target.document_id}/{context.target.entity_id}"
    published = context.workspace.replace_directory(
        relative_path=relative_path,
        files=project.files,
        generator_id=GENERATOR_ID,
        document_id=context.target.document_id,
        design_id=context.target.entity_id,
    )
    report = RtlGenerationReport(
        generator_id=GENERATOR_ID,
        generator_version=GENERATOR_VERSION,
        document_id=context.snapshot.source.document_id,
        source_revision_hash=context.snapshot.source.source_revision_hash,
        design=context.target,
        design_vlnv=target.vlnv,
        output_path=published.relative_path,
        top_module=project.top_module,
        wrapper_generated=project.wrapper_generated,
        module_count=project.module_count,
        component_module_count=project.component_module_count,
        instance_count=project.instance_count,
        net_count=project.net_count,
        unconnected_port_count=project.unconnected_port_count,
        warnings=project.warnings,
        name_mappings=tuple(RtlNameMapping(**item.as_json()) for item in project.name_mappings),
        source_sections=tuple(RtlSourceSection(**item) for item in project.source_sections),
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
        summary=f"Generated RTL project at {published.relative_path}.",
        report=report.model_dump(mode="json"),
        artifacts=(artifact,),
    )


def register_extensions(registry: SpecExtensionRegistry) -> None:
    """Register the deterministic RTL generator."""
    registry.register_activity(generate_rtl)

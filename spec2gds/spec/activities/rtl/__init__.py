"""Component/design-scoped deterministic SystemVerilog generation Activity."""

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
from spec2gds.spec.activities.rtl.codegen import (
    ACTIVITY_ID,
    ACTIVITY_VERSION,
    generate_project,
    validate_project,
)
from spec2gds.spec.spec_format.models import EntityRef

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

    schema_version: typing.Literal["spec2gds.rtl-generation-report.v2", "spec2gds.rtl-generation-report.v3"] = "spec2gds.rtl-generation-report.v3"
    activity_id: str
    activity_version: str
    document_id: str
    source_revision_hash: str
    target: EntityRef
    target_vlnv: str
    target_name: str = ""
    document_name: str = ""
    implementation_status: dict[str, str] = pydantic.Field(default_factory=dict)
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

    @pydantic.model_validator(mode="before")
    @classmethod
    def read_legacy_report(cls, value: typing.Any) -> typing.Any:
        if isinstance(value, dict) and value.get("schema_version") == "spec2gds.rtl-generation-report.v2":
            value = dict(value)
            value["target"] = value.pop("design")
            value["target_vlnv"] = value.pop("design_vlnv")
        return value


def _availability(context: ActivitySelectionContext) -> ActivityAvailability:
    if context.target is None or context.target.entity_kind not in {"component", "design"}:
        return ActivityAvailability(
            available=False,
            diagnostics=("Error: RTL generation requires a selected component or design.",),
        )
    diagnostics = validate_project(context.spec, context.target)
    return ActivityAvailability(
        available=not diagnostics.errors,
        diagnostics=diagnostics.messages,
    )


@activity(
    activity_id=ACTIVITY_ID,
    version=ACTIVITY_VERSION,
    title="Generate RTL",
    description="Generate deterministic SystemVerilog from IP-XACT structure and stored module bodies.",
    scopes=ActivityScopes(entity_kinds=("component", "design")),
    report_model=RtlGenerationReport,
    artifact_roles=(REPORT_ROLE,),
    requires_workspace_output=True,
    availability=_availability,
)
def generate_rtl(context: ActivityContext) -> ActivityResult:
    """Generate and publish one deterministic RTL project."""
    context.cancellation.raise_if_cancelled()
    if context.target is None or context.workspace is None:
        raise RuntimeError("RTL generation requires a component or design target and workspace.")

    target = context.spec.high.entity(context.target)
    project = generate_project(context.spec, context.target)
    source_entities = tuple(sorted(project.source_entities, key=lambda ref: (ref.entity_kind, ref.entity_id)))
    relative_path = context.spec.high.project_path(context.target, "rtl")
    published = context.workspace.replace_directory(
        relative_path=relative_path,
        files=project.files,
        activity_id=ACTIVITY_ID,
        document_id=context.target.document_id,
        design_id=context.target.entity_id,
    )
    report = RtlGenerationReport(
        activity_id=ACTIVITY_ID,
        activity_version=ACTIVITY_VERSION,
        document_id=context.snapshot.source.document_id,
        source_revision_hash=context.snapshot.source.source_revision_hash,
        target=context.target,
        target_vlnv=target.vlnv,
        target_name=target.display_name,
        document_name=context.spec.high.document["title"],
        implementation_status=project.implementation_status,
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

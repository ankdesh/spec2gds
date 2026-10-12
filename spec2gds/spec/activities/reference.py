"""Small built-in extensions demonstrating the public Activity SDK."""

from __future__ import annotations

import json

import pydantic

from spec2gds.spec.activities.contracts import (
    ActivityContext,
    ActivityResult,
    ActivityScopes,
    ContextRenderContext,
    ContextRendererDefinition,
    RenderedContext,
)
from spec2gds.spec.activities.registry import SpecExtensionRegistry, activity


class SummaryReport(pydantic.BaseModel):
    """Typed report returned by the reference summary Activity."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    component_count: int
    design_count: int
    narrative_block_count: int


@activity(
    activity_id="reference.spec_summary",
    version="2.0.0",
    title="Export target details (JSON)",
    description="Export all saved Section details for the selected target and its dependencies as diagnostic JSON.",
    scopes=ActivityScopes(entity_kinds=("component", "design")),
    report_model=SummaryReport,
    artifact_roles=("spec.summary",),
)
def specification_summary(context: ActivityContext) -> ActivityResult:
    """Export complete source Section data through the public read-only SDK."""
    context.cancellation.raise_if_cancelled()
    if context.target is None:
        raise ValueError("Select a Component or Design to export.")
    projection = context.spec.low.document_projection()
    closure = context.spec.low.dependencies(context.target)
    included = set(closure)
    sections = [section.model_dump(mode="json") for section in projection.sections
                if section.entity_ref in included]
    # Preserve full nested blocks. Include shared notes that link to the closure.
    def linked(block: dict) -> bool:
        refs = [*block.get("entity_refs", []),
                *(inline.get("entity_ref") for inline in block.get("inlines", []) if inline.get("entity_ref"))]
        return any(any(ref == item.model_dump(mode="json") for item in closure) for ref in refs) or any(
            linked(child) for child in block.get("children", []))

    narrative = [block for section in projection.sections if section.entity_ref is None
                 for block in section.narrative if linked(block)]
    def block_count(blocks: list[dict]) -> int:
        return sum(1 + block_count(block.get("children", [])) for block in blocks)

    value = {
        "schema_version": "spec2gds.section-diagnostics.v1",
        "snapshot_id": context.snapshot.snapshot_id,
        "document_id": projection.document_id,
        "source_revision_hash": projection.source_revision_hash,
        "target": context.target.model_dump(mode="json"),
        "dependency_closure": [item.model_dump(mode="json") for item in closure],
        "sections": sections,
        "linked_narrative": narrative,
    }
    context.cancellation.raise_if_cancelled()
    from spec2gds.spec.spec_format.naming import filename_stem
    target = context.spec.high.entity(context.target)
    artifact = context.outputs.add_text(
        role="spec.summary",
        name=f"{filename_stem(target.display_name or target.name, 'target')}-section-details.json",
        text=json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        media_type="application/json",
        source_entities=(context.target,),
    )
    return ActivityResult(
        summary=f"Exported {len(sections)} source Sections for {target.display_name or target.name} and its dependencies.",
        report=SummaryReport(
            component_count=sum(item.entity_kind == "component" for item in closure),
            design_count=sum(item.entity_kind == "design" for item in closure),
            narrative_block_count=sum(block_count(section["narrative"]) for section in sections) + block_count(narrative),
        ).model_dump(mode="json"),
        artifacts=(artifact,),
    )


class SpecTextContextRenderer:
    """Reference deterministic textual context for the Spec AI Assistant."""

    definition = ContextRendererDefinition(
        renderer_id="reference.spec_text_context",
        version="1.1.0",
        title="Spec text context",
        scopes=ActivityScopes(
            document=True,
            entity_kinds=(
                "component",
                "design",
                "bus_definition",
                "abstraction_definition",
                "narrative_block",
                "asset",
            ),
        ),
    )

    def render(self, context: ContextRenderContext) -> RenderedContext:
        """Render a compact entity inventory and linked narrative for one snapshot."""
        document = context.spec.high.document
        lines = [
            f"Spec document: {document['document_id']}",
            f"Source revision: {document['source_revision_hash']}",
            f"Title: {document['title'] or '(untitled)'}",
        ]
        if context.target is None:
            entities = context.spec.high.entities().all()
            semantic_ir = {
                "manifest": context.spec.low.manifest.model_dump(mode="json"),
                "components": [
                    _jsonable(item) for item in context.spec.low.components
                ],
                "designs": [
                    _jsonable(item) for item in context.spec.low.designs
                ],
                "bus_definitions": [
                    _jsonable(item)
                    for item in context.spec.low.bus_definitions
                ],
                "abstraction_definitions": [
                    _jsonable(item)
                    for item in context.spec.low.abstraction_definitions
                ],
                "entity_sections": [
                    _jsonable(item) for item in context.spec.low.entity_sections
                ],
                "narrative": context.spec.low.narrative.model_dump(mode="json"),
            }
            lines.extend(
                [
                    "",
                    "DOCUMENT ENTITIES:",
                    *[
                        f"- {item.ref.entity_kind}:{item.ref.entity_id} name={item.name}"
                        for item in entities
                    ],
                    "",
                    "NARRATIVE TEXT:",
                    context.spec.high.text.all().plain_text() or "(none)",
                    "",
                    "SEMANTIC SPECIFICATION (READ-ONLY):",
                    json.dumps(semantic_ir, ensure_ascii=False, sort_keys=True, indent=2),
                ]
            )
        else:
            target = context.spec.high.entity(context.target)
            dependencies = context.spec.high.related(context.target, "dependencies").all()
            usages = context.spec.high.related(context.target, "usages").all()
            lines.extend(
                [
                    f"Selected target: {target.ref.entity_kind}:{target.ref.entity_id}",
                    "",
                    "DEPENDENCIES:",
                    *[f"- {item.ref.entity_kind}:{item.ref.entity_id}" for item in dependencies],
                    "",
                    "USAGES:",
                    *[f"- {item.ref.entity_kind}:{item.ref.entity_id}" for item in usages],
                    "",
                    "LINKED NARRATIVE:",
                    context.spec.high.text.linked_to(context.target).plain_text() or "(none)",
                ]
            )
        return RenderedContext(
            renderer_id=self.definition.renderer_id,
            renderer_version=self.definition.version,
            snapshot_id=context.snapshot.snapshot_id,
            document_id=context.snapshot.source.document_id,
            source_revision_hash=context.snapshot.source.source_revision_hash,
            target=context.target,
            text="\n".join(lines),
        )


def register_extensions(registry: SpecExtensionRegistry) -> None:
    """Register the built-in examples through the same public plugin hook as teams."""
    registry.register_activity(specification_summary)
    registry.register_context_renderer(SpecTextContextRenderer())


def _jsonable(value: object) -> object:
    """Serialize one typed dataclass IR value without exposing source XML."""
    return pydantic.TypeAdapter(type(value)).dump_python(value, mode="json")

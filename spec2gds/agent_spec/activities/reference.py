"""Small built-in extensions demonstrating the public Activity SDK."""

from __future__ import annotations

import json

import pydantic

from spec2gds.agent_spec.activities.contracts import (
    ActivityContext,
    ActivityResult,
    ActivityScopes,
    ContextRenderContext,
    ContextRendererDefinition,
    RenderedContext,
)
from spec2gds.agent_spec.activities.registry import SpecExtensionRegistry, activity


class SummaryReport(pydantic.BaseModel):
    """Typed report returned by the reference summary Activity."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    component_count: int
    design_count: int
    narrative_block_count: int


@activity(
    activity_id="reference.spec_summary",
    version="1.0.0",
    title="Specification summary",
    description="Create a deterministic text summary using the high-level Spec API.",
    scopes=ActivityScopes(document=True, entity_kinds=("component", "design")),
    report_model=SummaryReport,
    artifact_roles=("spec.summary",),
)
def specification_summary(context: ActivityContext) -> ActivityResult:
    """Demonstrate generic entity and narrative queries without concrete IR access."""
    context.cancellation.raise_if_cancelled()
    components = context.spec.high.entities(kind="component").all()
    designs = context.spec.high.entities(kind="design").all()
    text_blocks = context.spec.high.text.all().all()
    lines = [
        f"Specification: {context.spec.high.document['title'] or context.spec.high.document['document_id']}",
        f"Source revision: {context.spec.high.document['source_revision_hash']}",
        f"Components: {len(components)}",
        *[f"- {item.name} ({item.vlnv})" for item in components],
        f"Designs: {len(designs)}",
        *[f"- {item.name} ({item.vlnv})" for item in designs],
        f"Narrative blocks: {len(text_blocks)}",
    ]
    artifact = context.outputs.add_text(
        role="spec.summary",
        name="spec-summary.txt",
        text="\n".join(lines) + "\n",
        source_entities=(context.target,) if context.target else (),
    )
    return ActivityResult(
        summary=f"Summarized {len(components)} components and {len(designs)} designs.",
        report=SummaryReport(
            component_count=len(components),
            design_count=len(designs),
            narrative_block_count=len(text_blocks),
        ).model_dump(mode="json"),
        artifacts=(artifact,),
    )


class SpecTextContextRenderer:
    """Reference deterministic textual context for the Spec AI Assistant."""

    definition = ContextRendererDefinition(
        renderer_id="reference.spec_text_context",
        version="1.1.0",
        title="Specification text context",
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

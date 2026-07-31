"""Simple OpenAI-backed exploration and typed proposal agent for Spec Editor."""

from __future__ import annotations

from uuid import uuid4

from openai import AsyncOpenAI

from ..config import Settings
from ..models import (
    SpecAgentRequest,
    SpecEntityRef,
    SpecProposalArtifact,
    SpecProposalDraft,
)
from .context import SpecContextProcessor


EXPLORATION_INSTRUCTIONS = """\
You are a hardware specification design partner. Explore the user's idea using the
selected entity's semantic IR, linked narrative, owned internal design, and the
read-only relationship context. Explain concrete implications, alternatives, and
open assumptions. Do not emit XML or claim that a change was applied. Do not create
a formal operation proposal unless the request explicitly asks for one.
"""


PROPOSAL_INSTRUCTIONS = """\
Prepare a safe reviewable proposal for one existing .spec entity. Stay strictly
inside the WRITABLE BOUNDARY. Surrounding and shared context is read-only. Reuse
exact entity IDs, VLNV values, instance names, interface names, port names, and
narrative block IDs from context. Never change vendor/library/name/version, never
emit XML, never create or delete a top-level source document, and never edit assets.

Each operation has operation_id, type, and the named fields below. Nullable
fields that are not changing must be null. To explicitly remove a metadata or
bus-definition field, put its name in clear_fields; otherwise use an empty list.
- set_entity_metadata: entity plus display_name/short_description/description
  and clear_fields.
- upsert_parameter: entity plus parameter {name,value,resolve,data_type,choice_ref,
  minimum,maximum,description}; delete_parameter: entity plus name.
- upsert_component_port: component plus port {name,style,direction,left,right,
  bus_width,description}; delete_component_port: component plus name.
- upsert_bus_interface: component plus interface {name,role,bus_vlnv,
  abstraction_vlnv,connection_required,bits_in_lau,endianness,description,
  port_maps:[{logical,physical,tie_off,invert,informative}]}.
- upsert_channel: component plus channel {name,interfaces,description}.
- upsert_instance/delete_instance/reorder_instances: design plus the corresponding
  instance, instance_name, or instance_names field.
- upsert_connection/delete_connection/reorder_connections: design plus connection,
  connection_name, or kind and connection_names. Connections use the existing
  semantic IR shape.
- set_internal_design: component plus internal_design; clear_internal_design:
  component.
- update_bus_definition: bus_definition plus properties {direct_connection,
  broadcast,addressable,extends_vlnv,max_initiators,max_targets,system_groups,
  clear_fields}.
- set_abstraction_bus_type: abstraction_definition plus bus_vlnv.
- upsert_abstraction_port: abstraction_definition plus port {name,style,match,
  description,qualifiers,on_initiator,on_target,on_system}; role-mode objects use
  group,direction,initiative,presence,width,bus_width.
- narrative operations use block/block_id/block_ids/parent_block_id/index/entity_refs
  and the current typed narrative block shape.

For narrative block options, return a list of {key,value}; it is normalized to
the document's options object after parsing. List every material assumption. If
the requested change is outside this vocabulary or boundary, return
supported=false.
"""


class SpecEditingAgent:
    def __init__(
        self,
        settings: Settings,
        *,
        context_processor: SpecContextProcessor | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.settings = settings
        self.context_processor = context_processor or SpecContextProcessor()
        self._client = client

    async def respond(
        self, request: SpecAgentRequest
    ) -> str | SpecProposalArtifact | SpecProposalDraft:
        processed = self.context_processor.process(request)
        client = self._client
        if client is None:
            if not self.settings.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is required to use the Spec assistant.")
            client = AsyncOpenAI(api_key=self.settings.openai_api_key)

        prompt = f"{processed.text}\n\nCURRENT USER REQUEST:\n{request.user_request}"
        if not request.proposal_requested:
            response = await client.responses.create(
                model=self.settings.openai_model,
                instructions=EXPLORATION_INSTRUCTIONS,
                input=prompt,
                store=False,
            )
            answer = response.output_text.strip()
            if not answer:
                raise RuntimeError("The model did not return an exploration response.")
            return answer

        response = await client.responses.parse(
            model=self.settings.openai_model,
            instructions=PROPOSAL_INSTRUCTIONS,
            input=[{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            text_format=SpecProposalDraft,
            store=False,
        )
        draft = response.output_parsed
        if draft is None:
            raise RuntimeError("The model did not return a Spec proposal.")
        if not draft.supported:
            return draft
        target = SpecEntityRef.model_validate(request.context.get("target"))
        return SpecProposalArtifact(
            proposal_id=f"proposal_{uuid4().hex}",
            document_id=processed.document_id,
            target=target,
            base_source_revision_hash=processed.revision,
            title=draft.title,
            summary=draft.summary,
            rationale=draft.rationale,
            assumptions=draft.assumptions,
            operations=[_operation_payload(operation) for operation in draft.operations],
        )


def _operation_payload(operation: object) -> dict[str, object]:
    """Normalize the strict model-output schema into the public operation contract."""
    if not hasattr(operation, "model_dump"):
        raise TypeError("Spec proposal operations must be typed models.")
    value = operation.model_dump(mode="json", exclude_none=True)  # type: ignore[attr-defined]
    operation_type = value.get("type")
    if operation_type == "set_entity_metadata":
        for field in value.pop("clear_fields", []):
            value[str(field)] = None
    elif operation_type == "update_bus_definition":
        properties = value.get("properties")
        if isinstance(properties, dict):
            for field in properties.pop("clear_fields", []):
                properties[str(field)] = None
    elif operation_type == "upsert_narrative_block":
        block = value.get("block")
        if isinstance(block, dict):
            _normalize_narrative_options(block)
    return value


def _normalize_narrative_options(block: dict[str, object]) -> None:
    options = block.get("options")
    if isinstance(options, list):
        block["options"] = {
            str(item["key"]): item["value"]
            for item in options
            if isinstance(item, dict) and "key" in item and "value" in item
        }
    children = block.get("children")
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                _normalize_narrative_options(child)

"""Simple OpenAI-backed exploration and typed proposal agent for Spec Editor."""

from __future__ import annotations

from uuid import uuid4

from openai import AsyncOpenAI
from spec2gds_runtime import StructuredLogger

from ..config import Settings
from ..models import (
    CreateEntityOperation,
    SpecAgentRequest,
    SpecEntityRef,
    SpecProposalArtifact,
    SpecProposalDraft,
)
from .context import SpecContextProcessor

EXPLORATION_INSTRUCTIONS = """\
You are a hardware specification design partner. Explore the user's idea using the
provided immutable semantic specification context. The context states whether it
covers the complete document or one selected entity. Explain concrete
implications, alternatives, and open assumptions. Do not emit XML or claim that a
change was applied. Create a formal operation proposal only when the request asks
for a concrete change.
"""


PROPOSAL_INSTRUCTIONS = """\
Prepare a safe reviewable proposal for the scope stated in context. Stay strictly
inside its WRITABLE BOUNDARY. Surrounding and shared context is read-only. Reuse
exact entity IDs, VLNV values, instance names, interface names, port names, and
narrative block IDs from context. Never change vendor/library/name/version, never
emit XML, never create or delete a top-level source document, and never edit assets.

For document scope, the only supported operation is create_entity:
- To add a component, use kind="component", its requested XML-compatible name,
  and instances=[].
- To add a design, use kind="design" and include all requested initial component
  instances in the same operation. Every instance needs a unique name and an exact
  component_vlnv copied from EXISTING REFERENCES. A phrase such as "asd 1" may
  refer to the uniquely matching existing component named "asd1"; still emit its
  exact VLNV from context. If the user requests 10 instances, emit exactly 10
  instances with clear unique names such as asd1_1 through asd1_10.
- Existing entities remain read-only from document scope. Do not emit entity-bound
  operations alongside create_entity.

Each operation has operation_id, type, and the named fields below. Nullable
fields that are not changing must be null. To explicitly remove a metadata or
bus-definition field, put its name in clear_fields; otherwise use an empty list.

For entity scope, map common short requests according to the selected target:
- On a component, "create/add a port" means upsert_component_port. It creates the
  named port when absent and replaces that same port when present.
- On a design, "create/add a component" means upsert_instance using an existing
  component_vlnv from available references; it does not create a component type.
- On a design, "connect ports" or "create a net" means upsert_connection. Direct
  physical port wiring uses kind="ad_hoc" with only port_endpoints and
  external_ports. Bus-interface wiring uses kind="interface" with only
  interface_endpoints and hierarchy_interfaces. Never put interface_endpoints in
  an ad_hoc connection or port_endpoints in an interface connection. Preserve the
  complete existing connection when adding endpoints to it.
- Use only component_vlnv, port_name, and interface_name values explicitly present
  in EXISTING REFERENCES. Do not invent a generic name such as port1. An ad_hoc
  connection needs at least two endpoints and compatible wire directions (an out
  or inout source and an in or inout sink). An interface connection needs at least
  two compatible interface endpoints. If the context lacks compatible named
  endpoints, return supported=false instead of assuming them.
- A request to create a top-level component or design requires document scope.

- create_entity: kind (component/design), name, and instances. Components require
  an empty instances list. Designs may contain initial instances using exact
  existing component VLNV values.
- set_entity_metadata: entity plus display_name/short_description/description
  and clear_fields.
- upsert_parameter: entity plus parameter {name,value,resolve,data_type,choice_ref,
  minimum,maximum,description}; delete_parameter: entity plus name.
- upsert_component_port: component plus exactly one editor-profiled port shape.
  All families have name, family, display_name, and description. Wire adds
  direction (in/out/inout) and range (empty for scalar or `left:right`).
  Transactional adds initiative (requires/provides/both), optional kind
  (tlm_port/tlm_socket/simple_socket/multi_socket/custom), custom_kind only
  when kind is custom, and optional bus_width. Structured adds direction and
  always means the server-owned packed struct profile. Never emit hidden
  structured type definitions. Port names and families are immutable: update
  the port with the same name and family, and never model a rename or family
  conversion. This is a complete replacement value: preserve every unchanged
  port field from context, and use null only when explicitly clearing an
  optional field. Ports on components owning internal designs are read-only.
  delete_component_port: component plus name.
- upsert_bus_interface: component plus interface {name,role,bus_vlnv,
  abstraction_vlnv,connection_required,bits_in_lau,endianness,description,
  port_maps:[{logical,physical,tie_off,invert,informative}]}.
- upsert_channel: component plus channel {name,interfaces,description}.
- upsert_instance/delete_instance/reorder_instances: design plus the corresponding
  instance, instance_name, or instance_names field.
- upsert_connection: design plus exactly one connection shape. Interface is
  {name,kind:"interface",interface_endpoints:[{instance_name,interface_name}],
  hierarchy_interfaces}. Ad-hoc is
  {name,kind:"ad_hoc",port_endpoints:[{instance_name,port_name}],external_ports}.
  delete_connection/reorder_connections use connection_name, or kind and
  connection_names.
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
- upsert_entity_section creates or completely replaces the selected component or
  design's singleton SystemVerilog body. Use owner, section_type="sv",
  type_version=1, preserve section_id when one exists, and payload {content}.
  The content is module-body SystemVerilog only: never emit module/endmodule,
  `include, or `line. delete_entity_section uses owner, section_type="sv", and
  the existing section_id. Preserve the complete existing source unless the user
  explicitly asks for a replacement or deletion.

For narrative block options, return a list of {key,value}; it is normalized to
the document's options object after parsing. List every material assumption. If
the requested change is outside this vocabulary or boundary, return
supported=false.
"""


class SpecEditingAgent:
    """Explore Spec context or produce source operations for explicit changes."""
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
        self._logger = StructuredLogger("ai-assistant", settings.logging) if settings.logging else None

    async def respond(
        self, request: SpecAgentRequest
    ) -> str | SpecProposalArtifact | SpecProposalDraft:
        """Return exploration text or a revision-bound, reviewable proposal."""
        processed = self.context_processor.process(request)
        client = self._client
        if client is None:
            if not self.settings.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is required to use the Spec AI Assistant.")
            client = AsyncOpenAI(api_key=self.settings.openai_api_key)

        prompt = f"{processed.text}\n\nCURRENT USER REQUEST:\n{request.user_request}"
        if not request.proposal_requested:
            call = {
                "model": self.settings.openai_model,
                "instructions": EXPLORATION_INSTRUCTIONS,
                "input": prompt,
                "store": False,
            }
            if self._logger:
                self._logger.event(
                    "openai", "request", "Sending Spec exploration request to OpenAI",
                    details=call,
                )
            response = await client.responses.create(
                model=self.settings.openai_model,
                instructions=EXPLORATION_INSTRUCTIONS,
                input=prompt,
                store=False,
            )
            if self._logger:
                self._logger.event(
                    "openai", "response", "Received Spec exploration response from OpenAI",
                    details=response,
                )
            answer = response.output_text.strip()
            if not answer:
                raise RuntimeError("The model did not return an exploration response.")
            return answer

        call = {
            "model": self.settings.openai_model,
            "instructions": PROPOSAL_INSTRUCTIONS,
            "input": prompt,
            "text_format": SpecProposalDraft.__name__,
            "store": False,
        }
        if self._logger:
            self._logger.event(
                "openai", "request", "Sending Spec proposal request to OpenAI",
                details=call,
            )
        response = await client.responses.parse(
            model=self.settings.openai_model,
            instructions=PROPOSAL_INSTRUCTIONS,
            input=[{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            text_format=SpecProposalDraft,
            store=False,
        )
        if self._logger:
            self._logger.event(
                "openai", "response", "Received Spec proposal response from OpenAI",
                details=response,
            )
        draft = response.output_parsed
        if draft is None:
            raise RuntimeError("The model did not return a Spec proposal.")
        if not draft.supported:
            return draft
        if processed.scope == "document" and any(
            not isinstance(operation, CreateEntityOperation)
            for operation in draft.operations
        ):
            return SpecProposalDraft(
                supported=False,
                title=draft.title,
                summary=draft.summary,
                rationale=draft.rationale,
                assumptions=draft.assumptions,
                unsupported_reason=(
                    "Document-level chats may only create top-level components or designs."
                ),
                operations=[],
            )
        target = (
            SpecEntityRef.model_validate(request.context.get("target"))
            if processed.scope == "entity"
            else None
        )
        return SpecProposalArtifact(
            proposal_id=f"proposal_{uuid4().hex}",
            document_id=processed.document_id,
            scope=processed.scope or "entity",
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
    if operation_type == "create_entity":
        value["entity_id"] = (
            f"{value['kind']}_{value['name']}_{uuid4().hex}"
        )
    elif operation_type == "set_entity_metadata":
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

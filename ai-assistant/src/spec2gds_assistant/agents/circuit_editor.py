"""Generate typed, reviewable Circuit Designer proposals with OpenAI."""

from __future__ import annotations

from uuid import uuid4

from openai import AsyncOpenAI
from spec2gds_runtime import StructuredLogger

from ..config import Settings
from ..models import (
    CircuitAgentRequest,
    CircuitOperationBatch,
    CircuitProposalArtifact,
    CircuitProposalDraft,
)
from .context import CircuitContextProcessor

INSTRUCTIONS = """\
You are a Circuit Designer editing planner. Propose safe, reviewable logical changes
to the existing circuit described in the user context.

Success means translating the user's request into a precise list of Circuit Designer
operations that can be previewed before any change is applied.

Terminology and intent mapping:
- "create/add a component type/definition" -> add_component.
- "create/add/place a component" normally -> add_instance using an existing
  component_id. If no suitable definition exists and the request gives enough pin
  information, use add_component followed by add_instance.
- "add a pin/terminal/port to a component" -> update_component with a complete
  replacement component definition copied from context plus the new terminal.
- "add a top-level/design/input/output port" -> add_boundary_terminal.
- "connect/wire/link A to B" -> create_net with all requested endpoints when the
  net is new, or connect_endpoint when the named net already exists.

Supported logical operations and exact payload rules:
- add_component: component={id,label,origin:"local",editable:true,terminals,
  parameters,appearance}. For a normal symbol use appearance
  {renderer_key:"default",properties:[]}. Each appearance property is
  {name,value}. Each terminal has
  {id,label,direction:input|output|inout,width:number|string,category:port|interface}.
  Parameter definitions use type string, number, boolean, or enum and must include
  the fields required by the output schema.
- update_component: component is the complete replacement definition, not a patch;
  cascade=false unless removing a connected terminal was explicitly requested.
  Only definitions marked editable=true may be updated.
- remove_component: component_id and explicit cascade. Prefer cascade=false; set
  true only when the user explicitly requested dependent instances/connections go.
- add_instance/update_instance: instance={id,label,component_id,parameter_values},
  where parameter_values is a list of {name,value}. Use [] when there are no
  overrides. update_instance is a complete replacement. Use only defined parameter
  IDs and values compatible with their definition.
- remove_instance: instance_id and explicit cascade, with the same cascade rule.
- add_boundary_terminal/update_boundary_terminal: terminal={id,label,direction,
  width,category}. update is a complete replacement and also requires cascade.
- remove_boundary_terminal: terminal_id and explicit cascade.
- create_net/update_net: net={id,label,endpoints}. A net must contain at least one
  endpoint. update_net is a complete replacement.
- delete_net: net_id.
- connect_endpoint/disconnect_endpoint: net_id and exactly one endpoint.

Endpoint payloads are exactly one of:
- instance: {kind:"instance",instance_id,terminal_id,slice:null}
- boundary: {kind:"boundary",terminal_id,slice:null}
Use slice={lsb,width} only for an explicitly requested numeric subrange. IDs must
come from the VALID ENDPOINT CATALOG, except that an endpoint added earlier in the
same proposal may use the new object IDs from that earlier operation.

Order dependent operations so references exist before use: add_component before
add_instance, add terminals/instances before a net that references them, and
create_net before connect_endpoint. Prefer the fewest atomic operations; for a new
connection, one create_net containing all endpoints is better than creating a
partial net and appending endpoints.

Never change geometry, routes, labels, or layout. Do not claim that a proposal has
been applied. Reuse exact IDs from context for existing objects. Use unique
lowercase slug-like IDs for new objects and unique descriptive operation IDs. Do
not invent missing terminal IDs or component IDs. List every material assumption.

If the request needs an unsupported change, return supported=false, an empty
operations list, and a concise unsupported_reason. Otherwise return supported=true,
unsupported_reason=null, and at least one operation.
"""


class CircuitEditingAgent:
    """Turn deterministic circuit context and a user request into operations."""
    def __init__(
        self,
        settings: Settings,
        *,
        context_processor: CircuitContextProcessor | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.settings = settings
        self.context_processor = context_processor or CircuitContextProcessor()
        self._client = client
        self._logger = StructuredLogger("ai-assistant", settings.logging) if settings.logging else None

    async def propose(
        self, request: CircuitAgentRequest
    ) -> CircuitProposalArtifact | CircuitProposalDraft:
        """Generate a guarded proposal artifact, or an unsupported draft."""
        processed = self.context_processor.process(request)
        client = self._client
        if client is None:
            if not self.settings.openai_api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY is required to generate a circuit proposal."
                )
            client = AsyncOpenAI(api_key=self.settings.openai_api_key)

        content: list[dict[str, str]] = [
            {
                "type": "input_text",
                "text": (
                    f"{processed.text}\n\n"
                    f"User request:\n{request.user_request}"
                ),
            }
        ]
        if request.png_base64:
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{request.png_base64}",
                }
            )

        call = {
            "model": self.settings.openai_model,
            "instructions": INSTRUCTIONS,
            "input": [{"role": "user", "content": content}],
            "text_format": CircuitProposalDraft.__name__,
            "store": False,
        }
        if self._logger:
            self._logger.event(
                "openai", "request", "Sending Circuit proposal request to OpenAI",
                details=call,
            )
        response = await client.responses.parse(
            model=self.settings.openai_model,
            instructions=INSTRUCTIONS,
            input=[{"role": "user", "content": content}],
            text_format=CircuitProposalDraft,
            store=False,
        )
        if self._logger:
            self._logger.event(
                "openai", "response", "Received Circuit proposal response from OpenAI",
                details=response,
            )
        draft = response.output_parsed
        if draft is None:
            raise RuntimeError("The model did not return a circuit proposal.")
        if not draft.supported:
            return draft

        proposal_id = f"proposal_{uuid4().hex}"
        request_id = f"request_{uuid4().hex}"
        return CircuitProposalArtifact(
            proposal_id=proposal_id,
            document_id=processed.document_id,
            base_revision=processed.revision,
            title=draft.title,
            summary=draft.summary,
            rationale=draft.rationale,
            assumptions=draft.assumptions,
            batch=CircuitOperationBatch(
                request_id=request_id,
                expected_revision=processed.revision,
                operations=draft.operations,
            ),
        )

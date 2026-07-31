from __future__ import annotations

from uuid import uuid4

from openai import AsyncOpenAI

from ..config import Settings
from ..models import (
    CircuitAgentRequest,
    CircuitOperationBatch,
    CircuitProposalArtifact,
    CircuitProposalDraft,
)
from .context import CircuitContextProcessor

INSTRUCTIONS = """\
You propose safe, reviewable changes to an existing circuit.

Success means translating the user's request into a precise list of Circuit Designer
operations that can be previewed before any change is applied.

Allowed changes:
- add, update, or remove instances of component definitions already present;
- create, update, or delete nets;
- connect or disconnect net endpoints.

Never create or edit component definitions, boundary terminals, geometry, routes,
labels, or layout. Do not claim that a proposal has been applied. Reuse exact IDs
from the context where referring to existing objects. Use unique lowercase slug-like
IDs for new objects and unique operation IDs. List every material assumption.

If the request needs an unsupported change, return supported=false, an empty
operations list, and a concise unsupported_reason. Otherwise return supported=true,
unsupported_reason=null, and at least one operation.
"""


class CircuitEditingAgent:
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

    async def propose(
        self, request: CircuitAgentRequest
    ) -> CircuitProposalArtifact | CircuitProposalDraft:
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

        response = await client.responses.parse(
            model=self.settings.openai_model,
            instructions=INSTRUCTIONS,
            input=[{"role": "user", "content": content}],
            text_format=CircuitProposalDraft,
            store=False,
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

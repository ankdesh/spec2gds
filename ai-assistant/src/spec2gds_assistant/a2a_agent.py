from __future__ import annotations

import json
import re
from typing import Any

from a2a.helpers.proto_helpers import (
    get_data_parts,
    get_message_text,
    get_raw_parts,
    new_data_part,
    new_task_from_user_message,
    new_text_message,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState

from .agents.circuit_editor import CircuitEditingAgent
from .agents.spec_editor import SpecEditingAgent
from .models import (
    CircuitAgentRequest,
    CircuitProposalArtifact,
    CircuitProposalDraft,
    SpecAgentRequest,
    SpecProposalArtifact,
    SpecProposalDraft,
)


class CircuitEditingAgentExecutor(AgentExecutor):
    """A2A bridge for the simple CircuitEditingAgent."""

    def __init__(self, agent: CircuitEditingAgent) -> None:
        self.agent = agent

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        task = context.current_task
        if task is None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work(
            new_text_message(
                "Preparing a reviewable circuit change proposal…",
                context_id=task.context_id,
                task_id=task.id,
            )
        )

        try:
            request = self._request(context)
            result = await self.agent.propose(request)
            if isinstance(result, CircuitProposalDraft):
                await updater.complete(
                    new_text_message(
                        result.unsupported_reason
                        or "That request is outside the circuit editing scope.",
                        context_id=task.context_id,
                        task_id=task.id,
                    )
                )
                return

            await updater.add_artifact(
                [
                    new_data_part(
                        result.model_dump(mode="json"),
                        media_type="application/vnd.spec2gds.circuit-proposal+json",
                    )
                ],
                artifact_id=result.proposal_id,
                name="Circuit change proposal",
                metadata={
                    "kind": "circuit_change_proposal",
                    "schema_version": "1",
                },
                last_chunk=True,
            )
            await updater.complete(
                new_text_message(
                    (
                        f"Proposal ready: {result.title}. "
                        "Review the assumptions and before/after circuit before sending it."
                    ),
                    context_id=task.context_id,
                    task_id=task.id,
                )
            )
        except Exception as reason:
            await updater.failed(
                new_text_message(
                    str(reason),
                    context_id=task.context_id,
                    task_id=task.id,
                )
            )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        task_id = context.task_id
        context_id = context.context_id
        if not task_id or not context_id:
            return
        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.update_status(
            TaskState.TASK_STATE_CANCELED,
            new_text_message(
                "Circuit proposal generation was canceled.",
                context_id=context_id,
                task_id=task_id,
            ),
        )

    def _request(self, context: RequestContext) -> CircuitAgentRequest:
        message = context.message
        user_request = get_message_text(message).strip()
        snapshot: dict[str, object] | None = None
        svg: str | None = None
        png_base64: str | None = None

        for value in get_data_parts(message.parts):
            if not isinstance(value, dict):
                continue
            candidate = value.get("snapshot")
            if value.get("kind") == "circuit_context" and isinstance(candidate, dict):
                snapshot = candidate
                encoded = value.get("png_base64")
                png_base64 = encoded if isinstance(encoded, str) else None
                rendered = value.get("svg")
                svg = rendered if isinstance(rendered, str) else None
            elif "revision" in value and "document" in value:
                snapshot = value

        for part, raw in zip(
            [part for part in message.parts if part.HasField("raw")],
            get_raw_parts(message.parts),
            strict=False,
        ):
            if part.media_type == "application/json" and snapshot is None:
                decoded = json.loads(raw.decode("utf-8"))
                if isinstance(decoded, dict):
                    snapshot = decoded.get("snapshot", decoded)
            elif part.media_type == "image/svg+xml":
                svg = raw.decode("utf-8")
            elif part.media_type == "image/png":
                import base64

                png_base64 = base64.b64encode(raw).decode("ascii")

        if snapshot is None:
            raise ValueError(
                "Attach the current Circuit Designer snapshot before requesting an edit."
            )
        if not user_request:
            raise ValueError("A circuit editing request is required.")
        return CircuitAgentRequest(
            user_request=user_request,
            snapshot=snapshot,
            svg=svg,
            png_base64=png_base64,
        )


class SpecEditingAgentExecutor(AgentExecutor):
    """A2A bridge for conversational Spec exploration and review proposals."""

    def __init__(self, agent: SpecEditingAgent) -> None:
        self.agent = agent

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if task is None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        try:
            request = self._request(context)
            await updater.start_work(
                new_text_message(
                    "Preparing a Spec proposal…" if request.proposal_requested else "Exploring the selected specification…",
                    context_id=task.context_id,
                    task_id=task.id,
                )
            )
            result = await self.agent.respond(request)
            if isinstance(result, str):
                await updater.complete(new_text_message(result, context_id=task.context_id, task_id=task.id))
                return
            if isinstance(result, SpecProposalDraft):
                await updater.complete(
                    new_text_message(
                        result.unsupported_reason or "That change is outside this Spec chat's writable boundary.",
                        context_id=task.context_id,
                        task_id=task.id,
                    )
                )
                return
            await updater.add_artifact(
                [
                    new_data_part(
                        result.model_dump(mode="json"),
                        media_type="application/vnd.spec2gds.spec-proposal+json",
                    )
                ],
                artifact_id=result.proposal_id,
                name="Spec change proposal",
                metadata={"kind": "spec_change_proposal", "schema_version": "1.0"},
                last_chunk=True,
            )
            await updater.complete(
                new_text_message(
                    f"Proposal ready: {result.title}. Review the rendered changes before applying it.",
                    context_id=task.context_id,
                    task_id=task.id,
                )
            )
        except Exception as reason:
            await updater.failed(new_text_message(str(reason), context_id=task.context_id, task_id=task.id))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        if not context.task_id or not context.context_id:
            return
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.update_status(
            TaskState.TASK_STATE_CANCELED,
            new_text_message(
                "Spec AI Assistant request was canceled.",
                context_id=context.context_id,
                task_id=context.task_id,
            ),
        )

    def _request(self, context: RequestContext) -> SpecAgentRequest:
        user_request = get_message_text(context.message).strip()
        spec_context: dict[str, Any] | None = None
        proposal_requested = False
        summary: str | None = None
        recent_messages: list[dict[str, Any]] = []
        for value in get_data_parts(context.message.parts):
            if not isinstance(value, dict) or value.get("kind") != "spec_context":
                continue
            candidate = value.get("context")
            if isinstance(candidate, dict):
                spec_context = candidate
            proposal_requested = value.get("proposal_requested") is True
            conversation = value.get("conversation")
            if isinstance(conversation, dict):
                candidate_summary = conversation.get("summary")
                summary = candidate_summary if isinstance(candidate_summary, str) else None
                messages = conversation.get("recent_messages")
                if isinstance(messages, list):
                    recent_messages = [item for item in messages if isinstance(item, dict)]
        if spec_context is None:
            raise ValueError("Attach the selected Spec entity context before asking the Spec agent.")
        if not user_request:
            raise ValueError("A Spec exploration request is required.")
        return SpecAgentRequest(
            user_request=user_request,
            context=spec_context,
            proposal_requested=proposal_requested
            or _explicit_spec_proposal_intent(user_request),
            conversation_summary=summary,
            recent_messages=recent_messages,
        )


def _explicit_spec_proposal_intent(user_request: str) -> bool:
    return bool(
        re.search(
            r"\b(prepare|create|generate|make|turn\s+this\s+into)\b.{0,30}\bproposal\b|\bpropose\s+(the\s+)?changes?\b",
            user_request,
            flags=re.IGNORECASE,
        )
    )


class CombinedEditingAgentExecutor(AgentExecutor):
    """Dispatch A2A messages by attached domain context."""

    def __init__(
        self,
        circuit: CircuitEditingAgentExecutor,
        spec: SpecEditingAgentExecutor,
    ) -> None:
        self.circuit = circuit
        self.spec = spec

    def _delegate(self, context: RequestContext) -> AgentExecutor:
        for value in get_data_parts(context.message.parts):
            if isinstance(value, dict) and value.get("kind") == "spec_context":
                return self.spec
        return self.circuit

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await self._delegate(context).execute(context, event_queue)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await self._delegate(context).cancel(context, event_queue)

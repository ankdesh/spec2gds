from __future__ import annotations

import base64
import typing
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict

from .circuit_client import (
    CircuitDesignerClient,
    CircuitServiceError,
    normalize_circuit_base_url,
)
from .database import AssistantDatabase
from .spec_client import SpecEditorClient, SpecServiceError


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateThreadRequest(ApiModel):
    local_id: str | None = None
    title: str = "New circuit chat"
    domain: Literal["circuit", "spec"] = "circuit"


class UpdateThreadRequest(ApiModel):
    title: str | None = None
    include_png: bool | None = None


class MessageRequest(ApiModel):
    id: str
    parent_id: str | None = None
    role: str
    content: object


class CircuitBindingRequest(ApiModel):
    base_url: str
    document_id: str


class SpecBindingRequest(ApiModel):
    base_url: str
    document_id: str
    entity_kind: Literal[
        "component",
        "design",
        "bus_definition",
        "abstraction_definition",
        "narrative_block",
    ]
    entity_id: str


class SpecDocumentBindingRequest(ApiModel):
    base_url: str
    document_id: str


class PreviewRequest(ApiModel):
    proposal_id: str
    message_id: str | None = None
    artifact: dict[str, Any]


class SubmitProposalRequest(ApiModel):
    proposal_id: str


class ReviewStateRequest(ApiModel):
    state: Literal["draft", "invalid", "ready", "stale", "discarded", "applied"]


def create_api_router(
    *,
    database: AssistantDatabase,
    circuit_client: CircuitDesignerClient,
    spec_client: SpecEditorClient | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api")

    def db() -> AssistantDatabase:
        return database

    def require_thread(
        thread_id: str, repository: AssistantDatabase = Depends(db)
    ) -> dict[str, Any]:
        thread = repository.get_thread(thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="Unknown assistant thread.")
        return thread

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/threads")
    async def list_threads(
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, list[dict[str, Any]]]:
        return {"threads": repository.list_threads()}

    @router.post("/threads", status_code=status.HTTP_201_CREATED)
    async def create_thread(
        body: CreateThreadRequest,
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        try:
            return repository.create_thread(
                thread_id=body.local_id, title=body.title, domain=body.domain
            )
        except Exception as reason:
            if "UNIQUE constraint" in str(reason):
                existing = repository.get_thread(body.local_id or "")
                if existing:
                    return existing
            raise

    @router.post("/spec/launch", status_code=status.HTTP_201_CREATED)
    async def launch_spec_thread(
        body: SpecBindingRequest,
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        client = _require_spec_client(spec_client)
        try:
            thread = await create_bound_spec_thread(
                repository,
                client,
                base_url=body.base_url,
                document_id=body.document_id,
                entity_kind=body.entity_kind,
                entity_id=body.entity_id,
            )
        except ValueError as reason:
            raise HTTPException(status_code=400, detail=str(reason)) from reason
        except SpecServiceError as reason:
            raise _spec_http_exception(reason) from reason
        return {"thread": thread}

    @router.post("/spec/document/launch", status_code=status.HTTP_201_CREATED)
    async def launch_spec_document_thread(
        body: SpecDocumentBindingRequest,
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        client = _require_spec_client(spec_client)
        try:
            thread = await create_bound_spec_document_thread(
                repository,
                client,
                base_url=body.base_url,
                document_id=body.document_id,
            )
        except ValueError as reason:
            raise HTTPException(status_code=400, detail=str(reason)) from reason
        except SpecServiceError as reason:
            raise _spec_http_exception(reason) from reason
        return {"thread": thread}

    @router.get("/threads/{thread_id}")
    async def get_thread(
        thread: dict[str, Any] = Depends(require_thread),
    ) -> dict[str, Any]:
        return thread

    @router.patch("/threads/{thread_id}")
    async def update_thread(
        thread_id: str,
        body: UpdateThreadRequest,
        _: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        updated = repository.update_thread(
            thread_id, title=body.title, include_png=body.include_png
        )
        assert updated is not None
        return updated

    @router.post("/threads/{thread_id}/archive")
    async def archive_thread(
        thread_id: str,
        _: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        updated = repository.update_thread(thread_id, status="archived")
        assert updated is not None
        return updated

    @router.post("/threads/{thread_id}/unarchive")
    async def unarchive_thread(
        thread_id: str,
        _: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        updated = repository.update_thread(thread_id, status="regular")
        assert updated is not None
        return updated

    @router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_thread(
        thread_id: str,
        _: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> Response:
        repository.delete_thread(thread_id)
        return Response(status_code=204)

    @router.get("/threads/{thread_id}/messages")
    async def list_messages(
        thread_id: str,
        _: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, list[dict[str, Any]]]:
        return {"messages": repository.list_messages(thread_id)}

    @router.post(
        "/threads/{thread_id}/messages",
        status_code=status.HTTP_201_CREATED,
    )
    async def append_message(
        thread_id: str,
        body: MessageRequest,
        _: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        return repository.append_message(
            thread_id,
            message_id=body.id,
            parent_id=body.parent_id,
            role=body.role,
            content=body.content,
        )

    @router.patch("/threads/{thread_id}/messages/{message_id}")
    async def update_message(
        thread_id: str,
        message_id: str,
        body: MessageRequest,
        _: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        updated = repository.update_message(
            thread_id, message_id, role=body.role, content=body.content
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Unknown message.")
        return updated

    @router.delete(
        "/threads/{thread_id}/messages/{message_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_message(
        thread_id: str,
        message_id: str,
        _: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> Response:
        if not repository.delete_message(thread_id, message_id):
            raise HTTPException(status_code=404, detail="Unknown message.")
        return Response(status_code=204)

    @router.put("/threads/{thread_id}/circuit")
    async def bind_circuit(
        thread_id: str,
        body: CircuitBindingRequest,
        _: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        try:
            base_url = normalize_circuit_base_url(
                body.base_url,
                getattr(circuit_client, "allowlist", ()),
            )
            snapshot = await circuit_client.snapshot(base_url, body.document_id)
            bound = repository.bind_circuit(
                thread_id, base_url=base_url, document_id=body.document_id
            )
        except ValueError as reason:
            raise HTTPException(status_code=400, detail=str(reason)) from reason
        except CircuitServiceError as reason:
            raise _circuit_http_exception(reason) from reason
        assert bound is not None
        return {"thread": bound, "snapshot": snapshot}

    @router.get("/threads/{thread_id}/circuit/context")
    async def circuit_context(
        thread: dict[str, Any] = Depends(require_thread),
    ) -> dict[str, Any]:
        base_url, document_id = _binding(thread)
        try:
            snapshot = await circuit_client.snapshot(base_url, document_id)
            svg = await circuit_client.svg(base_url, document_id)
            png_base64 = None
            if thread["include_png"]:
                png_base64 = base64.b64encode(
                    await circuit_client.png(base_url, document_id)
                ).decode("ascii")
            return {"snapshot": snapshot, "svg": svg, "png_base64": png_base64}
        except CircuitServiceError as reason:
            raise _circuit_http_exception(reason) from reason

    @router.put("/threads/{thread_id}/spec")
    async def bind_spec(
        thread_id: str,
        body: SpecBindingRequest,
        _: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        client = _require_spec_client(spec_client)
        try:
            base_url = client.normalize(body.base_url)
            context = await client.context(
                base_url,
                body.document_id,
                body.entity_kind,
                body.entity_id,
            )
            bound = repository.bind_spec(
                thread_id,
                base_url=base_url,
                document_id=body.document_id,
                entity_kind=body.entity_kind,
                entity_id=body.entity_id,
            )
        except ValueError as reason:
            raise HTTPException(status_code=400, detail=str(reason)) from reason
        except SpecServiceError as reason:
            raise _spec_http_exception(reason) from reason
        assert bound is not None
        return {"thread": bound, "context": context}

    @router.get("/threads/{thread_id}/spec/context")
    async def spec_context(
        thread: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        client = _require_spec_client(spec_client)
        base_url, document_id = _spec_connection(thread)
        try:
            if thread.get("binding_scope") == "document":
                context = await client.document_context(base_url, document_id)
            else:
                _, _, entity_kind, entity_id = _spec_entity_binding(thread)
                context = await client.context(
                    base_url, document_id, entity_kind, entity_id
                )
        except SpecServiceError as reason:
            raise _spec_http_exception(reason) from reason
        current_revision = context.get("source_revision_hash")
        for review in repository.list_reviews(thread["id"]):
            artifact = review["artifact"]
            if (
                review["state"] in {"draft", "ready", "invalid"}
                and isinstance(artifact, dict)
                and artifact.get("kind") == "spec_change_proposal"
                and artifact.get("base_source_revision_hash") != current_revision
            ):
                repository.upsert_review(
                    proposal_id=review["proposal_id"],
                    thread_id=thread["id"],
                    message_id=review["message_id"],
                    state="stale",
                    artifact=artifact,
                    base_document=review["base_document"],
                    candidate=review["candidate"],
                    diff=review["diff"],
                    diagnostics=["The Spec source revision changed."],
                    submitted_proposal_id=review["submitted_proposal_id"],
                )
        return {
            "context": context,
            "conversation": repository.conversation_context(thread["id"]),
        }

    @router.post("/threads/{thread_id}/circuit/preview")
    async def preview_proposal(
        body: PreviewRequest,
        thread: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        base_url, document_id = _binding(thread)
        if body.artifact.get("document_id") != document_id:
            raise HTTPException(
                status_code=400, detail="Proposal targets a different document."
            )
        batch = body.artifact.get("batch")
        if not isinstance(batch, dict):
            raise HTTPException(status_code=400, detail="Proposal batch is required.")
        try:
            current = await circuit_client.snapshot(base_url, document_id)
            if body.artifact.get("base_revision") != current.get("revision"):
                review = repository.upsert_review(
                    proposal_id=body.proposal_id,
                    thread_id=thread["id"],
                    message_id=body.message_id,
                    state="stale",
                    artifact=body.artifact,
                    base_document=current.get("document"),
                )
                return {"review": review}
            result = await circuit_client.preview(base_url, document_id, batch)
        except CircuitServiceError as reason:
            if reason.status_code in (400, 409):
                review = repository.upsert_review(
                    proposal_id=body.proposal_id,
                    thread_id=thread["id"],
                    message_id=body.message_id,
                    state="invalid",
                    artifact=body.artifact,
                    diagnostics=reason.detail,
                )
                return {"review": review}
            raise _circuit_http_exception(reason) from reason

        state = "ready" if result.get("status") == "accepted" else "invalid"
        review = repository.upsert_review(
            proposal_id=body.proposal_id,
            thread_id=thread["id"],
            message_id=body.message_id,
            state=state,
            artifact=body.artifact,
            base_document=current.get("document"),
            candidate=result.get("candidate"),
            diff=result.get("diff"),
            diagnostics=result.get("diagnostics"),
        )
        return {"review": review}

    @router.post("/threads/{thread_id}/spec/preview")
    async def preview_spec_proposal(
        body: PreviewRequest,
        thread: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        client = _require_spec_client(spec_client)
        base_url, document_id = _spec_connection(thread)
        artifact = body.artifact
        target = artifact.get("target")
        scope = artifact.get("scope", "entity")
        if artifact.get("kind") != "spec_change_proposal":
            raise HTTPException(status_code=400, detail="A typed Spec proposal is required.")
        if artifact.get("document_id") != document_id:
            raise HTTPException(status_code=400, detail="Proposal targets a different Spec chat binding.")
        if thread.get("binding_scope") == "document":
            if scope != "document" or target is not None:
                raise HTTPException(
                    status_code=400,
                    detail="A document-bound chat requires a document-scoped proposal.",
                )
        else:
            _, _, entity_kind, entity_id = _spec_entity_binding(thread)
            if (
                scope != "entity"
                or not isinstance(target, dict)
                or target.get("entity_kind") != entity_kind
                or target.get("entity_id") != entity_id
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Proposal targets a different Spec chat binding.",
                )
        for previous in repository.list_reviews(thread["id"]):
            if previous["proposal_id"] != body.proposal_id and previous["state"] in {"draft", "ready", "invalid"}:
                repository.upsert_review(
                    proposal_id=previous["proposal_id"],
                    thread_id=thread["id"],
                    message_id=previous["message_id"],
                    state="discarded",
                    artifact=previous["artifact"],
                    base_document=previous["base_document"],
                    candidate=previous["candidate"],
                    diff=previous["diff"],
                    diagnostics=previous["diagnostics"],
                    submitted_proposal_id=previous["submitted_proposal_id"],
                )
        try:
            result = await client.preview(base_url, artifact)
        except SpecServiceError as reason:
            state = "stale" if reason.status_code == 409 else "invalid"
            if reason.status_code not in {400, 409, 422}:
                raise _spec_http_exception(reason) from reason
            review = repository.upsert_review(
                proposal_id=body.proposal_id,
                thread_id=thread["id"],
                message_id=body.message_id,
                state=state,
                artifact=artifact,
                diagnostics=reason.detail,
            )
            return {"review": review}
        state = {
            "valid": "ready",
            "invalid": "invalid",
            "stale": "stale",
        }.get(str(result.get("status")), "invalid")
        review = repository.upsert_review(
            proposal_id=body.proposal_id,
            thread_id=thread["id"],
            message_id=body.message_id,
            state=state,
            artifact=artifact,
            base_document=result.get("current_sections"),
            candidate=result.get("candidate_sections"),
            diff=result.get("diff"),
            diagnostics=result.get("diagnostics"),
        )
        return {"review": review}

    @router.get("/threads/{thread_id}/reviews")
    async def list_reviews(
        thread_id: str,
        _: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, list[dict[str, Any]]]:
        return {"reviews": repository.list_reviews(thread_id)}

    @router.get("/threads/{thread_id}/reviews/{proposal_id}")
    async def get_review(
        thread_id: str,
        proposal_id: str,
        _: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        review = repository.get_review(thread_id, proposal_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Unknown proposal review.")
        return review

    @router.patch("/threads/{thread_id}/reviews/{proposal_id}")
    async def update_review_state(
        thread_id: str,
        proposal_id: str,
        body: ReviewStateRequest,
        _: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        review = repository.get_review(thread_id, proposal_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Unknown proposal review.")
        return repository.upsert_review(
            proposal_id=proposal_id,
            thread_id=thread_id,
            message_id=review["message_id"],
            state=body.state,
            artifact=review["artifact"],
            base_document=review["base_document"],
            candidate=review["candidate"],
            diff=review["diff"],
            diagnostics=review["diagnostics"],
            submitted_proposal_id=review["submitted_proposal_id"],
        )

    @router.post("/threads/{thread_id}/circuit/proposals")
    async def submit_proposal(
        body: SubmitProposalRequest,
        thread: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        review = repository.get_review(thread["id"], body.proposal_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Unknown proposal review.")
        if review["state"] != "ready":
            raise HTTPException(
                status_code=409, detail="Only a ready proposal can be sent."
            )
        artifact = review["artifact"]
        base_url, document_id = _binding(thread)
        request = {
            "proposal_id": artifact["proposal_id"],
            "document_id": artifact["document_id"],
            "base_revision": artifact["base_revision"],
            "title": artifact["title"],
            "summary": artifact["summary"],
            "rationale": artifact["rationale"],
            "assumptions": artifact["assumptions"],
            "batch": artifact["batch"],
        }
        try:
            saved = await circuit_client.submit_proposal(
                base_url, document_id, request
            )
        except CircuitServiceError as reason:
            if reason.status_code == 409:
                repository.upsert_review(
                    proposal_id=body.proposal_id,
                    thread_id=thread["id"],
                    message_id=review["message_id"],
                    state="stale",
                    artifact=artifact,
                    base_document=review["base_document"],
                    candidate=review["candidate"],
                    diff=review["diff"],
                    diagnostics=reason.detail,
                )
            raise _circuit_http_exception(reason) from reason
        updated = repository.upsert_review(
            proposal_id=body.proposal_id,
            thread_id=thread["id"],
            message_id=review["message_id"],
            state="sent",
            artifact=artifact,
            base_document=review["base_document"],
            candidate=review["candidate"],
            diff=review["diff"],
            diagnostics=review["diagnostics"],
            submitted_proposal_id=str(saved.get("proposal_id", body.proposal_id)),
        )
        return {"proposal": saved, "review": updated}

    @router.post("/threads/{thread_id}/spec/proposals")
    async def apply_spec_proposal(
        body: SubmitProposalRequest,
        thread: dict[str, Any] = Depends(require_thread),
        repository: AssistantDatabase = Depends(db),
    ) -> dict[str, Any]:
        review = repository.get_review(thread["id"], body.proposal_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Unknown proposal review.")
        if review["state"] != "ready":
            raise HTTPException(status_code=409, detail="Only a ready proposal can be applied.")
        client = _require_spec_client(spec_client)
        base_url, _ = _spec_connection(thread)
        try:
            applied = await client.apply(base_url, review["artifact"])
        except SpecServiceError as reason:
            failed = repository.upsert_review(
                proposal_id=body.proposal_id,
                thread_id=thread["id"],
                message_id=review["message_id"],
                state="stale" if reason.status_code == 409 else "invalid",
                artifact=review["artifact"],
                base_document=review["base_document"],
                candidate=review["candidate"],
                diff=review["diff"],
                diagnostics=reason.detail,
                submitted_proposal_id=review["submitted_proposal_id"],
            )
            return {"result": None, "review": failed}
        updated = repository.upsert_review(
            proposal_id=body.proposal_id,
            thread_id=thread["id"],
            message_id=review["message_id"],
            state="applied",
            artifact=review["artifact"],
            base_document=review["base_document"],
            candidate=review["candidate"],
            diff=review["diff"],
            diagnostics=review["diagnostics"],
            submitted_proposal_id=str(applied.get("proposal_id", body.proposal_id)),
        )
        return {"result": applied, "review": updated}

    return router


def _binding(thread: dict[str, Any]) -> tuple[str, str]:
    base_url = thread.get("circuit_base_url")
    document_id = thread.get("document_id")
    if not isinstance(base_url, str) or not isinstance(document_id, str):
        raise HTTPException(status_code=409, detail="Connect this chat to a circuit first.")
    return base_url, document_id


def _spec_connection(thread: dict[str, Any]) -> tuple[str, str]:
    values = (thread.get("service_base_url"), thread.get("document_id"))
    if thread.get("domain") != "spec" or any(
        not isinstance(value, str) for value in values
    ):
        raise HTTPException(status_code=409, detail="Connect this chat to a Spec first.")
    return typing.cast(tuple[str, str], values)


def _spec_entity_binding(thread: dict[str, Any]) -> tuple[str, str, str, str]:
    values = (
        thread.get("service_base_url"),
        thread.get("document_id"),
        thread.get("entity_kind"),
        thread.get("entity_id"),
    )
    if thread.get("domain") != "spec" or any(not isinstance(value, str) for value in values):
        raise HTTPException(status_code=409, detail="Connect this chat to a Spec entity first.")
    return typing.cast(tuple[str, str, str, str], values)


def _circuit_http_exception(reason: CircuitServiceError) -> HTTPException:
    return HTTPException(status_code=reason.status_code, detail=reason.detail)


def _require_spec_client(client: SpecEditorClient | None) -> SpecEditorClient:
    if client is None:
        raise HTTPException(status_code=503, detail="Spec integration is not configured.")
    return client


def _spec_http_exception(reason: SpecServiceError) -> HTTPException:
    return HTTPException(status_code=reason.status_code, detail=reason.detail)


async def create_bound_spec_thread(
    database: AssistantDatabase,
    spec_client: SpecEditorClient,
    *,
    base_url: str,
    document_id: str,
    entity_kind: str,
    entity_id: str,
) -> dict[str, Any]:
    """Create a new thread only after its requested Spec binding validates."""
    normalized = spec_client.normalize(base_url)
    await spec_client.context(normalized, document_id, entity_kind, entity_id)
    thread = database.create_thread(
        title=f"{entity_kind.replace('_', ' ').title()} · {entity_id}",
        domain="spec",
    )
    bound = database.bind_spec(
        thread["id"],
        base_url=normalized,
        document_id=document_id,
        entity_kind=entity_kind,
        entity_id=entity_id,
    )
    assert bound is not None
    return bound


async def create_bound_spec_document_thread(
    database: AssistantDatabase,
    spec_client: SpecEditorClient,
    *,
    base_url: str,
    document_id: str,
) -> dict[str, Any]:
    """Create a document-bound thread after validating document-wide Spec context."""
    normalized = spec_client.normalize(base_url)
    await spec_client.document_context(normalized, document_id)
    thread = database.create_thread(
        title=f"Specification · {document_id}",
        domain="spec",
    )
    bound = database.bind_spec_document(
        thread["id"],
        base_url=normalized,
        document_id=document_id,
    )
    assert bound is not None
    return bound

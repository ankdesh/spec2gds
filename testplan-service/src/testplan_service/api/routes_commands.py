"""Command execution and preview routes."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from testplan_service.application.service import VerificationPlannerService
from testplan_service.domain.operations import CommandBatchRequest, CommandBatchResponse
from testplan_service.exceptions import (
    DomainValidationError,
    IdempotencyMismatchError,
    PlanNotFoundError,
    PreconditionRequiredError,
    RecordNotFoundError,
    RevisionConflictError,
)

router = APIRouter()


def create_commands_router(get_service: Callable[[], VerificationPlannerService]) -> APIRouter:
    """Factory creating command batch execution endpoints."""
    commands_router = APIRouter(tags=["Commands"])

    @commands_router.post(
        "/plans/{plan_id}/commands/preview",
        response_model=CommandBatchResponse,
    )
    @commands_router.post(
        "/plans/{plan_id}/commands/preview",
        response_model=CommandBatchResponse,
    )
    def preview_commands(
        plan_id: str,
        payload: CommandBatchRequest,
        service: VerificationPlannerService = Depends(get_service),
    ) -> Any:
        """Validate candidate operations and return diff/diagnostics without committing changes."""
        return service.execute_commands(
            plan_id=plan_id,
            base_edit_revision=payload.base_edit_revision,
            request_id=payload.request_id,
            operations=payload.operations,
            preview_only=True,
        )

    @commands_router.post(
        "/plans/{plan_id}/commands",
        response_model=CommandBatchResponse,
    )
    def apply_commands(
        plan_id: str,
        payload: CommandBatchRequest,
        preview: bool = Query(False, description="Preview changes without committing"),
        if_match: str | None = Header(None, alias="If-Match"),
        service: VerificationPlannerService = Depends(get_service),
    ) -> Any:
        """Apply an atomic batch of typed operations with revision precondition and idempotency."""
        base_rev = payload.base_edit_revision
        if if_match is not None:
            clean_if_match = if_match.strip().strip('"')
            try:
                header_rev = int(clean_if_match)
                if header_rev != base_rev:
                    raise RevisionConflictError(
                        plan_id=plan_id,
                        base_revision=base_rev,
                        current_revision=header_rev,
                        request_id=payload.request_id,
                    )
            except ValueError:
                pass

        if base_rev is None:
            raise PreconditionRequiredError()

        return service.execute_commands(
            plan_id=plan_id,
            base_edit_revision=base_rev,
            request_id=payload.request_id,
            operations=payload.operations,
            preview_only=preview,
        )

    return commands_router


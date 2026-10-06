"""Server-Sent Events (SSE) notification streaming for plan changes."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator, Callable

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse

from testplan_service.application.service import VerificationPlannerService

router = APIRouter()


def create_events_router(get_service: Callable[[], VerificationPlannerService]) -> APIRouter:
    """Factory creating SSE event streaming endpoint."""
    events_router = APIRouter(tags=["Events"])

    @events_router.get("/plans/{plan_id}/events")
    async def stream_plan_events(
        plan_id: str,
        last_event_id: str | None = Header(None, alias="Last-Event-ID"),
        service: VerificationPlannerService = Depends(get_service),
    ) -> StreamingResponse:
        """Stream real-time SSE notifications for plan and checkpoint changes."""

        async def event_generator() -> AsyncGenerator[str, None]:
            curr_last_id = last_event_id
            while True:
                events = service.get_events(plan_id, curr_last_id)
                for ev in events:
                    curr_last_id = ev["event_id"]
                    ev_data = json.dumps(ev)
                    yield f"id: {curr_last_id}\nevent: {ev['kind']}\ndata: {ev_data}\n\n"

                await asyncio.sleep(2)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return events_router

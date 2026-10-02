"""Legacy prototype export router; not mounted by the Verification Planner app.

The current service uses routes_exports.py and application/export_service.py.
Keep this distinction explicit when reading old JSON-node import behavior.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response, status

from testplan_service.models.testplan import TestPlanDocument
from testplan_service.service.export_service import ExportService
from testplan_service.service.manager import TestPlanManager


def create_export_router(
    manager_provider: Any,
    export_service_provider: Any,
) -> APIRouter:
    """Compose the legacy JSON-node routes, independently of the current API."""
    router = APIRouter(prefix="/testplans", tags=["Export & Import"])

    @router.get("/{plan_id}/export/markdown")
    def export_markdown(
        plan_id: str,
        manager: TestPlanManager = Depends(manager_provider),
        exporter: ExportService = Depends(export_service_provider),
    ) -> Response:
        """Export the testplan as a structured, human-auditable Markdown document."""
        doc = manager.get_plan(plan_id)
        md_text = exporter.to_markdown(doc)
        return Response(
            content=md_text,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{plan_id}_testplan.md"'},
        )

    @router.get("/{plan_id}/export/json", response_model=TestPlanDocument)
    def export_json(
        plan_id: str,
        manager: TestPlanManager = Depends(manager_provider),
        exporter: ExportService = Depends(export_service_provider),
    ) -> dict[str, Any]:
        """Export the testplan as a canonical JSON document."""
        doc = manager.get_plan(plan_id)
        return exporter.to_dict(doc)

    @router.post("/import", response_model=TestPlanDocument, status_code=status.HTTP_201_CREATED)
    def import_json(
        payload: dict[str, Any],
        manager: TestPlanManager = Depends(manager_provider),
        exporter: ExportService = Depends(export_service_provider),
    ) -> TestPlanDocument:
        """Import a complete testplan document from JSON payload."""
        doc = exporter.from_dict(payload)
        # Create plan in manager
        created = manager.create_plan(
            plan_id=doc.id,
            name=doc.name,
            description=doc.description,
            target_design=doc.target_design,
            version=doc.version,
            tags=doc.tags,
            metadata=doc.metadata,
        )
        # Add all nodes in topological / parent-first order
        added_node_ids: set[str] = set()
        remaining = list(doc.nodes.values())
        max_passes = len(remaining) + 1

        for _ in range(max_passes):
            progress = False
            next_remaining = []
            for node in remaining:
                if node.parent_id is None or node.parent_id in added_node_ids:
                    manager.add_node(created.id, node)
                    added_node_ids.add(node.id)
                    progress = True
                else:
                    next_remaining.append(node)
            remaining = next_remaining
            if not remaining or not progress:
                break

        return manager.get_plan(created.id)

    return router

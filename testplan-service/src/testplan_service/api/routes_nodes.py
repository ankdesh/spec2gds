"""FastAPI routes for hierarchical node CRUD and tree movement operations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from testplan_service.models.node import TestPlanNode
from testplan_service.models.operations import PlanOperation
from testplan_service.service.manager import TestPlanManager


class MoveNodeRequest(BaseModel):
    target_parent_id: str | None = Field(default=None)
    target_order: int | None = Field(default=None)


class BatchOperationsRequest(BaseModel):
    operations: list[PlanOperation] = Field(..., min_length=1)


def create_nodes_router(manager_provider: Any) -> APIRouter:
    router = APIRouter(prefix="/testplans/{plan_id}", tags=["Nodes"])

    @router.post("/nodes", response_model=TestPlanNode, status_code=status.HTTP_201_CREATED)
    def add_node(
        plan_id: str,
        node: TestPlanNode,
        manager: TestPlanManager = Depends(manager_provider),
    ) -> TestPlanNode:
        return manager.add_node(plan_id, node)

    @router.get("/nodes/{node_id}", response_model=TestPlanNode)
    def get_node(
        plan_id: str,
        node_id: str,
        manager: TestPlanManager = Depends(manager_provider),
    ) -> TestPlanNode:
        return manager.get_node(plan_id, node_id)

    @router.put("/nodes/{node_id}", response_model=TestPlanNode)
    def update_node(
        plan_id: str,
        node_id: str,
        updates: dict[str, Any],
        manager: TestPlanManager = Depends(manager_provider),
    ) -> TestPlanNode:
        return manager.update_node(plan_id, node_id, updates)

    @router.delete("/nodes/{node_id}")
    def delete_node(
        plan_id: str,
        node_id: str,
        cascade: bool = Query(True, description="Whether to recursively delete child nodes"),
        manager: TestPlanManager = Depends(manager_provider),
    ) -> dict[str, Any]:
        deleted = manager.delete_node(plan_id, node_id, cascade=cascade)
        return {"deleted_nodes": deleted, "count": len(deleted)}

    @router.post("/nodes/{node_id}/move", response_model=TestPlanNode)
    def move_node(
        plan_id: str,
        node_id: str,
        request: MoveNodeRequest,
        manager: TestPlanManager = Depends(manager_provider),
    ) -> TestPlanNode:
        return manager.move_node(
            plan_id,
            node_id,
            target_parent_id=request.target_parent_id,
            target_order=request.target_order,
        )

    @router.post("/batch")
    def batch_operations(
        plan_id: str,
        request: BatchOperationsRequest,
        manager: TestPlanManager = Depends(manager_provider),
    ) -> dict[str, Any]:
        audit_log = manager.execute_batch(plan_id, request.operations)
        return {"success": True, "applied_operations": len(request.operations), "audit_log": audit_log}

    return router

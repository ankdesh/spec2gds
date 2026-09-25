"""FastAPI routes for testplan document CRUD operations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from testplan_service.models.summary import TestPlanSummary
from testplan_service.models.testplan import TestPlanDocument
from testplan_service.service.manager import TestPlanManager


class CreateTestPlanRequest(BaseModel):
    id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(default="", max_length=32768)
    target_design: str = Field(default="", max_length=256)
    version: str = Field(default="1.0.0")
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateTestPlanRequest(BaseModel):
    name: str | None = Field(default=None, max_length=256)
    description: str | None = Field(default=None, max_length=32768)
    target_design: str | None = Field(default=None, max_length=256)
    version: str | None = Field(default=None)
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class CloneTestPlanRequest(BaseModel):
    new_id: str = Field(..., min_length=1, max_length=128)
    new_name: str = Field(..., min_length=1, max_length=256)


def create_testplans_router(manager_provider: Any) -> APIRouter:
    router = APIRouter(prefix="/testplans", tags=["Testplans"])

    @router.get("", response_model=list[TestPlanDocument])
    def list_testplans(
        target_design: str | None = Query(None, description="Filter by target design"),
        tag: str | None = Query(None, description="Filter by tag"),
        manager: TestPlanManager = Depends(manager_provider),
    ) -> list[TestPlanDocument]:
        return manager.list_plans(target_design=target_design, tag=tag)

    @router.post("", response_model=TestPlanDocument, status_code=status.HTTP_201_CREATED)
    def create_testplan(
        request: CreateTestPlanRequest,
        manager: TestPlanManager = Depends(manager_provider),
    ) -> TestPlanDocument:
        return manager.create_plan(
            plan_id=request.id,
            name=request.name,
            description=request.description,
            target_design=request.target_design,
            version=request.version,
            tags=request.tags,
            metadata=request.metadata,
        )

    @router.get("/{plan_id}", response_model=TestPlanDocument)
    def get_testplan(
        plan_id: str,
        manager: TestPlanManager = Depends(manager_provider),
    ) -> TestPlanDocument:
        return manager.get_plan(plan_id)

    @router.put("/{plan_id}", response_model=TestPlanDocument)
    def update_testplan(
        plan_id: str,
        request: UpdateTestPlanRequest,
        manager: TestPlanManager = Depends(manager_provider),
    ) -> TestPlanDocument:
        return manager.update_plan(
            plan_id,
            name=request.name,
            description=request.description,
            target_design=request.target_design,
            version=request.version,
            tags=request.tags,
            metadata=request.metadata,
        )

    @router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_testplan(
        plan_id: str,
        manager: TestPlanManager = Depends(manager_provider),
    ) -> None:
        manager.delete_plan(plan_id)

    @router.post("/{plan_id}/clone", response_model=TestPlanDocument, status_code=status.HTTP_201_CREATED)
    def clone_testplan(
        plan_id: str,
        request: CloneTestPlanRequest,
        manager: TestPlanManager = Depends(manager_provider),
    ) -> TestPlanDocument:
        return manager.clone_plan(plan_id, request.new_id, request.new_name)

    @router.get("/{plan_id}/summary", response_model=TestPlanSummary)
    def get_testplan_summary(
        plan_id: str,
        manager: TestPlanManager = Depends(manager_provider),
    ) -> TestPlanSummary:
        return manager.get_summary(plan_id)

    @router.get("/{plan_id}/tree")
    def get_testplan_tree(
        plan_id: str,
        manager: TestPlanManager = Depends(manager_provider),
    ) -> list[dict[str, Any]]:
        tree_nodes = manager.get_tree(plan_id)
        return [node.model_dump() for node in tree_nodes]

    return router

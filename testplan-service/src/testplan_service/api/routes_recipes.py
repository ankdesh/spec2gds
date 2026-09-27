"""Recipe, Target Binding, and Backend Configuration routes."""

from __future__ import annotations

from typing import Any, Callable
from fastapi import APIRouter, Depends, HTTPException

from testplan_service.application.service import TestPlanService
from testplan_service.domain.recipes import BackendConfiguration, Recipe, TargetBindingSet
from testplan_service.exceptions import PlanNotFoundError, RecordNotFoundError


def create_recipes_router(get_service: Callable[[], TestPlanService]) -> APIRouter:
    """Factory creating recipes and implementation authoring endpoints."""
    router = APIRouter(tags=["Recipes & Implementation"])

    @router.post("/plans/{plan_id}/recipes/{recipe_id}/validate")
    def validate_recipe(
        plan_id: str,
        recipe_id: str,
        service: TestPlanService = Depends(get_service),
    ) -> dict[str, Any]:
        """Validate a recipe against Core Validation Order and capability rules without mutating state."""
        try:
            diags = service.validate_recipe(plan_id, recipe_id)
            return {
                "plan_id": plan_id,
                "recipe_id": recipe_id,
                "diagnostics": diags,
                "valid": len([d for d in diags if d.get("severity") == "error"]) == 0,
            }
        except PlanNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except RecordNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @router.get("/plans/{plan_id}/recipes", response_model=list[Recipe])
    def list_recipes(
        plan_id: str,
        service: TestPlanService = Depends(get_service),
    ) -> list[Recipe]:
        """List all active recipes in a plan."""
        return service.get_recipes(plan_id)

    @router.get("/plans/{plan_id}/recipes/{recipe_id}", response_model=Recipe)
    def get_recipe(
        plan_id: str,
        recipe_id: str,
        service: TestPlanService = Depends(get_service),
    ) -> Recipe:
        """Get an individual recipe by ID."""
        recipe = service.get_recipe(plan_id, recipe_id)
        if not recipe:
            raise HTTPException(
                status_code=404,
                detail=f"Recipe '{recipe_id}' not found in plan '{plan_id}'.",
            )
        return recipe

    @router.get("/plans/{plan_id}/binding-sets", response_model=list[TargetBindingSet])
    def list_binding_sets(
        plan_id: str,
        service: TestPlanService = Depends(get_service),
    ) -> list[TargetBindingSet]:
        """List all target signal binding sets for a plan."""
        return service.get_binding_sets(plan_id)

    @router.get("/plans/{plan_id}/binding-sets/{binding_set_id}", response_model=TargetBindingSet)
    def get_binding_set(
        plan_id: str,
        binding_set_id: str,
        service: TestPlanService = Depends(get_service),
    ) -> TargetBindingSet:
        """Get a single target binding set by ID."""
        bnd = service.get_binding_set(plan_id, binding_set_id)
        if not bnd:
            raise HTTPException(
                status_code=404,
                detail=f"TargetBindingSet '{binding_set_id}' not found in plan '{plan_id}'.",
            )
        return bnd

    @router.get("/plans/{plan_id}/backend-configurations", response_model=list[BackendConfiguration])
    def list_backend_configurations(
        plan_id: str,
        service: TestPlanService = Depends(get_service),
    ) -> list[BackendConfiguration]:
        """List all saved backend toolchain configurations for a plan."""
        return service.get_backend_configurations(plan_id)

    return router

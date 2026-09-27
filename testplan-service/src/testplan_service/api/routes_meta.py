"""Metadata, capabilities, operation catalog, and health check routes."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter

from testplan_service.constants import (
    DEFAULT_PRODUCT_TITLE,
    DEFAULT_SERVICE_NAME,
    DEFAULT_SERVICE_VERSION,
    MAX_HIERARCHY_DEPTH,
    MAX_INTENTS_LIMIT,
    MAX_OPERATIONS_PER_BATCH,
    MAX_REQUIREMENTS_LIMIT,
    SCHEMA_VERSION_BUNDLE,
    SCHEMA_VERSION_COVERAGE,
    SCHEMA_VERSION_PLAN,
    SCHEMA_VERSION_PRODUCER,
    SCHEMA_VERSION_REPORT,
    SCHEMA_VERSION_RESULTS,
    SCHEMA_VERSION_TEST_IR,
)
from testplan_service.domain.models import Intent, PlanCheckpoint, PlanHeader, Requirement, Section
from testplan_service.domain.objectives import CoverageDimension, CoverageExclusion, CoverageObjective
from testplan_service.domain.operations import CommandBatchRequest
from testplan_service.domain.policies import IntentEvidencePolicy
from testplan_service.domain.recipes import BackendConfiguration, Recipe, TargetBindingSet
from testplan_service.domain.test_ir import TestIR

router = APIRouter()
meta_router = router


@router.get("/health", tags=["Meta"])
def get_health() -> dict[str, str]:
    """Health readiness check with zero neighboring service dependencies."""
    return {"status": "ok", "storage": "ready"}


@router.get("/capabilities", tags=["Meta"])
def get_capabilities() -> dict[str, Any]:
    """Expose service capabilities, schema versions, and configured limits."""
    return {
        "service_name": DEFAULT_SERVICE_NAME,
        "product_title": DEFAULT_PRODUCT_TITLE,
        "version": DEFAULT_SERVICE_VERSION,
        "schemas": {
            "plan": SCHEMA_VERSION_PLAN,
            "coverage": SCHEMA_VERSION_COVERAGE,
            "test_ir": SCHEMA_VERSION_TEST_IR,
            "producer": SCHEMA_VERSION_PRODUCER,
            "results": SCHEMA_VERSION_RESULTS,
            "evidence_report": SCHEMA_VERSION_REPORT,
            "bundle": SCHEMA_VERSION_BUNDLE,
        },
        "limits": {
            "max_hierarchy_depth": MAX_HIERARCHY_DEPTH,
            "max_intents": MAX_INTENTS_LIMIT,
            "max_requirements": MAX_REQUIREMENTS_LIMIT,
            "max_operations_per_batch": MAX_OPERATIONS_PER_BATCH,
        },
        "layers": {
            "layer_1_test_plan": True,
            "layer_2_coverage": True,
            "layer_3_implementation": True,
        },
    }


@router.get("/operation-catalog", tags=["Meta"])
def get_operation_catalog() -> list[dict[str, Any]]:
    """Operation discovery endpoint cataloging all supported typed batch operations."""
    return [
        {"op": "plan.update", "description": "Update plan header metadata (name, description, owner, tags)."},
        {"op": "source_section.assess", "description": "Set source section audit disposition, reason, and mapped requirement IDs."},
        {"op": "requirement.create", "description": "Capture new behavioral requirement cited from source."},
        {"op": "requirement.update", "description": "Update requirement statement, disposition, or notes."},
        {"op": "section.create", "description": "Create a new organizational section within a scope."},
        {"op": "section.update", "description": "Update section title, priority, or tags."},
        {"op": "intent.create", "description": "Author atomic verification intent with Given/When/Then and observations."},
        {"op": "intent.update", "description": "Update intent behavior; semantic edits automatically reset ready intent to draft."},
        {"op": "intent.set_state", "description": "Transition intent state (draft, ready, blocked) with validation."},
        {"op": "intent.link_requirement", "description": "Link requirement to intent."},
        {"op": "intent.unlink_requirement", "description": "Unlink requirement from intent."},
        {"op": "item.move", "description": "Move section or intent to target scope and parent."},
        {"op": "section.copy", "description": "Deep copy section and descendant intents to another occurrence scope."},
        {"op": "record.archive", "description": "Soft archive a record and its descendants."},
        {"op": "record.restore", "description": "Restore an archived record."},
        {"op": "record.delete_draft", "description": "Hard delete an unreferenced draft record."},
        {"op": "issue.create", "description": "Raise an open question, ambiguity, or contradiction."},
        {"op": "issue.resolve", "description": "Resolve an issue with explanation."},
        {"op": "issue.reopen", "description": "Reopen a previously resolved issue."},
        {"op": "dimension.create", "description": "Define a parameter or scenario dimension for coverage binning."},
        {"op": "dimension.update", "description": "Update dimension description, value classes, or rationale."},
        {"op": "dimension.archive", "description": "Archive a coverage dimension."},
        {"op": "objective.create", "description": "Author coverage objective with family, semantic definition, bins, and acceptance."},
        {"op": "objective.update", "description": "Update objective; semantic edits automatically reset ready objective to draft."},
        {"op": "objective.archive", "description": "Archive a coverage objective."},
        {"op": "bin.add", "description": "Add an explicit scenario or functional bin to an objective."},
        {"op": "bin.update", "description": "Update bin target hits, assignments, or applicability."},
        {"op": "bin.remove", "description": "Remove a bin from a working objective definition."},
        {"op": "policy.set", "description": "Set complete multi-branch evidence policy and justifications for an intent."},
        {"op": "exclusion.propose", "description": "Propose an exclusion with technical rationale."},
        {"op": "exclusion.update", "description": "Update proposed exclusion rationale or supporting evidence."},
        {"op": "coverage.rebase", "description": "Rebase coverage definitions and mappings against a target plan checkpoint."},
    ]


@router.get("/schemas/{schema_id}", tags=["Meta"])
def get_schema(schema_id: str) -> dict[str, Any]:
    """Return JSON Schema for core domain models and command envelopes."""
    if schema_id == "plan":
        return PlanHeader.model_json_schema()
    elif schema_id == "intent":
        return Intent.model_json_schema()
    elif schema_id == "section":
        return Section.model_json_schema()
    elif schema_id == "requirement":
        return Requirement.model_json_schema()
    elif schema_id == "checkpoint":
        return PlanCheckpoint.model_json_schema()
    elif schema_id == "objective":
        return CoverageObjective.model_json_schema()
    elif schema_id == "dimension":
        return CoverageDimension.model_json_schema()
    elif schema_id == "policy":
        return IntentEvidencePolicy.model_json_schema()
    elif schema_id == "exclusion":
        return CoverageExclusion.model_json_schema()
    elif schema_id == "recipe":
        return Recipe.model_json_schema()
    elif schema_id in {"target_binding_set", "binding_set"}:
        return TargetBindingSet.model_json_schema()
    elif schema_id in {"backend_configuration", "backend_config"}:
        return BackendConfiguration.model_json_schema()
    elif schema_id in {"test_ir", "verification.test-ir.v1"}:
        return TestIR.model_json_schema()
    elif schema_id == "command_batch":
        return CommandBatchRequest.model_json_schema()
    return {"error": f"Schema '{schema_id}' not found."}

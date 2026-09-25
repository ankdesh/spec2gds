"""FastAPI routes implementing the AI Assistant interaction contract."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from testplan_service.constants import (
    DEFAULT_SERVICE_NAME,
    DEFAULT_SERVICE_VERSION,
    SERVICE_CAPABILITIES,
)
from testplan_service.models.operations import (
    ProposalApplyResult,
    ProposalArtifact,
    ProposalPreviewResult,
)
from testplan_service.service.export_service import ExportService
from testplan_service.service.manager import TestPlanManager
from testplan_service.service.proposal_handler import ProposalHandler


def create_assistant_router(
    manager_provider: Any,
    proposal_handler_provider: Any,
    export_service_provider: Any,
) -> APIRouter:
    router = APIRouter(tags=["AI Assistant Contract"])

    @router.get("/health")
    @router.get("/api/v1/health")
    def health_check() -> dict[str, Any]:
        """Health check endpoint matching spec-editor probe contract."""
        return {"status": "ok", "service": DEFAULT_SERVICE_NAME, "version": DEFAULT_SERVICE_VERSION}

    @router.get("/capabilities")
    @router.get("/api/v1/capabilities")
    def get_capabilities() -> dict[str, Any]:
        """Capabilities endpoint matching circuit-designer probe contract."""
        return {
            "service": DEFAULT_SERVICE_NAME,
            "version": DEFAULT_SERVICE_VERSION,
            "capabilities": list(SERVICE_CAPABILITIES),
        }

    @router.get("/documents")
    def list_documents(manager: TestPlanManager = Depends(manager_provider)) -> dict[str, Any]:
        """Document discovery endpoint matching assistant targets discovery."""
        plans = manager.list_plans()
        summaries = [
            {
                "document_id": p.id,
                "title": p.name,
                "target_design": p.target_design,
                "revision": p.revision,
                "node_count": len(p.nodes),
                "updated_at": p.updated_at,
            }
            for p in plans
        ]
        return {"documents": summaries}

    @router.get("/documents/{document_id}")
    def get_document(
        document_id: str,
        manager: TestPlanManager = Depends(manager_provider),
    ) -> dict[str, Any]:
        """Direct document retrieval by document ID."""
        doc = manager.get_plan(document_id)
        summary = manager.get_summary(document_id)
        return {
            "document_id": doc.id,
            "title": doc.name,
            "target_design": doc.target_design,
            "revision": doc.revision,
            "summary": summary.model_dump(),
            "nodes": [n.model_dump() for n in doc.build_tree()],
        }

    def _build_context(
        doc_id: str,
        manager: TestPlanManager,
        exporter: ExportService,
    ) -> dict[str, Any]:
        doc = manager.get_plan(doc_id)
        summary = manager.get_summary(doc_id)
        markdown_view = exporter.to_markdown(doc)
        return {
            "domain": "testplan",
            "document_id": doc.id,
            "title": doc.name,
            "target_design": doc.target_design,
            "revision": doc.revision,
            "version": doc.version,
            "updated_at": doc.updated_at,
            "summary": summary.model_dump(),
            "markdown_overview": markdown_view,
            "hierarchy_tree": [n.model_dump() for n in doc.build_tree()],
            "proposal_instructions": {
                "supported_actions": ["add_node", "update_node", "delete_node", "move_node"],
                "node_kinds": ["group", "feature", "testpoint", "testcase", "covergroup", "assertion"],
                "coverage_categories": [
                    "port_boundary", "reset_behavior", "functional_mode", "protocol_compliance",
                    "error_injection", "timing_sequencing", "cross_port", "structural_connectivity",
                    "special_patterns", "general"
                ],
                "methodologies": ["directed", "constrained_random", "formal", "assertion", "lint"],
                "stages": ["V0", "V1", "V2", "V3"],
            },
        }

    @router.get("/assistant/context")
    def get_assistant_context(
        document_id: str = Query(..., description="Document identifier for query parameter binding"),
        manager: TestPlanManager = Depends(manager_provider),
        exporter: ExportService = Depends(export_service_provider),
    ) -> dict[str, Any]:
        """Provide detailed context to AI Assistant via query parameter."""
        return _build_context(document_id, manager, exporter)

    @router.get("/documents/{document_id}/context")
    def get_document_context(
        document_id: str,
        manager: TestPlanManager = Depends(manager_provider),
        exporter: ExportService = Depends(export_service_provider),
    ) -> dict[str, Any]:
        """Provide detailed context to AI Assistant via path parameter."""
        return _build_context(document_id, manager, exporter)

    @router.post("/assistant/proposals/preview", response_model=ProposalPreviewResult)
    def preview_proposal(
        proposal: ProposalArtifact,
        handler: ProposalHandler = Depends(proposal_handler_provider),
    ) -> ProposalPreviewResult:
        """Preview and validate proposed operations without committing mutations."""
        return handler.preview(proposal)

    @router.post("/documents/{document_id}/operations/preview", response_model=ProposalPreviewResult)
    def preview_document_operations(
        document_id: str,
        proposal: ProposalArtifact,
        handler: ProposalHandler = Depends(proposal_handler_provider),
    ) -> ProposalPreviewResult:
        """Preview operations targeted at a specific document path."""
        if proposal.document_id != document_id:
            proposal = proposal.model_copy(update={"document_id": document_id})
        return handler.preview(proposal)

    @router.post("/assistant/proposals/apply", response_model=ProposalApplyResult)
    def apply_proposal(
        proposal: ProposalArtifact,
        handler: ProposalHandler = Depends(proposal_handler_provider),
    ) -> ProposalApplyResult:
        """Atomically commit reviewed proposal operations to the target testplan."""
        return handler.apply(proposal)

    @router.post("/documents/{document_id}/proposals", response_model=ProposalApplyResult)
    def apply_document_proposal(
        document_id: str,
        proposal: ProposalArtifact,
        handler: ProposalHandler = Depends(proposal_handler_provider),
    ) -> ProposalApplyResult:
        """Atomically commit proposal targeted at a specific document path."""
        if proposal.document_id != document_id:
            proposal = proposal.model_copy(update={"document_id": document_id})
        return handler.apply(proposal)

    return router

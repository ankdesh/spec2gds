"""Pytest fixtures for Testplan Service direct tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from testplan_service.api.app import create_app
from testplan_service.models.enums import (
    CoverageCategory,
    NodeKind,
    NodePriority,
    NodeStatus,
    VerificationMethodology,
    VerificationStage,
)
from testplan_service.models.node import TestPlanNode
from testplan_service.models.testplan import TestPlanDocument
from testplan_service.service.export_service import ExportService
from testplan_service.service.manager import TestPlanManager
from testplan_service.service.proposal_handler import ProposalHandler
from testplan_service.storage.memory_repository import MemoryTestPlanRepository


@pytest.fixture
def repository() -> MemoryTestPlanRepository:
    """Provide a clean in-memory testplan repository."""
    return MemoryTestPlanRepository()


@pytest.fixture
def manager(repository: MemoryTestPlanRepository) -> TestPlanManager:
    """Provide an initialized TestPlanManager backed by memory storage."""
    return TestPlanManager(repository)


@pytest.fixture
def proposal_handler(manager: TestPlanManager) -> ProposalHandler:
    """Provide an initialized ProposalHandler."""
    return ProposalHandler(manager)


@pytest.fixture
def export_service() -> ExportService:
    """Provide an ExportService instance."""
    return ExportService()


@pytest.fixture
def sample_plan(manager: TestPlanManager) -> TestPlanDocument:
    """Create a populated sample testplan with hierarchical nodes."""
    doc = manager.create_plan(
        plan_id="sample_alu_plan",
        name="Sample ALU Testplan",
        description="Hierarchical verification plan for ALU unit.",
        target_design="alu_top",
        version="1.0.0",
        tags=["alu", "sample"],
    )

    group = TestPlanNode(
        id="grp_arithmetic",
        parent_id=None,
        title="Arithmetic Operations",
        kind=NodeKind.GROUP,
        category=CoverageCategory.FUNCTIONAL_MODE,
        description="Verification group for all arithmetic datapath operations.",
        order=0,
    )
    manager.add_node(doc.id, group)

    tc1 = TestPlanNode(
        id="tc_add_basic",
        parent_id="grp_arithmetic",
        title="Basic 32-bit Addition",
        kind=NodeKind.TESTCASE,
        category=CoverageCategory.FUNCTIONAL_MODE,
        methodology=VerificationMethodology.DIRECTED,
        stage=VerificationStage.V1,
        priority=NodePriority.HIGH,
        status=NodeStatus.PASSED,
        stimulus="a=10, b=20, op=ADD",
        expected_outcome="sum=30",
        coverage_bins=["functional_mode:add:basic"],
        order=0,
    )
    manager.add_node(doc.id, tc1)

    tc2 = TestPlanNode(
        id="tc_add_max",
        parent_id="grp_arithmetic",
        title="Addition with Max Port Boundary",
        kind=NodeKind.TESTCASE,
        category=CoverageCategory.PORT_BOUNDARY,
        methodology=VerificationMethodology.CONSTRAINED_RANDOM,
        stage=VerificationStage.V2,
        priority=NodePriority.CRITICAL,
        status=NodeStatus.PLANNED,
        stimulus="a=0xFFFFFFFF, b=1, op=ADD",
        expected_outcome="sum=0, carry=1",
        coverage_bins=["boundary:a:max", "boundary:b:min"],
        order=1,
    )
    manager.add_node(doc.id, tc2)

    return manager.get_plan(doc.id)


@pytest.fixture
def client(repository: MemoryTestPlanRepository) -> TestClient:
    """Provide a FastAPI TestClient bound to an in-memory repository."""
    app = create_app(repository=repository)
    return TestClient(app)

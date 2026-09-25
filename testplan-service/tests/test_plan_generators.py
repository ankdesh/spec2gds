"""Tests that generate diverse hardware testplans and verify hierarchy, metrics, and exports."""

from __future__ import annotations

from pathlib import Path

from testplan_service.models.enums import (
    CoverageCategory,
    NodeKind,
    NodeStatus,
    VerificationMethodology,
    VerificationStage,
)
from testplan_service.models.summary import TestPlanSummary
from testplan_service.samples import (
    AluTestPlanBuilder,
    CrossbarTestPlanBuilder,
    FifoTestPlanBuilder,
    UartTestPlanBuilder,
    build_all_sample_plans,
)
from testplan_service.samples.seed import seed_repository
from testplan_service.service.export_service import ExportService
from testplan_service.storage.file_repository import FileTestPlanRepository


def test_generate_all_sample_plans() -> None:
    """Verify that all sample builders generate complete, valid testplan documents."""
    plans = build_all_sample_plans()
    assert len(plans) == 4

    plan_ids = [p.id for p in plans]
    assert "riscv_alu_verification_plan" in plan_ids
    assert "uart_16550_verification_plan" in plan_ids
    assert "dual_clock_fifo_verification_plan" in plan_ids
    assert "axi_lite_crossbar_verification_plan" in plan_ids

    for plan in plans:
        assert len(plan.name) > 0
        assert len(plan.target_design) > 0
        assert len(plan.description) > 0
        assert len(plan.nodes) >= 10, f"Plan {plan.id} should have a substantial number of nodes."


def test_sample_plans_hierarchy_integrity() -> None:
    """Verify that tree hierarchies in each plan are acyclic and reference valid parent nodes."""
    plans = build_all_sample_plans()
    for plan in plans:
        tree = plan.build_tree()
        assert len(tree) >= 3, f"Plan {plan.id} should have multiple root groups."

        # Verify all nodes with parents reference existing nodes
        for node in plan.nodes.values():
            if node.parent_id is not None:
                assert node.parent_id in plan.nodes, (
                    f"Node '{node.id}' in '{plan.id}' references missing parent '{node.parent_id}'"
                )

        # Count total nodes in tree traversal matches dictionary size
        def count_tree_nodes(roots: list) -> int:
            total = len(roots)
            for r in roots:
                total += count_tree_nodes(r.children)
            return total

        assert count_tree_nodes(tree) == len(plan.nodes)


def test_coverage_taxonomy_breadth() -> None:
    """Verify that all major hardware verification coverage categories are exercised."""
    plans = build_all_sample_plans()
    found_categories: set[CoverageCategory] = set()

    for plan in plans:
        for node in plan.nodes.values():
            found_categories.add(node.category)

    expected_categories = {
        CoverageCategory.PORT_BOUNDARY,
        CoverageCategory.RESET_BEHAVIOR,
        CoverageCategory.FUNCTIONAL_MODE,
        CoverageCategory.PROTOCOL_COMPLIANCE,
        CoverageCategory.ERROR_INJECTION,
        CoverageCategory.TIMING_SEQUENCING,
        CoverageCategory.CROSS_PORT,
        CoverageCategory.STRUCTURAL_CONNECTIVITY,
        CoverageCategory.SPECIAL_PATTERNS,
    }

    assert expected_categories.issubset(found_categories), (
        f"Missing categories: {expected_categories - found_categories}"
    )


def test_methodology_and_stage_diversity() -> None:
    """Verify that multiple verification methodologies and stages are represented."""
    plans = build_all_sample_plans()
    methodologies: set[VerificationMethodology] = set()
    stages: set[VerificationStage] = set()
    statuses: set[NodeStatus] = set()
    kinds: set[NodeKind] = set()

    for plan in plans:
        for node in plan.nodes.values():
            methodologies.add(node.methodology)
            stages.add(node.stage)
            statuses.add(node.status)
            kinds.add(node.kind)

    assert {VerificationMethodology.DIRECTED, VerificationMethodology.CONSTRAINED_RANDOM, VerificationMethodology.FORMAL}.issubset(methodologies)
    assert {VerificationStage.V0, VerificationStage.V1, VerificationStage.V2}.issubset(stages)
    assert {NodeStatus.PASSED, NodeStatus.FAILED, NodeStatus.IN_PROGRESS, NodeStatus.PLANNED}.issubset(statuses)
    assert {NodeKind.GROUP, NodeKind.FEATURE, NodeKind.TESTCASE, NodeKind.ASSERTION}.issubset(kinds)


def test_summary_metrics_calculation_on_samples() -> None:
    """Verify summary metrics aggregation across all generated testplans."""
    plans = build_all_sample_plans()
    for plan in plans:
        summary = TestPlanSummary.from_document(plan)
        assert summary.total_nodes == len(plan.nodes)
        assert summary.total_coverage_bins > 0
        assert len(summary.unique_coverage_bins) > 0
        assert 0.0 <= summary.pass_rate_percent <= 100.0
        assert 0.0 <= summary.completion_rate_percent <= 100.0


def test_export_markdown_and_json_on_samples() -> None:
    """Verify that every generated sample plan produces rich Markdown and JSON documentation."""
    exporter = ExportService()
    plans = build_all_sample_plans()

    for plan in plans:
        md = exporter.to_markdown(plan)
        assert f"# Testplan: {plan.name}" in md
        assert f"**Target Design:** `{plan.target_design}`" in md
        assert "## Hierarchical Testplan" in md
        assert "## Verification Summary & Metrics" in md

        data = exporter.to_dict(plan)
        assert data["id"] == plan.id
        assert len(data["nodes"]) == len(plan.nodes)


def test_seed_into_disk_repository(tmp_path: Path) -> None:
    """Verify seeding plans into an on-disk JSON repository works and enables immediate inspection."""
    repo = FileTestPlanRepository(tmp_path)
    seeded_plans = seed_repository(repo)

    assert len(seeded_plans) == 4
    for plan in seeded_plans:
        assert repo.exists(plan.id) is True
        loaded = repo.get(plan.id)
        assert loaded is not None
        assert loaded.name == plan.name
        assert len(loaded.nodes) == len(plan.nodes)

    # Verify all JSON files written to disk
    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) == 4


def test_individual_builders() -> None:
    """Test each individual builder class separately."""
    alu = AluTestPlanBuilder().build()
    assert alu.id == "riscv_alu_verification_plan"

    uart = UartTestPlanBuilder().build()
    assert uart.id == "uart_16550_verification_plan"

    fifo = FifoTestPlanBuilder().build()
    assert fifo.id == "dual_clock_fifo_verification_plan"

    xbar = CrossbarTestPlanBuilder().build()
    assert xbar.id == "axi_lite_crossbar_verification_plan"

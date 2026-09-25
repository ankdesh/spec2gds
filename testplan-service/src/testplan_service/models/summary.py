"""Summary statistics and coverage aggregation model for a testplan."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from testplan_service.models.enums import NodeKind, NodeStatus
from testplan_service.models.testplan import TestPlanDocument


class TestPlanSummary(BaseModel):
    """Aggregated metrics and coverage statistics for a testplan document."""

    model_config = ConfigDict(extra="forbid")

    total_nodes: int = 0
    nodes_by_kind: dict[str, int] = Field(default_factory=dict)
    nodes_by_category: dict[str, int] = Field(default_factory=dict)
    nodes_by_status: dict[str, int] = Field(default_factory=dict)
    nodes_by_priority: dict[str, int] = Field(default_factory=dict)
    nodes_by_stage: dict[str, int] = Field(default_factory=dict)
    total_coverage_bins: int = 0
    unique_coverage_bins: list[str] = Field(default_factory=list)
    pass_rate_percent: float = 0.0
    completion_rate_percent: float = 0.0

    @classmethod
    def from_document(cls, document: TestPlanDocument) -> TestPlanSummary:
        """Compute aggregated statistics from an active testplan document."""
        by_kind: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        by_stage: dict[str, int] = {}
        all_bins: set[str] = set()

        testcase_count = 0
        passed_count = 0
        completed_count = 0

        for node in document.nodes.values():
            k_val = node.kind.value
            by_kind[k_val] = by_kind.get(k_val, 0) + 1

            cat_val = node.category.value
            by_category[cat_val] = by_category.get(cat_val, 0) + 1

            st_val = node.status.value
            by_status[st_val] = by_status.get(st_val, 0) + 1

            prio_val = node.priority.value
            by_priority[prio_val] = by_priority.get(prio_val, 0) + 1

            stage_val = node.stage.value
            by_stage[stage_val] = by_stage.get(stage_val, 0) + 1

            for bin_name in node.coverage_bins:
                if bin_name.strip():
                    all_bins.add(bin_name.strip())

            # Evaluate execution metrics for leaf/testpoint items
            if node.kind in (NodeKind.TESTCASE, NodeKind.TESTPOINT, NodeKind.ASSERTION):
                testcase_count += 1
                if node.status == NodeStatus.PASSED:
                    passed_count += 1
                    completed_count += 1
                elif node.status in (NodeStatus.SKIPPED, NodeStatus.FAILED):
                    completed_count += 1

        pass_rate = round((passed_count / testcase_count * 100.0), 1) if testcase_count > 0 else 0.0
        completion_rate = (
            round((completed_count / testcase_count * 100.0), 1) if testcase_count > 0 else 0.0
        )

        return cls(
            total_nodes=len(document.nodes),
            nodes_by_kind=by_kind,
            nodes_by_category=by_category,
            nodes_by_status=by_status,
            nodes_by_priority=by_priority,
            nodes_by_stage=by_stage,
            total_coverage_bins=len(all_bins),
            unique_coverage_bins=sorted(all_bins),
            pass_rate_percent=pass_rate,
            completion_rate_percent=completion_rate,
        )

"""Direct tests for Markdown and JSON export/import services."""

from __future__ import annotations

from testplan_service.models.testplan import TestPlanDocument
from testplan_service.service.export_service import ExportService


def test_markdown_export_rendering(
    export_service: ExportService,
    sample_plan: TestPlanDocument,
) -> None:
    md = export_service.to_markdown(sample_plan)
    assert f"# Testplan: {sample_plan.name}" in md
    assert f"**Target Design:** `{sample_plan.target_design}`" in md
    assert "## Verification Summary & Metrics" in md
    assert "| Total Nodes | 3 |" in md
    assert "## Hierarchical Testplan" in md
    assert "[GROUP] Arithmetic Operations" in md
    assert "[TESTCASE] Basic 32-bit Addition" in md
    assert "[TESTCASE] Addition with Max Port Boundary" in md
    assert "**Stimulus:**" in md
    assert "**Expected Outcome:**" in md
    assert "`functional_mode:add:basic`" in md


def test_json_dict_roundtrip(
    export_service: ExportService,
    sample_plan: TestPlanDocument,
) -> None:
    data = export_service.to_dict(sample_plan)
    assert isinstance(data, dict)
    assert data["id"] == sample_plan.id
    assert len(data["nodes"]) == 3

    reconstructed = export_service.from_dict(data)
    assert reconstructed.id == sample_plan.id
    assert reconstructed.name == sample_plan.name
    assert len(reconstructed.nodes) == 3

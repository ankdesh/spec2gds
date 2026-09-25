"""Export and import service for testplan documents in Markdown and JSON formats."""

from __future__ import annotations

from typing import Any

from testplan_service.models.node import TestPlanNode
from testplan_service.models.summary import TestPlanSummary
from testplan_service.models.testplan import TestPlanDocument


class ExportService:
    """Serializes testplan hierarchies into human-auditable Markdown and JSON formats."""

    def to_dict(self, document: TestPlanDocument) -> dict[str, Any]:
        """Convert a testplan document to its canonical JSON-serializable dictionary."""
        return document.model_dump()

    def from_dict(self, payload: dict[str, Any]) -> TestPlanDocument:
        """Validate and construct a TestPlanDocument from arbitrary input dictionary."""
        return TestPlanDocument.model_validate(payload)

    def to_markdown(self, document: TestPlanDocument) -> str:
        """Render the testplan as a structured, human-auditable Markdown document."""
        summary = TestPlanSummary.from_document(document)
        lines: list[str] = [
            f"# Testplan: {document.name}",
            "",
            f"**Target Design:** `{document.target_design or 'Unspecified'}`  ",
            f"**Version:** `{document.version}` | **Revision:** `{document.revision}`  ",
            f"**Last Updated:** {document.updated_at}",
            "",
        ]

        if document.description:
            lines.extend([
                "## Overview",
                "",
                document.description,
                "",
            ])

        # Summary Metrics Table
        lines.extend([
            "## Verification Summary & Metrics",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Total Nodes | {summary.total_nodes} |",
            f"| Total Coverage Bins | {summary.total_coverage_bins} |",
            f"| Pass Rate | {summary.pass_rate_percent}% |",
            f"| Completion Rate | {summary.completion_rate_percent}% |",
            "",
            "### Breakdown by Status",
            "",
            "| Status | Count |",
            "| --- | --- |",
        ])
        for st, count in sorted(summary.nodes_by_status.items()):
            lines.append(f"| `{st}` | {count} |")

        lines.extend([
            "",
            "### Breakdown by Coverage Category",
            "",
            "| Category | Count |",
            "| --- | --- |",
        ])
        for cat, count in sorted(summary.nodes_by_category.items()):
            lines.append(f"| `{cat}` | {count} |")

        lines.extend([
            "",
            "## Hierarchical Testplan",
            "",
        ])

        tree = document.build_tree()
        if not tree:
            lines.append("_No verification nodes defined in this testplan._")
        else:
            for root_node in tree:
                self._render_node_md(root_node, depth=2, lines=lines)

        return "\n".join(lines) + "\n"

    def _render_node_md(self, node: TestPlanNode, depth: int, lines: list[str]) -> None:
        prefix = "#" * min(depth, 6)
        kind_label = node.kind.value.upper()
        lines.append(f"{prefix} [{kind_label}] {node.title}")
        lines.append("")

        meta_items = [
            f"**ID:** `{node.id}`",
            f"**Category:** `{node.category.value}`",
            f"**Methodology:** `{node.methodology.value}`",
            f"**Stage:** `{node.stage.value}`",
            f"**Priority:** `{node.priority.value}`",
            f"**Status:** `{node.status.value}`",
        ]
        lines.append(" • ".join(meta_items) + "  ")

        if node.tags:
            lines.append(f"**Tags:** {', '.join(f'`{t}`' for t in node.tags)}  ")

        if node.description:
            lines.append("")
            lines.append(node.description)

        if node.stimulus:
            lines.append("")
            lines.append("**Stimulus:**")
            lines.append(f"> {node.stimulus}")

        if node.expected_outcome:
            lines.append("")
            lines.append("**Expected Outcome:**")
            lines.append(f"> {node.expected_outcome}")

        if node.coverage_bins:
            lines.append("")
            lines.append("**Target Coverage Bins:**")
            for b in node.coverage_bins:
                lines.append(f"- `{b}`")

        lines.append("")

        # Render children recursively
        for child in node.children:
            self._render_node_md(child, depth + 1, lines)

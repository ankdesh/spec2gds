"""Domain model representing a complete hierarchical testplan document."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from testplan_service.constants import MAX_DESCRIPTION_LENGTH, MAX_TITLE_LENGTH
from testplan_service.models.node import TestPlanNode


class TestPlanDocument(BaseModel):
    """Authoritative hierarchical testplan document."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(
        ...,
        description="Unique identifier for the testplan document.",
        min_length=1,
        max_length=128,
    )
    name: str = Field(
        ...,
        description="Human-readable title of the verification plan.",
        min_length=1,
        max_length=MAX_TITLE_LENGTH,
    )
    description: str = Field(
        default="",
        description="Overview narrative or verification strategy description.",
        max_length=MAX_DESCRIPTION_LENGTH,
    )
    version: str = Field(
        default="1.0.0",
        description="SemVer string indicating the testplan release version.",
    )
    target_design: str = Field(
        default="",
        description="Target IP-XACT design, module, or component name under verification.",
        max_length=MAX_TITLE_LENGTH,
    )
    revision: int = Field(
        default=1,
        description="Monotonically increasing edit revision number.",
        ge=1,
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp when the testplan was created.",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp when the testplan was last modified.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Labels associated with the testplan document.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible document-level metadata.",
    )
    nodes: dict[str, TestPlanNode] = Field(
        default_factory=dict,
        description="Dictionary mapping node_id to TestPlanNode.",
    )

    def build_tree(self) -> list[TestPlanNode]:
        """Materialize the flat dictionary into a nested hierarchy tree."""
        # Deep copy nodes so we don't mutate stored nodes' children
        clones: dict[str, TestPlanNode] = {
            nid: node.model_copy(deep=True) for nid, node in self.nodes.items()
        }
        for node in clones.values():
            node.children = []

        roots: list[TestPlanNode] = []
        for node in clones.values():
            if node.parent_id and node.parent_id in clones:
                clones[node.parent_id].children.append(node)
            else:
                roots.append(node)

        # Sort children and roots by order, then title
        def sort_key(n: TestPlanNode) -> tuple[int, str]:
            return (n.order, n.title)

        roots.sort(key=sort_key)
        for node in clones.values():
            node.children.sort(key=sort_key)

        return roots

    def get_node_depth(self, node_id: str) -> int:
        """Calculate the tree depth of a node (0 for root nodes)."""
        depth = 0
        current_id: str | None = node_id
        visited: set[str] = set()

        while current_id is not None:
            if current_id in visited:
                break
            visited.add(current_id)
            node = self.nodes.get(current_id)
            if node is None or node.parent_id is None:
                break
            current_id = node.parent_id
            depth += 1
        return depth

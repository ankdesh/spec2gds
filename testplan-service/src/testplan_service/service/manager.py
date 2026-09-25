"""Business logic manager for hierarchical testplan documents and nodes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from testplan_service.constants import (
    ACTION_ADD_NODE,
    ACTION_DELETE_NODE,
    ACTION_MOVE_NODE,
    ACTION_UPDATE_NODE,
    MAX_NODES_PER_PLAN,
    MAX_TREE_DEPTH,
)
from testplan_service.exceptions import (
    CycleDetectedError,
    DuplicateNodeError,
    InvalidOperationError,
    MaxDepthExceededError,
    NodeNotFoundError,
    TestPlanAlreadyExistsError,
    TestPlanNotFoundError,
)
from testplan_service.logging import StructuredLogger
from testplan_service.models.node import TestPlanNode
from testplan_service.models.operations import PlanOperation
from testplan_service.models.summary import TestPlanSummary
from testplan_service.models.testplan import TestPlanDocument
from testplan_service.storage.interface import TestPlanRepository


class TestPlanManager:
    """Orchestrates CRUD operations, hierarchical tree manipulation, and cycle detection."""

    def __init__(
        self,
        repository: TestPlanRepository,
        logger: StructuredLogger | None = None,
    ) -> None:
        self._repo = repository
        self._logger = logger or StructuredLogger("testplan-manager")

    def create_plan(
        self,
        plan_id: str,
        name: str,
        *,
        description: str = "",
        target_design: str = "",
        version: str = "1.0.0",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TestPlanDocument:
        """Create a new empty testplan document."""
        clean_id = plan_id.strip()
        if not clean_id:
            raise InvalidOperationError("Testplan ID cannot be empty.", "create_plan")

        if self._repo.exists(clean_id):
            raise TestPlanAlreadyExistsError(clean_id)

        doc = TestPlanDocument(
            id=clean_id,
            name=name.strip(),
            description=description.strip(),
            target_design=target_design.strip(),
            version=version.strip(),
            tags=tags or [],
            metadata=metadata or {},
        )
        self._repo.save(doc)
        self._logger.info(f"Created testplan '{clean_id}' ({name})")
        return doc

    def get_plan(self, plan_id: str) -> TestPlanDocument:
        """Retrieve a testplan document by ID."""
        doc = self._repo.get(plan_id)
        if doc is None:
            raise TestPlanNotFoundError(plan_id)
        return doc

    def list_plans(
        self,
        *,
        target_design: str | None = None,
        tag: str | None = None,
    ) -> list[TestPlanDocument]:
        """List all testplans, with optional filtering."""
        plans = self._repo.list_all()
        if target_design:
            plans = [p for p in plans if p.target_design == target_design]
        if tag:
            plans = [p for p in plans if tag in p.tags]
        return sorted(plans, key=lambda p: p.name)

    def update_plan(
        self,
        plan_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        target_design: str | None = None,
        version: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TestPlanDocument:
        """Update testplan document metadata and bump its revision."""
        doc = self.get_plan(plan_id)
        changed = False

        if name is not None and name.strip() and doc.name != name.strip():
            doc.name = name.strip()
            changed = True
        if description is not None and doc.description != description.strip():
            doc.description = description.strip()
            changed = True
        if target_design is not None and doc.target_design != target_design.strip():
            doc.target_design = target_design.strip()
            changed = True
        if version is not None and doc.version != version.strip():
            doc.version = version.strip()
            changed = True
        if tags is not None and doc.tags != tags:
            doc.tags = tags
            changed = True
        if metadata is not None and doc.metadata != metadata:
            doc.metadata = metadata
            changed = True

        if changed:
            doc.revision += 1
            doc.updated_at = datetime.now(timezone.utc).isoformat()
            self._repo.save(doc)
            self._logger.info(f"Updated testplan '{plan_id}' to revision {doc.revision}")

        return doc

    def delete_plan(self, plan_id: str) -> None:
        """Permanently delete a testplan document."""
        if not self._repo.exists(plan_id):
            raise TestPlanNotFoundError(plan_id)
        self._repo.delete(plan_id)
        self._logger.info(f"Deleted testplan '{plan_id}'")

    def clone_plan(self, source_id: str, new_id: str, new_name: str) -> TestPlanDocument:
        """Clone an existing testplan under a new identifier."""
        source = self.get_plan(source_id)
        if self._repo.exists(new_id):
            raise TestPlanAlreadyExistsError(new_id)

        cloned = source.model_copy(deep=True)
        cloned.id = new_id.strip()
        cloned.name = new_name.strip()
        cloned.revision = 1
        now = datetime.now(timezone.utc).isoformat()
        cloned.created_at = now
        cloned.updated_at = now

        self._repo.save(cloned)
        self._logger.info(f"Cloned testplan '{source_id}' to '{new_id}'")
        return cloned

    def add_node(self, plan_id: str, node: TestPlanNode) -> TestPlanNode:
        """Add a new node to the testplan hierarchy."""
        doc = self.get_plan(plan_id)

        if len(doc.nodes) >= MAX_NODES_PER_PLAN:
            raise InvalidOperationError(
                f"Testplan reached node capacity limit ({MAX_NODES_PER_PLAN}).",
                "add_node",
            )

        if node.id in doc.nodes:
            raise DuplicateNodeError(plan_id, node.id)

        # Validate parent exists if specified
        if node.parent_id is not None:
            if node.parent_id not in doc.nodes:
                raise NodeNotFoundError(plan_id, node.parent_id)

        # Validate tree depth
        tentative_doc = doc.model_copy(deep=True)
        tentative_doc.nodes[node.id] = node
        depth = tentative_doc.get_node_depth(node.id)
        if depth > MAX_TREE_DEPTH:
            raise MaxDepthExceededError(node.id, depth, MAX_TREE_DEPTH)

        doc.nodes[node.id] = node
        doc.revision += 1
        doc.updated_at = datetime.now(timezone.utc).isoformat()
        self._repo.save(doc)

        self._logger.info(f"Added node '{node.id}' to testplan '{plan_id}'")
        return node

    def get_node(self, plan_id: str, node_id: str) -> TestPlanNode:
        """Retrieve a specific node from a testplan."""
        doc = self.get_plan(plan_id)
        node = doc.nodes.get(node_id)
        if node is None:
            raise NodeNotFoundError(plan_id, node_id)
        return node

    def update_node(
        self,
        plan_id: str,
        node_id: str,
        updates: dict[str, Any],
    ) -> TestPlanNode:
        """Update mutable fields on an existing node."""
        doc = self.get_plan(plan_id)
        existing = doc.nodes.get(node_id)
        if existing is None:
            raise NodeNotFoundError(plan_id, node_id)

        # Do not allow updating id directly via update_node
        clean_updates = {k: v for k, v in updates.items() if k != "id" and k != "children"}

        # If updating parent_id, delegate to move_node for cycle and depth validation
        if "parent_id" in clean_updates:
            new_parent = clean_updates.pop("parent_id")
            self.move_node(plan_id, node_id, target_parent_id=new_parent)
            # Re-fetch node after move
            doc = self.get_plan(plan_id)
            existing = doc.nodes[node_id]

        node_data = existing.model_dump()
        node_data.update(clean_updates)
        updated_node = TestPlanNode.model_validate(node_data)

        doc.nodes[node_id] = updated_node
        doc.revision += 1
        doc.updated_at = datetime.now(timezone.utc).isoformat()
        self._repo.save(doc)

        self._logger.info(f"Updated node '{node_id}' in testplan '{plan_id}'")
        return updated_node

    def delete_node(
        self,
        plan_id: str,
        node_id: str,
        *,
        cascade: bool = True,
    ) -> list[str]:
        """Delete a node from the testplan.

        If cascade=True, deletes all descendant nodes.
        If cascade=False, re-parents children to the deleted node's parent.
        Returns the list of deleted node IDs.
        """
        doc = self.get_plan(plan_id)
        target = doc.nodes.get(node_id)
        if target is None:
            raise NodeNotFoundError(plan_id, node_id)

        deleted_ids: list[str] = []

        if cascade:
            # Find all descendants via BFS
            to_delete: list[str] = [node_id]
            idx = 0
            while idx < len(to_delete):
                curr = to_delete[idx]
                children = [nid for nid, n in doc.nodes.items() if n.parent_id == curr]
                to_delete.extend(children)
                idx += 1

            for nid in to_delete:
                doc.nodes.pop(nid, None)
                deleted_ids.append(nid)
        else:
            # Re-parent children to target's parent
            parent_id = target.parent_id
            for n in doc.nodes.values():
                if n.parent_id == node_id:
                    n.parent_id = parent_id
            doc.nodes.pop(node_id, None)
            deleted_ids.append(node_id)

        doc.revision += 1
        doc.updated_at = datetime.now(timezone.utc).isoformat()
        self._repo.save(doc)

        self._logger.info(
            f"Deleted {len(deleted_ids)} node(s) from testplan '{plan_id}' (cascade={cascade})"
        )
        return deleted_ids

    def move_node(
        self,
        plan_id: str,
        node_id: str,
        *,
        target_parent_id: str | None = None,
        target_order: int | None = None,
    ) -> TestPlanNode:
        """Move a node to a new parent and/or adjust sibling ordering."""
        doc = self.get_plan(plan_id)
        node = doc.nodes.get(node_id)
        if node is None:
            raise NodeNotFoundError(plan_id, node_id)

        if target_parent_id == node_id:
            raise CycleDetectedError(node_id, node_id)

        if target_parent_id is not None:
            if target_parent_id not in doc.nodes:
                raise NodeNotFoundError(plan_id, target_parent_id)

            # Cycle check: target_parent_id cannot be a descendant of node_id
            curr: str | None = target_parent_id
            while curr is not None:
                if curr == node_id:
                    raise CycleDetectedError(node_id, target_parent_id)
                parent_node = doc.nodes.get(curr)
                curr = parent_node.parent_id if parent_node else None

        # Check maximum depth under new parent
        tentative_doc = doc.model_copy(deep=True)
        tentative_doc.nodes[node_id].parent_id = target_parent_id
        depth = tentative_doc.get_node_depth(node_id)
        if depth > MAX_TREE_DEPTH:
            raise MaxDepthExceededError(node_id, depth, MAX_TREE_DEPTH)

        # Apply move
        node.parent_id = target_parent_id
        if target_order is not None:
            node.order = target_order

        doc.revision += 1
        doc.updated_at = datetime.now(timezone.utc).isoformat()
        self._repo.save(doc)

        self._logger.info(
            f"Moved node '{node_id}' to parent '{target_parent_id}' (order={node.order})"
        )
        return node

    def execute_batch(
        self,
        plan_id: str,
        operations: list[PlanOperation],
    ) -> list[str]:
        """Atomically execute a batch of operations against a testplan."""
        doc = self.get_plan(plan_id)
        audit_log: list[str] = []

        # Work on a tentative copy to guarantee atomicity
        tentative_doc = doc.model_copy(deep=True)

        for op in operations:
            if op.action == ACTION_ADD_NODE:
                if not op.node_data:
                    raise InvalidOperationError("Missing node_data for add_node", op.action)
                node_dict = dict(op.node_data)
                if "id" not in node_dict:
                    node_dict["id"] = f"node_{uuid.uuid4().hex[:8]}"
                if op.parent_id is not None:
                    node_dict["parent_id"] = op.parent_id
                node = TestPlanNode.model_validate(node_dict)
                if node.id in tentative_doc.nodes:
                    raise DuplicateNodeError(plan_id, node.id)
                if node.parent_id and node.parent_id not in tentative_doc.nodes:
                    raise NodeNotFoundError(plan_id, node.parent_id)
                tentative_doc.nodes[node.id] = node
                audit_log.append(f"Added node '{node.id}' ({node.title})")

            elif op.action == ACTION_UPDATE_NODE:
                if not op.node_id:
                    raise InvalidOperationError("Missing node_id for update_node", op.action)
                if op.node_id not in tentative_doc.nodes:
                    raise NodeNotFoundError(plan_id, op.node_id)
                updates = op.node_data or {}
                node = tentative_doc.nodes[op.node_id]
                data = node.model_dump()
                data.update({k: v for k, v in updates.items() if k != "id"})
                tentative_doc.nodes[op.node_id] = TestPlanNode.model_validate(data)
                audit_log.append(f"Updated node '{op.node_id}'")

            elif op.action == ACTION_DELETE_NODE:
                if not op.node_id:
                    raise InvalidOperationError("Missing node_id for delete_node", op.action)
                if op.node_id not in tentative_doc.nodes:
                    raise NodeNotFoundError(plan_id, op.node_id)
                # Remove target and its descendants
                to_remove = [op.node_id]
                idx = 0
                while idx < len(to_remove):
                    curr = to_remove[idx]
                    children = [nid for nid, n in tentative_doc.nodes.items() if n.parent_id == curr]
                    to_remove.extend(children)
                    idx += 1
                for nid in to_remove:
                    tentative_doc.nodes.pop(nid, None)
                audit_log.append(f"Deleted node '{op.node_id}' and {len(to_remove)-1} descendant(s)")

            elif op.action == ACTION_MOVE_NODE:
                if not op.node_id:
                    raise InvalidOperationError("Missing node_id for move_node", op.action)
                if op.node_id not in tentative_doc.nodes:
                    raise NodeNotFoundError(plan_id, op.node_id)
                if op.parent_id and op.parent_id not in tentative_doc.nodes:
                    raise NodeNotFoundError(plan_id, op.parent_id)
                node = tentative_doc.nodes[op.node_id]
                node.parent_id = op.parent_id
                if op.target_order is not None:
                    node.order = op.target_order
                audit_log.append(f"Moved node '{op.node_id}' to parent '{op.parent_id}'")
            else:
                raise InvalidOperationError(f"Unsupported action '{op.action}'", op.action)

        tentative_doc.revision += 1
        tentative_doc.updated_at = datetime.now(timezone.utc).isoformat()
        self._repo.save(tentative_doc)
        return audit_log

    def get_tree(self, plan_id: str) -> list[TestPlanNode]:
        """Retrieve the materialized hierarchical tree for a testplan."""
        doc = self.get_plan(plan_id)
        return doc.build_tree()

    def get_summary(self, plan_id: str) -> TestPlanSummary:
        """Calculate aggregated metrics and coverage statistics for a testplan."""
        doc = self.get_plan(plan_id)
        return TestPlanSummary.from_document(doc)

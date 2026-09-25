"""Handler for previewing and applying AI Assistant proposals to testplans."""

from __future__ import annotations

from testplan_service.constants import (
    ACTION_ADD_NODE,
    ACTION_DELETE_NODE,
    ACTION_MOVE_NODE,
    ACTION_UPDATE_NODE,
    VALID_PROPOSAL_ACTIONS,
)
from testplan_service.exceptions import ProposalValidationError, TestPlanNotFoundError
from testplan_service.logging import StructuredLogger
from testplan_service.models.operations import (
    ProposalApplyResult,
    ProposalArtifact,
    ProposalPreviewResult,
)
from testplan_service.service.manager import TestPlanManager


class ProposalHandler:
    """Processes, previews, and applies AI Assistant proposal batches."""

    def __init__(
        self,
        manager: TestPlanManager,
        logger: StructuredLogger | None = None,
    ) -> None:
        self._manager = manager
        self._logger = logger or StructuredLogger("proposal-handler")

    def preview(self, proposal: ProposalArtifact) -> ProposalPreviewResult:
        """Evaluate a proposal against the current testplan state without mutating it."""
        diagnostics: list[str] = []
        try:
            doc = self._manager.get_plan(proposal.document_id)
        except TestPlanNotFoundError:
            return ProposalPreviewResult(
                valid=False,
                diagnostics=[f"Target testplan '{proposal.document_id}' does not exist."],
            )

        if proposal.base_revision != doc.revision:
            diagnostics.append(
                f"Warning: Proposal base revision ({proposal.base_revision}) does not match "
                f"current testplan revision ({doc.revision})."
            )

        if not proposal.operations:
            diagnostics.append("Proposal contains no operations.")
            return ProposalPreviewResult(valid=False, diagnostics=diagnostics)

        added = 0
        modified = 0
        deleted = 0
        diff_lines: list[str] = []

        tentative_nodes = set(doc.nodes.keys())

        for idx, op in enumerate(proposal.operations):
            op_num = idx + 1
            if op.action not in VALID_PROPOSAL_ACTIONS:
                diagnostics.append(f"Operation #{op_num}: Unknown action '{op.action}'.")
                continue

            if op.action == ACTION_ADD_NODE:
                node_data = op.node_data or {}
                node_id = str(node_data.get("id") or f"proposed_node_{op_num}")
                title = node_data.get("title", "Untitled")
                kind = node_data.get("kind", "testcase")

                if op.parent_id and op.parent_id not in tentative_nodes:
                    diagnostics.append(
                        f"Operation #{op_num}: Parent '{op.parent_id}' does not exist."
                    )
                if node_id in tentative_nodes:
                    diagnostics.append(
                        f"Operation #{op_num}: Node '{node_id}' already exists in testplan."
                    )
                tentative_nodes.add(node_id)
                added += 1
                diff_lines.append(f"+ Add {kind.capitalize()}: '{title}' (id={node_id})")

            elif op.action == ACTION_UPDATE_NODE:
                if not op.node_id:
                    diagnostics.append(f"Operation #{op_num}: Missing node_id for update.")
                elif op.node_id not in tentative_nodes:
                    diagnostics.append(
                        f"Operation #{op_num}: Node '{op.node_id}' does not exist for update."
                    )
                else:
                    modified += 1
                    diff_lines.append(f"~ Update node: '{op.node_id}'")

            elif op.action == ACTION_DELETE_NODE:
                if not op.node_id:
                    diagnostics.append(f"Operation #{op_num}: Missing node_id for deletion.")
                elif op.node_id not in tentative_nodes:
                    diagnostics.append(
                        f"Operation #{op_num}: Node '{op.node_id}' does not exist for deletion."
                    )
                else:
                    deleted += 1
                    tentative_nodes.discard(op.node_id)
                    diff_lines.append(f"- Delete node: '{op.node_id}'")

            elif op.action == ACTION_MOVE_NODE:
                if not op.node_id or op.node_id not in tentative_nodes:
                    diagnostics.append(
                        f"Operation #{op_num}: Node '{op.node_id}' does not exist for move."
                    )
                elif op.parent_id and op.parent_id not in tentative_nodes:
                    diagnostics.append(
                        f"Operation #{op_num}: Target parent '{op.parent_id}' does not exist."
                    )
                else:
                    modified += 1
                    diff_lines.append(f"~ Move node '{op.node_id}' to parent '{op.parent_id}'")

        is_valid = not any(d.startswith("Operation") or "does not exist" in d for d in diagnostics)
        return ProposalPreviewResult(
            valid=is_valid,
            diagnostics=diagnostics,
            nodes_added=added,
            nodes_modified=modified,
            nodes_deleted=deleted,
            summary_diff=diff_lines,
        )

    def apply(self, proposal: ProposalArtifact) -> ProposalApplyResult:
        """Validate and atomically commit proposal operations to the testplan."""
        preview_res = self.preview(proposal)
        if not preview_res.valid:
            raise ProposalValidationError(
                f"Proposal '{proposal.proposal_id}' validation failed.",
                preview_res.diagnostics,
            )

        doc = self._manager.get_plan(proposal.document_id)
        prev_rev = doc.revision

        self._manager.execute_batch(proposal.document_id, proposal.operations)

        updated_doc = self._manager.get_plan(proposal.document_id)
        new_rev = updated_doc.revision

        self._logger.info(
            f"Applied proposal '{proposal.proposal_id}' to '{proposal.document_id}' "
            f"(rev {prev_rev} -> {new_rev})"
        )

        return ProposalApplyResult(
            applied=True,
            document_id=proposal.document_id,
            previous_revision=prev_rev,
            new_revision=new_rev,
            message=(
                f"Successfully applied {len(proposal.operations)} operation(s) from proposal "
                f"'{proposal.title}'."
            ),
            diagnostics=preview_res.diagnostics,
        )

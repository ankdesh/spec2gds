"""Builder for a high-reliability dual-clock asynchronous FIFO testplan."""

from __future__ import annotations

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


class FifoTestPlanBuilder:
    """Constructs a hierarchical testplan for an asynchronous dual-clock FIFO."""

    PLAN_ID = "dual_clock_fifo_verification_plan"
    PLAN_NAME = "Dual-Clock Asynchronous FIFO Verification Plan"
    TARGET_DESIGN = "fifo_dual_clock_512x32"
    DESCRIPTION = (
        "Verification plan targeting a 512-word by 32-bit asynchronous dual-clock FIFO queue. "
        "Focuses on multi-clock domain crossing (CDC), Gray-coded pointer synchronization, "
        "almost-full/almost-empty programmable thresholds, underflow/overflow safeguards, "
        "and formal data-ordering retention proofs."
    )

    def build(self) -> TestPlanDocument:
        doc = TestPlanDocument(
            id=self.PLAN_ID,
            name=self.PLAN_NAME,
            target_design=self.TARGET_DESIGN,
            description=self.DESCRIPTION,
            version="1.0.0",
            tags=["fifo", "memory", "cdc", "async_queue"],
        )

        nodes: list[TestPlanNode] = [
            # Group 1: CDC Synchronization
            TestPlanNode(
                id="grp_cdc_sync",
                parent_id=None,
                title="CDC Pointer Synchronization (Gray Code)",
                kind=NodeKind.GROUP,
                category=CoverageCategory.TIMING_SEQUENCING,
                description="Cross-domain clock domain crossing verification for read and write pointers.",
                order=0,
            ),
            TestPlanNode(
                id="feat_gray_pointers",
                parent_id="grp_cdc_sync",
                title="Gray Coded Pointer Encoding",
                kind=NodeKind.FEATURE,
                category=CoverageCategory.SPECIAL_PATTERNS,
                order=0,
            ),
            TestPlanNode(
                id="tc_gray_single_bit_transition",
                parent_id="feat_gray_pointers",
                title="Hamming Distance 1 Gray Pointer Transition Check",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.SPECIAL_PATTERNS,
                methodology=VerificationMethodology.CONSTRAINED_RANDOM,
                stage=VerificationStage.V1,
                priority=NodePriority.CRITICAL,
                status=NodeStatus.PASSED,
                stimulus="Increment write address pointer across all 512 states; sample Gray code output",
                expected_outcome="Successive Gray codes differ by exactly one bit for every binary increment step",
                coverage_bins=["special_patterns:gray_code:single_bit_hamming"],
                tags=["cdc", "gray_code"],
                order=0,
            ),
            TestPlanNode(
                id="sva_gray_no_glitch",
                parent_id="feat_gray_pointers",
                title="Formal Proof: Gray Vector Never Changes More Than 1 Bit Per Cycle",
                kind=NodeKind.ASSERTION,
                category=CoverageCategory.TIMING_SEQUENCING,
                methodology=VerificationMethodology.FORMAL,
                stage=VerificationStage.V2,
                priority=NodePriority.CRITICAL,
                status=NodeStatus.PASSED,
                expected_outcome="Formal solver proves bounded property: $countones(gray ^ $past(gray)) <= 1",
                coverage_bins=["timing_sequencing:formal:gray_single_bit"],
                tags=["formal", "cdc"],
                order=1,
            ),
            TestPlanNode(
                id="feat_clock_ratios",
                parent_id="grp_cdc_sync",
                title="Asynchronous Frequency Ratio Robustness",
                kind=NodeKind.FEATURE,
                category=CoverageCategory.TIMING_SEQUENCING,
                order=1,
            ),
            TestPlanNode(
                id="tc_fast_wr_slow_rd",
                parent_id="feat_clock_ratios",
                title="Fast Write (200MHz) to Slow Read (50MHz) Sweep",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.TIMING_SEQUENCING,
                methodology=VerificationMethodology.CONSTRAINED_RANDOM,
                stage=VerificationStage.V2,
                priority=NodePriority.HIGH,
                status=NodeStatus.PASSED,
                stimulus="Write bursts of 128 words at 200MHz while draining at 50MHz",
                expected_outcome="No packet loss; Full flag asserts conservatively without false empty",
                coverage_bins=["timing_sequencing:clock_ratio:fast_wr_slow_rd"],
                tags=["cdc", "frequency_sweep"],
                order=0,
            ),
            TestPlanNode(
                id="tc_slow_wr_fast_rd",
                parent_id="feat_clock_ratios",
                title="Slow Write (33MHz) to Fast Read (250MHz) Sweep",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.TIMING_SEQUENCING,
                methodology=VerificationMethodology.CONSTRAINED_RANDOM,
                stage=VerificationStage.V2,
                priority=NodePriority.HIGH,
                status=NodeStatus.IN_PROGRESS,
                stimulus="Intermittent single-word writes at 33MHz while reading constantly at 250MHz",
                expected_outcome="Empty flag deasserts and asserts cleanly without metastability glitch on rdata",
                coverage_bins=["timing_sequencing:clock_ratio:slow_wr_fast_rd"],
                tags=["cdc", "metastability"],
                order=1,
            ),

            # Group 2: Boundary Flags
            TestPlanNode(
                id="grp_boundary_flags",
                parent_id=None,
                title="Full / Empty Boundary Flag Generation",
                kind=NodeKind.GROUP,
                category=CoverageCategory.PORT_BOUNDARY,
                description="Checks for edge conditions when FIFO reaches 0 words, 511 words, and 512 words capacity.",
                order=1,
            ),
            TestPlanNode(
                id="feat_full_empty",
                parent_id="grp_boundary_flags",
                title="Pessimistic Flag Boundary Checks",
                kind=NodeKind.FEATURE,
                category=CoverageCategory.PORT_BOUNDARY,
                order=0,
            ),
            TestPlanNode(
                id="tc_capacity_512_full",
                parent_id="feat_full_empty",
                title="Fill to Max Capacity (512 Words)",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.PORT_BOUNDARY,
                methodology=VerificationMethodology.DIRECTED,
                stage=VerificationStage.V1,
                priority=NodePriority.CRITICAL,
                status=NodeStatus.PASSED,
                stimulus="Write exactly 512 sequential words without reading",
                expected_outcome="wfull asserts on 512th write; further writes ignored; memory array undamaged",
                coverage_bins=["boundary:fifo_depth:max_512"],
                tags=["fifo", "full"],
                order=0,
            ),
            TestPlanNode(
                id="tc_empty_underflow_safeguard",
                parent_id="feat_full_empty",
                title="Read from Empty Queue (Underflow Safeguard)",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.ERROR_INJECTION,
                methodology=VerificationMethodology.DIRECTED,
                stage=VerificationStage.V1,
                priority=NodePriority.CRITICAL,
                status=NodeStatus.PASSED,
                stimulus="Assert r_en=1 when rempty=1",
                expected_outcome="Read pointer does not advance; r_err error flag pulses high",
                coverage_bins=["error_injection:fifo:underflow_prevented"],
                tags=["fifo", "error", "underflow"],
                order=1,
            ),
            TestPlanNode(
                id="tc_simul_push_pop_at_full",
                parent_id="feat_full_empty",
                title="Simultaneous Write and Read at Full Boundary",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.TIMING_SEQUENCING,
                methodology=VerificationMethodology.CONSTRAINED_RANDOM,
                stage=VerificationStage.V2,
                priority=NodePriority.HIGH,
                status=NodeStatus.FAILED,
                stimulus="At 512/512 occupancy, assert both w_en=1 and r_en=1 simultaneously across clocks",
                expected_outcome="FIFO occupancy remains at 512; outgoing word popped; new incoming word stored",
                coverage_bins=["timing_sequencing:simultaneous_rw_full"],
                tags=["fifo", "corner_case"],
                order=2,
            ),

            # Group 3: Formal Verification
            TestPlanNode(
                id="grp_formal_properties",
                parent_id=None,
                title="Formal Data Integrity & Order Proofs",
                kind=NodeKind.GROUP,
                category=CoverageCategory.FUNCTIONAL_MODE,
                description="End-to-end formal correctness proofs for packet integrity and ordering retention.",
                order=2,
            ),
            TestPlanNode(
                id="sva_fifo_order_retention",
                parent_id="grp_formal_properties",
                title="Formal Proof: Strict First-In First-Out Packet Ordering",
                kind=NodeKind.ASSERTION,
                category=CoverageCategory.FUNCTIONAL_MODE,
                methodology=VerificationMethodology.FORMAL,
                stage=VerificationStage.V3,
                priority=NodePriority.CRITICAL,
                status=NodeStatus.PASSED,
                expected_outcome="Formal scoreboarding property proves popped payload sequence matches pushed sequence.",
                coverage_bins=["functional_mode:formal:fifo_order_retention"],
                tags=["formal", "ordering"],
                order=0,
            ),
            TestPlanNode(
                id="sva_async_reset_flushes",
                parent_id="grp_formal_properties",
                title="Formal Proof: Asynchronous Reset Clears All Pointers and Asserts Empty",
                kind=NodeKind.ASSERTION,
                category=CoverageCategory.RESET_BEHAVIOR,
                methodology=VerificationMethodology.FORMAL,
                stage=VerificationStage.V1,
                priority=NodePriority.CRITICAL,
                status=NodeStatus.PASSED,
                expected_outcome="Proves rempty asserts within 1 read cycle after reset deassertion.",
                coverage_bins=["reset_behavior:formal:immediate_empty"],
                tags=["formal", "reset"],
                order=1,
            ),
        ]

        for n in nodes:
            doc.nodes[n.id] = n

        return doc

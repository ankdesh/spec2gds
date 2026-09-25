"""Builder for an industry-standard UART 16550 hierarchical testplan."""

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


class UartTestPlanBuilder:
    """Constructs a comprehensive hierarchical testplan for a 16550 UART controller."""

    PLAN_ID = "uart_16550_verification_plan"
    PLAN_NAME = "UART 16550 Serial Controller Verification Plan"
    TARGET_DESIGN = "uart_16550"
    DESCRIPTION = (
        "Verification plan covering the standard National Semiconductor 16550 UART. "
        "Includes programmable baud rate generator prescalers, 16-byte TX/RX FIFOs, "
        "start/stop/parity framing compliance, noise glitch rejection, and interrupt triggers."
    )

    def build(self) -> TestPlanDocument:
        doc = TestPlanDocument(
            id=self.PLAN_ID,
            name=self.PLAN_NAME,
            target_design=self.TARGET_DESIGN,
            description=self.DESCRIPTION,
            version="2.0.0",
            tags=["uart", "serial", "protocol", "peripheral"],
        )

        nodes: list[TestPlanNode] = [
            # Group 1: Baud Rate Generator
            TestPlanNode(
                id="grp_baud_gen",
                parent_id=None,
                title="Baud Rate Generator Subsystem",
                kind=NodeKind.GROUP,
                category=CoverageCategory.TIMING_SEQUENCING,
                description="Verification of programmable 16-bit clock divisor latch (DLL, DLM) and prescaler clock outputs.",
                order=0,
            ),
            TestPlanNode(
                id="feat_baud_prescaler",
                parent_id="grp_baud_gen",
                title="Divisor Prescaler & Duty Cycle",
                kind=NodeKind.FEATURE,
                category=CoverageCategory.TIMING_SEQUENCING,
                order=0,
            ),
            TestPlanNode(
                id="tc_baud_115200",
                parent_id="feat_baud_prescaler",
                title="Standard 115200 Baud at 50MHz Clock",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.FUNCTIONAL_MODE,
                methodology=VerificationMethodology.DIRECTED,
                stage=VerificationStage.V1,
                priority=NodePriority.HIGH,
                status=NodeStatus.PASSED,
                stimulus="Set DLL=27, DLM=0 (divisor=27 for 50MHz / (16 * 115200) ≈ 27.1)",
                expected_outcome="Baud clock period measures 8.68 us +/- 1.5% jitter tolerance",
                coverage_bins=["functional_mode:baud:115200"],
                tags=["baud", "smoke"],
                order=0,
            ),
            TestPlanNode(
                id="tc_baud_divisor_min_boundary",
                parent_id="feat_baud_prescaler",
                title="Minimum Divisor Boundary (Divisor = 1)",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.PORT_BOUNDARY,
                methodology=VerificationMethodology.CONSTRAINED_RANDOM,
                stage=VerificationStage.V2,
                priority=NodePriority.CRITICAL,
                status=NodeStatus.PASSED,
                stimulus="Write DLL=0x01, DLM=0x00 with DLAB=1",
                expected_outcome="Highest possible sampling frequency (sys_clk / 16); no clock lockup",
                coverage_bins=["boundary:baud_divisor:min_1"],
                tags=["baud", "boundary"],
                order=1,
            ),
            TestPlanNode(
                id="tc_baud_divisor_max_boundary",
                parent_id="feat_baud_prescaler",
                title="Maximum Divisor Boundary (Divisor = 65535)",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.PORT_BOUNDARY,
                methodology=VerificationMethodology.CONSTRAINED_RANDOM,
                stage=VerificationStage.V2,
                priority=NodePriority.MEDIUM,
                status=NodeStatus.PLANNED,
                stimulus="Write DLL=0xFF, DLM=0xFF with DLAB=1",
                expected_outcome="Lowest possible baud rate (~47.6 baud at 50MHz); 16-bit counter rolls over cleanly",
                coverage_bins=["boundary:baud_divisor:max_65535"],
                tags=["baud", "boundary"],
                order=2,
            ),
            TestPlanNode(
                id="sva_baud_clock_period",
                parent_id="feat_baud_prescaler",
                title="Formal Check: Baud Tick Period Matches Exactly 16*Divisor Cycles",
                kind=NodeKind.ASSERTION,
                category=CoverageCategory.TIMING_SEQUENCING,
                methodology=VerificationMethodology.FORMAL,
                stage=VerificationStage.V2,
                priority=NodePriority.HIGH,
                status=NodeStatus.PASSED,
                expected_outcome="Formal induction proves counter equality at divisor terminal count.",
                coverage_bins=["timing_sequencing:formal:baud_tick_exactness"],
                tags=["formal", "baud"],
                order=3,
            ),

            # Group 2: Transmitter FSM
            TestPlanNode(
                id="grp_transmitter",
                parent_id=None,
                title="Transmitter FSM & Serializer",
                kind=NodeKind.GROUP,
                category=CoverageCategory.PROTOCOL_COMPLIANCE,
                description="Verification of shift register serialization, framing parameters, parity, and stop bit duration.",
                order=1,
            ),
            TestPlanNode(
                id="feat_tx_framing",
                parent_id="grp_transmitter",
                title="Configurable Line Control Framing (LCR)",
                kind=NodeKind.FEATURE,
                category=CoverageCategory.PROTOCOL_COMPLIANCE,
                order=0,
            ),
            TestPlanNode(
                id="tc_tx_8n1_standard",
                parent_id="feat_tx_framing",
                title="Standard 8-N-1 Serial Packet Transmission",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.PROTOCOL_COMPLIANCE,
                methodology=VerificationMethodology.DIRECTED,
                stage=VerificationStage.V1,
                priority=NodePriority.HIGH,
                status=NodeStatus.PASSED,
                stimulus="Configure 8 data bits, no parity, 1 stop bit; write byte 0xA5 to THR",
                expected_outcome="TX line asserts Start(0), serialized bits (1,0,1,0,0,1,0,1 LSB first), Stop(1)",
                coverage_bins=["protocol_compliance:tx:8n1"],
                tags=["tx", "protocol"],
                order=0,
            ),
            TestPlanNode(
                id="tc_tx_parity_odd_even",
                parent_id="feat_tx_framing",
                title="Odd and Even Parity Bit Generation",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.FUNCTIONAL_MODE,
                methodology=VerificationMethodology.CONSTRAINED_RANDOM,
                stage=VerificationStage.V2,
                priority=NodePriority.HIGH,
                status=NodeStatus.PASSED,
                stimulus="Transmit random payloads with LCR[3]=1 (parity enable) alternating LCR[4] (even/odd)",
                expected_outcome="Parity bit matches modulo-2 sum of data bits strictly",
                coverage_bins=["functional_mode:tx:parity_odd", "functional_mode:tx:parity_even"],
                tags=["tx", "parity"],
                order=1,
            ),
            TestPlanNode(
                id="tc_tx_break_control",
                parent_id="feat_tx_framing",
                title="Break Condition Assertion (LCR[6])",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.ERROR_INJECTION,
                methodology=VerificationMethodology.DIRECTED,
                stage=VerificationStage.V2,
                priority=NodePriority.MEDIUM,
                status=NodeStatus.IN_PROGRESS,
                stimulus="Set LCR[6]=1 during active transmission",
                expected_outcome="TX pin forced immediately to continuous Logic 0 (spacing state)",
                coverage_bins=["error_injection:tx:break_condition"],
                tags=["tx", "break"],
                order=2,
            ),

            # Group 3: Receiver FSM
            TestPlanNode(
                id="grp_receiver",
                parent_id=None,
                title="Receiver FSM & Sampling Engine",
                kind=NodeKind.GROUP,
                category=CoverageCategory.PROTOCOL_COMPLIANCE,
                description="Checks for start bit qualification, 16x oversampling center vote, and error flags.",
                order=2,
            ),
            TestPlanNode(
                id="feat_rx_sampling",
                parent_id="grp_receiver",
                title="16x Oversampling & Glitch Filter",
                kind=NodeKind.FEATURE,
                category=CoverageCategory.PROTOCOL_COMPLIANCE,
                order=0,
            ),
            TestPlanNode(
                id="tc_rx_false_start_glitch",
                parent_id="feat_rx_sampling",
                title="False Start Bit Glitch Filter (< 4 Baud Clocks)",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.ERROR_INJECTION,
                methodology=VerificationMethodology.CONSTRAINED_RANDOM,
                stage=VerificationStage.V2,
                priority=NodePriority.CRITICAL,
                status=NodeStatus.PASSED,
                stimulus="Inject 2-cycle low pulse on RX line during idle state",
                expected_outcome="FSM samples middle of start bit (sample 7/8/9), detects high, aborts to IDLE",
                coverage_bins=["error_injection:rx:false_start_rejected"],
                tags=["rx", "glitch"],
                order=0,
            ),
            TestPlanNode(
                id="tc_rx_framing_error",
                parent_id="feat_rx_sampling",
                title="Missing Stop Bit Framing Error Flag (LSR[3])",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.ERROR_INJECTION,
                methodology=VerificationMethodology.DIRECTED,
                stage=VerificationStage.V2,
                priority=NodePriority.HIGH,
                status=NodeStatus.FAILED,
                stimulus="Drive valid start and data bits, but hold RX at Logic 0 during Stop bit period",
                expected_outcome="LSR[3] (FE) asserts immediately; byte placed in FIFO with error tag",
                coverage_bins=["error_injection:rx:framing_error_asserted"],
                tags=["rx", "error", "framing"],
                order=1,
            ),

            # Group 4: FIFO Subsystem & Watermarks
            TestPlanNode(
                id="grp_fifo",
                parent_id=None,
                title="16-Byte TX & RX FIFO Subsystem",
                kind=NodeKind.GROUP,
                category=CoverageCategory.RESET_BEHAVIOR,
                description="FIFO buffer depth, overrun protection, watermark interrupts, and reset flush.",
                order=3,
            ),
            TestPlanNode(
                id="feat_fifo_triggers",
                parent_id="grp_fifo",
                title="FCR Programmable Trigger Interrupts",
                kind=NodeKind.FEATURE,
                category=CoverageCategory.RESET_BEHAVIOR,
                order=0,
            ),
            TestPlanNode(
                id="tc_fifo_reset_flush",
                parent_id="feat_fifo_triggers",
                title="FCR Bit 1/2 FIFO Clearance & Pointer Reset",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.RESET_BEHAVIOR,
                methodology=VerificationMethodology.DIRECTED,
                stage=VerificationStage.V1,
                priority=NodePriority.HIGH,
                status=NodeStatus.PASSED,
                stimulus="Fill RX FIFO with 10 bytes, then write FCR[1]=1 (RX FIFO Reset)",
                expected_outcome="LSR[0] (Data Ready) clears immediately; internal FIFO count resets to 0",
                coverage_bins=["reset_behavior:fifo:fcr_flush"],
                tags=["fifo", "reset"],
                order=0,
            ),
            TestPlanNode(
                id="tc_fifo_overrun_error",
                parent_id="feat_fifo_triggers",
                title="17th Byte Overflow Error (OE Flag in LSR[1])",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.PORT_BOUNDARY,
                methodology=VerificationMethodology.DIRECTED,
                stage=VerificationStage.V2,
                priority=NodePriority.CRITICAL,
                status=NodeStatus.PASSED,
                stimulus="Fill RX FIFO with 16 bytes, receive 17th byte without CPU reading RBR",
                expected_outcome="LSR[1] (Overrun Error) asserts; 16th byte retained, 17th byte discarded",
                coverage_bins=["boundary:fifo:overrun_16bytes"],
                tags=["fifo", "overrun"],
                order=1,
            ),
        ]

        for n in nodes:
            doc.nodes[n.id] = n

        return doc

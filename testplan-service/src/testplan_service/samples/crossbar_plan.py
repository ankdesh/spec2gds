"""Builder for an AXI4-Lite 1-to-4 crossbar interconnect testplan."""

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


class CrossbarTestPlanBuilder:
    """Constructs a hierarchical testplan for an AXI4-Lite crossbar interconnect."""

    PLAN_ID = "axi_lite_crossbar_verification_plan"
    PLAN_NAME = "AXI4-Lite 1x4 Crossbar Interconnect Verification Plan"
    TARGET_DESIGN = "axi_crossbar_1x4"
    DESCRIPTION = (
        "Verification plan for a 1-Master to 4-Slave AXI4-Lite bus matrix crossbar. "
        "Verifies memory map address decoding across 4 peripheral apertures, read/write "
        "handshake synchronization, slave backpressure stalls, unmapped DECERR responses, "
        "and interconnect structural connectivity."
    )

    def build(self) -> TestPlanDocument:
        doc = TestPlanDocument(
            id=self.PLAN_ID,
            name=self.PLAN_NAME,
            target_design=self.TARGET_DESIGN,
            description=self.DESCRIPTION,
            version="1.1.0",
            tags=["axi", "interconnect", "bus", "crossbar", "soc"],
        )

        nodes: list[TestPlanNode] = [
            # Group 1: Address Decoding & Steering
            TestPlanNode(
                id="grp_addr_decode",
                parent_id=None,
                title="Address Decoding & Slave Steering",
                kind=NodeKind.GROUP,
                category=CoverageCategory.STRUCTURAL_CONNECTIVITY,
                description="Verification of address window routing across 4 slave base addresses.",
                order=0,
            ),
            TestPlanNode(
                id="feat_slave_apertures",
                parent_id="grp_addr_decode",
                title="Peripheral Base Address Window Routing",
                kind=NodeKind.FEATURE,
                category=CoverageCategory.STRUCTURAL_CONNECTIVITY,
                order=0,
            ),
            TestPlanNode(
                id="tc_route_slave0_uart",
                parent_id="feat_slave_apertures",
                title="Route Address 0x1000_0000 to Slave 0 (UART)",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.STRUCTURAL_CONNECTIVITY,
                methodology=VerificationMethodology.DIRECTED,
                stage=VerificationStage.V1,
                priority=NodePriority.HIGH,
                status=NodeStatus.PASSED,
                stimulus="Master initiates read at ARADDR = 0x1000_0004",
                expected_outcome="Slave 0 ARVALID asserts; Slave 1-3 ARVALID remain low; data routed to master",
                coverage_bins=["structural_connectivity:route:slave0_uart"],
                tags=["routing", "uart"],
                order=0,
            ),
            TestPlanNode(
                id="tc_route_slave1_spi",
                parent_id="feat_slave_apertures",
                title="Route Address 0x1000_1000 to Slave 1 (SPI)",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.STRUCTURAL_CONNECTIVITY,
                methodology=VerificationMethodology.DIRECTED,
                stage=VerificationStage.V1,
                priority=NodePriority.HIGH,
                status=NodeStatus.PASSED,
                stimulus="Master initiates write at AWADDR = 0x1000_1010",
                expected_outcome="Slave 1 AWVALID asserts; transactions strictly steered to SPI target",
                coverage_bins=["structural_connectivity:route:slave1_spi"],
                tags=["routing", "spi"],
                order=1,
            ),
            TestPlanNode(
                id="tc_decode_unmapped_decerr",
                parent_id="feat_slave_apertures",
                title="Unmapped Address Range Returns DECERR (0b11)",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.ERROR_INJECTION,
                methodology=VerificationMethodology.CONSTRAINED_RANDOM,
                stage=VerificationStage.V2,
                priority=NodePriority.CRITICAL,
                status=NodeStatus.PASSED,
                stimulus="Master accesses 0xDEAD_BEEF (outside any peripheral base/mask)",
                expected_outcome="Internal default slave terminates transfer; RRESP/BRESP asserts DECERR (2'b11)",
                coverage_bins=["error_injection:axi:decerr_unmapped"],
                tags=["axi", "error", "decerr"],
                order=2,
            ),

            # Group 2: Protocol Handshakes
            TestPlanNode(
                id="grp_handshakes",
                parent_id=None,
                title="AXI4-Lite Channel Handshake Compliance",
                kind=NodeKind.GROUP,
                category=CoverageCategory.PROTOCOL_COMPLIANCE,
                description="Valid/Ready handshake protocols across Read Address, Read Data, Write Address, Write Data, and Write Response channels.",
                order=1,
            ),
            TestPlanNode(
                id="feat_read_handshake",
                parent_id="grp_handshakes",
                title="AR & R Channel Interlocking",
                kind=NodeKind.FEATURE,
                category=CoverageCategory.PROTOCOL_COMPLIANCE,
                order=0,
            ),
            TestPlanNode(
                id="tc_read_zero_waitstate",
                parent_id="feat_read_handshake",
                title="Zero-Wait-State Single-Cycle Read Burst",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.PROTOCOL_COMPLIANCE,
                methodology=VerificationMethodology.DIRECTED,
                stage=VerificationStage.V1,
                priority=NodePriority.HIGH,
                status=NodeStatus.PASSED,
                stimulus="Slave asserts ARREADY=1 and RVALID=1 concurrently with Master ARVALID=1 and RREADY=1",
                expected_outcome="Immediate single-cycle data transfer without dead clock cycles",
                coverage_bins=["protocol_compliance:read:zero_waitstate"],
                tags=["read", "throughput"],
                order=0,
            ),
            TestPlanNode(
                id="tc_read_slave_backpressure",
                parent_id="feat_read_handshake",
                title="Read Backpressure (Slave Holds ARREADY Low for 32 Cycles)",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.TIMING_SEQUENCING,
                methodology=VerificationMethodology.CONSTRAINED_RANDOM,
                stage=VerificationStage.V2,
                priority=NodePriority.HIGH,
                status=NodeStatus.IN_PROGRESS,
                stimulus="Master asserts ARVALID; Target slave delays ARREADY for 32 cycles",
                expected_outcome="Master ARVALID and ARADDR remain stable without glitch until handshake completes",
                coverage_bins=["timing_sequencing:read:backpressure_stall"],
                tags=["read", "backpressure"],
                order=1,
            ),
            TestPlanNode(
                id="feat_write_channel_order",
                parent_id="grp_handshakes",
                title="Write Address / Data Independent Arrival Order",
                kind=NodeKind.FEATURE,
                category=CoverageCategory.PROTOCOL_COMPLIANCE,
                order=1,
            ),
            TestPlanNode(
                id="tc_write_aw_before_w",
                parent_id="feat_write_channel_order",
                title="AWVALID Asserts 4 Cycles Prior to WVALID",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.TIMING_SEQUENCING,
                methodology=VerificationMethodology.DIRECTED,
                stage=VerificationStage.V2,
                priority=NodePriority.MEDIUM,
                status=NodeStatus.PASSED,
                stimulus="Drive write address phase, wait 4 cycles, drive write data phase",
                expected_outcome="Crossbar buffers address, pairs with incoming data, drives slave target cleanly",
                coverage_bins=["timing_sequencing:write:aw_before_w"],
                tags=["write", "ordering"],
                order=0,
            ),
            TestPlanNode(
                id="tc_write_w_before_aw",
                parent_id="feat_write_channel_order",
                title="WVALID Asserts 4 Cycles Prior to AWVALID",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.TIMING_SEQUENCING,
                methodology=VerificationMethodology.DIRECTED,
                stage=VerificationStage.V2,
                priority=NodePriority.MEDIUM,
                status=NodeStatus.PLANNED,
                stimulus="Drive write data phase first, wait 4 cycles, drive write address phase",
                expected_outcome="Crossbar queues data in write skid buffer, matches when address arrives",
                coverage_bins=["timing_sequencing:write:w_before_aw"],
                tags=["write", "ordering"],
                order=1,
            ),

            # Group 3: System Reset
            TestPlanNode(
                id="grp_system_reset",
                parent_id=None,
                title="Bus Reset & Quiescence Checks",
                kind=NodeKind.GROUP,
                category=CoverageCategory.RESET_BEHAVIOR,
                description="Verification that ARESETn resets all valid outputs and clears in-flight transactions.",
                order=2,
            ),
            TestPlanNode(
                id="tc_reset_deasserts_all_valides",
                parent_id="grp_system_reset",
                title="Synchronous Reset Clears All Channel VALID Signals to 0",
                kind=NodeKind.TESTCASE,
                category=CoverageCategory.RESET_BEHAVIOR,
                methodology=VerificationMethodology.DIRECTED,
                stage=VerificationStage.V0,
                priority=NodePriority.CRITICAL,
                status=NodeStatus.PASSED,
                stimulus="Assert ARESETn=0 during simultaneous multi-channel active transactions",
                expected_outcome="ARVALID, AWVALID, WVALID, RVALID, BVALID drive 0 within 1 cycle",
                coverage_bins=["reset_behavior:axi:valides_cleared"],
                tags=["reset", "safety"],
                order=0,
            ),
            TestPlanNode(
                id="sva_never_highz_when_active",
                parent_id="grp_system_reset",
                title="Formal Check: Bus Signals Never Float to High-Z While Clock Running",
                kind=NodeKind.ASSERTION,
                category=CoverageCategory.STRUCTURAL_CONNECTIVITY,
                methodology=VerificationMethodology.FORMAL,
                stage=VerificationStage.V2,
                priority=NodePriority.HIGH,
                status=NodeStatus.PASSED,
                expected_outcome="Formal proof ensures 100% deterministic binary 0/1 output across all bus lines.",
                coverage_bins=["structural_connectivity:formal:no_floating_signals"],
                tags=["formal", "electrical"],
                order=1,
            ),
        ]

        for n in nodes:
            doc.nodes[n.id] = n

        return doc

"""Phase 3 Monitoring & Control component definitions (Batch 4: 5 components).

Includes:
1. watchdog: Watchdog timer with pet/kick, sticky expiry flag, and runtime limit reduction protection
2. timeout_monitor: One-shot/retriggerable transaction timeout monitor
3. interrupt_controller: Maskable fixed-priority interrupt aggregator and index encoder
4. fault_collector: Sticky fault accumulator with first-fault index capture
5. lockstep_compare: Dual-core / lockstep bus payload and valid comparator
"""

from __future__ import annotations

from spec_catalog_service.catalog.components.models import ComponentDef, ParamDef, PortDef, TimingInfo
from spec_catalog_service.catalog.components.phase3_models import (
    FaultCollectorRef,
    InterruptControllerRef,
    LockstepCompareRef,
    TimeoutMonitorRef,
    WatchdogRef,
)


# -----------------------------------------------------------------------------
# 1. watchdog
# -----------------------------------------------------------------------------
def _validate_watchdog(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 32):
        errors.append(f"W={w} out of range [1..32]")
    return errors


WATCHDOG_DEF = ComponentDef(
    id="watchdog",
    category="integrity_control",
    phase=3,
    implementation="composite",
    summary="Watchdog timer with pet/kick, sticky expiry flag, and runtime limit reduction support",
    tags=["control", "watchdog", "timer", "safety", "monitoring"],
    contract_anchor="watchdog",
    parameters=[
        ParamDef("W", "int unsigned", "16", "Counter and limit width in bits", min_value=1, max_value=32),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("enable_i", "in", None, "Watchdog count enable"),
        PortDef("kick_i", "in", None, "Watchdog timer kick/pet (clears count)"),
        PortDef("limit_i", "in", "W-1:0", "Watchdog expiry limit threshold"),
        PortDef("clear_i", "in", None, "Synchronous clear (clears count and sticky expired)"),
        PortDef("expired_o", "out", None, "Sticky expiry flag"),
        PortDef("count_o", "out", "W-1:0", "Current watchdog timer count value"),
    ],
    timing=TimingInfo(latency="1", throughput="1", reset="rst_ni"),
    presets={
        "default": {"W": "16"},
        "w1": {"W": "1"},
        "w4": {"W": "4"},
        "w32": {"W": "32"},
    },
    limitations=[
        "clear_i wins over enable/kick and clears both count and expired flag.",
        "Disabling clears count but preserves sticky expired flag.",
        "Runtime limit reduction below current count expires on next non-kick edge without wrapping.",
    ],
    is_stateful=True,
    validate_params=_validate_watchdog,
    create_reference=lambda params: WatchdogRef(params),
    systemverilog="""    logic [W-1:0] count_q;
    logic expired_q;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            count_q <= '0;
            expired_q <= 1'b0;
        end else if (clear_i) begin
            count_q <= '0;
            expired_q <= 1'b0;
        end else if (!enable_i) begin
            count_q <= '0;
        end else if (kick_i) begin
            count_q <= '0;
        end else begin
            if (count_q >= limit_i) begin
                expired_q <= 1'b1;
            end else begin
                count_q <= count_q + 1'b1;
                if (count_q + 1'b1 >= limit_i) begin
                    expired_q <= 1'b1;
                end
            end
        end
    end

    assign count_o = count_q;
    assign expired_o = expired_q;
""",
)


# -----------------------------------------------------------------------------
# 2. timeout_monitor
# -----------------------------------------------------------------------------
def _validate_timeout_monitor(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 32):
        errors.append(f"W={w} out of range [1..32]")
    return errors


TIMEOUT_MONITOR_DEF = ComponentDef(
    id="timeout_monitor",
    category="integrity_control",
    phase=3,
    implementation="composite",
    summary="Transaction timeout monitor with cancel, complete, and restart priorities",
    tags=["control", "timeout", "timer", "transaction", "monitoring"],
    contract_anchor="timeout_monitor",
    parameters=[
        ParamDef("W", "int unsigned", "16", "Timer count and limit width in bits", min_value=1, max_value=32),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("start_i", "in", None, "Start timeout monitor and capture limit"),
        PortDef("complete_i", "in", None, "Monitored operation completion (cancels timer)"),
        PortDef("cancel_i", "in", None, "Cancel timeout monitor"),
        PortDef("limit_i", "in", "W-1:0", "Timeout limit in clock cycles"),
        PortDef("busy_o", "out", None, "Asserted while monitor is actively timing"),
        PortDef("timeout_o", "out", None, "One-cycle pulse asserted when timeout expires"),
    ],
    timing=TimingInfo(latency="1", throughput="1", reset="rst_ni"),
    presets={
        "default": {"W": "16"},
        "w1": {"W": "1"},
        "w4": {"W": "4"},
        "w32": {"W": "32"},
    },
    limitations=[
        "Priority order: cancel_i wins, then complete_i, then start_i.",
        "Start with limit_i=0 pulses timeout_o immediately (busy_o remains 0).",
        "Start while busy restarts count with newly captured limit.",
        "Completion on expiry edge wins over timeout.",
    ],
    is_stateful=True,
    validate_params=_validate_timeout_monitor,
    create_reference=lambda params: TimeoutMonitorRef(params),
    systemverilog="""    logic busy_q;
    logic timeout_q;
    logic [W-1:0] count_q;
    logic [W-1:0] cap_limit_q;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            busy_q <= 1'b0;
            timeout_q <= 1'b0;
            count_q <= '0;
            cap_limit_q <= '0;
        end else begin
            timeout_q <= 1'b0;
            if (cancel_i) begin
                busy_q <= 1'b0;
                count_q <= '0;
            end else if (complete_i) begin
                busy_q <= 1'b0;
                count_q <= '0;
            end else if (start_i) begin
                cap_limit_q <= limit_i;
                if (limit_i == '0) begin
                    timeout_q <= 1'b1;
                    busy_q <= 1'b0;
                    count_q <= '0;
                end else begin
                    busy_q <= 1'b1;
                    count_q <= '0;
                end
            end else if (busy_q) begin
                if (count_q + 1'b1 >= cap_limit_q) begin
                    timeout_q <= 1'b1;
                    busy_q <= 1'b0;
                    count_q <= '0;
                end else begin
                    count_q <= count_q + 1'b1;
                end
            end
        end
    end

    assign busy_o = busy_q;
    assign timeout_o = timeout_q;
""",
)


# -----------------------------------------------------------------------------
# 3. interrupt_controller
# -----------------------------------------------------------------------------
def _validate_interrupt_controller(params: dict[str, int]) -> list[str]:
    errors = []
    n = params.get("N", 0)
    if not (1 <= n <= 64):
        errors.append(f"N={n} out of range [1..64]")
    return errors


INTERRUPT_CONTROLLER_DEF = ComponentDef(
    id="interrupt_controller",
    category="integrity_control",
    phase=3,
    implementation="composite",
    summary="Maskable fixed-priority interrupt controller with lowest-index arbitration",
    tags=["control", "interrupt", "irq", "priority", "controller"],
    contract_anchor="interrupt_controller",
    parameters=[
        ParamDef("N", "int unsigned", "8", "Number of interrupt lines", min_value=1, max_value=64),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("irq_i", "in", "N-1:0", "Input interrupt request lines"),
        PortDef("enable_i", "in", "N-1:0", "Interrupt enable mask"),
        PortDef("clear_i", "in", "N-1:0", "Synchronous interrupt clear lines"),
        PortDef("pending_o", "out", "N-1:0", "Interrupt pending register state"),
        PortDef("irq_o", "out", None, "Aggregated interrupt request to CPU"),
        PortDef("index_o", "out", "(N > 1 ? ($clog2(N)-1) : 0):0", "Index of lowest active enabled interrupt"),
        PortDef("valid_o", "out", None, "Asserted iff index_o contains a valid interrupt index"),
    ],
    timing=TimingInfo(latency="1", throughput="1", reset="rst_ni"),
    presets={
        "default": {"N": "8"},
        "n1": {"N": "1"},
        "n3": {"N": "3"},
        "n64": {"N": "64"},
    },
    limitations=[
        "Pending update: set (irq_i) wins over clear (clear_i).",
        "Mask (enable_i) affects aggregate irq_o and index_o only, not capture in pending_o.",
        "Lowest enabled pending bit wins arbitration; index_o=0 and valid_o=0 when no eligible source.",
    ],
    is_stateful=True,
    validate_params=_validate_interrupt_controller,
    create_reference=lambda params: InterruptControllerRef(params),
    systemverilog="""    localparam int unsigned IDX_W = (N > 1) ? $clog2(N) : 1;

    logic [N-1:0] pending_q;
    wire [N-1:0] eligible = pending_q & enable_i;
    logic [IDX_W-1:0] pri_index;
    logic pri_valid;

    always_comb begin
        pri_index = '0;
        pri_valid = 1'b0;
        for (int i = N - 1; i >= 0; i = i - 1) begin
            if (eligible[i]) begin
                pri_index = IDX_W'(i);
                pri_valid = 1'b1;
            end
        end
    end

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            pending_q <= '0;
        end else begin
            pending_q <= (pending_q & ~clear_i) | irq_i;
        end
    end

    assign pending_o = pending_q;
    assign irq_o = pri_valid;
    assign valid_o = pri_valid;
    assign index_o = pri_index;
""",
)


# -----------------------------------------------------------------------------
# 4. fault_collector
# -----------------------------------------------------------------------------
def _validate_fault_collector(params: dict[str, int]) -> list[str]:
    errors = []
    n = params.get("N", 0)
    if not (1 <= n <= 64):
        errors.append(f"N={n} out of range [1..64]")
    return errors


FAULT_COLLECTOR_DEF = ComponentDef(
    id="fault_collector",
    category="integrity_control",
    phase=3,
    implementation="composite",
    summary="Sticky fault accumulator with lowest first-fault index capture and hold",
    tags=["control", "fault", "safety", "diagnostic", "first_fail"],
    contract_anchor="fault_collector",
    parameters=[
        ParamDef("N", "int unsigned", "8", "Number of fault input lines", min_value=1, max_value=64),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("fault_i", "in", "N-1:0", "Input fault detection lines"),
        PortDef("clear_i", "in", "N-1:0", "Fault sticky clear lines"),
        PortDef("sticky_o", "out", "N-1:0", "Accumulated sticky fault register"),
        PortDef("any_o", "out", None, "Asserted iff any sticky fault bit is set"),
        PortDef("first_valid_o", "out", None, "Asserted iff first_index_o is valid"),
        PortDef("first_index_o", "out", "(N > 1 ? ($clog2(N)-1) : 0):0", "Captured index of first occurred fault"),
    ],
    timing=TimingInfo(latency="1", throughput="1", reset="rst_ni"),
    presets={
        "default": {"N": "8"},
        "n1": {"N": "1"},
        "n3": {"N": "3"},
        "n64": {"N": "64"},
    },
    limitations=[
        "Sticky bits use set-wins-clear.",
        "Captures lowest fault index on first fault after no sticky bits remain.",
        "Retains first_index_o while any sticky bit remains, even if its own bit clears.",
        "Clears first_valid_o when all resulting sticky bits become zero.",
    ],
    is_stateful=True,
    validate_params=_validate_fault_collector,
    create_reference=lambda params: FaultCollectorRef(params),
    systemverilog="""    localparam int unsigned IDX_W = (N > 1) ? $clog2(N) : 1;

    logic [N-1:0] sticky_q;
    logic [IDX_W-1:0] first_index_q;
    logic first_valid_q;

    logic [IDX_W-1:0] fault_first_idx;
    always_comb begin
        fault_first_idx = '0;
        for (int i = N - 1; i >= 0; i = i - 1) begin
            if (fault_i[i]) begin
                fault_first_idx = IDX_W'(i);
            end
        end
    end

    wire [N-1:0] next_sticky = (sticky_q & ~clear_i) | fault_i;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            sticky_q <= '0;
            first_index_q <= '0;
            first_valid_q <= 1'b0;
        end else begin
            if (sticky_q == '0 && fault_i != '0) begin
                first_index_q <= fault_first_idx;
                first_valid_q <= 1'b1;
            end else if (next_sticky == '0) begin
                first_index_q <= '0;
                first_valid_q <= 1'b0;
            end
            sticky_q <= next_sticky;
        end
    end

    assign sticky_o = sticky_q;
    assign any_o = (sticky_q != '0);
    assign first_valid_o = first_valid_q;
    assign first_index_o = first_index_q;
""",
)


# -----------------------------------------------------------------------------
# 5. lockstep_compare
# -----------------------------------------------------------------------------
def _validate_lockstep_compare(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


LOCKSTEP_COMPARE_DEF = ComponentDef(
    id="lockstep_compare",
    category="integrity_control",
    phase=3,
    implementation="composite",
    summary="Dual-channel payload and valid lockstep comparison monitor with sticky flag",
    tags=["control", "lockstep", "compare", "redundancy", "safety"],
    contract_anchor="lockstep_compare",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Monitored payload data width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("valid_a_i", "in", None, "Channel A valid"),
        PortDef("data_a_i", "in", "W-1:0", "Channel A data payload"),
        PortDef("valid_b_i", "in", None, "Channel B valid"),
        PortDef("data_b_i", "in", "W-1:0", "Channel B data payload"),
        PortDef("clear_i", "in", None, "Synchronous clear of sticky mismatch flag"),
        PortDef("mismatch_o", "out", None, "Cycle-accurate registered comparison mismatch"),
        PortDef("sticky_o", "out", None, "Accumulated sticky mismatch flag"),
    ],
    timing=TimingInfo(latency="1", throughput="1", reset="rst_ni"),
    presets={
        "default": {"W": "32"},
        "w1": {"W": "1"},
        "w7": {"W": "7"},
        "w256": {"W": "256"},
    },
    limitations=[
        "Registers mismatch when valids differ or when both are valid and payloads differ.",
        "When both are invalid, payloads are ignored and mismatch is not asserted.",
        "Sticky mismatch flag: set wins over clear.",
    ],
    is_stateful=True,
    validate_params=_validate_lockstep_compare,
    create_reference=lambda params: LockstepCompareRef(params),
    systemverilog="""    logic mismatch_q;
    logic sticky_q;

    wire mismatch_comb = (valid_a_i != valid_b_i) || (valid_a_i && valid_b_i && (data_a_i != data_b_i));

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            mismatch_q <= 1'b0;
            sticky_q <= 1'b0;
        end else begin
            mismatch_q <= mismatch_comb;
            if (mismatch_comb) begin
                sticky_q <= 1'b1;
            end else if (clear_i) begin
                sticky_q <= 1'b0;
            end
        end
    end

    assign mismatch_o = mismatch_q;
    assign sticky_o = sticky_q;
""",
)

PHASE3_CONTROL_COMPONENTS: list[ComponentDef] = [
    WATCHDOG_DEF,
    TIMEOUT_MONITOR_DEF,
    INTERRUPT_CONTROLLER_DEF,
    FAULT_COLLECTOR_DEF,
    LOCKSTEP_COMPARE_DEF,
]

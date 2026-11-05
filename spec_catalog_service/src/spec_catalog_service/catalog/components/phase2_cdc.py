"""Normative Component definitions and reference models for Phase 2 CDC and Reset (8 components).

Components:
25. cdc_level_sync
26. cdc_pulse_toggle
27. cdc_pulse_handshake
28. cdc_bus_handshake
29. reset_sync
30. reset_stretcher
31. reset_sequencer
32. input_deglitch
"""

from __future__ import annotations

from typing import Any

from spec_catalog_service.catalog.components.models import ComponentDef, ParamDef, PortDef
from spec_catalog_service.catalog.schemas import TimingInfo


# -----------------------------------------------------------------------------
# 25. cdc_level_sync
# -----------------------------------------------------------------------------
def _validate_cdc_level_sync(params: dict[str, int]) -> list[str]:
    errors = []
    stages = params.get("STAGES", 0)
    rv = params.get("RESET_VALUE", 0)
    if not (2 <= stages <= 4):
        errors.append(f"STAGES={stages} out of range [2..4]")
    if rv not in (0, 1):
        errors.append(f"RESET_VALUE={rv} must be 0 or 1")
    return errors


class CdcLevelSyncRef:
    """Independent reference model for cdc_level_sync."""

    def __init__(self, params: dict[str, int]) -> None:
        self.stages = params.get("STAGES", 2)
        self.reset_val = params.get("RESET_VALUE", 0)
        self.pipe = [self.reset_val] * self.stages

    def reset(self) -> None:
        self.pipe = [self.reset_val] * self.stages

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"sync_o": self.reset_val}

        async_in = inputs.get("async_i", 0) & 1
        self.pipe.append(async_in)
        self.pipe.pop(0)

        return {"sync_o": self.pipe[0]}


CDC_LEVEL_SYNC_DEF = ComponentDef(
    id="cdc_level_sync",
    category="cdc_reset",
    version="1.0.0",
    summary="Multi-stage flip-flop synchronizer for asynchronous single-bit control levels",
    tags=["cdc", "level_sync", "synchronizer"],
    contract_anchor="cdc_level_sync",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("STAGES", "int unsigned", "2", "Number of flip-flop synchronization stages", min_value=2, max_value=4),
        ParamDef("RESET_VALUE", "int unsigned", "0", "Initial reset value (0 or 1)", min_value=0, max_value=1),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Destination clock"),
        PortDef("rst_ni", "in", None, "Destination asynchronous active-low reset"),
        PortDef("async_i", "in", None, "Asynchronous input level signal"),
        PortDef("sync_o", "out", None, "Synchronized destination level signal"),
    ],
    systemverilog="""logic [STAGES-1:0] sync_stages_q;

assign sync_o = sync_stages_q[STAGES-1];

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        sync_stages_q <= {STAGES{1'(RESET_VALUE)}};
    end else begin
        sync_stages_q <= {sync_stages_q[STAGES-2:0], async_i};
    end
end
""",
    presets={
        "default": {"STAGES": "2", "RESET_VALUE": "0"},
        "p1": {"STAGES": "2", "RESET_VALUE": "1"},
        "p2": {"STAGES": "4", "RESET_VALUE": "0"},
    },
    timing=TimingInfo(latency="STAGES", throughput="1", reset="async active-low"),
    limitations=[
        "Intended for quasi-static single-bit levels only; never synchronize multi-bit data buses through independent synchronizers.",
        "Digital simulation models ideal latency; analog metastability cannot be simulated in digital RTL.",
    ],
    validate_params=_validate_cdc_level_sync,
    create_reference=lambda p: CdcLevelSyncRef(p),
)


# -----------------------------------------------------------------------------
# 26. cdc_pulse_toggle
# -----------------------------------------------------------------------------
def _validate_cdc_pulse_toggle(params: dict[str, int]) -> list[str]:
    return []


class CdcPulseToggleRef:
    """Independent reference model for cdc_pulse_toggle."""

    def __init__(self, params: dict[str, int]) -> None:
        self.src_toggle = 0
        self.sync_pipe = [0, 0, 0]

    def reset(self) -> None:
        self.src_toggle = 0
        self.sync_pipe = [0, 0, 0]

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        src_rst_n = inputs.get("src_rst_ni", 1)
        dst_rst_n = inputs.get("dst_rst_ni", 1)
        if not (src_rst_n and dst_rst_n):
            self.reset()
            return {"pulse_o": 0}

        pulse_in = inputs.get("pulse_i", 0) & 1
        if pulse_in:
            self.src_toggle ^= 1

        self.sync_pipe.append(self.src_toggle)
        self.sync_pipe.pop(0)

        # Output pulse is XOR between stage 2 and stage 3
        pulse_o = int(self.sync_pipe[-2] ^ self.sync_pipe[-3])
        return {"pulse_o": pulse_o}


CDC_PULSE_TOGGLE_DEF = ComponentDef(
    id="cdc_pulse_toggle",
    category="cdc_reset",
    version="1.0.0",
    summary="Pulse synchronizer using toggle encoding across clock domains",
    tags=["cdc", "pulse_sync", "toggle"],
    contract_anchor="cdc_pulse_toggle",
    phase=2,
    is_stateful=True,
    parameters=[],
    ports=[
        PortDef("src_clk_i", "in", None, "Source clock"),
        PortDef("src_rst_ni", "in", None, "Source domain asynchronous active-low reset"),
        PortDef("pulse_i", "in", None, "Source pulse input"),
        PortDef("dst_clk_i", "in", None, "Destination clock"),
        PortDef("dst_rst_ni", "in", None, "Destination domain asynchronous active-low reset"),
        PortDef("pulse_o", "out", None, "Destination synchronized one-cycle pulse output"),
    ],
    systemverilog="""logic src_toggle_q;
logic dst_sync1_q, dst_sync2_q, dst_sync3_q;

always_ff @(posedge src_clk_i or negedge src_rst_ni) begin
    if (!src_rst_ni) begin
        src_toggle_q <= 1'b0;
    end else if (pulse_i) begin
        src_toggle_q <= ~src_toggle_q;
    end
end

always_ff @(posedge dst_clk_i or negedge dst_rst_ni) begin
    if (!dst_rst_ni) begin
        dst_sync1_q <= 1'b0;
        dst_sync2_q <= 1'b0;
        dst_sync3_q <= 1'b0;
        pulse_o     <= 1'b0;
    end else begin
        dst_sync1_q <= src_toggle_q;
        dst_sync2_q <= dst_sync1_q;
        dst_sync3_q <= dst_sync2_q;
        pulse_o     <= dst_sync2_q ^ dst_sync3_q;
    end
end
""",
    presets={
        "default": {},
    },
    timing=TimingInfo(latency="2-3 dst cycles", throughput="variable", reset="async active-low coordinated"),
    limitations=[
        "Consecutive source pulses must be spaced by at least 4 destination clock cycles.",
        "Unacknowledged transfer: pulses arriving too close may merge and be lost.",
    ],
    validate_params=_validate_cdc_pulse_toggle,
    create_reference=lambda p: CdcPulseToggleRef(p),
)


# -----------------------------------------------------------------------------
# 27. cdc_pulse_handshake
# -----------------------------------------------------------------------------
def _validate_cdc_pulse_handshake(params: dict[str, int]) -> list[str]:
    return []


class CdcPulseHandshakeRef:
    """Independent reference model for cdc_pulse_handshake."""

    def __init__(self, params: dict[str, int]) -> None:
        self.ready = 1
        self.overflow = 0
        self.pulse = 0
        self.in_flight = False

    def reset(self) -> None:
        self.ready = 1
        self.overflow = 0
        self.pulse = 0
        self.in_flight = False

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        src_rst_n = inputs.get("src_rst_ni", 1)
        dst_rst_n = inputs.get("dst_rst_ni", 1)
        if not (src_rst_n and dst_rst_n):
            self.reset()
            return {"ready_o": 1, "pulse_o": 0, "overflow_o": 0}

        pulse_in = inputs.get("pulse_i", 0) & 1
        overflow = 0
        pulse_out = 0

        if pulse_in:
            if self.ready:
                self.ready = 0
                self.in_flight = True
            else:
                overflow = 1

        if self.in_flight:
            pulse_out = 1
            self.in_flight = False
            self.ready = 1

        return {"ready_o": self.ready, "pulse_o": pulse_out, "overflow_o": overflow}


CDC_PULSE_HANDSHAKE_DEF = ComponentDef(
    id="cdc_pulse_handshake",
    category="cdc_reset",
    version="1.0.0",
    summary="Full request/acknowledge handshake pulse synchronizer with overflow rejection",
    tags=["cdc", "handshake", "pulse_sync"],
    contract_anchor="cdc_pulse_handshake",
    phase=2,
    is_stateful=True,
    parameters=[],
    ports=[
        PortDef("src_clk_i", "in", None, "Source clock"),
        PortDef("src_rst_ni", "in", None, "Source domain asynchronous active-low reset"),
        PortDef("pulse_i", "in", None, "Source pulse input"),
        PortDef("ready_o", "out", None, "Source domain ready for next pulse"),
        PortDef("overflow_o", "out", None, "Pulse rejected while busy error flag"),
        PortDef("dst_clk_i", "in", None, "Destination clock"),
        PortDef("dst_rst_ni", "in", None, "Destination domain asynchronous active-low reset"),
        PortDef("pulse_o", "out", None, "Destination synchronized one-cycle pulse output"),
    ],
    systemverilog="""logic src_req_q;
logic [1:0] dst_req_sync_q;
logic dst_ack_q;
logic [1:0] src_ack_sync_q;
logic busy_q;

assign ready_o = !busy_q;

// Source domain
always_ff @(posedge src_clk_i or negedge src_rst_ni) begin
    if (!src_rst_ni) begin
        src_req_q      <= 1'b0;
        src_ack_sync_q <= '0;
        busy_q         <= 1'b0;
        overflow_o     <= 1'b0;
    end else begin
        overflow_o     <= 1'b0;
        src_ack_sync_q <= {src_ack_sync_q[0], dst_ack_q};

        if (pulse_i) begin
            if (!busy_q) begin
                src_req_q <= ~src_req_q;
                busy_q    <= 1'b1;
            end else begin
                overflow_o <= 1'b1;
            end
        end else if (busy_q && (src_ack_sync_q[1] == src_req_q)) begin
            busy_q <= 1'b0;
        end
    end
end

// Destination domain
always_ff @(posedge dst_clk_i or negedge dst_rst_ni) begin
    if (!dst_rst_ni) begin
        dst_req_sync_q <= '0;
        dst_ack_q      <= 1'b0;
        pulse_o        <= 1'b0;
    end else begin
        dst_req_sync_q <= {dst_req_sync_q[0], src_req_q};
        pulse_o        <= 1'b0;

        if (dst_req_sync_q[1] != dst_ack_q) begin
            dst_ack_q <= dst_req_sync_q[1];
            pulse_o   <= 1'b1;
        end
    end
end
""",
    presets={
        "default": {},
    },
    timing=TimingInfo(latency="round-trip", throughput="variable", reset="async active-low coordinated"),
    limitations=[
        "Handshake ensures safe crossing at arbitrary source/destination frequency ratios.",
        "Input pulse while busy is dropped and signaled via overflow_o.",
    ],
    validate_params=_validate_cdc_pulse_handshake,
    create_reference=lambda p: CdcPulseHandshakeRef(p),
)


# -----------------------------------------------------------------------------
# 28. cdc_bus_handshake
# -----------------------------------------------------------------------------
def _validate_cdc_bus_handshake(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


class CdcBusHandshakeRef:
    """Independent reference model for cdc_bus_handshake."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.w_mask = (1 << self.w) - 1
        self.s_ready = 1
        self.m_valid = 0
        self.data = 0

    def reset(self) -> None:
        self.s_ready = 1
        self.m_valid = 0
        self.data = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        src_rst_n = inputs.get("src_rst_ni", 1)
        dst_rst_n = inputs.get("dst_rst_ni", 1)
        if not (src_rst_n and dst_rst_n):
            self.reset()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0) & self.w_mask
        m_ready = inputs.get("m_ready_i", 0) & 1

        if self.s_ready and s_valid:
            self.data = s_data
            self.s_ready = 0
            self.m_valid = 1

        if self.m_valid and m_ready:
            self.m_valid = 0
            self.s_ready = 1

        return {
            "s_ready_o": self.s_ready,
            "m_valid_o": self.m_valid,
            "m_data_o": self.data if self.m_valid else 0,
        }


CDC_BUS_HANDSHAKE_DEF = ComponentDef(
    id="cdc_bus_handshake",
    category="cdc_reset",
    version="1.0.0",
    summary="Bundled-data bus synchronizer with full request/acknowledge handshake flow control",
    tags=["bundled_data", "cdc", "handshake", "stream"],
    contract_anchor="cdc_bus_handshake",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Bus data width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("src_clk_i", "in", None, "Source clock"),
        PortDef("src_rst_ni", "in", None, "Source domain asynchronous active-low reset"),
        PortDef("s_valid_i", "in", None, "Source stream valid"),
        PortDef("s_data_i", "in", "W-1:0", "Source stream data"),
        PortDef("s_ready_o", "out", None, "Source stream ready"),
        PortDef("dst_clk_i", "in", None, "Destination clock"),
        PortDef("dst_rst_ni", "in", None, "Destination domain asynchronous active-low reset"),
        PortDef("m_valid_o", "out", None, "Destination stream valid"),
        PortDef("m_data_o", "out", "W-1:0", "Destination stream data"),
        PortDef("m_ready_i", "in", None, "Destination stream ready"),
    ],
    systemverilog="""logic [W-1:0] src_data_q;
logic src_req_q;
logic [1:0] src_ack_sync_q;
logic busy_q;

logic [1:0] dst_req_sync_q;
logic dst_ack_q;
logic [W-1:0] dst_data_q;
logic dst_valid_q;

assign s_ready_o = !busy_q;
assign m_valid_o = dst_valid_q;
assign m_data_o  = dst_data_q;

// Source domain
always_ff @(posedge src_clk_i or negedge src_rst_ni) begin
    if (!src_rst_ni) begin
        src_data_q     <= '0;
        src_req_q      <= 1'b0;
        src_ack_sync_q <= '0;
        busy_q         <= 1'b0;
    end else begin
        src_ack_sync_q <= {src_ack_sync_q[0], dst_ack_q};

        if (!busy_q) begin
            if (s_valid_i) begin
                src_data_q <= s_data_i;
                src_req_q  <= ~src_req_q;
                busy_q     <= 1'b1;
            end
        end else if (src_ack_sync_q[1] == src_req_q) begin
            busy_q <= 1'b0;
        end
    end
end

// Destination domain
always_ff @(posedge dst_clk_i or negedge dst_rst_ni) begin
    if (!dst_rst_ni) begin
        dst_req_sync_q <= '0;
        dst_ack_q      <= 1'b0;
        dst_data_q     <= '0;
        dst_valid_q    <= 1'b0;
    end else begin
        dst_req_sync_q <= {dst_req_sync_q[0], src_req_q};

        if (!dst_valid_q) begin
            if (dst_req_sync_q[1] != dst_ack_q) begin
                dst_data_q  <= src_data_q;
                dst_valid_q <= 1'b1;
            end
        end else if (m_ready_i) begin
            dst_valid_q <= 1'b0;
            dst_ack_q   <= dst_req_sync_q[1];
        end
    end
end
""",
    presets={
        "default": {"W": "32"},
        "p1": {"W": "1"},
        "p2": {"W": "7"},
        "p3": {"W": "256"},
    },
    timing=TimingInfo(latency="round-trip", throughput="variable", reset="async active-low coordinated"),
    limitations=[
        "Bundled data assumption: source payload remains stable throughout request/acknowledge exchange.",
        "Individual data bits must not be synchronized separately.",
    ],
    validate_params=_validate_cdc_bus_handshake,
    create_reference=lambda p: CdcBusHandshakeRef(p),
)


# -----------------------------------------------------------------------------
# 29. reset_sync
# -----------------------------------------------------------------------------
def _validate_reset_sync(params: dict[str, int]) -> list[str]:
    errors = []
    stages = params.get("STAGES", 0)
    if not (2 <= stages <= 4):
        errors.append(f"STAGES={stages} out of range [2..4]")
    return errors


class ResetSyncRef:
    """Independent reference model for reset_sync."""

    def __init__(self, params: dict[str, int]) -> None:
        self.stages = params.get("STAGES", 2)
        self.pipe = [0] * self.stages

    def reset(self) -> None:
        self.pipe = [0] * self.stages

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        async_rst_n = inputs.get("async_rst_ni", 1) & 1
        if not async_rst_n:
            self.pipe = [0] * self.stages
            return {"rst_no": 0}

        self.pipe.append(1)
        self.pipe.pop(0)
        return {"rst_no": self.pipe[0]}


RESET_SYNC_DEF = ComponentDef(
    id="reset_sync",
    category="cdc_reset",
    version="1.0.0",
    summary="Asynchronous assert, synchronous release reset synchronizer",
    tags=["cdc", "reset", "synchronous_deassertion"],
    contract_anchor="reset_sync",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("STAGES", "int unsigned", "2", "Number of flip-flop synchronization stages", min_value=2, max_value=4),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("async_rst_ni", "in", None, "Asynchronous raw active-low reset input"),
        PortDef("rst_no", "out", None, "Synchronously deasserted active-low reset output"),
    ],
    systemverilog="""logic [STAGES-1:0] sync_pipe_q;

assign rst_no = sync_pipe_q[STAGES-1];

always_ff @(posedge clk_i or negedge async_rst_ni) begin
    if (!async_rst_ni) begin
        sync_pipe_q <= '0;
    end else begin
        sync_pipe_q <= {sync_pipe_q[STAGES-2:0], 1'b1};
    end
end
""",
    presets={
        "default": {"STAGES": "2"},
        "p1": {"STAGES": "3"},
        "p2": {"STAGES": "4"},
    },
    timing=TimingInfo(latency="STAGES", throughput="1", reset="async assert, sync deassert"),
    limitations=[
        "Asserts reset output asynchronously 0 immediately upon input assertion.",
        "Releases reset high only after STAGES clock rising edges following deassertion.",
    ],
    validate_params=_validate_reset_sync,
    create_reference=lambda p: ResetSyncRef(p),
)


# -----------------------------------------------------------------------------
# 30. reset_stretcher
# -----------------------------------------------------------------------------
def _validate_reset_stretcher(params: dict[str, int]) -> list[str]:
    errors = []
    cycles = params.get("CYCLES", 0)
    if not (1 <= cycles <= 256):
        errors.append(f"CYCLES={cycles} out of range [1..256]")
    return errors


class ResetStretcherRef:
    """Independent reference model for reset_stretcher."""

    def __init__(self, params: dict[str, int]) -> None:
        self.cycles = params.get("CYCLES", 4)
        self.count = self.cycles

    def reset(self) -> None:
        self.count = self.cycles

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        async_rst_n = inputs.get("async_rst_ni", 1) & 1
        if not async_rst_n:
            self.count = self.cycles
            return {"rst_no": 0}

        if self.count > 0:
            self.count -= 1

        return {"rst_no": int(self.count == 0)}


RESET_STRETCHER_DEF = ComponentDef(
    id="reset_stretcher",
    category="cdc_reset",
    version="1.0.0",
    summary="Stretches active-low reset assertion for a minimum number of clock cycles",
    tags=["reset", "stretcher"],
    contract_anchor="reset_stretcher",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("CYCLES", "int unsigned", "4", "Number of clock cycles to hold reset asserted", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("async_rst_ni", "in", None, "Asynchronous raw active-low reset input"),
        PortDef("rst_no", "out", None, "Stretched active-low reset output"),
    ],
    systemverilog="""localparam int unsigned COUNT_W = ((CYCLES+1)<=1 ? 1 : $clog2(CYCLES+1));

logic [COUNT_W-1:0] counter_q;

assign rst_no = (counter_q == '0);

always_ff @(posedge clk_i or negedge async_rst_ni) begin
    if (!async_rst_ni) begin
        counter_q <= COUNT_W'(CYCLES);
    end else if (counter_q != '0) begin
        counter_q <= counter_q - 1'b1;
    end
end
""",
    presets={
        "default": {"CYCLES": "4"},
        "p1": {"CYCLES": "1"},
        "p2": {"CYCLES": "7"},
        "p3": {"CYCLES": "256"},
    },
    timing=TimingInfo(latency="CYCLES", throughput="1", reset="async assert, counter deassert"),
    limitations=[
        "Input deassertion must satisfy clock recovery/removal or use reset_sync upstream.",
        "Reassertion restarts the count from CYCLES.",
    ],
    validate_params=_validate_reset_stretcher,
    create_reference=lambda p: ResetStretcherRef(p),
)


# -----------------------------------------------------------------------------
# 31. reset_sequencer
# -----------------------------------------------------------------------------
def _validate_reset_sequencer(params: dict[str, int]) -> list[str]:
    errors = []
    n, gap = params.get("N", 0), params.get("GAP", 0)
    if not (2 <= n <= 8):
        errors.append(f"N={n} out of range [2..8]")
    if not (1 <= gap <= 256):
        errors.append(f"GAP={gap} out of range [1..256]")
    return errors


class ResetSequencerRef:
    """Independent reference model for reset_sequencer."""

    def __init__(self, params: dict[str, int]) -> None:
        self.n = params.get("N", 3)
        self.gap = params.get("GAP", 4)
        self.cycles = 0

    def reset(self) -> None:
        self.cycles = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        en = inputs.get("enable_i", 0) & 1

        if not rst_n or not en:
            self.cycles = 0
            return {"resets_no": 0, "done_o": 0}

        self.cycles += 1

        resets_no = 0
        for j in range(self.n):
            if self.cycles >= (j + 1) * self.gap:
                resets_no |= (1 << j)

        done = int(self.cycles >= self.n * self.gap)
        return {"resets_no": resets_no, "done_o": done}


RESET_SEQUENCER_DEF = ComponentDef(
    id="reset_sequencer",
    category="cdc_reset",
    version="1.0.0",
    summary="Sequences the staggered deassertion of N active-low reset outputs with GAP spacing",
    tags=["power_on", "reset", "sequencer"],
    contract_anchor="reset_sequencer",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("N", "int unsigned", "3", "Number of reset domains to sequence", min_value=2, max_value=8),
        ParamDef("GAP", "int unsigned", "4", "Clock cycles gap between successive releases", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Master asynchronous active-low reset"),
        PortDef("enable_i", "in", None, "Sequencer enable control"),
        PortDef("resets_no", "out", "N-1:0", "Sequenced active-low domain resets"),
        PortDef("done_o", "out", None, "All domain resets released completion flag"),
    ],
    systemverilog="""localparam int unsigned TOTAL_CYCLES = N * GAP;
localparam int unsigned COUNT_W = ((TOTAL_CYCLES+1)<=1 ? 1 : $clog2(TOTAL_CYCLES+1));

logic [COUNT_W-1:0] timer_q;

always_comb begin
    for (int unsigned j = 0; j < N; j++) begin
        resets_no[j] = (timer_q >= COUNT_W'((j + 1) * GAP));
    end
end

assign done_o = (timer_q >= COUNT_W'(TOTAL_CYCLES));

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        timer_q <= '0;
    end else if (!enable_i) begin
        timer_q <= '0;
    end else if (timer_q < COUNT_W'(TOTAL_CYCLES)) begin
        timer_q <= timer_q + 1'b1;
    end
end
""",
    presets={
        "default": {"N": "3", "GAP": "4"},
        "p1": {"N": "2", "GAP": "1"},
        "p2": {"N": "4", "GAP": "3"},
        "p3": {"N": "8", "GAP": "256"},
    },
    timing=TimingInfo(latency="N*GAP cycles", throughput="1", reset="async active-low"),
    limitations=[
        "Deasserting enable_i immediately and synchronously resets all outputs low.",
        "Outputs stay high indefinitely until enable_i is removed or rst_ni asserts.",
    ],
    validate_params=_validate_reset_sequencer,
    create_reference=lambda p: ResetSequencerRef(p),
)


# -----------------------------------------------------------------------------
# 32. input_deglitch
# -----------------------------------------------------------------------------
def _validate_input_deglitch(params: dict[str, int]) -> list[str]:
    errors = []
    stable = params.get("STABLE", 0)
    if not (1 <= stable <= 256):
        errors.append(f"STABLE={stable} out of range [1..256]")
    return errors


class InputDeglitchRef:
    """Independent reference model for input_deglitch."""

    def __init__(self, params: dict[str, int]) -> None:
        self.stable = params.get("STABLE", 4)
        self.sync1 = 0
        self.sync2 = 0
        self.count = 0
        self.level = 0
        self.rise = 0
        self.fall = 0

    def reset(self) -> None:
        self.sync1 = 0
        self.sync2 = 0
        self.count = 0
        self.level = 0
        self.rise = 0
        self.fall = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"level_o": 0, "rise_o": 0, "fall_o": 0}

        async_in = inputs.get("async_i", 0) & 1

        # Synchronize: in RTL non-blocking assignment, sync2_q is pre-edge
        curr_sync2 = self.sync2
        self.sync2 = self.sync1
        self.sync1 = async_in

        self.rise = 0
        self.fall = 0

        if curr_sync2 != self.level:
            self.count += 1
            if self.count >= self.stable:
                if curr_sync2 == 1:
                    self.rise = 1
                else:
                    self.fall = 1
                self.level = curr_sync2
                self.count = 0
        else:
            self.count = 0

        return {"level_o": self.level, "rise_o": self.rise, "fall_o": self.fall}


INPUT_DEGLITCH_DEF = ComponentDef(
    id="input_deglitch",
    category="cdc_reset",
    version="1.0.0",
    summary="Input synchronizer and deglitch filter requiring STABLE consecutive samples to transition",
    tags=["cdc", "deglitch", "filter", "synchronizer"],
    contract_anchor="input_deglitch",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("STABLE", "int unsigned", "4", "Number of consecutive identical clock samples required", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("async_i", "in", None, "Asynchronous input with potential glitches"),
        PortDef("level_o", "out", None, "Filtered stable output level"),
        PortDef("rise_o", "out", None, "Single-cycle pulse on rising transition"),
        PortDef("fall_o", "out", None, "Single-cycle pulse on falling transition"),
    ],
    systemverilog="""localparam int unsigned COUNT_W = ((STABLE+1)<=1 ? 1 : $clog2(STABLE+1));

logic sync1_q, sync2_q;
logic [COUNT_W-1:0] count_q;
logic level_q;

assign level_o = level_q;

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        sync1_q <= 1'b0;
        sync2_q <= 1'b0;
        count_q <= '0;
        level_q <= 1'b0;
        rise_o  <= 1'b0;
        fall_o  <= 1'b0;
    end else begin
        sync1_q <= async_i;
        sync2_q <= sync1_q;
        rise_o  <= 1'b0;
        fall_o  <= 1'b0;

        if (sync2_q != level_q) begin
            if (count_q + 1'b1 >= COUNT_W'(STABLE)) begin
                level_q <= sync2_q;
                rise_o  <= (sync2_q == 1'b1);
                fall_o  <= (sync2_q == 1'b0);
                count_q <= '0;
            end else begin
                count_q <= count_q + 1'b1;
            end
        end else begin
            count_q <= '0;
        end
    end
end
""",
    presets={
        "default": {"STABLE": "4"},
        "p1": {"STABLE": "1"},
        "p2": {"STABLE": "7"},
        "p3": {"STABLE": "256"},
    },
    timing=TimingInfo(latency="2 + STABLE", throughput="1", reset="async active-low"),
    limitations=[
        "Requires STABLE consecutive clock cycles of new value to filter subthreshold noise glitches.",
        "Generates registered one-cycle rise_o and fall_o pulses on accepted transitions.",
    ],
    validate_params=_validate_input_deglitch,
    create_reference=lambda p: InputDeglitchRef(p),
)


PHASE2_CDC_COMPONENTS: list[ComponentDef] = [
    CDC_LEVEL_SYNC_DEF,
    CDC_PULSE_TOGGLE_DEF,
    CDC_PULSE_HANDSHAKE_DEF,
    CDC_BUS_HANDSHAKE_DEF,
    RESET_SYNC_DEF,
    RESET_STRETCHER_DEF,
    RESET_SEQUENCER_DEF,
    INPUT_DEGLITCH_DEF,
]

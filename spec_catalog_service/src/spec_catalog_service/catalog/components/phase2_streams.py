"""Normative Component definitions and reference models for Phase 2 Streams (12 components).

Components:
13. stream_register
14. stream_skid_buffer
15. stream_spill_buffer
16. stream_half_buffer
17. stream_mux
18. stream_demux
19. stream_fork
20. stream_join
21. stream_upsizer
22. stream_downsizer
23. stream_credit_adapter
24. stream_rate_limiter
"""

from __future__ import annotations

from typing import Any

from spec_catalog_service.catalog.components.models import ComponentDef, ParamDef, PortDef
from spec_catalog_service.catalog.schemas import TimingInfo


# -----------------------------------------------------------------------------
# 13. stream_register
# -----------------------------------------------------------------------------
def _validate_stream_register(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


class StreamRegisterRef:
    """Independent reference model for stream_register."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.w_mask = (1 << self.w) - 1
        self.data = 0
        self.valid = 0

    def reset(self) -> None:
        self.data = 0
        self.valid = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0) & self.w_mask
        m_ready = inputs.get("m_ready_i", 0) & 1

        s_ready = int((not self.valid) or m_ready)

        if s_ready:
            self.valid = s_valid
            if s_valid:
                self.data = s_data

        next_ready = int((not self.valid) or m_ready)
        return {"s_ready_o": next_ready, "m_valid_o": self.valid, "m_data_o": self.data}


STREAM_REGISTER_DEF = ComponentDef(
    id="stream_register",
    category="streams",
    version="1.0.0",
    summary="Elastic stream register providing full pipelining without combinational fall-through",
    tags=["pipeline", "register", "stream"],
    contract_anchor="stream_register",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Stream payload width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("s_valid_i", "in", None, "Input stream valid"),
        PortDef("s_data_i", "in", "W-1:0", "Input stream data"),
        PortDef("s_ready_o", "out", None, "Input stream ready"),
        PortDef("m_valid_o", "out", None, "Output stream valid"),
        PortDef("m_data_o", "out", "W-1:0", "Output stream data"),
        PortDef("m_ready_i", "in", None, "Output stream ready"),
    ],
    systemverilog="""assign s_ready_o = !m_valid_o || m_ready_i;

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        m_valid_o <= 1'b0;
        m_data_o  <= '0;
    end else if (s_ready_o) begin
        m_valid_o <= s_valid_i;
        if (s_valid_i) begin
            m_data_o <= s_data_i;
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
    timing=TimingInfo(latency="1", throughput="1", reset="async active-low"),
    limitations=[
        "Elastic output register; latency 1 cycle.",
        "Simultaneous pop and push replaces stored word.",
    ],
    validate_params=_validate_stream_register,
    create_reference=lambda p: StreamRegisterRef(p),
)


# -----------------------------------------------------------------------------
# 14. stream_skid_buffer
# -----------------------------------------------------------------------------
def _validate_stream_skid_buffer(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


class StreamSkidBufferRef:
    """Independent reference model for stream_skid_buffer."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.w_mask = (1 << self.w) - 1
        self.queue: list[int] = []

    def reset(self) -> None:
        self.queue.clear()

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.queue.clear()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0) & self.w_mask
        m_ready = inputs.get("m_ready_i", 0) & 1

        s_ready = int(len(self.queue) < 2)
        m_valid = int(len(self.queue) > 0)

        push = bool(s_valid and s_ready)
        pop = bool(m_valid and m_ready)

        if pop and self.queue:
            self.queue.pop(0)
        if push:
            self.queue.append(s_data)

        next_ready = int(len(self.queue) < 2)
        next_valid = int(len(self.queue) > 0)
        next_data = self.queue[0] if self.queue else 0

        return {"s_ready_o": next_ready, "m_valid_o": next_valid, "m_data_o": next_data}


STREAM_SKID_BUFFER_DEF = ComponentDef(
    id="stream_skid_buffer",
    category="streams",
    version="1.0.0",
    summary="Two-entry skid buffer decoupling upstream ready from downstream ready",
    tags=["backpressure", "decoupling", "skid_buffer", "stream"],
    contract_anchor="stream_skid_buffer",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Stream payload width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("s_valid_i", "in", None, "Input stream valid"),
        PortDef("s_data_i", "in", "W-1:0", "Input stream data"),
        PortDef("s_ready_o", "out", None, "Input stream ready (registered occupancy < 2)"),
        PortDef("m_valid_o", "out", None, "Output stream valid"),
        PortDef("m_data_o", "out", "W-1:0", "Output stream data"),
        PortDef("m_ready_i", "in", None, "Output stream ready"),
    ],
    systemverilog="""logic [W-1:0] head_q;
logic [W-1:0] skid_q;
logic [1:0] count_q;

assign s_ready_o = (count_q < 2'd2);
assign m_valid_o = (count_q > 2'd0);
assign m_data_o  = (count_q > 2'd0) ? head_q : '0;

wire push = s_valid_i && s_ready_o;
wire pop  = m_valid_o && m_ready_i;

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        head_q  <= '0;
        skid_q  <= '0;
        count_q <= '0;
    end else begin
        case ({push, pop})
            2'b10: begin // Push only
                if (count_q == 2'd0) begin
                    head_q <= s_data_i;
                end else begin
                    skid_q <= s_data_i;
                end
                count_q <= count_q + 1'b1;
            end
            2'b01: begin // Pop only
                head_q  <= skid_q;
                count_q <= count_q - 1'b1;
            end
            2'b11: begin // Simultaneous push and pop
                if (count_q == 2'd1) begin
                    head_q <= s_data_i;
                end else begin // count == 2
                    head_q <= skid_q;
                    skid_q <= s_data_i;
                end
            end
            default: ;
        endcase
    end
end
""",
    presets={
        "default": {"W": "32"},
        "p1": {"W": "1"},
        "p2": {"W": "7"},
        "p3": {"W": "256"},
    },
    timing=TimingInfo(latency="1", throughput="1", reset="async active-low"),
    limitations=[
        "Input ready depends strictly on registered occupancy (<2); breaks combinational ready loop.",
        "Draining a full buffer creates a one-cycle input bubble.",
    ],
    validate_params=_validate_stream_skid_buffer,
    create_reference=lambda p: StreamSkidBufferRef(p),
)


# -----------------------------------------------------------------------------
# 15. stream_spill_buffer
# -----------------------------------------------------------------------------
def _validate_stream_spill_buffer(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


class StreamSpillBufferRef:
    """Independent reference model for stream_spill_buffer."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.w_mask = (1 << self.w) - 1
        self.stored = 0
        self.has_stored = False

    def reset(self) -> None:
        self.stored = 0
        self.has_stored = False

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0) & self.w_mask
        m_ready = inputs.get("m_ready_i", 0) & 1

        if not self.has_stored:
            # Fall-through mode: if downstream stalls, store word
            if s_valid and not m_ready:
                self.stored = s_data
                self.has_stored = True
        else:
            # Occupied: output comes from stored word; ready=m_ready
            if m_ready:
                if s_valid:
                    self.stored = s_data
                    self.has_stored = True
                else:
                    self.has_stored = False

        if not self.has_stored:
            next_ready = 1
            next_valid = s_valid
            next_data = s_data if s_valid else 0
        else:
            next_ready = m_ready
            next_valid = 1
            next_data = self.stored

        return {"s_ready_o": next_ready, "m_valid_o": next_valid, "m_data_o": next_data}


STREAM_SPILL_BUFFER_DEF = ComponentDef(
    id="stream_spill_buffer",
    category="streams",
    version="1.0.0",
    summary="One-word fall-through spill buffer with zero-latency forward path",
    tags=["fallthrough", "spill_buffer", "stream"],
    contract_anchor="stream_spill_buffer",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Stream payload width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("s_valid_i", "in", None, "Input stream valid"),
        PortDef("s_data_i", "in", "W-1:0", "Input stream data"),
        PortDef("s_ready_o", "out", None, "Input stream ready"),
        PortDef("m_valid_o", "out", None, "Output stream valid"),
        PortDef("m_data_o", "out", "W-1:0", "Output stream data"),
        PortDef("m_ready_i", "in", None, "Output stream ready"),
    ],
    systemverilog="""logic [W-1:0] stored_q;
logic has_stored_q;

assign s_ready_o = !has_stored_q || m_ready_i;
assign m_valid_o = has_stored_q ? 1'b1 : s_valid_i;
assign m_data_o  = has_stored_q ? stored_q : (s_valid_i ? s_data_i : '0);

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        stored_q     <= '0;
        has_stored_q <= 1'b0;
    end else begin
        if (!has_stored_q) begin
            if (s_valid_i && !m_ready_i) begin
                stored_q     <= s_data_i;
                has_stored_q <= 1'b1;
            end
        end else if (m_ready_i) begin
            if (s_valid_i) begin
                stored_q     <= s_data_i;
                has_stored_q <= 1'b1;
            end else begin
                has_stored_q <= 1'b0;
            end
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
    timing=TimingInfo(latency="0", throughput="1", reset="async active-low"),
    limitations=[
        "Latency 0 when empty; captures incoming word only if downstream stalls.",
        "When full, s_ready_o tracks m_ready_i to allow simultaneous replacement.",
    ],
    validate_params=_validate_stream_spill_buffer,
    create_reference=lambda p: StreamSpillBufferRef(p),
)


# -----------------------------------------------------------------------------
# 16. stream_half_buffer
# -----------------------------------------------------------------------------
def _validate_stream_half_buffer(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


class StreamHalfBufferRef:
    """Independent reference model for stream_half_buffer."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.w_mask = (1 << self.w) - 1
        self.data = 0
        self.full = False

    def reset(self) -> None:
        self.data = 0
        self.full = False

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0) & self.w_mask
        m_ready = inputs.get("m_ready_i", 0) & 1

        if not self.full:
            if s_valid:
                self.data = s_data
                self.full = True
        else:
            if m_ready:
                self.full = False

        next_ready = int(not self.full)
        next_valid = int(self.full)
        next_data = self.data if self.full else 0

        return {"s_ready_o": next_ready, "m_valid_o": next_valid, "m_data_o": next_data}


STREAM_HALF_BUFFER_DEF = ComponentDef(
    id="stream_half_buffer",
    category="streams",
    version="1.0.0",
    summary="Half-throughput single-slot buffer preventing simultaneous push/pop replacement",
    tags=["half_buffer", "stream"],
    contract_anchor="stream_half_buffer",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Stream payload width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("s_valid_i", "in", None, "Input stream valid"),
        PortDef("s_data_i", "in", "W-1:0", "Input stream data"),
        PortDef("s_ready_o", "out", None, "Input stream ready"),
        PortDef("m_valid_o", "out", None, "Output stream valid"),
        PortDef("m_data_o", "out", "W-1:0", "Output stream data"),
        PortDef("m_ready_i", "in", None, "Output stream ready"),
    ],
    systemverilog="""logic [W-1:0] data_q;
logic full_q;

assign s_ready_o = !full_q;
assign m_valid_o = full_q;
assign m_data_o  = full_q ? data_q : '0;

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        data_q <= '0;
        full_q <= 1'b0;
    end else begin
        if (!full_q) begin
            if (s_valid_i) begin
                data_q <= s_data_i;
                full_q <= 1'b1;
            end
        end else if (m_ready_i) begin
            full_q <= 1'b0;
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
    timing=TimingInfo(latency="1", throughput="0.5", reset="async active-low"),
    limitations=[
        "Maximum throughput is one word per two clock cycles.",
        "No simultaneous replacement: input accepts new word no earlier than edge after output transfer.",
    ],
    validate_params=_validate_stream_half_buffer,
    create_reference=lambda p: StreamHalfBufferRef(p),
)


# -----------------------------------------------------------------------------
# 17. stream_mux
# -----------------------------------------------------------------------------
def _validate_stream_mux(params: dict[str, int]) -> list[str]:
    errors = []
    w, n = params.get("W", 0), params.get("N", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (2 <= n <= 16):
        errors.append(f"N={n} out of range [2..16]")
    return errors


class StreamMuxRef:
    """Independent reference model for stream_mux."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.n = params.get("N", 4)
        self.w_mask = (1 << self.w) - 1
        self.stalled = False
        self.latched_sel = 0

    def reset(self) -> None:
        self.stalled = False
        self.latched_sel = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": 0, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0)
        s_data = inputs.get("s_data_i", 0)
        sel = inputs.get("sel_i", 0)
        m_ready = inputs.get("m_ready_i", 0) & 1

        active_sel = self.latched_sel if self.stalled else sel

        if active_sel < self.n:
            lane_valid = (s_valid >> active_sel) & 1
            lane_data = (s_data >> (active_sel * self.w)) & self.w_mask
            m_valid = lane_valid
            m_data = lane_data if lane_valid else 0
            s_ready = (1 << active_sel) if m_ready else 0
        else:
            m_valid = 0
            m_data = 0
            s_ready = 0

        # Latch selection state transition on clock edge
        if m_valid and not m_ready:
            self.stalled = True
            self.latched_sel = active_sel
        else:
            self.stalled = False

        return {"s_ready_o": s_ready, "m_valid_o": m_valid, "m_data_o": m_data}


STREAM_MUX_DEF = ComponentDef(
    id="stream_mux",
    category="streams",
    version="1.0.0",
    summary="N-to-1 stream multiplexer with stall-locking lane selection",
    tags=["multiplexer", "mux", "stream"],
    contract_anchor="stream_mux",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Stream payload width in bits", min_value=1, max_value=256),
        ParamDef("N", "int unsigned", "4", "Number of input stream lanes", min_value=2, max_value=16),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("s_valid_i", "in", "N-1:0", "Input stream valid signals"),
        PortDef("s_data_i", "in", "(N*W)-1:0", "Packed input stream payloads"),
        PortDef("sel_i", "in", "(((N)<=1 ? 1 : $clog2(N)) - 1):0", "Lane select input"),
        PortDef("m_ready_i", "in", None, "Output stream ready"),
        PortDef("s_ready_o", "out", "N-1:0", "Input stream ready signals"),
        PortDef("m_valid_o", "out", None, "Output stream valid"),
        PortDef("m_data_o", "out", "W-1:0", "Selected output payload"),
    ],
    systemverilog="""localparam int unsigned SEL_W = ((N)<=1 ? 1 : $clog2(N));

logic stalled_q;
logic [SEL_W-1:0] latched_sel_q;

wire [SEL_W-1:0] active_sel = stalled_q ? latched_sel_q : sel_i;
wire sel_valid = (32'(active_sel) < N);

assign m_valid_o = sel_valid ? s_valid_i[active_sel] : 1'b0;
assign m_data_o  = (sel_valid && s_valid_i[active_sel]) ? s_data_i[active_sel*W +: W] : '0;

always_comb begin
    s_ready_o = '0;
    if (sel_valid && m_ready_i) begin
        s_ready_o[active_sel] = 1'b1;
    end
end

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        stalled_q     <= 1'b0;
        latched_sel_q <= '0;
    end else begin
        if (m_valid_o && !m_ready_i) begin
            stalled_q     <= 1'b1;
            latched_sel_q <= active_sel;
        end else if (m_valid_o && m_ready_i) begin
            stalled_q <= 1'b0;
        end else begin
            stalled_q <= 1'b0;
        end
    end
end
""",
    presets={
        "default": {"W": "32", "N": "4"},
        "p1": {"W": "1", "N": "2"},
        "p2": {"W": "7", "N": "3"},
        "p3": {"W": "64", "N": "16"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="async active-low"),
    limitations=[
        "Selection is latched during a downstream stall to guarantee payload stability.",
        "Invalid selection stalls all input lanes and deasserts output valid.",
    ],
    validate_params=_validate_stream_mux,
    create_reference=lambda p: StreamMuxRef(p),
)


# -----------------------------------------------------------------------------
# 18. stream_demux
# -----------------------------------------------------------------------------
def _validate_stream_demux(params: dict[str, int]) -> list[str]:
    errors = []
    w, n = params.get("W", 0), params.get("N", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (2 <= n <= 16):
        errors.append(f"N={n} out of range [2..16]")
    return errors


class StreamDemuxRef:
    """Independent reference model for stream_demux."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.n = params.get("N", 4)
        self.w_mask = (1 << self.w) - 1
        self.stalled = False
        self.latched_sel = 0

    def reset(self) -> None:
        self.stalled = False
        self.latched_sel = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": 0, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0) & self.w_mask
        sel = inputs.get("sel_i", 0)
        m_ready = inputs.get("m_ready_i", 0)

        active_sel = self.latched_sel if self.stalled else sel

        if active_sel < self.n:
            s_ready = (m_ready >> active_sel) & 1
            m_valid = (1 << active_sel) if s_valid else 0
        else:
            s_ready = 0
            m_valid = 0

        # Data replicated to all output lanes
        m_data = 0
        if s_valid:
            for j in range(self.n):
                m_data |= s_data << (j * self.w)

        if s_valid and (active_sel < self.n) and not ((m_ready >> active_sel) & 1):
            self.stalled = True
            self.latched_sel = active_sel
        elif (m_ready >> active_sel) & 1:
            self.stalled = False

        return {"s_ready_o": s_ready, "m_valid_o": m_valid, "m_data_o": m_data}


STREAM_DEMUX_DEF = ComponentDef(
    id="stream_demux",
    category="streams",
    version="1.0.0",
    summary="1-to-N stream demultiplexer with stall-locking routing",
    tags=["demultiplexer", "demux", "stream"],
    contract_anchor="stream_demux",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Stream payload width in bits", min_value=1, max_value=256),
        ParamDef("N", "int unsigned", "4", "Number of output stream lanes", min_value=2, max_value=16),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("s_valid_i", "in", None, "Input stream valid"),
        PortDef("s_data_i", "in", "W-1:0", "Input stream data"),
        PortDef("sel_i", "in", "(((N)<=1 ? 1 : $clog2(N)) - 1):0", "Lane select input"),
        PortDef("m_ready_i", "in", "N-1:0", "Output stream ready signals"),
        PortDef("s_ready_o", "out", None, "Input stream ready"),
        PortDef("m_valid_o", "out", "N-1:0", "Output stream valid signals"),
        PortDef("m_data_o", "out", "(N*W)-1:0", "Replicated output stream payloads"),
    ],
    systemverilog="""localparam int unsigned SEL_W = ((N)<=1 ? 1 : $clog2(N));

logic stalled_q;
logic [SEL_W-1:0] latched_sel_q;

wire [SEL_W-1:0] active_sel = stalled_q ? latched_sel_q : sel_i;
wire sel_valid = (32'(active_sel) < N);

assign s_ready_o = sel_valid ? m_ready_i[active_sel] : 1'b0;

always_comb begin
    m_valid_o = '0;
    if (sel_valid && s_valid_i) begin
        m_valid_o[active_sel] = 1'b1;
    end
    for (int unsigned j = 0; j < N; j++) begin
        m_data_o[j*W +: W] = s_valid_i ? s_data_i : '0;
    end
end

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        stalled_q     <= 1'b0;
        latched_sel_q <= '0;
    end else begin
        if (s_valid_i && sel_valid && !m_ready_i[active_sel]) begin
            stalled_q     <= 1'b1;
            latched_sel_q <= active_sel;
        end else if (m_ready_i[active_sel]) begin
            stalled_q <= 1'b0;
        end
    end
end
""",
    presets={
        "default": {"W": "32", "N": "4"},
        "p1": {"W": "1", "N": "2"},
        "p2": {"W": "7", "N": "3"},
        "p3": {"W": "64", "N": "16"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="async active-low"),
    limitations=[
        "Selection is latched during a downstream stall to guarantee valid destination stability.",
        "Input payload is replicated to all output data lanes, but valid is asserted only on the selected lane.",
    ],
    validate_params=_validate_stream_demux,
    create_reference=lambda p: StreamDemuxRef(p),
)


# -----------------------------------------------------------------------------
# 19. stream_fork
# -----------------------------------------------------------------------------
def _validate_stream_fork(params: dict[str, int]) -> list[str]:
    errors = []
    w, n = params.get("W", 0), params.get("N", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (2 <= n <= 8):
        errors.append(f"N={n} out of range [2..8]")
    return errors


class StreamForkRef:
    """Independent reference model for stream_fork."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.n = params.get("N", 2)
        self.w_mask = (1 << self.w) - 1
        self.pending = 0
        self.held_data = 0

    def reset(self) -> None:
        self.pending = 0
        self.held_data = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0) & self.w_mask
        m_ready = inputs.get("m_ready_i", 0)

        if self.pending == 0:
            if s_valid:
                self.held_data = s_data
                self.pending = (1 << self.n) - 1
        else:
            for j in range(self.n):
                if (m_ready >> j) & 1:
                    self.pending &= ~(1 << j)

        next_ready = int(self.pending == 0)
        next_valid = self.pending
        next_data = 0
        for j in range(self.n):
            next_data |= self.held_data << (j * self.w)

        return {"s_ready_o": next_ready, "m_valid_o": next_valid, "m_data_o": next_data}


STREAM_FORK_DEF = ComponentDef(
    id="stream_fork",
    category="streams",
    version="1.0.0",
    summary="1-to-N stream replicating fork with per-sink pending completion tracking",
    tags=["broadcast", "fork", "stream"],
    contract_anchor="stream_fork",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Stream payload width in bits", min_value=1, max_value=256),
        ParamDef("N", "int unsigned", "2", "Number of output stream sinks", min_value=2, max_value=8),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("s_valid_i", "in", None, "Input stream valid"),
        PortDef("s_data_i", "in", "W-1:0", "Input stream data"),
        PortDef("m_ready_i", "in", "N-1:0", "Output stream ready signals"),
        PortDef("s_ready_o", "out", None, "Input stream ready (empty and ready to capture)"),
        PortDef("m_valid_o", "out", "N-1:0", "Output stream valid signals"),
        PortDef("m_data_o", "out", "(N*W)-1:0", "Replicated output stream payloads"),
    ],
    systemverilog="""logic [W-1:0] held_data_q;
logic [N-1:0] pending_q;

assign s_ready_o = (pending_q == '0);
assign m_valid_o = pending_q;

always_comb begin
    for (int unsigned j = 0; j < N; j++) begin
        m_data_o[j*W +: W] = held_data_q;
    end
end

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        held_data_q <= '0;
        pending_q   <= '0;
    end else begin
        if (pending_q == '0) begin
            if (s_valid_i) begin
                held_data_q <= s_data_i;
                pending_q   <= {N{1'b1}};
            end
        end else begin
            for (int unsigned j = 0; j < N; j++) begin
                if (pending_q[j] && m_ready_i[j]) begin
                    pending_q[j] <= 1'b0;
                end
            end
        end
    end
end
""",
    presets={
        "default": {"W": "32", "N": "2"},
        "p1": {"W": "1", "N": "2"},
        "p2": {"W": "7", "N": "3"},
        "p3": {"W": "64", "N": "8"},
    },
    timing=TimingInfo(latency="1", throughput="variable", reset="async active-low"),
    limitations=[
        "Captures 1 word into register when empty; delivers exactly once to each sink.",
        "Input ready asserts only when all sinks have received the word (no same-edge replacement).",
    ],
    validate_params=_validate_stream_fork,
    create_reference=lambda p: StreamForkRef(p),
)


# -----------------------------------------------------------------------------
# 20. stream_join
# -----------------------------------------------------------------------------
def _validate_stream_join(params: dict[str, int]) -> list[str]:
    errors = []
    w, n = params.get("W", 0), params.get("N", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (2 <= n <= 8):
        errors.append(f"N={n} out of range [2..8]")
    return errors


class StreamJoinRef:
    """Independent reference model for stream_join."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.n = params.get("N", 2)
        self.w_mask = (1 << self.w) - 1
        self.full = [False] * self.n
        self.slots = [0] * self.n

    def reset(self) -> None:
        self.full = [False] * self.n
        self.slots = [0] * self.n

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": (1 << self.n) - 1, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0)
        s_data = inputs.get("s_data_i", 0)
        m_ready = inputs.get("m_ready_i", 0) & 1

        all_full = all(self.full)

        if all_full and m_ready:
            self.full = [False] * self.n
        else:
            for j in range(self.n):
                if not self.full[j]:
                    if (s_valid >> j) & 1:
                        self.slots[j] = (s_data >> (j * self.w)) & self.w_mask
                        self.full[j] = True

        next_ready = 0
        for j in range(self.n):
            if not self.full[j]:
                next_ready |= (1 << j)

        next_all_full = all(self.full)
        next_valid = int(next_all_full)
        next_data = 0
        if next_all_full:
            for j in range(self.n):
                next_data |= self.slots[j] << (j * self.w)

        return {"s_ready_o": next_ready, "m_valid_o": next_valid, "m_data_o": next_data}


STREAM_JOIN_DEF = ComponentDef(
    id="stream_join",
    category="streams",
    version="1.0.0",
    summary="N-to-1 stream join synchronizing multiple lanes into a concatenated word",
    tags=["join", "stream", "synchronization"],
    contract_anchor="stream_join",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Lane payload width in bits", min_value=1, max_value=256),
        ParamDef("N", "int unsigned", "2", "Number of input stream lanes", min_value=2, max_value=8),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("s_valid_i", "in", "N-1:0", "Input stream valid signals"),
        PortDef("s_data_i", "in", "(N*W)-1:0", "Packed input stream payloads"),
        PortDef("m_ready_i", "in", None, "Output stream ready"),
        PortDef("s_ready_o", "out", "N-1:0", "Input stream ready signals"),
        PortDef("m_valid_o", "out", None, "Output stream valid (all lanes present)"),
        PortDef("m_data_o", "out", "(N*W)-1:0", "Joined output stream payload"),
    ],
    systemverilog="""logic [W-1:0] slots_q [0:N-1];
logic [N-1:0] full_q;

always_comb begin
    for (int unsigned j = 0; j < N; j++) begin
        s_ready_o[j] = !full_q[j];
        m_data_o[j*W +: W] = all_full ? slots_q[j] : '0;
    end
end

wire all_full = (&full_q);
assign m_valid_o = all_full;

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        full_q <= '0;
        for (int unsigned j = 0; j < N; j++) begin
            slots_q[j] <= '0;
        end
    end else begin
        if (all_full && m_ready_i) begin
            full_q <= '0;
        end else begin
            for (int unsigned j = 0; j < N; j++) begin
                if (!full_q[j] && s_valid_i[j]) begin
                    slots_q[j] <= s_data_i[j*W +: W];
                    full_q[j]  <= 1'b1;
                end
            end
        end
    end
end
""",
    presets={
        "default": {"W": "32", "N": "2"},
        "p1": {"W": "1", "N": "2"},
        "p2": {"W": "7", "N": "3"},
        "p3": {"W": "64", "N": "8"},
    },
    timing=TimingInfo(latency="variable", throughput="1", reset="async active-low"),
    limitations=[
        "Each lane has an independent 1-slot capture buffer.",
        "Output valid asserts only when all N slots are occupied; flushed simultaneously.",
    ],
    validate_params=_validate_stream_join,
    create_reference=lambda p: StreamJoinRef(p),
)


# -----------------------------------------------------------------------------
# 21. stream_upsizer
# -----------------------------------------------------------------------------
def _validate_stream_upsizer(params: dict[str, int]) -> list[str]:
    errors = []
    iw, ratio = params.get("IW", 0), params.get("RATIO", 0)
    if not (1 <= iw <= 128):
        errors.append(f"IW={iw} out of range [1..128]")
    if not (2 <= ratio <= 16):
        errors.append(f"RATIO={ratio} out of range [2..16]")
    if iw * ratio > 256:
        errors.append(f"IW*RATIO={iw * ratio} exceeds 256 bits limit")
    return errors


class StreamUpsizerRef:
    """Independent reference model for stream_upsizer."""

    def __init__(self, params: dict[str, int]) -> None:
        self.iw = params.get("IW", 8)
        self.ratio = params.get("RATIO", 4)
        self.iw_mask = (1 << self.iw) - 1
        self.buffer: list[int] = []
        self.output_valid = False
        self.output_data = 0

    def reset(self) -> None:
        self.buffer.clear()
        self.output_valid = False
        self.output_data = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0) & self.iw_mask
        m_ready = inputs.get("m_ready_i", 0) & 1

        if self.output_valid:
            if m_ready:
                self.output_valid = False
        else:
            if s_valid:
                self.buffer.append(s_data)
                if len(self.buffer) == self.ratio:
                    out = 0
                    for j, val in enumerate(self.buffer):
                        out |= val << (j * self.iw)
                    self.output_data = out
                    self.output_valid = True
                    self.buffer.clear()

        next_ready = int(not self.output_valid)
        next_valid = int(self.output_valid)
        next_data = self.output_data if self.output_valid else 0

        return {"s_ready_o": next_ready, "m_valid_o": next_valid, "m_data_o": next_data}


STREAM_UPSIZER_DEF = ComponentDef(
    id="stream_upsizer",
    category="streams",
    version="1.0.0",
    summary="Packs RATIO narrow stream words into a wider output stream word",
    tags=["stream", "upsizer", "width_conversion"],
    contract_anchor="stream_upsizer",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("IW", "int unsigned", "8", "Input word width in bits", min_value=1, max_value=128),
        ParamDef("RATIO", "int unsigned", "4", "Grouping aggregation factor", min_value=2, max_value=16),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("s_valid_i", "in", None, "Input narrow stream valid"),
        PortDef("s_data_i", "in", "IW-1:0", "Input narrow stream payload"),
        PortDef("s_ready_o", "out", None, "Input narrow stream ready"),
        PortDef("m_valid_o", "out", None, "Output wide stream valid"),
        PortDef("m_data_o", "out", "(IW*RATIO)-1:0", "Output wide stream payload"),
        PortDef("m_ready_i", "in", None, "Output wide stream ready"),
    ],
    systemverilog="""localparam int unsigned COUNT_W = ((RATIO+1)<=1 ? 1 : $clog2(RATIO+1));

logic [(IW*RATIO)-1:0] buffer_q;
logic [COUNT_W-1:0] count_q;
logic output_valid_q;

assign s_ready_o = !output_valid_q;
assign m_valid_o = output_valid_q;
assign m_data_o  = output_valid_q ? buffer_q : '0;

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        buffer_q       <= '0;
        count_q        <= '0;
        output_valid_q <= 1'b0;
    end else begin
        if (output_valid_q) begin
            if (m_ready_i) begin
                output_valid_q <= 1'b0;
            end
        end else if (s_valid_i) begin
            buffer_q[count_q*IW +: IW] <= s_data_i;
            if (count_q == COUNT_W'(RATIO - 1)) begin
                output_valid_q <= 1'b1;
                count_q        <= '0;
            end else begin
                count_q <= count_q + 1'b1;
            end
        end
    end
end
""",
    presets={
        "default": {"IW": "8", "RATIO": "4"},
        "p1": {"IW": "1", "RATIO": "2"},
        "p2": {"IW": "7", "RATIO": "3"},
        "p3": {"IW": "16", "RATIO": "16"},
    },
    timing=TimingInfo(latency="RATIO", throughput="1/RATIO", reset="async active-low"),
    limitations=[
        "Publishes only complete groups of RATIO words; earliest word packed into lowest lane.",
        "Input blocked while output group is held, including the output transfer edge.",
    ],
    validate_params=_validate_stream_upsizer,
    create_reference=lambda p: StreamUpsizerRef(p),
)


# -----------------------------------------------------------------------------
# 22. stream_downsizer
# -----------------------------------------------------------------------------
def _validate_stream_downsizer(params: dict[str, int]) -> list[str]:
    errors = []
    ow, ratio = params.get("OW", 0), params.get("RATIO", 0)
    if not (1 <= ow <= 128):
        errors.append(f"OW={ow} out of range [1..128]")
    if not (2 <= ratio <= 16):
        errors.append(f"RATIO={ratio} out of range [2..16]")
    if ow * ratio > 256:
        errors.append(f"OW*RATIO={ow * ratio} exceeds 256 bits limit")
    return errors


class StreamDownsizerRef:
    """Independent reference model for stream_downsizer."""

    def __init__(self, params: dict[str, int]) -> None:
        self.ow = params.get("OW", 8)
        self.ratio = params.get("RATIO", 4)
        self.ow_mask = (1 << self.ow) - 1
        self.words: list[int] = []

    def reset(self) -> None:
        self.words.clear()

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0)
        m_ready = inputs.get("m_ready_i", 0) & 1

        if not self.words:
            if s_valid:
                for j in range(self.ratio):
                    self.words.append((s_data >> (j * self.ow)) & self.ow_mask)
        else:
            if m_ready:
                self.words.pop(0)

        next_ready = int(len(self.words) == 0)
        next_valid = int(len(self.words) > 0)
        next_data = self.words[0] if self.words else 0

        return {"s_ready_o": next_ready, "m_valid_o": next_valid, "m_data_o": next_data}


STREAM_DOWNSIZER_DEF = ComponentDef(
    id="stream_downsizer",
    category="streams",
    version="1.0.0",
    summary="Serializes a wide stream word into RATIO narrow stream words",
    tags=["downsizer", "stream", "width_conversion"],
    contract_anchor="stream_downsizer",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("OW", "int unsigned", "8", "Output narrow word width in bits", min_value=1, max_value=128),
        ParamDef("RATIO", "int unsigned", "4", "Serialization division factor", min_value=2, max_value=16),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("s_valid_i", "in", None, "Input wide stream valid"),
        PortDef("s_data_i", "in", "(OW*RATIO)-1:0", "Input wide stream payload"),
        PortDef("s_ready_o", "out", None, "Input wide stream ready"),
        PortDef("m_valid_o", "out", None, "Output narrow stream valid"),
        PortDef("m_data_o", "out", "OW-1:0", "Output narrow stream payload"),
        PortDef("m_ready_i", "in", None, "Output narrow stream ready"),
    ],
    systemverilog="""localparam int unsigned COUNT_W = ((RATIO+1)<=1 ? 1 : $clog2(RATIO+1));

logic [(OW*RATIO)-1:0] buffer_q;
logic [COUNT_W-1:0] words_left_q;

assign s_ready_o = (words_left_q == '0);
assign m_valid_o = (words_left_q != '0);

wire [COUNT_W-1:0] current_idx = COUNT_W'(RATIO) - words_left_q;
assign m_data_o = (words_left_q != '0) ? buffer_q[current_idx*OW +: OW] : '0;

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        buffer_q     <= '0;
        words_left_q <= '0;
    end else begin
        if (words_left_q == '0) begin
            if (s_valid_i) begin
                buffer_q     <= s_data_i;
                words_left_q <= COUNT_W'(RATIO);
            end
        end else if (m_ready_i) begin
            words_left_q <= words_left_q - 1'b1;
        end
    end
end
""",
    presets={
        "default": {"OW": "8", "RATIO": "4"},
        "p1": {"OW": "1", "RATIO": "2"},
        "p2": {"OW": "7", "RATIO": "3"},
        "p3": {"OW": "16", "RATIO": "16"},
    },
    timing=TimingInfo(latency="1", throughput="RATIO", reset="async active-low"),
    limitations=[
        "Captures wide word and emits exactly RATIO low-first lanes.",
        "Input blocked while held, including the final output word edge.",
    ],
    validate_params=_validate_stream_downsizer,
    create_reference=lambda p: StreamDownsizerRef(p),
)


# -----------------------------------------------------------------------------
# 23. stream_credit_adapter
# -----------------------------------------------------------------------------
def _validate_stream_credit_adapter(params: dict[str, int]) -> list[str]:
    errors = []
    w, credits = params.get("W", 0), params.get("CREDITS", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (1 <= credits <= 256):
        errors.append(f"CREDITS={credits} out of range [1..256]")
    return errors


class StreamCreditAdapterRef:
    """Independent reference model for stream_credit_adapter."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.max_credits = params.get("CREDITS", 4)
        self.w_mask = (1 << self.w) - 1
        self.credits = self.max_credits

    def reset(self) -> None:
        self.credits = self.max_credits

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": 1, "tx_valid_o": 0, "tx_data_o": 0, "credits_o": self.max_credits, "error_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0) & self.w_mask
        ret = inputs.get("credit_return_i", 0) & 1

        s_ready = int(self.credits > 0)
        send = bool(s_valid and s_ready)

        error = int(ret and not send and (self.credits == self.max_credits))

        # State transition on clock edge
        if send and not ret:
            self.credits -= 1
        elif not send and ret:
            if self.credits < self.max_credits:
                self.credits += 1

        return {
            "s_ready_o": int(self.credits > 0),
            "tx_valid_o": int(s_valid and self.credits > 0),
            "tx_data_o": s_data if (s_valid and self.credits > 0) else 0,
            "credits_o": self.credits,
            "error_o": error,
        }


STREAM_CREDIT_ADAPTER_DEF = ComponentDef(
    id="stream_credit_adapter",
    category="streams",
    version="1.0.0",
    summary="Adapts ready/valid streaming to a credit-based downstream flow control interface",
    tags=["credit_based", "flow_control", "stream"],
    contract_anchor="stream_credit_adapter",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Stream payload width in bits", min_value=1, max_value=256),
        ParamDef("CREDITS", "int unsigned", "4", "Maximum credit capacity", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("s_valid_i", "in", None, "Input stream valid"),
        PortDef("s_data_i", "in", "W-1:0", "Input stream data"),
        PortDef("credit_return_i", "in", None, "Credit return pulse from receiver"),
        PortDef("s_ready_o", "out", None, "Input stream ready (credits available)"),
        PortDef("tx_valid_o", "out", None, "Transmitted credit stream valid"),
        PortDef("tx_data_o", "out", "W-1:0", "Transmitted credit stream payload"),
        PortDef("credits_o", "out", "(((CREDITS+1)<=1 ? 1 : $clog2(CREDITS+1)) - 1):0", "Available credits"),
        PortDef("error_o", "out", None, "Credit overflow error pulse"),
    ],
    systemverilog="""localparam int unsigned CRED_W = ((CREDITS+1)<=1 ? 1 : $clog2(CREDITS+1));

logic [CRED_W-1:0] credits_q;

assign s_ready_o  = (credits_q != '0);
assign tx_valid_o = s_valid_i && (credits_q != '0);
assign tx_data_o  = tx_valid_o ? s_data_i : '0;
assign credits_o  = credits_q;

wire send = tx_valid_o;
wire ret  = credit_return_i;

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        credits_q <= CRED_W'(CREDITS);
        error_o   <= 1'b0;
    end else begin
        error_o <= ret && !send && (credits_q == CRED_W'(CREDITS));

        case ({send, ret})
            2'b10: credits_q <= credits_q - 1'b1;
            2'b01: begin
                if (credits_q < CRED_W'(CREDITS)) begin
                    credits_q <= credits_q + 1'b1;
                end
            end
            default: ;
        endcase
    end
end
""",
    presets={
        "default": {"W": "32", "CREDITS": "4"},
        "p1": {"W": "1", "CREDITS": "1"},
        "p2": {"W": "7", "CREDITS": "3"},
        "p3": {"W": "64", "CREDITS": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="async active-low"),
    limitations=[
        "Downstream receiver must always be able to accept tx_valid_o.",
        "Credit return when credits is already at CREDITS pulses error_o and clamps.",
    ],
    validate_params=_validate_stream_credit_adapter,
    create_reference=lambda p: StreamCreditAdapterRef(p),
)


# -----------------------------------------------------------------------------
# 24. stream_rate_limiter
# -----------------------------------------------------------------------------
def _validate_stream_rate_limiter(params: dict[str, int]) -> list[str]:
    errors = []
    w, interval = params.get("W", 0), params.get("INTERVAL", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (1 <= interval <= 256):
        errors.append(f"INTERVAL={interval} out of range [1..256]")
    return errors


class StreamRateLimiterRef:
    """Independent reference model for stream_rate_limiter."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.interval = params.get("INTERVAL", 4)
        self.w_mask = (1 << self.w) - 1
        self.cooldown = 0

    def reset(self) -> None:
        self.cooldown = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0) & self.w_mask
        m_ready = inputs.get("m_ready_i", 0) & 1

        transfer = bool((self.cooldown == 0) and s_valid and m_ready)

        if transfer:
            self.cooldown = self.interval - 1
        elif self.cooldown > 0:
            self.cooldown -= 1

        can_send = (self.cooldown == 0)
        s_ready = int(can_send and m_ready)
        m_valid = int(can_send and s_valid)
        m_data = s_data if m_valid else 0

        return {"s_ready_o": s_ready, "m_valid_o": m_valid, "m_data_o": m_data}


STREAM_RATE_LIMITER_DEF = ComponentDef(
    id="stream_rate_limiter",
    category="streams",
    version="1.0.0",
    summary="Zero-storage stream throttler enforcing an INTERVAL clock cycle minimum gap between transfers",
    tags=["rate_limiter", "stream", "throttle"],
    contract_anchor="stream_rate_limiter",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Stream payload width in bits", min_value=1, max_value=256),
        ParamDef("INTERVAL", "int unsigned", "4", "Minimum cycle interval between transfers", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("s_valid_i", "in", None, "Input stream valid"),
        PortDef("s_data_i", "in", "W-1:0", "Input stream data"),
        PortDef("s_ready_o", "out", None, "Input stream ready"),
        PortDef("m_valid_o", "out", None, "Output stream valid"),
        PortDef("m_data_o", "out", "W-1:0", "Output stream data"),
        PortDef("m_ready_i", "in", None, "Output stream ready"),
    ],
    systemverilog="""localparam int unsigned COUNT_W = ((INTERVAL)<=1 ? 1 : $clog2(INTERVAL));

logic [COUNT_W-1:0] cooldown_q;

wire can_transfer = (cooldown_q == '0);

assign s_ready_o = can_transfer && m_ready_i;
assign m_valid_o = can_transfer && s_valid_i;
assign m_data_o  = (can_transfer && s_valid_i) ? s_data_i : '0;

wire transfer = m_valid_o && m_ready_i;

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        cooldown_q <= '0;
    end else begin
        if (transfer) begin
            cooldown_q <= COUNT_W'(INTERVAL - 1);
        end else if (cooldown_q != '0) begin
            cooldown_q <= cooldown_q - 1'b1;
        end
    end
end
""",
    presets={
        "default": {"W": "32", "INTERVAL": "4"},
        "p1": {"W": "1", "INTERVAL": "1"},
        "p2": {"W": "7", "INTERVAL": "3"},
        "p3": {"W": "64", "INTERVAL": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1/INTERVAL", reset="async active-low"),
    limitations=[
        "Zero-storage combinational forwarding when cooldown is zero.",
        "Idle time accumulates no burst credit; INTERVAL=1 sustains full throughput.",
    ],
    validate_params=_validate_stream_rate_limiter,
    create_reference=lambda p: StreamRateLimiterRef(p),
)


PHASE2_STREAMS_COMPONENTS: list[ComponentDef] = [
    STREAM_REGISTER_DEF,
    STREAM_SKID_BUFFER_DEF,
    STREAM_SPILL_BUFFER_DEF,
    STREAM_HALF_BUFFER_DEF,
    STREAM_MUX_DEF,
    STREAM_DEMUX_DEF,
    STREAM_FORK_DEF,
    STREAM_JOIN_DEF,
    STREAM_UPSIZER_DEF,
    STREAM_DOWNSIZER_DEF,
    STREAM_CREDIT_ADAPTER_DEF,
    STREAM_RATE_LIMITER_DEF,
]

"""Normative Component definitions and reference models for Phase 2 Storage (12 components).

Components:
1.  fifo_sync
2.  fifo_fallthrough
3.  fifo_async
4.  fifo_packet
5.  lifo_stack
6.  ring_buffer
7.  ram_1rw
8.  ram_1r1w
9.  ram_2rw
10. rom
11. register_file_2r1w
12. cam_binary
"""

from __future__ import annotations

from typing import Any

from spec_catalog_service.catalog.components.models import ComponentDef, ParamDef, PortDef
from spec_catalog_service.catalog.schemas import TimingInfo


# -----------------------------------------------------------------------------
# 1. fifo_sync
# -----------------------------------------------------------------------------
def _validate_fifo_sync(params: dict[str, int]) -> list[str]:
    errors = []
    w, depth = params.get("W", 0), params.get("DEPTH", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (1 <= depth <= 256):
        errors.append(f"DEPTH={depth} out of range [1..256]")
    return errors


class FifoSyncRef:
    """Independent reference model for fifo_sync."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.depth = params.get("DEPTH", 4)
        self.w_mask = (1 << self.w) - 1
        self.queue: list[int] = []

    def reset(self) -> None:
        self.queue.clear()

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.queue.clear()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0, "level_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0) & self.w_mask
        m_ready = inputs.get("m_ready_i", 0) & 1

        curr_level = len(self.queue)
        s_ready = int(curr_level < self.depth)
        m_valid = int(curr_level > 0)

        push = bool(s_valid and s_ready)
        pop = bool(m_valid and m_ready)

        if pop and self.queue:
            self.queue.pop(0)
        if push:
            self.queue.append(s_data)

        next_level = len(self.queue)
        next_ready = int(next_level < self.depth)
        next_valid = int(next_level > 0)
        next_data = self.queue[0] if self.queue else 0

        return {
            "s_ready_o": next_ready,
            "m_valid_o": next_valid,
            "m_data_o": next_data,
            "level_o": next_level,
        }


FIFO_SYNC_DEF = ComponentDef(
    id="fifo_sync",
    category="storage",
    version="1.0.0",
    summary="Synchronous FIFO queue with parameterized data width and depth",
    tags=["fifo", "queue", "storage", "stream"],
    contract_anchor="fifo_sync",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
        ParamDef("DEPTH", "int unsigned", "4", "FIFO depth in words", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("s_valid_i", "in", None, "Input stream valid"),
        PortDef("s_data_i", "in", "W-1:0", "Input stream data"),
        PortDef("s_ready_o", "out", None, "Input stream ready (space available)"),
        PortDef("m_valid_o", "out", None, "Output stream valid (item available)"),
        PortDef("m_data_o", "out", "W-1:0", "Output stream data"),
        PortDef("m_ready_i", "in", None, "Output stream ready"),
        PortDef("level_o", "out", "(((DEPTH+1)<=1 ? 1 : $clog2(DEPTH+1)) - 1):0", "Occupancy count"),
    ],
    systemverilog="""localparam int unsigned PTR_W = ((DEPTH)<=1 ? 1 : $clog2(DEPTH));
localparam int unsigned LEVEL_W = ((DEPTH+1)<=1 ? 1 : $clog2(DEPTH+1));

logic [W-1:0] mem [0:DEPTH-1];
logic [PTR_W-1:0] wr_ptr;
logic [PTR_W-1:0] rd_ptr;
logic [LEVEL_W-1:0] level_q;

assign level_o = level_q;
assign s_ready_o = (32'(level_q) < DEPTH);
assign m_valid_o = (level_q != '0);
assign m_data_o = (level_q != '0) ? mem[rd_ptr] : '0;

wire push = s_valid_i && s_ready_o;
wire pop  = m_valid_o && m_ready_i;

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        wr_ptr  <= '0;
        rd_ptr  <= '0;
        level_q <= '0;
    end else begin
        if (push) begin
            mem[wr_ptr] <= s_data_i;
            wr_ptr <= (32'(wr_ptr) == DEPTH - 1) ? '0 : wr_ptr + 1'b1;
        end
        if (pop) begin
            rd_ptr <= (32'(rd_ptr) == DEPTH - 1) ? '0 : rd_ptr + 1'b1;
        end
        case ({push, pop})
            2'b10: level_q <= level_q + 1'b1;
            2'b01: level_q <= level_q - 1'b1;
            default: level_q <= level_q;
        endcase
    end
end
""",
    presets={
        "default": {"W": "32", "DEPTH": "4"},
        "p1": {"W": "1", "DEPTH": "1"},
        "p2": {"W": "7", "DEPTH": "3"},
        "p3": {"W": "64", "DEPTH": "256"},
    },
    timing=TimingInfo(latency="1", throughput="1", reset="async active-low"),
    limitations=[
        "No fall-through: words are available on the edge after push.",
        "Full pop does not admit simultaneous push.",
    ],
    validate_params=_validate_fifo_sync,
    create_reference=lambda p: FifoSyncRef(p),
)


# -----------------------------------------------------------------------------
# 2. fifo_fallthrough
# -----------------------------------------------------------------------------
def _validate_fifo_fallthrough(params: dict[str, int]) -> list[str]:
    errors = []
    w, depth = params.get("W", 0), params.get("DEPTH", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (1 <= depth <= 256):
        errors.append(f"DEPTH={depth} out of range [1..256]")
    return errors


class FifoFallthroughRef:
    """Independent reference model for fifo_fallthrough."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.depth = params.get("DEPTH", 4)
        self.w_mask = (1 << self.w) - 1
        self.queue: list[int] = []

    def reset(self) -> None:
        self.queue.clear()

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.queue.clear()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0, "level_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0) & self.w_mask
        m_ready = inputs.get("m_ready_i", 0) & 1

        curr_stored = len(self.queue)
        if curr_stored == 0:
            if s_valid and not m_ready:
                self.queue.append(s_data)
        else:
            pop = bool(m_ready)
            push = bool(s_valid and (curr_stored < self.depth or pop))
            if pop and self.queue:
                self.queue.pop(0)
            if push:
                self.queue.append(s_data)

        next_stored = len(self.queue)
        if next_stored == 0:
            next_ready = 1
            next_valid = s_valid
            next_data = s_data if s_valid else 0
        else:
            next_ready = int(next_stored < self.depth or m_ready)
            next_valid = 1
            next_data = self.queue[0]

        return {
            "s_ready_o": next_ready,
            "m_valid_o": next_valid,
            "m_data_o": next_data,
            "level_o": next_stored,
        }


FIFO_FALLTHROUGH_DEF = ComponentDef(
    id="fifo_fallthrough",
    category="storage",
    version="1.0.0",
    summary="Fall-through FIFO queue with zero-cycle latency when empty",
    tags=["fifo", "fallthrough", "queue", "storage", "stream"],
    contract_anchor="fifo_fallthrough",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
        ParamDef("DEPTH", "int unsigned", "4", "FIFO depth in words", min_value=1, max_value=256),
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
        PortDef("level_o", "out", "(((DEPTH+1)<=1 ? 1 : $clog2(DEPTH+1)) - 1):0", "Occupancy count of stored words"),
    ],
    systemverilog="""localparam int unsigned PTR_W = ((DEPTH)<=1 ? 1 : $clog2(DEPTH));
localparam int unsigned LEVEL_W = ((DEPTH+1)<=1 ? 1 : $clog2(DEPTH+1));

logic [W-1:0] mem [0:DEPTH-1];
logic [PTR_W-1:0] wr_ptr;
logic [PTR_W-1:0] rd_ptr;
logic [LEVEL_W-1:0] level_q;

assign level_o = level_q;

wire is_empty = (level_q == '0);
wire is_full  = (32'(level_q) == DEPTH);

assign s_ready_o = is_empty ? 1'b1 : (!is_full || m_ready_i);
assign m_valid_o = is_empty ? s_valid_i : 1'b1;
assign m_data_o  = is_empty ? (s_valid_i ? s_data_i : '0) : mem[rd_ptr];

wire push_nonempty = s_valid_i && (!is_full || m_ready_i);
wire pop_nonempty  = m_ready_i;

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        wr_ptr  <= '0;
        rd_ptr  <= '0;
        level_q <= '0;
    end else begin
        if (is_empty) begin
            if (s_valid_i && !m_ready_i) begin
                mem[wr_ptr] <= s_data_i;
                wr_ptr      <= (32'(wr_ptr) == DEPTH - 1) ? '0 : wr_ptr + 1'b1;
                level_q     <= level_q + 1'b1;
            end
        end else begin
            if (push_nonempty) begin
                mem[wr_ptr] <= s_data_i;
                wr_ptr      <= (32'(wr_ptr) == DEPTH - 1) ? '0 : wr_ptr + 1'b1;
            end
            if (pop_nonempty) begin
                rd_ptr <= (32'(rd_ptr) == DEPTH - 1) ? '0 : rd_ptr + 1'b1;
            end
            case ({push_nonempty, pop_nonempty})
                2'b10: level_q <= level_q + 1'b1;
                2'b01: level_q <= level_q - 1'b1;
                default: level_q <= level_q;
            endcase
        end
    end
end
""",
    presets={
        "default": {"W": "32", "DEPTH": "4"},
        "p1": {"W": "1", "DEPTH": "1"},
        "p2": {"W": "7", "DEPTH": "3"},
        "p3": {"W": "64", "DEPTH": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="async active-low"),
    limitations=[
        "Combinational bypass when empty (latency 0).",
        "level_o reflects stored words only, not words undergoing zero-cycle bypass.",
    ],
    validate_params=_validate_fifo_fallthrough,
    create_reference=lambda p: FifoFallthroughRef(p),
)


# -----------------------------------------------------------------------------
# 3. fifo_async
# -----------------------------------------------------------------------------
def _validate_fifo_async(params: dict[str, int]) -> list[str]:
    errors = []
    w, depth = params.get("W", 0), params.get("DEPTH", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (2 <= depth <= 256) or (depth & (depth - 1)) != 0:
        errors.append(f"DEPTH={depth} must be a power of two in range [2..256]")
    return errors


class FifoAsyncRef:
    """Independent reference model for fifo_async across independent write/read domains."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.depth = params.get("DEPTH", 8)
        self.w_mask = (1 << self.w) - 1
        self.queue: list[int] = []

    def reset(self) -> None:
        self.queue.clear()

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        wrst_n = inputs.get("wrst_ni", 1)
        rrst_n = inputs.get("rrst_ni", 1)
        if not (wrst_n and rrst_n):
            self.queue.clear()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0) & self.w_mask
        m_ready = inputs.get("m_ready_i", 0) & 1

        s_ready = int(len(self.queue) < self.depth)
        m_valid = int(len(self.queue) > 0)

        push = bool(s_valid and s_ready)
        pop = bool(m_valid and m_ready)

        if pop and self.queue:
            self.queue.pop(0)
        if push:
            self.queue.append(s_data)

        next_ready = int(len(self.queue) < self.depth)
        next_valid = int(len(self.queue) > 0)
        next_data = self.queue[0] if self.queue else 0

        return {"s_ready_o": next_ready, "m_valid_o": next_valid, "m_data_o": next_data}


FIFO_ASYNC_DEF = ComponentDef(
    id="fifo_async",
    category="storage",
    version="1.0.0",
    summary="Asynchronous dual-clock FIFO with Gray-coded pointer synchronization",
    tags=["cdc", "fifo", "dual_clock", "gray_code", "storage"],
    contract_anchor="fifo_async",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
        ParamDef("DEPTH", "int unsigned", "8", "Power-of-two FIFO depth", min_value=2, max_value=256),
    ],
    ports=[
        PortDef("wclk_i", "in", None, "Write clock"),
        PortDef("wrst_ni", "in", None, "Write domain asynchronous active-low reset"),
        PortDef("s_valid_i", "in", None, "Write stream valid"),
        PortDef("s_data_i", "in", "W-1:0", "Write stream data"),
        PortDef("s_ready_o", "out", None, "Write stream ready"),
        PortDef("rclk_i", "in", None, "Read clock"),
        PortDef("rrst_ni", "in", None, "Read domain asynchronous active-low reset"),
        PortDef("m_valid_o", "out", None, "Read stream valid"),
        PortDef("m_data_o", "out", "W-1:0", "Read stream data"),
        PortDef("m_ready_i", "in", None, "Read stream ready"),
    ],
    systemverilog="""localparam int unsigned ADDR_W = $clog2(DEPTH);
localparam int unsigned PTR_W  = ADDR_W + 1;

logic [W-1:0] mem [0:DEPTH-1];

// Write domain registers
logic [PTR_W-1:0] wbin;
logic [PTR_W-1:0] wgray;
logic [PTR_W-1:0] rgray_sync1, rgray_sync2;

// Read domain registers
logic [PTR_W-1:0] rbin;
logic [PTR_W-1:0] rgray;
logic [PTR_W-1:0] wgray_sync1, wgray_sync2;

// Synchronize read pointer into write domain
always_ff @(posedge wclk_i or negedge wrst_ni) begin
    if (!wrst_ni) begin
        rgray_sync1 <= '0;
        rgray_sync2 <= '0;
    end else begin
        rgray_sync1 <= rgray;
        rgray_sync2 <= rgray_sync1;
    end
end

// Synchronize write pointer into read domain
always_ff @(posedge rclk_i or negedge rrst_ni) begin
    if (!rrst_ni) begin
        wgray_sync1 <= '0;
        wgray_sync2 <= '0;
    end else begin
        wgray_sync1 <= wgray;
        wgray_sync2 <= wgray_sync1;
    end
end

// Write domain logic
wire [PTR_W-1:0] wbin_next  = wbin + 1'b1;
wire [PTR_W-1:0] wgray_next = (wbin_next >> 1) ^ wbin_next;
wire wfull;
generate
    if (PTR_W == 2) begin : gen_full_small
        assign wfull = (wgray_next == ~rgray_sync2);
    end else begin : gen_full_wide
        assign wfull = (wgray_next == {~rgray_sync2[PTR_W-1:PTR_W-2], rgray_sync2[PTR_W-3:0]});
    end
endgenerate

assign s_ready_o = !wfull;

always_ff @(posedge wclk_i or negedge wrst_ni) begin
    if (!wrst_ni) begin
        wbin  <= '0;
        wgray <= '0;
    end else if (s_valid_i && s_ready_o) begin
        mem[wbin[ADDR_W-1:0]] <= s_data_i;
        wbin                  <= wbin_next;
        wgray                 <= wgray_next;
    end
end

// Read domain logic
wire rempty = (rgray == wgray_sync2);
assign m_valid_o = !rempty;
assign m_data_o  = mem[rbin[ADDR_W-1:0]];

wire [PTR_W-1:0] rbin_next  = rbin + 1'b1;
wire [PTR_W-1:0] rgray_next = (rbin_next >> 1) ^ rbin_next;

always_ff @(posedge rclk_i or negedge rrst_ni) begin
    if (!rrst_ni) begin
        rbin  <= '0;
        rgray <= '0;
    end else if (m_valid_o && m_ready_i) begin
        rbin  <= rbin_next;
        rgray <= rgray_next;
    end
end
""",
    presets={
        "default": {"W": "32", "DEPTH": "8"},
        "p1": {"W": "1", "DEPTH": "2"},
        "p2": {"W": "7", "DEPTH": "4"},
        "p3": {"W": "64", "DEPTH": "256"},
    },
    timing=TimingInfo(latency="2", throughput="1", reset="async active-low coordinated"),
    limitations=[
        "DEPTH must be a power of two.",
        "Both resets must be asserted together; each domain releases synchronously.",
        "Digital simulation cannot model analog metastability; MTBF sign-off is not claimed.",
    ],
    validate_params=_validate_fifo_async,
    create_reference=lambda p: FifoAsyncRef(p),
)


# -----------------------------------------------------------------------------
# 4. fifo_packet
# -----------------------------------------------------------------------------
def _validate_fifo_packet(params: dict[str, int]) -> list[str]:
    errors = []
    w, depth = params.get("W", 0), params.get("DEPTH", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (2 <= depth <= 256):
        errors.append(f"DEPTH={depth} out of range [2..256]")
    return errors


class FifoPacketRef:
    """Independent reference model for fifo_packet."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.depth = params.get("DEPTH", 16)
        self.w_mask = (1 << self.w) - 1
        self.committed_packets: list[list[tuple[int, int]]] = []  # list of packets, each word is (data, last)
        self.current_partial: list[tuple[int, int]] = []
        self.discarding = False

    def reset(self) -> None:
        self.committed_packets.clear()
        self.current_partial.clear()
        self.discarding = False

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0, "m_last_o": 0, "level_o": 0, "drop_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        s_data = inputs.get("s_data_i", 0) & self.w_mask
        s_last = inputs.get("s_last_i", 0) & 1
        m_ready = inputs.get("m_ready_i", 0) & 1

        committed_word_count = sum(len(pkt) for pkt in self.committed_packets)
        total_level = committed_word_count + len(self.current_partial)

        drop = 0
        s_ready = int(total_level < self.depth) or int(self.discarding)

        # Sample pop condition based on state at beginning of cycle
        pop_active = bool(self.committed_packets and self.committed_packets[0]) and bool(m_ready)

        if s_valid and s_ready:
            if self.discarding:
                if s_last:
                    self.discarding = False
            else:
                self.current_partial.append((s_data, s_last))
                if s_last:
                    self.committed_packets.append(self.current_partial)
                    self.current_partial = []
                elif len(self.current_partial) == self.depth:
                    # Oversized packet without last: discard and pulse drop
                    self.current_partial = []
                    self.discarding = True
                    drop = 1

        # Read consumption
        if pop_active:
            head_pkt = self.committed_packets[0]
            head_pkt.pop(0)
            if not head_pkt:
                self.committed_packets.pop(0)

        next_committed_count = sum(len(pkt) for pkt in self.committed_packets)
        next_level = next_committed_count + len(self.current_partial)
        next_ready = int(next_level < self.depth) or int(self.discarding)

        if self.committed_packets and self.committed_packets[0]:
            next_valid = 1
            next_data, next_last = self.committed_packets[0][0]
        else:
            next_valid = 0
            next_data, next_last = 0, 0

        return {
            "s_ready_o": next_ready,
            "m_valid_o": next_valid,
            "m_data_o": next_data,
            "m_last_o": next_last,
            "level_o": next_level,
            "drop_o": drop,
        }


FIFO_PACKET_DEF = ComponentDef(
    id="fifo_packet",
    category="storage",
    version="1.0.0",
    summary="Packet FIFO that exposes words only after full packet commitment",
    tags=["fifo", "packet", "stream", "storage"],
    contract_anchor="fifo_packet",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
        ParamDef("DEPTH", "int unsigned", "16", "Capacity in words", min_value=2, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("s_valid_i", "in", None, "Input stream valid"),
        PortDef("s_data_i", "in", "W-1:0", "Input stream data"),
        PortDef("s_last_i", "in", None, "Input stream packet boundary"),
        PortDef("s_ready_o", "out", None, "Input stream ready"),
        PortDef("m_valid_o", "out", None, "Output stream valid"),
        PortDef("m_data_o", "out", "W-1:0", "Output stream data"),
        PortDef("m_last_o", "out", None, "Output stream packet boundary"),
        PortDef("m_ready_i", "in", None, "Output stream ready"),
        PortDef("level_o", "out", "(((DEPTH+1)<=1 ? 1 : $clog2(DEPTH+1)) - 1):0", "Total stored words count"),
        PortDef("drop_o", "out", None, "Oversized packet drop pulse"),
    ],
    systemverilog="""localparam int unsigned PTR_W = ((DEPTH)<=1 ? 1 : $clog2(DEPTH));
localparam int unsigned LEVEL_W = ((DEPTH+1)<=1 ? 1 : $clog2(DEPTH+1));

logic [W-1:0] mem_data [0:DEPTH-1];
logic mem_last [0:DEPTH-1];

logic [PTR_W-1:0] rd_ptr;
logic [PTR_W-1:0] commit_wr_ptr;
logic [PTR_W-1:0] curr_wr_ptr;
logic [LEVEL_W-1:0] committed_count;
logic [LEVEL_W-1:0] partial_count;
logic discarding_q;

assign level_o = committed_count + partial_count;

wire total_full = ((committed_count + partial_count) == LEVEL_W'(DEPTH));
assign s_ready_o = discarding_q ? 1'b1 : !total_full;

assign m_valid_o = (committed_count != '0);
assign m_data_o  = (committed_count != '0) ? mem_data[rd_ptr] : '0;
assign m_last_o  = (committed_count != '0) ? mem_last[rd_ptr] : 1'b0;

wire [PTR_W-1:0] next_curr_wr = (32'(curr_wr_ptr) == DEPTH - 1) ? '0 : curr_wr_ptr + 1'b1;
wire push_word   = s_valid_i && s_ready_o && !discarding_q;
wire push_commit = push_word && s_last_i;
wire pop_word    = m_valid_o && m_ready_i;

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        rd_ptr          <= '0;
        commit_wr_ptr   <= '0;
        curr_wr_ptr     <= '0;
        committed_count <= '0;
        partial_count   <= '0;
        discarding_q    <= 1'b0;
        drop_o          <= 1'b0;
    end else begin
        drop_o <= 1'b0;

        // Ingress handling
        if (s_valid_i && s_ready_o) begin
            if (discarding_q) begin
                if (s_last_i) begin
                    discarding_q <= 1'b0;
                end
            end else begin
                mem_data[curr_wr_ptr] <= s_data_i;
                mem_last[curr_wr_ptr] <= s_last_i;

                if (s_last_i) begin
                    commit_wr_ptr <= next_curr_wr;
                    curr_wr_ptr   <= next_curr_wr;
                    partial_count <= '0;
                end else if ((partial_count + 1'b1) == LEVEL_W'(DEPTH)) begin
                    // Packet overflow without last: discard and pulse drop
                    curr_wr_ptr   <= commit_wr_ptr;
                    partial_count <= '0;
                    discarding_q  <= 1'b1;
                    drop_o        <= 1'b1;
                end else begin
                    curr_wr_ptr   <= next_curr_wr;
                    partial_count <= partial_count + 1'b1;
                end
            end
        end

        // Egress handling
        if (pop_word) begin
            rd_ptr <= (32'(rd_ptr) == DEPTH - 1) ? '0 : rd_ptr + 1'b1;
        end

        // Simultaneous commit and pop handling for committed words count
        if (push_commit && pop_word) begin
            committed_count <= committed_count + partial_count;
        end else if (push_commit) begin
            committed_count <= committed_count + partial_count + 1'b1;
        end else if (pop_word) begin
            committed_count <= committed_count - 1'b1;
        end
    end
end
""",
    presets={
        "default": {"W": "32", "DEPTH": "16"},
        "p1": {"W": "1", "DEPTH": "2"},
        "p2": {"W": "7", "DEPTH": "3"},
        "p3": {"W": "64", "DEPTH": "256"},
    },
    timing=TimingInfo(latency="packet", throughput="1", reset="async active-low"),
    limitations=[
        "Exposes only packets whose last word has been accepted.",
        "Oversized packets (>DEPTH words without last) are dropped with a 1-cycle drop_o pulse.",
    ],
    validate_params=_validate_fifo_packet,
    create_reference=lambda p: FifoPacketRef(p),
)


# -----------------------------------------------------------------------------
# 5. lifo_stack
# -----------------------------------------------------------------------------
def _validate_lifo_stack(params: dict[str, int]) -> list[str]:
    errors = []
    w, depth = params.get("W", 0), params.get("DEPTH", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (1 <= depth <= 256):
        errors.append(f"DEPTH={depth} out of range [1..256]")
    return errors


class LifoStackRef:
    """Independent reference model for lifo_stack."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.depth = params.get("DEPTH", 4)
        self.w_mask = (1 << self.w) - 1
        self.stack: list[int] = []

    def reset(self) -> None:
        self.stack.clear()

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.stack.clear()
            return {"data_o": 0, "valid_o": 0, "level_o": 0, "overflow_o": 0, "underflow_o": 0}

        push = inputs.get("push_i", 0) & 1
        pop = inputs.get("pop_i", 0) & 1
        data_i = inputs.get("data_i", 0) & self.w_mask

        overflow = 0
        underflow = 0

        if push and pop:
            if self.stack:
                self.stack[-1] = data_i
            else:
                self.stack.append(data_i)
                underflow = 1
        elif push:
            if len(self.stack) < self.depth:
                self.stack.append(data_i)
            else:
                overflow = 1
        elif pop:
            if self.stack:
                self.stack.pop()
            else:
                underflow = 1

        level = len(self.stack)
        valid = int(level > 0)
        data_o = self.stack[-1] if self.stack else 0

        return {
            "data_o": data_o,
            "valid_o": valid,
            "level_o": level,
            "overflow_o": overflow,
            "underflow_o": underflow,
        }


LIFO_STACK_DEF = ComponentDef(
    id="lifo_stack",
    category="storage",
    version="1.0.0",
    summary="Last-in-first-out stack with combinational top visibility and error flags",
    tags=["lifo", "stack", "storage"],
    contract_anchor="lifo_stack",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
        ParamDef("DEPTH", "int unsigned", "4", "Stack capacity in words", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("push_i", "in", None, "Push enable"),
        PortDef("pop_i", "in", None, "Pop enable"),
        PortDef("data_i", "in", "W-1:0", "Push data input"),
        PortDef("data_o", "out", "W-1:0", "Top of stack data output"),
        PortDef("valid_o", "out", None, "Stack non-empty valid flag"),
        PortDef("level_o", "out", "(((DEPTH+1)<=1 ? 1 : $clog2(DEPTH+1)) - 1):0", "Occupancy count"),
        PortDef("overflow_o", "out", None, "Overflow error pulse"),
        PortDef("underflow_o", "out", None, "Underflow error pulse"),
    ],
    systemverilog="""localparam int unsigned PTR_W = ((DEPTH)<=1 ? 1 : $clog2(DEPTH));
localparam int unsigned LEVEL_W = ((DEPTH+1)<=1 ? 1 : $clog2(DEPTH+1));

logic [W-1:0] mem [0:DEPTH-1];
logic [LEVEL_W-1:0] level_q;

assign level_o = level_q;
assign valid_o = (level_q != '0);
assign data_o  = (level_q != '0) ? mem[PTR_W'(level_q - 1'b1)] : '0;

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        level_q     <= '0;
        overflow_o  <= 1'b0;
        underflow_o <= 1'b0;
    end else begin
        overflow_o  <= 1'b0;
        underflow_o <= 1'b0;

        if (push_i && pop_i) begin
            if (level_q != '0) begin
                mem[PTR_W'(level_q - 1'b1)] <= data_i;
            end else begin
                mem[PTR_W'(0)] <= data_i;
                level_q        <= LEVEL_W'(1);
                underflow_o    <= 1'b1;
            end
        end else if (push_i) begin
            if (32'(level_q) < DEPTH) begin
                mem[PTR_W'(level_q)] <= data_i;
                level_q              <= level_q + 1'b1;
            end else begin
                overflow_o <= 1'b1;
            end
        end else if (pop_i) begin
            if (level_q != '0) begin
                level_q <= level_q - 1'b1;
            end else begin
                underflow_o <= 1'b1;
            end
        end
    end
end
""",
    presets={
        "default": {"W": "32", "DEPTH": "4"},
        "p1": {"W": "1", "DEPTH": "1"},
        "p2": {"W": "7", "DEPTH": "3"},
        "p3": {"W": "64", "DEPTH": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="async active-low"),
    limitations=[
        "Top is combinationally visible when non-empty.",
        "Error pulses last exactly one clock cycle.",
    ],
    validate_params=_validate_lifo_stack,
    create_reference=lambda p: LifoStackRef(p),
)


# -----------------------------------------------------------------------------
# 6. ring_buffer
# -----------------------------------------------------------------------------
def _validate_ring_buffer(params: dict[str, int]) -> list[str]:
    errors = []
    w, depth = params.get("W", 0), params.get("DEPTH", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (1 <= depth <= 256):
        errors.append(f"DEPTH={depth} out of range [1..256]")
    return errors


class RingBufferRef:
    """Independent reference model for ring_buffer."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.depth = params.get("DEPTH", 8)
        self.w_mask = (1 << self.w) - 1
        self.history: list[int] = []

    def reset(self) -> None:
        self.history.clear()

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.history.clear()
            return {"data_o": 0, "valid_o": 0, "count_o": 0}

        write = inputs.get("write_i", 0) & 1
        data_i = inputs.get("data_i", 0) & self.w_mask
        index_i = inputs.get("index_i", 0)

        if write:
            self.history.insert(0, data_i)
            if len(self.history) > self.depth:
                self.history.pop()

        count = len(self.history)
        valid = int(index_i < count)
        data_o = self.history[index_i] if valid else 0

        return {"data_o": data_o, "valid_o": valid, "count_o": count}


RING_BUFFER_DEF = ComponentDef(
    id="ring_buffer",
    category="storage",
    version="1.0.0",
    summary="Circular history ring buffer retaining the newest DEPTH words",
    tags=["circular_buffer", "history", "ring_buffer", "storage"],
    contract_anchor="ring_buffer",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
        ParamDef("DEPTH", "int unsigned", "8", "Capacity in words", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("write_i", "in", None, "Write enable"),
        PortDef("data_i", "in", "W-1:0", "Data to append"),
        PortDef("index_i", "in", "(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0", "Relative index (0=newest)"),
        PortDef("data_o", "out", "W-1:0", "Indexed historical word"),
        PortDef("valid_o", "out", None, "Valid index flag"),
        PortDef("count_o", "out", "(((DEPTH+1)<=1 ? 1 : $clog2(DEPTH+1)) - 1):0", "Count of valid stored words"),
    ],
    systemverilog="""localparam int unsigned PTR_W = ((DEPTH)<=1 ? 1 : $clog2(DEPTH));
localparam int unsigned COUNT_W = ((DEPTH+1)<=1 ? 1 : $clog2(DEPTH+1));

logic [W-1:0] mem [0:DEPTH-1];
logic [PTR_W-1:0] head_q;
logic [COUNT_W-1:0] count_q;

assign count_o = count_q;
assign valid_o = (32'(index_i) < 32'(count_q));

wire [PTR_W-1:0] target_idx = PTR_W'((32'(head_q) >= 32'(index_i)) ?
                         (32'(head_q) - 32'(index_i)) :
                         (32'(head_q) + DEPTH - 32'(index_i)));

assign data_o = valid_o ? mem[target_idx] : '0;

wire [PTR_W-1:0] next_head = (count_q == '0) ? '0 : ((32'(head_q) == DEPTH - 1) ? '0 : head_q + 1'b1);

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        head_q  <= '0;
        count_q <= '0;
    end else if (write_i) begin
        mem[next_head] <= data_i;
        head_q         <= next_head;
        if (32'(count_q) < DEPTH) begin
            count_q <= count_q + 1'b1;
        end
    end
end
""",
    presets={
        "default": {"W": "32", "DEPTH": "8"},
        "p1": {"W": "1", "DEPTH": "1"},
        "p2": {"W": "7", "DEPTH": "3"},
        "p3": {"W": "64", "DEPTH": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="async active-low"),
    limitations=[
        "Index 0 is newest recorded word; index 1 is previous.",
        "Overwrites oldest entry when capacity is exceeded.",
    ],
    validate_params=_validate_ring_buffer,
    create_reference=lambda p: RingBufferRef(p),
)


# -----------------------------------------------------------------------------
# 7. ram_1rw
# -----------------------------------------------------------------------------
def _validate_ram_1rw(params: dict[str, int]) -> list[str]:
    errors = []
    w, depth = params.get("W", 0), params.get("DEPTH", 0)
    if not (8 <= w <= 256) or (w % 8 != 0):
        errors.append(f"W={w} must be a multiple of 8 in range [8..256]")
    if not (2 <= depth <= 1024):
        errors.append(f"DEPTH={depth} out of range [2..1024]")
    return errors


class Ram1rwRef:
    """Independent reference model for ram_1rw with byte-level enables."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.depth = params.get("DEPTH", 16)
        self.bytes_per_word = self.w // 8
        self.mem: dict[int, list[int]] = {}  # addr -> list of byte ints
        self.last_rdata = 0

    def reset(self) -> None:
        # RAM storage is not reset
        self.last_rdata = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        en = inputs.get("en_i", 0) & 1
        we = inputs.get("we_i", 0) & 1
        addr = inputs.get("addr_i", 0)
        wdata = inputs.get("wdata_i", 0)
        be = inputs.get("be_i", 0)

        rvalid = 0
        addr_error = 0
        rdata = self.last_rdata

        if en:
            if addr >= self.depth:
                addr_error = 1
            elif we:
                if addr not in self.mem:
                    self.mem[addr] = [0] * self.bytes_per_word
                for b in range(self.bytes_per_word):
                    if (be >> b) & 1:
                        byte_val = (wdata >> (b * 8)) & 0xFF
                        self.mem[addr][b] = byte_val
            else:
                rvalid = 1
                word_bytes = self.mem.get(addr, [0] * self.bytes_per_word)
                rdata = 0
                for b in range(self.bytes_per_word):
                    rdata |= word_bytes[b] << (b * 8)
                self.last_rdata = rdata

        return {"rvalid_o": rvalid, "rdata_o": rdata, "addr_error_o": addr_error}


RAM_1RW_DEF = ComponentDef(
    id="ram_1rw",
    category="storage",
    version="1.0.0",
    summary="Single-port synchronous RAM with byte enables and out-of-range detection",
    tags=["ram", "sram", "storage"],
    contract_anchor="ram_1rw",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits (multiple of 8)", min_value=8, max_value=256),
        ParamDef("DEPTH", "int unsigned", "16", "Memory depth in words", min_value=2, max_value=1024),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset (controls flags only)"),
        PortDef("en_i", "in", None, "Memory enable"),
        PortDef("we_i", "in", None, "Write enable (1=write, 0=read)"),
        PortDef("addr_i", "in", "(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0", "Address input"),
        PortDef("wdata_i", "in", "W-1:0", "Write data"),
        PortDef("be_i", "in", "(W/8)-1:0", "Byte write enable mask"),
        PortDef("rvalid_o", "out", None, "Read data valid flag"),
        PortDef("rdata_o", "out", "W-1:0", "Read data output"),
        PortDef("addr_error_o", "out", None, "Out-of-range address error flag"),
    ],
    systemverilog="""localparam int unsigned BYTES = W / 8;

logic [W-1:0] mem [0:DEPTH-1];

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        rvalid_o     <= 1'b0;
        addr_error_o <= 1'b0;
        rdata_o      <= '0;
    end else if (en_i) begin
        if (32'(addr_i) >= DEPTH) begin
            addr_error_o <= 1'b1;
            rvalid_o     <= 1'b0;
        end else if (we_i) begin
            addr_error_o <= 1'b0;
            rvalid_o     <= 1'b0;
            for (int unsigned b = 0; b < BYTES; b++) begin
                if (be_i[b]) begin
                    mem[addr_i][b*8 +: 8] <= wdata_i[b*8 +: 8];
                end
            end
        end else begin
            addr_error_o <= 1'b0;
            rvalid_o     <= 1'b1;
            rdata_o      <= mem[addr_i];
        end
    end else begin
        addr_error_o <= 1'b0;
        rvalid_o     <= 1'b0;
    end
end
""",
    presets={
        "default": {"W": "32", "DEPTH": "16"},
        "p1": {"W": "8", "DEPTH": "2"},
        "p2": {"W": "24", "DEPTH": "3"},
        "p3": {"W": "256", "DEPTH": "1024"},
    },
    timing=TimingInfo(latency="1", throughput="1", reset="async active-low control only"),
    limitations=[
        "RAM memory array contents are uninitialized at power-on and not reset.",
        "Read latency is 1 cycle; disabled memory holds last registered read value.",
    ],
    validate_params=_validate_ram_1rw,
    create_reference=lambda p: Ram1rwRef(p),
)


# -----------------------------------------------------------------------------
# 8. ram_1r1w
# -----------------------------------------------------------------------------
def _validate_ram_1r1w(params: dict[str, int]) -> list[str]:
    errors = []
    w, depth = params.get("W", 0), params.get("DEPTH", 0)
    if not (8 <= w <= 256) or (w % 8 != 0):
        errors.append(f"W={w} must be a multiple of 8 in range [8..256]")
    if not (2 <= depth <= 1024):
        errors.append(f"DEPTH={depth} out of range [2..1024]")
    return errors


class Ram1r1wRef:
    """Independent reference model for ram_1r1w."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.depth = params.get("DEPTH", 16)
        self.bytes_per_word = self.w // 8
        self.mem: dict[int, list[int]] = {}
        self.last_rdata = 0

    def reset(self) -> None:
        self.last_rdata = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        we = inputs.get("we_i", 0) & 1
        waddr = inputs.get("waddr_i", 0)
        wdata = inputs.get("wdata_i", 0)
        be = inputs.get("be_i", 0)

        re = inputs.get("re_i", 0) & 1
        raddr = inputs.get("raddr_i", 0)

        write_error = int(we and (waddr >= self.depth))
        read_error = int(re and (raddr >= self.depth))

        rvalid = 0
        rdata = self.last_rdata

        # Sample read before write to reflect old pre-edge data on collision
        if re and not read_error:
            rvalid = 1
            word_bytes = self.mem.get(raddr, [0] * self.bytes_per_word)
            rdata = 0
            for b in range(self.bytes_per_word):
                rdata |= word_bytes[b] << (b * 8)
            self.last_rdata = rdata

        if we and not write_error:
            if waddr not in self.mem:
                self.mem[waddr] = [0] * self.bytes_per_word
            for b in range(self.bytes_per_word):
                if (be >> b) & 1:
                    self.mem[waddr][b] = (wdata >> (b * 8)) & 0xFF

        return {
            "rvalid_o": rvalid,
            "rdata_o": rdata,
            "write_error_o": write_error,
            "read_error_o": read_error,
        }


RAM_1R1W_DEF = ComponentDef(
    id="ram_1r1w",
    category="storage",
    version="1.0.0",
    summary="Simple dual-port synchronous RAM with independent read and write ports",
    tags=["dual_port", "ram", "sram", "storage"],
    contract_anchor="ram_1r1w",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits (multiple of 8)", min_value=8, max_value=256),
        ParamDef("DEPTH", "int unsigned", "16", "Memory depth in words", min_value=2, max_value=1024),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset (controls flags only)"),
        PortDef("we_i", "in", None, "Write enable"),
        PortDef("waddr_i", "in", "(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0", "Write address"),
        PortDef("wdata_i", "in", "W-1:0", "Write data"),
        PortDef("be_i", "in", "(W/8)-1:0", "Write byte enables"),
        PortDef("re_i", "in", None, "Read enable"),
        PortDef("raddr_i", "in", "(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0", "Read address"),
        PortDef("rvalid_o", "out", None, "Read data valid flag"),
        PortDef("rdata_o", "out", "W-1:0", "Read data output"),
        PortDef("write_error_o", "out", None, "Write address error pulse"),
        PortDef("read_error_o", "out", None, "Read address error pulse"),
    ],
    systemverilog="""localparam int unsigned BYTES = W / 8;

logic [W-1:0] mem [0:DEPTH-1];

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        rvalid_o     <= 1'b0;
        rdata_o      <= '0;
        write_error_o<= 1'b0;
        read_error_o <= 1'b0;
    end else begin
        // Write port
        if (we_i) begin
            if (32'(waddr_i) >= DEPTH) begin
                write_error_o <= 1'b1;
            end else begin
                write_error_o <= 1'b0;
                for (int unsigned b = 0; b < BYTES; b++) begin
                    if (be_i[b]) begin
                        mem[waddr_i][b*8 +: 8] <= wdata_i[b*8 +: 8];
                    end
                end
            end
        end else begin
            write_error_o <= 1'b0;
        end

        // Read port (registers pre-edge value on collision)
        if (re_i) begin
            if (32'(raddr_i) >= DEPTH) begin
                read_error_o <= 1'b1;
                rvalid_o     <= 1'b0;
            end else begin
                read_error_o <= 1'b0;
                rvalid_o     <= 1'b1;
                rdata_o      <= mem[raddr_i];
            end
        end else begin
            read_error_o <= 1'b0;
            rvalid_o     <= 1'b0;
        end
    end
end
""",
    presets={
        "default": {"W": "32", "DEPTH": "16"},
        "p1": {"W": "8", "DEPTH": "2"},
        "p2": {"W": "24", "DEPTH": "3"},
        "p3": {"W": "256", "DEPTH": "1024"},
    },
    timing=TimingInfo(latency="1", throughput="1", reset="async active-low control only"),
    limitations=[
        "Same-address read/write collision returns pre-edge old data.",
        "RAM storage array is not reset.",
    ],
    validate_params=_validate_ram_1r1w,
    create_reference=lambda p: Ram1r1wRef(p),
)


# -----------------------------------------------------------------------------
# 9. ram_2rw
# -----------------------------------------------------------------------------
def _validate_ram_2rw(params: dict[str, int]) -> list[str]:
    errors = []
    w, depth = params.get("W", 0), params.get("DEPTH", 0)
    if not (8 <= w <= 256) or (w % 8 != 0):
        errors.append(f"W={w} must be a multiple of 8 in range [8..256]")
    if not (2 <= depth <= 1024):
        errors.append(f"DEPTH={depth} out of range [2..1024]")
    return errors


class Ram2rwRef:
    """Independent reference model for true dual-port ram_2rw."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.depth = params.get("DEPTH", 16)
        self.bytes_per_word = self.w // 8
        self.mem: dict[int, list[int]] = {}
        self.a_last = 0
        self.b_last = 0

    def reset(self) -> None:
        self.a_last = 0
        self.b_last = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        a_en, a_we, a_addr = inputs.get("a_en_i", 0) & 1, inputs.get("a_we_i", 0) & 1, inputs.get("a_addr_i", 0)
        a_wdata, a_be = inputs.get("a_wdata_i", 0), inputs.get("a_be_i", 0)

        b_en, b_we, b_addr = inputs.get("b_en_i", 0) & 1, inputs.get("b_we_i", 0) & 1, inputs.get("b_addr_i", 0)
        b_wdata, b_be = inputs.get("b_wdata_i", 0), inputs.get("b_be_i", 0)

        a_legal = (a_addr < self.depth)
        b_legal = (b_addr < self.depth)

        a_is_write = bool(a_en and a_we and a_legal)
        b_is_write = bool(b_en and b_we and b_legal)

        write_collision = bool(a_is_write and b_is_write and (a_addr == b_addr))

        a_error = int(a_en and (not a_legal or write_collision))
        b_error = int(b_en and (not b_legal or write_collision))

        # Reads (sample old data before writes)
        a_rvalid = int(a_en and not a_we and a_legal)
        b_rvalid = int(b_en and not b_we and b_legal)

        a_rdata = self.a_last
        if a_rvalid:
            word_bytes = self.mem.get(a_addr, [0] * self.bytes_per_word)
            a_rdata = sum(word_bytes[b] << (b * 8) for b in range(self.bytes_per_word))
            self.a_last = a_rdata

        b_rdata = self.b_last
        if b_rvalid:
            word_bytes = self.mem.get(b_addr, [0] * self.bytes_per_word)
            b_rdata = sum(word_bytes[b] << (b * 8) for b in range(self.bytes_per_word))
            self.b_last = b_rdata

        # Execute writes only if no collision
        if not write_collision:
            if a_is_write:
                if a_addr not in self.mem:
                    self.mem[a_addr] = [0] * self.bytes_per_word
                for b in range(self.bytes_per_word):
                    if (a_be >> b) & 1:
                        self.mem[a_addr][b] = (a_wdata >> (b * 8)) & 0xFF
            if b_is_write:
                if b_addr not in self.mem:
                    self.mem[b_addr] = [0] * self.bytes_per_word
                for b in range(self.bytes_per_word):
                    if (b_be >> b) & 1:
                        self.mem[b_addr][b] = (b_wdata >> (b * 8)) & 0xFF

        return {
            "a_rvalid_o": a_rvalid,
            "a_rdata_o": a_rdata,
            "a_error_o": a_error,
            "b_rvalid_o": b_rvalid,
            "b_rdata_o": b_rdata,
            "b_error_o": b_error,
            "collision_o": int(write_collision),
        }


RAM_2RW_DEF = ComponentDef(
    id="ram_2rw",
    category="storage",
    version="1.0.0",
    summary="True dual-port synchronous RAM with write collision rejection",
    tags=["dual_port", "ram", "sram", "storage", "true_dual_port"],
    contract_anchor="ram_2rw",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits (multiple of 8)", min_value=8, max_value=256),
        ParamDef("DEPTH", "int unsigned", "16", "Memory depth in words", min_value=2, max_value=1024),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset (controls flags only)"),
        PortDef("a_en_i", "in", None, "Port A enable"),
        PortDef("a_we_i", "in", None, "Port A write enable"),
        PortDef("a_addr_i", "in", "(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0", "Port A address"),
        PortDef("a_wdata_i", "in", "W-1:0", "Port A write data"),
        PortDef("a_be_i", "in", "(W/8)-1:0", "Port A byte enables"),
        PortDef("a_rvalid_o", "out", None, "Port A read valid flag"),
        PortDef("a_rdata_o", "out", "W-1:0", "Port A read data"),
        PortDef("a_error_o", "out", None, "Port A error pulse"),
        PortDef("b_en_i", "in", None, "Port B enable"),
        PortDef("b_we_i", "in", None, "Port B write enable"),
        PortDef("b_addr_i", "in", "(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0", "Port B address"),
        PortDef("b_wdata_i", "in", "W-1:0", "Port B write data"),
        PortDef("b_be_i", "in", "(W/8)-1:0", "Port B byte enables"),
        PortDef("b_rvalid_o", "out", None, "Port B read valid flag"),
        PortDef("b_rdata_o", "out", "W-1:0", "Port B read data"),
        PortDef("b_error_o", "out", None, "Port B error pulse"),
        PortDef("collision_o", "out", None, "Simultaneous write collision pulse"),
    ],
    systemverilog="""localparam int unsigned BYTES = W / 8;

logic [W-1:0] mem [0:DEPTH-1];

wire a_legal = (32'(a_addr_i) < DEPTH);
wire b_legal = (32'(b_addr_i) < DEPTH);

wire a_write = a_en_i && a_we_i && a_legal;
wire b_write = b_en_i && b_we_i && b_legal;

wire collision = a_write && b_write && (a_addr_i == b_addr_i);

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        a_rvalid_o  <= 1'b0;
        a_rdata_o   <= '0;
        a_error_o   <= 1'b0;
        b_rvalid_o  <= 1'b0;
        b_rdata_o   <= '0;
        b_error_o   <= 1'b0;
        collision_o <= 1'b0;
    end else begin
        collision_o <= collision;

        // Port A
        if (a_en_i) begin
            if (!a_legal || collision) begin
                a_error_o  <= 1'b1;
                a_rvalid_o <= 1'b0;
            end else if (a_we_i) begin
                a_error_o  <= 1'b0;
                a_rvalid_o <= 1'b0;
                for (int unsigned b = 0; b < BYTES; b++) begin
                    if (a_be_i[b]) begin
                        mem[a_addr_i][b*8 +: 8] <= a_wdata_i[b*8 +: 8];
                    end
                end
            end else begin
                a_error_o  <= 1'b0;
                a_rvalid_o <= 1'b1;
                a_rdata_o  <= mem[a_addr_i];
            end
        end else begin
            a_error_o  <= 1'b0;
            a_rvalid_o <= 1'b0;
        end

        // Port B
        if (b_en_i) begin
            if (!b_legal || collision) begin
                b_error_o  <= 1'b1;
                b_rvalid_o <= 1'b0;
            end else if (b_we_i) begin
                b_error_o  <= 1'b0;
                b_rvalid_o <= 1'b0;
                for (int unsigned b = 0; b < BYTES; b++) begin
                    if (b_be_i[b]) begin
                        mem[b_addr_i][b*8 +: 8] <= b_wdata_i[b*8 +: 8];
                    end
                end
            end else begin
                b_error_o  <= 1'b0;
                b_rvalid_o <= 1'b1;
                b_rdata_o  <= mem[b_addr_i];
            end
        end else begin
            b_error_o  <= 1'b0;
            b_rvalid_o <= 1'b0;
        end
    end
end
""",
    presets={
        "default": {"W": "32", "DEPTH": "16"},
        "p1": {"W": "8", "DEPTH": "2"},
        "p2": {"W": "24", "DEPTH": "3"},
        "p3": {"W": "256", "DEPTH": "1024"},
    },
    timing=TimingInfo(latency="1", throughput="1", reset="async active-low control only"),
    limitations=[
        "Simultaneous writes to the exact same address reject both writes and pulse collision_o.",
        "Read+write on same address returns pre-edge old data to reader.",
    ],
    validate_params=_validate_ram_2rw,
    create_reference=lambda p: Ram2rwRef(p),
)


# -----------------------------------------------------------------------------
# 10. rom
# -----------------------------------------------------------------------------
def _validate_rom(params: dict[str, int]) -> list[str]:
    errors = []
    w, depth = params.get("W", 0), params.get("DEPTH", 0)
    init = params.get("INIT", 0)
    if not (1 <= w <= 64):
        errors.append(f"W={w} out of range [1..64]")
    if not (2 <= depth <= 256):
        errors.append(f"DEPTH={depth} out of range [2..256]")
    if init < 0 or init >= (1 << (w * depth)):
        errors.append(f"INIT={init} out of legal bounds [0..2**(W*DEPTH)-1]")
    return errors


class RomRef:
    """Independent reference model for rom."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.depth = params.get("DEPTH", 16)
        self.init = params.get("INIT", 0)
        self.w_mask = (1 << self.w) - 1
        self.last_data = 0

    def reset(self) -> None:
        self.last_data = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        en = inputs.get("en_i", 0) & 1
        addr = inputs.get("addr_i", 0)

        valid = 0
        error = 0
        data = self.last_data

        if en:
            if addr >= self.depth:
                error = 1
            else:
                valid = 1
                data = (self.init >> (addr * self.w)) & self.w_mask
                self.last_data = data

        return {"valid_o": valid, "data_o": data, "error_o": error}


ROM_DEF = ComponentDef(
    id="rom",
    category="storage",
    version="1.0.0",
    summary="Synchronous ROM initialized from packed parameter INIT",
    tags=["rom", "storage"],
    contract_anchor="rom",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Word width in bits", min_value=1, max_value=64),
        ParamDef("DEPTH", "int unsigned", "16", "Memory depth in words", min_value=2, max_value=256),
        ParamDef("INIT", "bit [(W*DEPTH)-1:0]", "0", "Packed memory initial contents", min_value=0, max_value=None),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("en_i", "in", None, "Read enable"),
        PortDef("addr_i", "in", "(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0", "Read address"),
        PortDef("valid_o", "out", None, "Read data valid flag"),
        PortDef("data_o", "out", "W-1:0", "Read data output"),
        PortDef("error_o", "out", None, "Out-of-range address error flag"),
    ],
    systemverilog="""logic [W-1:0] mem [0:DEPTH-1];

initial begin
    for (int unsigned j = 0; j < DEPTH; j++) begin
        mem[j] = INIT[j*W +: W];
    end
end

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        valid_o <= 1'b0;
        data_o  <= '0;
        error_o <= 1'b0;
    end else if (en_i) begin
        if (32'(addr_i) >= DEPTH) begin
            valid_o <= 1'b0;
            error_o <= 1'b1;
        end else begin
            valid_o <= 1'b1;
            data_o  <= mem[addr_i];
            error_o <= 1'b0;
        end
    end else begin
        valid_o <= 1'b0;
        error_o <= 1'b0;
    end
end
""",
    presets={
        "default": {"W": "32", "DEPTH": "16", "INIT": "0"},
        "p1": {"W": "1", "DEPTH": "2", "INIT": "2"},
        "p2": {"W": "8", "DEPTH": "3", "INIT": "197121"},
        "p3": {"W": "64", "DEPTH": "256", "INIT": "0"},
    },
    timing=TimingInfo(latency="1", throughput="1", reset="async active-low"),
    limitations=[
        "Packed parameter INIT stores image directly; no external files or network access.",
        "Disabled hold preserves last registered data output.",
    ],
    validate_params=_validate_rom,
    create_reference=lambda p: RomRef(p),
)


# -----------------------------------------------------------------------------
# 11. register_file_2r1w
# -----------------------------------------------------------------------------
def _validate_register_file_2r1w(params: dict[str, int]) -> list[str]:
    errors = []
    w, depth = params.get("W", 0), params.get("DEPTH", 0)
    zero_reg = params.get("ZERO_REG", 1)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (2 <= depth <= 256):
        errors.append(f"DEPTH={depth} out of range [2..256]")
    if zero_reg not in (0, 1):
        errors.append(f"ZERO_REG={zero_reg} must be 0 or 1")
    return errors


class RegisterFile2r1wRef:
    """Independent reference model for register_file_2r1w."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.depth = params.get("DEPTH", 16)
        self.zero_reg = params.get("ZERO_REG", 1)
        self.w_mask = (1 << self.w) - 1
        self.regs = [0] * self.depth

    def reset(self) -> None:
        self.regs = [0] * self.depth

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"rdata_a_o": 0, "rdata_b_o": 0, "rvalid_a_o": 0, "rvalid_b_o": 0, "write_error_o": 0}

        we = inputs.get("we_i", 0) & 1
        waddr = inputs.get("waddr_i", 0)
        wdata = inputs.get("wdata_i", 0) & self.w_mask

        raddr_a = inputs.get("raddr_a_i", 0)
        raddr_b = inputs.get("raddr_b_i", 0)

        write_error = 0
        if we:
            if waddr >= self.depth:
                write_error = 1
            elif not (self.zero_reg and waddr == 0):
                self.regs[waddr] = wdata

        # Reads reflect new values after edge
        rvalid_a = int(raddr_a < self.depth)
        rvalid_b = int(raddr_b < self.depth)

        if rvalid_a:
            rdata_a = 0 if (self.zero_reg and raddr_a == 0) else self.regs[raddr_a]
        else:
            rdata_a = 0

        if rvalid_b:
            rdata_b = 0 if (self.zero_reg and raddr_b == 0) else self.regs[raddr_b]
        else:
            rdata_b = 0

        return {
            "rdata_a_o": rdata_a,
            "rdata_b_o": rdata_b,
            "rvalid_a_o": rvalid_a,
            "rvalid_b_o": rvalid_b,
            "write_error_o": write_error,
        }


REGISTER_FILE_2R1W_DEF = ComponentDef(
    id="register_file_2r1w",
    category="storage",
    version="1.0.0",
    summary="Two read ports, one write port register file with optional zero register",
    tags=["register_file", "regfile", "storage"],
    contract_anchor="register_file_2r1w",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Register width in bits", min_value=1, max_value=256),
        ParamDef("DEPTH", "int unsigned", "16", "Number of registers", min_value=2, max_value=256),
        ParamDef("ZERO_REG", "int unsigned", "1", "Register 0 wired to zero flag (0 or 1)", min_value=0, max_value=1),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("we_i", "in", None, "Synchronous write enable"),
        PortDef("waddr_i", "in", "(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0", "Write address"),
        PortDef("wdata_i", "in", "W-1:0", "Write data"),
        PortDef("raddr_a_i", "in", "(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0", "Read port A address"),
        PortDef("raddr_b_i", "in", "(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0", "Read port B address"),
        PortDef("rdata_a_o", "out", "W-1:0", "Read port A data output"),
        PortDef("rdata_b_o", "out", "W-1:0", "Read port B data output"),
        PortDef("rvalid_a_o", "out", None, "Read port A address valid"),
        PortDef("rvalid_b_o", "out", None, "Read port B address valid"),
        PortDef("write_error_o", "out", None, "Write address error pulse"),
    ],
    systemverilog="""logic [W-1:0] regs [0:DEPTH-1];

assign rvalid_a_o = (32'(raddr_a_i) < DEPTH);
assign rvalid_b_o = (32'(raddr_b_i) < DEPTH);

assign rdata_a_o = (rvalid_a_o && !((ZERO_REG != 0) && (raddr_a_i == '0))) ? regs[raddr_a_i] : '0;
assign rdata_b_o = (rvalid_b_o && !((ZERO_REG != 0) && (raddr_b_i == '0))) ? regs[raddr_b_i] : '0;

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        /* verilator lint_off BLKSEQ */
        for (int unsigned j = 0; j < DEPTH; j++) begin
            regs[j] = '0;
        end
        /* verilator lint_on BLKSEQ */
        write_error_o <= 1'b0;
    end else if (we_i) begin
        if (32'(waddr_i) >= DEPTH) begin
            write_error_o <= 1'b1;
        end else begin
            write_error_o <= 1'b0;
            if (!((ZERO_REG != 0) && (waddr_i == '0))) begin
                regs[waddr_i] <= wdata_i;
            end
        end
    end else begin
        write_error_o <= 1'b0;
    end
end
""",
    presets={
        "default": {"W": "32", "DEPTH": "16", "ZERO_REG": "1"},
        "p1": {"W": "1", "DEPTH": "2", "ZERO_REG": "0"},
        "p2": {"W": "7", "DEPTH": "3", "ZERO_REG": "1"},
        "p3": {"W": "64", "DEPTH": "256", "ZERO_REG": "0"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="async active-low"),
    limitations=[
        "Asynchronous combinational reads; synchronous registered write.",
        "If ZERO_REG=1, register 0 always evaluates to zero and ignores writes.",
    ],
    validate_params=_validate_register_file_2r1w,
    create_reference=lambda p: RegisterFile2r1wRef(p),
)


# -----------------------------------------------------------------------------
# 12. cam_binary
# -----------------------------------------------------------------------------
def _validate_cam_binary(params: dict[str, int]) -> list[str]:
    errors = []
    kw, vw = params.get("KEY_W", 0), params.get("VALUE_W", 0)
    depth = params.get("DEPTH", 0)
    if not (1 <= kw <= 64):
        errors.append(f"KEY_W={kw} out of range [1..64]")
    if not (1 <= vw <= 256):
        errors.append(f"VALUE_W={vw} out of range [1..256]")
    if not (2 <= depth <= 64):
        errors.append(f"DEPTH={depth} out of range [2..64]")
    return errors


class CamBinaryRef:
    """Independent reference model for cam_binary."""

    def __init__(self, params: dict[str, int]) -> None:
        self.key_w = params.get("KEY_W", 16)
        self.val_w = params.get("VALUE_W", 32)
        self.depth = params.get("DEPTH", 8)
        self.key_mask = (1 << self.key_w) - 1
        self.val_mask = (1 << self.val_w) - 1
        self.valid = [0] * self.depth
        self.keys = [0] * self.depth
        self.values = [0] * self.depth

    def reset(self) -> None:
        self.valid = [0] * self.depth
        self.keys = [0] * self.depth
        self.values = [0] * self.depth

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"hit_o": 0, "multi_o": 0, "index_o": 0, "value_o": 0, "error_o": 0}

        write = inputs.get("write_i", 0) & 1
        delete = inputs.get("delete_i", 0) & 1
        index_i = inputs.get("index_i", 0)
        key_i = inputs.get("key_i", 0) & self.key_mask
        value_i = inputs.get("value_i", 0) & self.val_mask
        search_i = inputs.get("search_i", 0) & self.key_mask

        error = 0
        if delete:
            if index_i >= self.depth:
                error = 1
            else:
                self.valid[index_i] = 0
        elif write:
            if index_i >= self.depth:
                error = 1
            else:
                self.valid[index_i] = 1
                self.keys[index_i] = key_i
                self.values[index_i] = value_i

        # Search matching across active entries
        matches = [j for j in range(self.depth) if self.valid[j] and (self.keys[j] == search_i)]
        hit = int(len(matches) > 0)
        multi = int(len(matches) > 1)
        res_index = matches[0] if matches else 0
        res_value = self.values[matches[0]] if matches else 0

        return {
            "hit_o": hit,
            "multi_o": multi,
            "index_o": res_index,
            "value_o": res_value,
            "error_o": error,
        }


CAM_BINARY_DEF = ComponentDef(
    id="cam_binary",
    category="storage",
    version="1.0.0",
    summary="Binary content-addressable memory with priority index search",
    tags=["cam", "lookup", "search", "storage"],
    contract_anchor="cam_binary",
    phase=2,
    is_stateful=True,
    parameters=[
        ParamDef("KEY_W", "int unsigned", "16", "Key width in bits", min_value=1, max_value=64),
        ParamDef("VALUE_W", "int unsigned", "32", "Payload value width in bits", min_value=1, max_value=256),
        ParamDef("DEPTH", "int unsigned", "8", "Capacity in entries", min_value=2, max_value=64),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("write_i", "in", None, "Write entry enable"),
        PortDef("delete_i", "in", None, "Delete entry enable (priority over write)"),
        PortDef("index_i", "in", "(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0", "Entry slot index"),
        PortDef("key_i", "in", "KEY_W-1:0", "Key to write"),
        PortDef("value_i", "in", "VALUE_W-1:0", "Value to write"),
        PortDef("search_i", "in", "KEY_W-1:0", "Search key input"),
        PortDef("hit_o", "out", None, "Search match flag"),
        PortDef("multi_o", "out", None, "Multiple matches flag"),
        PortDef("index_o", "out", "(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0", "Lowest matching entry index"),
        PortDef("value_o", "out", "VALUE_W-1:0", "Value of lowest matching entry"),
        PortDef("error_o", "out", None, "Out-of-range index error pulse"),
    ],
    systemverilog="""localparam int unsigned INDEX_W = ((DEPTH)<=1 ? 1 : $clog2(DEPTH));

logic valid [0:DEPTH-1];
logic [KEY_W-1:0] keys [0:DEPTH-1];
logic [VALUE_W-1:0] values [0:DEPTH-1];

logic [DEPTH-1:0] match_bits;
always_comb begin
    for (int unsigned j = 0; j < DEPTH; j++) begin
        match_bits[j] = valid[j] && (keys[j] == search_i);
    end
end

wire [31:0] match_count = 32'($countones(match_bits));
assign hit_o   = (match_count > 0);
assign multi_o = (match_count > 1);

always_comb begin
    index_o = '0;
    value_o = '0;
    for (int unsigned j = 0; j < DEPTH; j++) begin
        if (match_bits[j]) begin
            index_o = INDEX_W'(j);
            value_o = values[j];
            break;
        end
    end
end

always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        for (int unsigned j = 0; j < DEPTH; j++) begin
            valid[j] <= 1'b0;
        end
        error_o <= 1'b0;
    end else begin
        if (delete_i) begin
            if (32'(index_i) >= DEPTH) begin
                error_o <= 1'b1;
            end else begin
                error_o <= 1'b0;
                valid[index_i] <= 1'b0;
            end
        end else if (write_i) begin
            if (32'(index_i) >= DEPTH) begin
                error_o <= 1'b1;
            end else begin
                error_o <= 1'b0;
                valid[index_i]  <= 1'b1;
                keys[index_i]   <= key_i;
                values[index_i] <= value_i;
            end
        end else begin
            error_o <= 1'b0;
        end
    end
end
""",
    presets={
        "default": {"KEY_W": "16", "VALUE_W": "32", "DEPTH": "8"},
        "p1": {"KEY_W": "1", "VALUE_W": "1", "DEPTH": "2"},
        "p2": {"KEY_W": "7", "VALUE_W": "9", "DEPTH": "3"},
        "p3": {"KEY_W": "64", "VALUE_W": "64", "DEPTH": "64"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="async active-low"),
    limitations=[
        "Combinational search resolves lowest matching index when multiple keys match.",
        "Delete operation has priority over write operation.",
    ],
    validate_params=_validate_cam_binary,
    create_reference=lambda p: CamBinaryRef(p),
)


PHASE2_STORAGE_COMPONENTS: list[ComponentDef] = [
    FIFO_SYNC_DEF,
    FIFO_FALLTHROUGH_DEF,
    FIFO_ASYNC_DEF,
    FIFO_PACKET_DEF,
    LIFO_STACK_DEF,
    RING_BUFFER_DEF,
    RAM_1RW_DEF,
    RAM_1R1W_DEF,
    RAM_2RW_DEF,
    ROM_DEF,
    REGISTER_FILE_2R1W_DEF,
    CAM_BINARY_DEF,
]

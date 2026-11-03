"""Normative Component definitions and reference models for Phase 1 (32 components)."""

from __future__ import annotations

import math
from typing import Any, Callable

from spec2gds.spec_library.components.models import ComponentDef, ParamDef, PortDef
from spec2gds.spec_library.schemas import TimingInfo


# -----------------------------------------------------------------------------
# 1. mux
# -----------------------------------------------------------------------------
def _validate_mux(params: dict[str, int]) -> list[str]:
    errors = []
    w, n = params.get("W", 0), params.get("N", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (2 <= n <= 16):
        errors.append(f"N={n} out of range [2..16]")
    return errors


class MuxRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.n = params.get("N", 4)
        self.w_mask = (1 << self.w) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data_i = inputs.get("data_i", 0)
        sel_i = inputs.get("sel_i", 0)
        if 0 <= sel_i < self.n:
            lane = (data_i >> (sel_i * self.w)) & self.w_mask
            return {"data_o": lane}
        return {"data_o": 0}


MUX_DEF = ComponentDef(
    id="mux",
    category="logic",
    summary="N-to-1 multiplexer with parameterized data width",
    tags=["combinational", "multiplexer", "mux"],
    contract_anchor="mux",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
        ParamDef("N", "int unsigned", "4", "Number of input lanes", min_value=2, max_value=16),
    ],
    ports=[
        PortDef("data_i", "in", "(N*W)-1:0", "Packed input data lanes"),
        PortDef("sel_i", "in", "(((N)<=1 ? 1 : $clog2(N)) - 1):0", "Lane select input"),
        PortDef("data_o", "out", "W-1:0", "Selected output lane"),
    ],
    systemverilog="assign data_o = (32'(sel_i) < N) ? data_i[sel_i*W +: W] : '0;\n",
    presets={
        "default": {"W": "32", "N": "4"},
        "p1": {"W": "1", "N": "2"},
        "p2": {"W": "7", "N": "3"},
        "p3": {"W": "256", "N": "16"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only; does not infer latches or register stages."],
    validate_params=_validate_mux,
    create_reference=lambda p: MuxRef(p),
)


# -----------------------------------------------------------------------------
# 2. demux
# -----------------------------------------------------------------------------
def _validate_demux(params: dict[str, int]) -> list[str]:
    errors = []
    w, n = params.get("W", 0), params.get("N", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (2 <= n <= 16):
        errors.append(f"N={n} out of range [2..16]")
    return errors


class DemuxRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.n = params.get("N", 4)
        self.w_mask = (1 << self.w) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data_i = inputs.get("data_i", 0) & self.w_mask
        sel_i = inputs.get("sel_i", 0)
        en_i = inputs.get("en_i", 0) & 1
        if en_i and (0 <= sel_i < self.n):
            return {"data_o": data_i << (sel_i * self.w)}
        return {"data_o": 0}


DEMUX_DEF = ComponentDef(
    id="demux",
    category="logic",
    summary="1-to-N demultiplexer with enable and parameterized width",
    tags=["combinational", "demultiplexer", "demux"],
    contract_anchor="demux",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
        ParamDef("N", "int unsigned", "4", "Number of output lanes", min_value=2, max_value=16),
    ],
    ports=[
        PortDef("data_i", "in", "W-1:0", "Input data"),
        PortDef("sel_i", "in", "(((N)<=1 ? 1 : $clog2(N)) - 1):0", "Lane select input"),
        PortDef("en_i", "in", None, "Enable input"),
        PortDef("data_o", "out", "(N*W)-1:0", "Packed output data lanes"),
    ],
    systemverilog="""always_comb begin
    data_o = '0;
    if (en_i && (32'(sel_i) < N)) begin
        data_o[sel_i*W +: W] = data_i;
    end
end
""",
    presets={
        "default": {"W": "32", "N": "4"},
        "p1": {"W": "1", "N": "2"},
        "p2": {"W": "7", "N": "3"},
        "p3": {"W": "256", "N": "16"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only."],
    validate_params=_validate_demux,
    create_reference=lambda p: DemuxRef(p),
)


# -----------------------------------------------------------------------------
# 3. priority_mux
# -----------------------------------------------------------------------------
def _validate_priority_mux(params: dict[str, int]) -> list[str]:
    errors = []
    w, n = params.get("W", 0), params.get("N", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (2 <= n <= 16):
        errors.append(f"N={n} out of range [2..16]")
    return errors


class PriorityMuxRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.n = params.get("N", 4)
        self.w_mask = (1 << self.w) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data_i = inputs.get("data_i", 0)
        req_i = inputs.get("req_i", 0) & ((1 << self.n) - 1)
        for i in range(self.n):
            if (req_i >> i) & 1:
                lane = (data_i >> (i * self.w)) & self.w_mask
                return {"data_o": lane, "valid_o": 1, "index_o": i}
        return {"data_o": 0, "valid_o": 0, "index_o": 0}


PRIORITY_MUX_DEF = ComponentDef(
    id="priority_mux",
    category="logic",
    summary="Priority multiplexer where lowest requested lane wins",
    tags=["arbitration", "combinational", "priority_mux"],
    contract_anchor="priority_mux",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
        ParamDef("N", "int unsigned", "4", "Number of input request lanes", min_value=2, max_value=16),
    ],
    ports=[
        PortDef("data_i", "in", "(N*W)-1:0", "Packed input data lanes"),
        PortDef("req_i", "in", "N-1:0", "Request vector"),
        PortDef("data_o", "out", "W-1:0", "Selected winning data lane"),
        PortDef("valid_o", "out", None, "Valid output indicator"),
        PortDef("index_o", "out", "(((N)<=1 ? 1 : $clog2(N)) - 1):0", "Index of winning lane"),
    ],
    systemverilog="""always_comb begin
    data_o = '0;
    valid_o = 1'b0;
    index_o = '0;
    for (int unsigned i = 0; i < N; i++) begin
        if (req_i[i]) begin
            data_o = data_i[i*W +: W];
            valid_o = 1'b1;
            index_o = (((N)<=1 ? 1 : $clog2(N)))'(i);
            break;
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
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational priority resolution."],
    validate_params=_validate_priority_mux,
    create_reference=lambda p: PriorityMuxRef(p),
)


# -----------------------------------------------------------------------------
# 4. binary_decoder
# -----------------------------------------------------------------------------
def _validate_binary_decoder(params: dict[str, int]) -> list[str]:
    errors = []
    n = params.get("N", 0)
    if not (2 <= n <= 256):
        errors.append(f"N={n} out of range [2..256]")
    return errors


class BinaryDecoderRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.n = params.get("N", 8)

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        index_i = inputs.get("index_i", 0)
        en_i = inputs.get("en_i", 0) & 1
        if en_i and (0 <= index_i < self.n):
            return {"onehot_o": 1 << index_i}
        return {"onehot_o": 0}


BINARY_DECODER_DEF = ComponentDef(
    id="binary_decoder",
    category="logic",
    summary="Binary index to one-hot decoder with enable",
    tags=["combinational", "decoder", "onehot"],
    contract_anchor="binary_decoder",
    parameters=[
        ParamDef("N", "int unsigned", "8", "Number of decoded outputs", min_value=2, max_value=256),
    ],
    ports=[
        PortDef("index_i", "in", "(((N)<=1 ? 1 : $clog2(N)) - 1):0", "Binary index input"),
        PortDef("en_i", "in", None, "Enable input"),
        PortDef("onehot_o", "out", "N-1:0", "One-hot decoded output"),
    ],
    systemverilog="""always_comb begin
    onehot_o = '0;
    if (en_i && (32'(index_i) < N)) begin
        onehot_o[index_i] = 1'b1;
    end
end
""",
    presets={
        "default": {"N": "8"},
        "p1": {"N": "2"},
        "p2": {"N": "3"},
        "p3": {"N": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only."],
    validate_params=_validate_binary_decoder,
    create_reference=lambda p: BinaryDecoderRef(p),
)


# -----------------------------------------------------------------------------
# 5. onehot_encoder
# -----------------------------------------------------------------------------
def _validate_onehot_encoder(params: dict[str, int]) -> list[str]:
    errors = []
    n = params.get("N", 0)
    if not (2 <= n <= 256):
        errors.append(f"N={n} out of range [2..256]")
    return errors


class OnehotEncoderRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.n = params.get("N", 8)

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        onehot_i = inputs.get("onehot_i", 0) & ((1 << self.n) - 1)
        if onehot_i.bit_count() == 1:
            idx = onehot_i.bit_length() - 1
            return {"index_o": idx, "valid_o": 1}
        return {"index_o": 0, "valid_o": 0}


ONEHOT_ENCODER_DEF = ComponentDef(
    id="onehot_encoder",
    category="logic",
    summary="Strict one-hot to binary index encoder",
    tags=["combinational", "encoder", "onehot"],
    contract_anchor="onehot_encoder",
    parameters=[
        ParamDef("N", "int unsigned", "8", "Number of input bits", min_value=2, max_value=256),
    ],
    ports=[
        PortDef("onehot_i", "in", "N-1:0", "One-hot input vector"),
        PortDef("index_o", "out", "(((N)<=1 ? 1 : $clog2(N)) - 1):0", "Binary encoded index"),
        PortDef("valid_o", "out", None, "Valid indicator (high only for exactly one bit set)"),
    ],
    systemverilog="""always_comb begin
    index_o = '0;
    valid_o = 1'b0;
    if ($countones(onehot_i) == 1) begin
        valid_o = 1'b1;
        for (int unsigned i = 0; i < N; i++) begin
            if (onehot_i[i]) begin
                index_o = (((N)<=1 ? 1 : $clog2(N)))'(i);
                break;
            end
        end
    end
end
""",
    presets={
        "default": {"N": "8"},
        "p1": {"N": "2"},
        "p2": {"N": "3"},
        "p3": {"N": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only; rejects zero or multiple active bits."],
    validate_params=_validate_onehot_encoder,
    create_reference=lambda p: OnehotEncoderRef(p),
)


# -----------------------------------------------------------------------------
# 6. priority_encoder
# -----------------------------------------------------------------------------
def _validate_priority_encoder(params: dict[str, int]) -> list[str]:
    errors = []
    n = params.get("N", 0)
    if not (2 <= n <= 256):
        errors.append(f"N={n} out of range [2..256]")
    return errors


class PriorityEncoderRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.n = params.get("N", 8)

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        req_i = inputs.get("req_i", 0) & ((1 << self.n) - 1)
        if req_i != 0:
            lsb = req_i & -req_i
            idx = lsb.bit_length() - 1
            return {"index_o": idx, "valid_o": 1, "grant_o": lsb}
        return {"index_o": 0, "valid_o": 0, "grant_o": 0}


PRIORITY_ENCODER_DEF = ComponentDef(
    id="priority_encoder",
    category="logic",
    summary="Priority encoder where lowest set request bit wins",
    tags=["arbitration", "combinational", "priority_encoder"],
    contract_anchor="priority_encoder",
    parameters=[
        ParamDef("N", "int unsigned", "8", "Number of request inputs", min_value=2, max_value=256),
    ],
    ports=[
        PortDef("req_i", "in", "N-1:0", "Request vector"),
        PortDef("index_o", "out", "(((N)<=1 ? 1 : $clog2(N)) - 1):0", "Lowest set index"),
        PortDef("valid_o", "out", None, "Valid request indicator"),
        PortDef("grant_o", "out", "N-1:0", "One-hot grant vector"),
    ],
    systemverilog="""always_comb begin
    index_o = '0;
    valid_o = 1'b0;
    grant_o = '0;
    for (int unsigned i = 0; i < N; i++) begin
        if (req_i[i]) begin
            index_o = (((N)<=1 ? 1 : $clog2(N)))'(i);
            valid_o = 1'b1;
            grant_o[i] = 1'b1;
            break;
        end
    end
end
""",
    presets={
        "default": {"N": "8"},
        "p1": {"N": "2"},
        "p2": {"N": "3"},
        "p3": {"N": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational priority resolution."],
    validate_params=_validate_priority_encoder,
    create_reference=lambda p: PriorityEncoderRef(p),
)


# -----------------------------------------------------------------------------
# 7. onehot_checker
# -----------------------------------------------------------------------------
def _validate_onehot_checker(params: dict[str, int]) -> list[str]:
    errors = []
    n = params.get("N", 0)
    if not (1 <= n <= 256):
        errors.append(f"N={n} out of range [1..256]")
    return errors


class OnehotCheckerRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.n = params.get("N", 8)

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data_i = inputs.get("data_i", 0) & ((1 << self.n) - 1)
        cnt = data_i.bit_count()
        return {"onehot_o": int(cnt == 1), "onehot0_o": int(cnt <= 1)}


ONEHOT_CHECKER_DEF = ComponentDef(
    id="onehot_checker",
    category="logic",
    summary="One-hot and one-hot-or-zero property checker",
    tags=["checker", "combinational", "onehot"],
    contract_anchor="onehot_checker",
    parameters=[
        ParamDef("N", "int unsigned", "8", "Input vector width", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("data_i", "in", "N-1:0", "Input vector"),
        PortDef("onehot_o", "out", None, "Exactly one bit set"),
        PortDef("onehot0_o", "out", None, "Zero or one bit set"),
    ],
    systemverilog="""assign onehot_o = ($countones(data_i) == 1);
assign onehot0_o = ($countones(data_i) <= 1);
""",
    presets={
        "default": {"N": "8"},
        "p1": {"N": "1"},
        "p2": {"N": "3"},
        "p3": {"N": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only."],
    validate_params=_validate_onehot_checker,
    create_reference=lambda p: OnehotCheckerRef(p),
)


# -----------------------------------------------------------------------------
# 8. leading_zero_count
# -----------------------------------------------------------------------------
def _validate_lzc(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


class LeadingZeroCountRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data_i = inputs.get("data_i", 0) & ((1 << self.w) - 1)
        if data_i == 0:
            return {"count_o": self.w, "zero_o": 1}
        lzc = self.w - data_i.bit_length()
        return {"count_o": lzc, "zero_o": 0}


LEADING_ZERO_COUNT_DEF = ComponentDef(
    id="leading_zero_count",
    category="logic",
    summary="Leading zero counter from MSB with zero detection flag",
    tags=["arithmetic", "combinational", "count", "lzc"],
    contract_anchor="leading_zero_count",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("data_i", "in", "W-1:0", "Input data word"),
        PortDef("count_o", "out", "(((W+1)<=1 ? 1 : $clog2(W+1)) - 1):0", "Leading zero count"),
        PortDef("zero_o", "out", None, "Input is all zero"),
    ],
    systemverilog="""always_comb begin
    zero_o = (data_i == '0);
    count_o = (((W+1)<=1 ? 1 : $clog2(W+1)))'(W);
    for (int unsigned i = 0; i < W; i++) begin
        if (data_i[W-1-i]) begin
            count_o = (((W+1)<=1 ? 1 : $clog2(W+1)))'(i);
            break;
        end
    end
end
""",
    presets={
        "default": {"W": "32"},
        "p1": {"W": "1"},
        "p2": {"W": "8"},
        "p3": {"W": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only."],
    validate_params=_validate_lzc,
    create_reference=lambda p: LeadingZeroCountRef(p),
)


# -----------------------------------------------------------------------------
# 9. trailing_zero_count
# -----------------------------------------------------------------------------
def _validate_tzc(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


class TrailingZeroCountRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data_i = inputs.get("data_i", 0) & ((1 << self.w) - 1)
        if data_i == 0:
            return {"count_o": self.w, "zero_o": 1}
        tzc = (data_i & -data_i).bit_length() - 1
        return {"count_o": tzc, "zero_o": 0}


TRAILING_ZERO_COUNT_DEF = ComponentDef(
    id="trailing_zero_count",
    category="logic",
    summary="Trailing zero counter from LSB with zero detection flag",
    tags=["arithmetic", "combinational", "count", "tzc"],
    contract_anchor="trailing_zero_count",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("data_i", "in", "W-1:0", "Input data word"),
        PortDef("count_o", "out", "(((W+1)<=1 ? 1 : $clog2(W+1)) - 1):0", "Trailing zero count"),
        PortDef("zero_o", "out", None, "Input is all zero"),
    ],
    systemverilog="""always_comb begin
    zero_o = (data_i == '0);
    count_o = (((W+1)<=1 ? 1 : $clog2(W+1)))'(W);
    for (int unsigned i = 0; i < W; i++) begin
        if (data_i[i]) begin
            count_o = (((W+1)<=1 ? 1 : $clog2(W+1)))'(i);
            break;
        end
    end
end
""",
    presets={
        "default": {"W": "32"},
        "p1": {"W": "1"},
        "p2": {"W": "8"},
        "p3": {"W": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only."],
    validate_params=_validate_tzc,
    create_reference=lambda p: TrailingZeroCountRef(p),
)


# -----------------------------------------------------------------------------
# 10. population_count
# -----------------------------------------------------------------------------
def _validate_popcount(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


class PopulationCountRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data_i = inputs.get("data_i", 0) & ((1 << self.w) - 1)
        return {"count_o": data_i.bit_count()}


POPULATION_COUNT_DEF = ComponentDef(
    id="population_count",
    category="logic",
    summary="Population count returning the number of set bits",
    tags=["arithmetic", "combinational", "count", "popcount"],
    contract_anchor="population_count",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("data_i", "in", "W-1:0", "Input data word"),
        PortDef("count_o", "out", "(((W+1)<=1 ? 1 : $clog2(W+1)) - 1):0", "Number of set bits"),
    ],
    systemverilog="assign count_o = (((W+1)<=1 ? 1 : $clog2(W+1)))'($countones(data_i));\n",
    presets={
        "default": {"W": "32"},
        "p1": {"W": "1"},
        "p2": {"W": "8"},
        "p3": {"W": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only."],
    validate_params=_validate_popcount,
    create_reference=lambda p: PopulationCountRef(p),
)


# -----------------------------------------------------------------------------
# 11. bit_reverse
# -----------------------------------------------------------------------------
def _validate_bit_reverse(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


class BitReverseRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data_i = inputs.get("data_i", 0)
        res = 0
        for i in range(self.w):
            if (data_i >> (self.w - 1 - i)) & 1:
                res |= 1 << i
        return {"data_o": res}


BIT_REVERSE_DEF = ComponentDef(
    id="bit_reverse",
    category="logic",
    summary="Bit reversal reflecting bit order across the word width",
    tags=["combinational", "permutation", "reverse"],
    contract_anchor="bit_reverse",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("data_i", "in", "W-1:0", "Input word"),
        PortDef("data_o", "out", "W-1:0", "Bit-reversed output word"),
    ],
    systemverilog="""always_comb begin
    for (int unsigned i = 0; i < W; i++) begin
        data_o[i] = data_i[W-1-i];
    end
end
""",
    presets={
        "default": {"W": "32"},
        "p1": {"W": "1"},
        "p2": {"W": "7"},
        "p3": {"W": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Pure wire permutation."],
    validate_params=_validate_bit_reverse,
    create_reference=lambda p: BitReverseRef(p),
)


# -----------------------------------------------------------------------------
# 12. byte_reverse
# -----------------------------------------------------------------------------
def _validate_byte_reverse(params: dict[str, int]) -> list[str]:
    errors = []
    b = params.get("BYTES", 0)
    if not (1 <= b <= 32):
        errors.append(f"BYTES={b} out of range [1..32]")
    return errors


class ByteReverseRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.bytes = params.get("BYTES", 4)

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data_i = inputs.get("data_i", 0)
        res = 0
        for i in range(self.bytes):
            byte_val = (data_i >> ((self.bytes - 1 - i) * 8)) & 0xFF
            res |= byte_val << (i * 8)
        return {"data_o": res}


BYTE_REVERSE_DEF = ComponentDef(
    id="byte_reverse",
    category="logic",
    summary="Byte order reversal preserving bit order within each byte",
    tags=["combinational", "endianness", "reverse"],
    contract_anchor="byte_reverse",
    parameters=[
        ParamDef("BYTES", "int unsigned", "4", "Number of bytes", min_value=1, max_value=32),
    ],
    ports=[
        PortDef("data_i", "in", "(8*BYTES)-1:0", "Input bytes"),
        PortDef("data_o", "out", "(8*BYTES)-1:0", "Byte-reversed output"),
    ],
    systemverilog="""always_comb begin
    for (int unsigned i = 0; i < BYTES; i++) begin
        data_o[i*8 +: 8] = data_i[(BYTES-1-i)*8 +: 8];
    end
end
""",
    presets={
        "default": {"BYTES": "4"},
        "p1": {"BYTES": "1"},
        "p2": {"BYTES": "3"},
        "p3": {"BYTES": "32"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Pure wire permutation; assumes 8-bit bytes."],
    validate_params=_validate_byte_reverse,
    create_reference=lambda p: ByteReverseRef(p),
)


# -----------------------------------------------------------------------------
# 13. barrel_shift
# -----------------------------------------------------------------------------
def _validate_barrel_shift(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


class BarrelShiftRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.mask = (1 << self.w) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data_i = inputs.get("data_i", 0) & self.mask
        amount_i = inputs.get("amount_i", 0)
        right_i = inputs.get("right_i", 0) & 1
        arith_i = inputs.get("arith_i", 0) & 1

        sign_bit = (data_i >> (self.w - 1)) & 1
        if amount_i >= self.w:
            if right_i and arith_i and sign_bit:
                return {"data_o": self.mask}
            return {"data_o": 0}
        if not right_i:
            return {"data_o": (data_i << amount_i) & self.mask}
        if arith_i and sign_bit:
            shifted = (data_i >> amount_i) | (((1 << amount_i) - 1) << (self.w - amount_i))
            return {"data_o": shifted & self.mask}
        return {"data_o": (data_i >> amount_i) & self.mask}


BARREL_SHIFT_DEF = ComponentDef(
    id="barrel_shift",
    category="logic",
    summary="Universal barrel shifter with direction and arithmetic mode controls",
    tags=["arithmetic", "combinational", "shifter"],
    contract_anchor="barrel_shift",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("data_i", "in", "W-1:0", "Data to shift"),
        PortDef("amount_i", "in", "(((W+1)<=1 ? 1 : $clog2(W+1)) - 1):0", "Shift amount"),
        PortDef("right_i", "in", None, "Direction control: 1=right, 0=left"),
        PortDef("arith_i", "in", None, "Arithmetic mode: 1=sign extend right shifts"),
        PortDef("data_o", "out", "W-1:0", "Shifted output"),
    ],
    systemverilog="""always_comb begin
    if (32'(amount_i) >= W) begin
        if (right_i && arith_i) begin
            data_o = {W{data_i[W-1]}};
        end else begin
            data_o = '0;
        end
    end else if (!right_i) begin
        data_o = data_i << amount_i;
    end else begin
        if (arith_i) begin
            data_o = $signed(data_i) >>> amount_i;
        end else begin
            data_o = data_i >> amount_i;
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
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only."],
    validate_params=_validate_barrel_shift,
    create_reference=lambda p: BarrelShiftRef(p),
)


# -----------------------------------------------------------------------------
# 14. rotate
# -----------------------------------------------------------------------------
def _validate_rotate(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


class RotateRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.mask = (1 << self.w) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data_i = inputs.get("data_i", 0) & self.mask
        amount_i = inputs.get("amount_i", 0)
        right_i = inputs.get("right_i", 0) & 1

        if self.w <= 1:
            return {"data_o": data_i}
        amt = amount_i % self.w
        if amt == 0:
            return {"data_o": data_i}
        if right_i:
            res = (data_i >> amt) | (data_i << (self.w - amt))
        else:
            res = (data_i << amt) | (data_i >> (self.w - amt))
        return {"data_o": res & self.mask}


ROTATE_DEF = ComponentDef(
    id="rotate",
    category="logic",
    summary="Bitwise rotator with direction control and modulo shift",
    tags=["combinational", "permutation", "rotate", "shifter"],
    contract_anchor="rotate",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Data width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("data_i", "in", "W-1:0", "Data to rotate"),
        PortDef("amount_i", "in", "(((W)<=1 ? 1 : $clog2(W)) - 1):0", "Rotation amount"),
        PortDef("right_i", "in", None, "Direction control: 1=right, 0=left"),
        PortDef("data_o", "out", "W-1:0", "Rotated output"),
    ],
    systemverilog="""always_comb begin
    if (W <= 1) begin
        data_o = data_i;
    end else begin
        int unsigned shift_amt;
        shift_amt = 32'(amount_i) % W;
        if (shift_amt == 0) begin
            data_o = data_i;
        end else if (right_i) begin
            data_o = (data_i >> shift_amt) | (data_i << (W - shift_amt));
        end else begin
            data_o = (data_i << shift_amt) | (data_i >> (W - shift_amt));
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
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only; W=1 is identity."],
    validate_params=_validate_rotate,
    create_reference=lambda p: RotateRef(p),
)


# -----------------------------------------------------------------------------
# 15. sign_extend
# -----------------------------------------------------------------------------
def _validate_sign_extend(params: dict[str, int]) -> list[str]:
    errors = []
    iw = params.get("IW", 0)
    ow = params.get("OW", 0)
    if not (1 <= iw <= 256):
        errors.append(f"IW={iw} out of range [1..256]")
    if not (iw <= ow <= 256):
        errors.append(f"OW={ow} must be in [{iw}..256]")
    return errors


class SignExtendRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.iw = params.get("IW", 8)
        self.ow = params.get("OW", 32)
        self.imask = (1 << self.iw) - 1
        self.omask = (1 << self.ow) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data_i = inputs.get("data_i", 0) & self.imask
        sign_bit = (data_i >> (self.iw - 1)) & 1
        if sign_bit and self.ow > self.iw:
            ext = (((1 << (self.ow - self.iw)) - 1) << self.iw) | data_i
            return {"data_o": ext & self.omask}
        return {"data_o": data_i}


SIGN_EXTEND_DEF = ComponentDef(
    id="sign_extend",
    category="logic",
    summary="Sign extender replicating MSB over upper lanes",
    tags=["arithmetic", "combinational", "sign_extend"],
    contract_anchor="sign_extend",
    parameters=[
        ParamDef("IW", "int unsigned", "8", "Input data width", min_value=1, max_value=256),
        ParamDef("OW", "int unsigned", "32", "Output data width (>= IW)", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("data_i", "in", "IW-1:0", "Narrow input word"),
        PortDef("data_o", "out", "OW-1:0", "Sign-extended output word"),
    ],
    systemverilog="assign data_o = OW'($signed(data_i));\n",
    presets={
        "default": {"IW": "8", "OW": "32"},
        "p1": {"IW": "1", "OW": "1"},
        "p2": {"IW": "7", "OW": "13"},
        "p3": {"IW": "128", "OW": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only; OW must be greater than or equal to IW."],
    validate_params=_validate_sign_extend,
    create_reference=lambda p: SignExtendRef(p),
)


# -----------------------------------------------------------------------------
# 16. zero_extend
# -----------------------------------------------------------------------------
def _validate_zero_extend(params: dict[str, int]) -> list[str]:
    errors = []
    iw = params.get("IW", 0)
    ow = params.get("OW", 0)
    if not (1 <= iw <= 256):
        errors.append(f"IW={iw} out of range [1..256]")
    if not (iw <= ow <= 256):
        errors.append(f"OW={ow} must be in [{iw}..256]")
    return errors


class ZeroExtendRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.iw = params.get("IW", 8)
        self.imask = (1 << self.iw) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        return {"data_o": inputs.get("data_i", 0) & self.imask}


ZERO_EXTEND_DEF = ComponentDef(
    id="zero_extend",
    category="logic",
    summary="Zero extender inserting zero bits above lower lanes",
    tags=["arithmetic", "combinational", "zero_extend"],
    contract_anchor="zero_extend",
    parameters=[
        ParamDef("IW", "int unsigned", "8", "Input data width", min_value=1, max_value=256),
        ParamDef("OW", "int unsigned", "32", "Output data width (>= IW)", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("data_i", "in", "IW-1:0", "Narrow input word"),
        PortDef("data_o", "out", "OW-1:0", "Zero-extended output word"),
    ],
    systemverilog="assign data_o = OW'(data_i);\n",
    presets={
        "default": {"IW": "8", "OW": "32"},
        "p1": {"IW": "1", "OW": "1"},
        "p2": {"IW": "7", "OW": "13"},
        "p3": {"IW": "128", "OW": "256"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only; OW must be greater than or equal to IW."],
    validate_params=_validate_zero_extend,
    create_reference=lambda p: ZeroExtendRef(p),
)


# -----------------------------------------------------------------------------
# 17. bit_mask
# -----------------------------------------------------------------------------
def _validate_bit_mask(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


class BitMaskRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.mask = (1 << self.w) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        start = inputs.get("start_i", 0)
        length = inputs.get("length_i", 0)
        if start >= self.w or length <= 0:
            return {"mask_o": 0}
        res = 0
        for j in range(self.w):
            if start <= j < (start + length):
                res |= 1 << j
        return {"mask_o": res & self.mask}


BIT_MASK_DEF = ComponentDef(
    id="bit_mask",
    category="logic",
    summary="Contiguous bit mask generator with start index and length",
    tags=["combinational", "mask"],
    contract_anchor="bit_mask",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Mask width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("start_i", "in", "(((W)<=1 ? 1 : $clog2(W)) - 1):0", "Starting bit position"),
        PortDef("length_i", "in", "(((W+1)<=1 ? 1 : $clog2(W+1)) - 1):0", "Number of bits to set"),
        PortDef("mask_o", "out", "W-1:0", "Generated bit mask"),
    ],
    systemverilog="""always_comb begin
    mask_o = '0;
    if (32'(start_i) < W) begin
        for (int unsigned j = 0; j < W; j++) begin
            if ((j >= 32'(start_i)) && (j < (32'(start_i) + 32'(length_i)))) begin
                mask_o[j] = 1'b1;
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
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only; start positions out of range return zero."],
    validate_params=_validate_bit_mask,
    create_reference=lambda p: BitMaskRef(p),
)


# -----------------------------------------------------------------------------
# 18. register
# -----------------------------------------------------------------------------
def _validate_register(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


class RegisterRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.mask = (1 << self.w) - 1
        self.q = 0

    def reset(self) -> None:
        self.q = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        d = inputs.get("d_i", 0) & self.mask
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.q = 0
        else:
            self.q = d
        return {"q_o": self.q}


REGISTER_DEF = ComponentDef(
    id="register",
    category="state",
    summary="Basic boundary-reset D flip-flop register",
    tags=["dff", "register", "sequential"],
    contract_anchor="register",
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Register width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("d_i", "in", "W-1:0", "Data input"),
        PortDef("q_o", "out", "W-1:0", "Registered data output"),
    ],
    systemverilog="""always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        q_o <= '0;
    end else begin
        q_o <= d_i;
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
    limitations=["Asynchronous active-low reset; single clock domain."],
    validate_params=_validate_register,
    create_reference=lambda p: RegisterRef(p),
)


# -----------------------------------------------------------------------------
# 19. register_enable
# -----------------------------------------------------------------------------
def _validate_register_enable(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


class RegisterEnableRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.mask = (1 << self.w) - 1
        self.q = 0

    def reset(self) -> None:
        self.q = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        d = inputs.get("d_i", 0) & self.mask
        en = inputs.get("en_i", 0) & 1
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.q = 0
        elif en:
            self.q = d
        return {"q_o": self.q}


REGISTER_ENABLE_DEF = ComponentDef(
    id="register_enable",
    category="state",
    summary="Register with synchronous clock enable and asynchronous reset",
    tags=["enable", "register", "sequential"],
    contract_anchor="register_enable",
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Register width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("d_i", "in", "W-1:0", "Data input"),
        PortDef("en_i", "in", None, "Clock enable"),
        PortDef("q_o", "out", "W-1:0", "Registered data output"),
    ],
    systemverilog="""always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        q_o <= '0;
    end else if (en_i) begin
        q_o <= d_i;
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
    limitations=["Asynchronous active-low reset; hold when disabled."],
    validate_params=_validate_register_enable,
    create_reference=lambda p: RegisterEnableRef(p),
)


# -----------------------------------------------------------------------------
# 20. register_sync_reset
# -----------------------------------------------------------------------------
def _validate_register_sync_reset(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    rv = params.get("RESET_VALUE", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (0 <= rv < (1 << w)):
        errors.append(f"RESET_VALUE={rv} out of range [0..2**W-1]")
    return errors


class RegisterSyncResetRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.mask = (1 << self.w) - 1
        self.rv = params.get("RESET_VALUE", 0) & self.mask
        self.q = self.rv

    def reset(self) -> None:
        self.q = self.rv

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        d = inputs.get("d_i", 0) & self.mask
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.q = self.rv
        else:
            self.q = d
        return {"q_o": self.q}


REGISTER_SYNC_RESET_DEF = ComponentDef(
    id="register_sync_reset",
    category="state",
    summary="Register with synchronous active-low reset and custom reset value",
    tags=["register", "sequential", "sync_reset"],
    contract_anchor="register_sync_reset",
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Register width in bits", min_value=1, max_value=256),
        ParamDef("RESET_VALUE", "int unsigned", "0", "Reset value", min_value=0, max_value=None),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Synchronous active-low reset"),
        PortDef("d_i", "in", "W-1:0", "Data input"),
        PortDef("q_o", "out", "W-1:0", "Registered data output"),
    ],
    systemverilog="""always_ff @(posedge clk_i) begin
    if (!rst_ni) begin
        q_o <= W'(RESET_VALUE);
    end else begin
        q_o <= d_i;
    end
end
""",
    presets={
        "default": {"W": "32", "RESET_VALUE": "0"},
        "p1": {"W": "1", "RESET_VALUE": "1"},
        "p2": {"W": "7", "RESET_VALUE": "85"},
        "p3": {"W": "256", "RESET_VALUE": "0"},
    },
    timing=TimingInfo(latency="1", throughput="1", reset="sync active-low"),
    limitations=["Reset is evaluated strictly at the rising clock edge."],
    validate_params=_validate_register_sync_reset,
    create_reference=lambda p: RegisterSyncResetRef(p),
)


# -----------------------------------------------------------------------------
# 21. register_async_reset
# -----------------------------------------------------------------------------
def _validate_register_async_reset(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    rv = params.get("RESET_VALUE", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (0 <= rv < (1 << w)):
        errors.append(f"RESET_VALUE={rv} out of range [0..2**W-1]")
    return errors


class RegisterAsyncResetRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.mask = (1 << self.w) - 1
        self.rv = params.get("RESET_VALUE", 0) & self.mask
        self.q = self.rv

    def reset(self) -> None:
        self.q = self.rv

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        d = inputs.get("d_i", 0) & self.mask
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.q = self.rv
        else:
            self.q = d
        return {"q_o": self.q}


REGISTER_ASYNC_RESET_DEF = ComponentDef(
    id="register_async_reset",
    category="state",
    summary="Register with asynchronous active-low reset and custom reset value",
    tags=["async_reset", "register", "sequential"],
    contract_anchor="register_async_reset",
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Register width in bits", min_value=1, max_value=256),
        ParamDef("RESET_VALUE", "int unsigned", "0", "Reset value", min_value=0, max_value=None),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("d_i", "in", "W-1:0", "Data input"),
        PortDef("q_o", "out", "W-1:0", "Registered data output"),
    ],
    systemverilog="""always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        q_o <= W'(RESET_VALUE);
    end else begin
        q_o <= d_i;
    end
end
""",
    presets={
        "default": {"W": "32", "RESET_VALUE": "0"},
        "p1": {"W": "1", "RESET_VALUE": "1"},
        "p2": {"W": "7", "RESET_VALUE": "85"},
        "p3": {"W": "256", "RESET_VALUE": "0"},
    },
    timing=TimingInfo(latency="1", throughput="1", reset="async active-low"),
    limitations=["Asynchronous reset updates output immediately on assertion."],
    validate_params=_validate_register_async_reset,
    create_reference=lambda p: RegisterAsyncResetRef(p),
)


# -----------------------------------------------------------------------------
# 22. shift_register
# -----------------------------------------------------------------------------
def _validate_shift_register(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    stages = params.get("STAGES", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (1 <= stages <= 32):
        errors.append(f"STAGES={stages} out of range [1..32]")
    return errors


class ShiftRegisterRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.stages = params.get("STAGES", 4)
        self.mask = (1 << self.w) - 1
        self.mem = [0] * self.stages

    def reset(self) -> None:
        self.mem = [0] * self.stages

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        d = inputs.get("d_i", 0) & self.mask
        en = inputs.get("en_i", 0) & 1
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.mem = [0] * self.stages
        elif en:
            self.mem = [d] + self.mem[:-1]
        taps = 0
        for i, val in enumerate(self.mem):
            taps |= val << (i * self.w)
        return {"q_o": self.mem[-1], "taps_o": taps}


SHIFT_REGISTER_DEF = ComponentDef(
    id="shift_register",
    category="state",
    summary="Serial/parallel-tap shift register with enable",
    tags=["register", "sequential", "shift_register"],
    contract_anchor="shift_register",
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Word width in bits", min_value=1, max_value=256),
        ParamDef("STAGES", "int unsigned", "4", "Number of shift stages", min_value=1, max_value=32),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("en_i", "in", None, "Shift enable"),
        PortDef("d_i", "in", "W-1:0", "Serial data input"),
        PortDef("q_o", "out", "W-1:0", "Oldest stage output"),
        PortDef("taps_o", "out", "(STAGES*W)-1:0", "Packed intermediate tap outputs"),
    ],
    systemverilog="""logic [W-1:0] shift_mem [0:STAGES-1];
always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        for (int unsigned i = 0; i < STAGES; i++) begin
            shift_mem[i] <= '0;
        end
    end else if (en_i) begin
        shift_mem[0] <= d_i;
        for (int unsigned i = 1; i < STAGES; i++) begin
            shift_mem[i] <= shift_mem[i-1];
        end
    end
end
assign q_o = shift_mem[STAGES-1];
always_comb begin
    for (int unsigned i = 0; i < STAGES; i++) begin
        taps_o[i*W +: W] = shift_mem[i];
    end
end
""",
    presets={
        "default": {"W": "32", "STAGES": "4"},
        "p1": {"W": "1", "STAGES": "1"},
        "p2": {"W": "7", "STAGES": "3"},
        "p3": {"W": "64", "STAGES": "32"},
    },
    timing=TimingInfo(latency="STAGES", throughput="1", reset="async active-low"),
    limitations=["Asynchronous reset clears all stages to zero."],
    validate_params=_validate_shift_register,
    create_reference=lambda p: ShiftRegisterRef(p),
)


# -----------------------------------------------------------------------------
# 23. pipeline_delay
# -----------------------------------------------------------------------------
def _validate_pipeline_delay(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    stages = params.get("STAGES", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    if not (1 <= stages <= 16):
        errors.append(f"STAGES={stages} out of range [1..16]")
    return errors


class PipelineDelayRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.stages = params.get("STAGES", 2)
        self.mask = (1 << self.w) - 1
        self.data_pipe = [0] * self.stages
        self.valid_pipe = [0] * self.stages

    def reset(self) -> None:
        self.data_pipe = [0] * self.stages
        self.valid_pipe = [0] * self.stages

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        d = inputs.get("data_i", 0) & self.mask
        v = inputs.get("valid_i", 0) & 1
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.data_pipe = [0] * self.stages
            self.valid_pipe = [0] * self.stages
        else:
            self.data_pipe = [d] + self.data_pipe[:-1]
            self.valid_pipe = [v] + self.valid_pipe[:-1]
        return {"data_o": self.data_pipe[-1], "valid_o": self.valid_pipe[-1]}


PIPELINE_DELAY_DEF = ComponentDef(
    id="pipeline_delay",
    category="state",
    summary="Unstalled multi-stage pipeline delay with valid framing",
    tags=["delay", "pipeline", "sequential"],
    contract_anchor="pipeline_delay",
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Payload width in bits", min_value=1, max_value=256),
        ParamDef("STAGES", "int unsigned", "2", "Number of delay stages", min_value=1, max_value=16),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("valid_i", "in", None, "Input valid framing"),
        PortDef("data_i", "in", "W-1:0", "Input payload data"),
        PortDef("valid_o", "out", None, "Delayed output valid"),
        PortDef("data_o", "out", "W-1:0", "Delayed output data"),
    ],
    systemverilog="""logic [W-1:0] data_pipe [0:STAGES-1];
logic valid_pipe [0:STAGES-1];
always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        for (int unsigned i = 0; i < STAGES; i++) begin
            data_pipe[i] <= '0;
            valid_pipe[i] <= 1'b0;
        end
    end else begin
        data_pipe[0] <= data_i;
        valid_pipe[0] <= valid_i;
        for (int unsigned i = 1; i < STAGES; i++) begin
            data_pipe[i] <= data_pipe[i-1];
            valid_pipe[i] <= valid_pipe[i-1];
        end
    end
end
assign data_o = data_pipe[STAGES-1];
assign valid_o = valid_pipe[STAGES-1];
""",
    presets={
        "default": {"W": "32", "STAGES": "2"},
        "p1": {"W": "1", "STAGES": "1"},
        "p2": {"W": "7", "STAGES": "3"},
        "p3": {"W": "64", "STAGES": "16"},
    },
    timing=TimingInfo(latency="STAGES", throughput="1", reset="async active-low"),
    limitations=["Unstalled pipeline; cannot backpressure producer."],
    validate_params=_validate_pipeline_delay,
    create_reference=lambda p: PipelineDelayRef(p),
)


# -----------------------------------------------------------------------------
# 24. counter_up
# -----------------------------------------------------------------------------
def _validate_counter_up(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 64):
        errors.append(f"W={w} out of range [1..64]")
    return errors


class CounterUpRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.mask = (1 << self.w) - 1
        self.count = 0
        self.wrap = 0

    def reset(self) -> None:
        self.count = 0
        self.wrap = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        en = inputs.get("en_i", 0) & 1
        clr = inputs.get("clear_i", 0) & 1
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.count = 0
            self.wrap = 0
        elif clr:
            self.count = 0
            self.wrap = 0
        elif en:
            if self.count == self.mask:
                self.count = 0
                self.wrap = 1
            else:
                self.count = (self.count + 1) & self.mask
                self.wrap = 0
        else:
            self.wrap = 0
        return {"count_o": self.count, "wrap_o": self.wrap}


COUNTER_UP_DEF = ComponentDef(
    id="counter_up",
    category="state",
    summary="Binary up-counter with enable, synchronous clear, and wrap pulse",
    tags=["counter", "sequential"],
    contract_anchor="counter_up",
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Counter width in bits", min_value=1, max_value=64),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("en_i", "in", None, "Count enable"),
        PortDef("clear_i", "in", None, "Synchronous clear (priority over enable)"),
        PortDef("count_o", "out", "W-1:0", "Current count output"),
        PortDef("wrap_o", "out", None, "Terminal wrap pulse (one edge at max -> 0)"),
    ],
    systemverilog="""localparam logic [W-1:0] MAX_VAL = '1;
always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        count_o <= '0;
        wrap_o <= 1'b0;
    end else if (clear_i) begin
        count_o <= '0;
        wrap_o <= 1'b0;
    end else if (en_i) begin
        if (count_o == MAX_VAL) begin
            count_o <= '0;
            wrap_o <= 1'b1;
        end else begin
            count_o <= count_o + 1'b1;
            wrap_o <= 1'b0;
        end
    end else begin
        wrap_o <= 1'b0;
    end
end
""",
    presets={
        "default": {"W": "32"},
        "p1": {"W": "1"},
        "p2": {"W": "5"},
        "p3": {"W": "64"},
    },
    timing=TimingInfo(latency="1", throughput="1", reset="async active-low"),
    limitations=["Clear takes precedence over enable."],
    validate_params=_validate_counter_up,
    create_reference=lambda p: CounterUpRef(p),
)


# -----------------------------------------------------------------------------
# 25. counter_up_down
# -----------------------------------------------------------------------------
def _validate_counter_up_down(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 64):
        errors.append(f"W={w} out of range [1..64]")
    return errors


class CounterUpDownRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.mask = (1 << self.w) - 1
        self.count = 0
        self.wrap = 0

    def reset(self) -> None:
        self.count = 0
        self.wrap = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        up = inputs.get("up_i", 0) & 1
        down = inputs.get("down_i", 0) & 1
        clr = inputs.get("clear_i", 0) & 1
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.count = 0
            self.wrap = 0
        elif clr:
            self.count = 0
            self.wrap = 0
        elif up and not down:
            if self.count == self.mask:
                self.count = 0
                self.wrap = 1
            else:
                self.count = (self.count + 1) & self.mask
                self.wrap = 0
        elif down and not up:
            if self.count == 0:
                self.count = self.mask
                self.wrap = 1
            else:
                self.count = (self.count - 1) & self.mask
                self.wrap = 0
        else:
            self.wrap = 0
        return {"count_o": self.count, "wrap_o": self.wrap}


COUNTER_UP_DOWN_DEF = ComponentDef(
    id="counter_up_down",
    category="state",
    summary="Bidirectional up/down counter with clear and wrap pulse",
    tags=["counter", "sequential", "up_down"],
    contract_anchor="counter_up_down",
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Counter width in bits", min_value=1, max_value=64),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("up_i", "in", None, "Count up enable"),
        PortDef("down_i", "in", None, "Count down enable"),
        PortDef("clear_i", "in", None, "Synchronous clear"),
        PortDef("count_o", "out", "W-1:0", "Current count output"),
        PortDef("wrap_o", "out", None, "Wrap pulse on max->0 or 0->max"),
    ],
    systemverilog="""localparam logic [W-1:0] MAX_VAL = '1;
always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        count_o <= '0;
        wrap_o <= 1'b0;
    end else if (clear_i) begin
        count_o <= '0;
        wrap_o <= 1'b0;
    end else if (up_i && !down_i) begin
        if (count_o == MAX_VAL) begin
            count_o <= '0;
            wrap_o <= 1'b1;
        end else begin
            count_o <= count_o + 1'b1;
            wrap_o <= 1'b0;
        end
    end else if (down_i && !up_i) begin
        if (count_o == '0) begin
            count_o <= MAX_VAL;
            wrap_o <= 1'b1;
        end else begin
            count_o <= count_o - 1'b1;
            wrap_o <= 1'b0;
        end
    end else begin
        wrap_o <= 1'b0;
    end
end
""",
    presets={
        "default": {"W": "32"},
        "p1": {"W": "1"},
        "p2": {"W": "5"},
        "p3": {"W": "64"},
    },
    timing=TimingInfo(latency="1", throughput="1", reset="async active-low"),
    limitations=["Clear has highest priority; simultaneous up and down holds value."],
    validate_params=_validate_counter_up_down,
    create_reference=lambda p: CounterUpDownRef(p),
)


# -----------------------------------------------------------------------------
# 26. counter_saturating
# -----------------------------------------------------------------------------
def _validate_counter_saturating(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 64):
        errors.append(f"W={w} out of range [1..64]")
    return errors


class CounterSaturatingRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.mask = (1 << self.w) - 1
        self.count = 0

    def reset(self) -> None:
        self.count = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        up = inputs.get("up_i", 0) & 1
        down = inputs.get("down_i", 0) & 1
        clr = inputs.get("clear_i", 0) & 1
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.count = 0
        elif clr:
            self.count = 0
        elif up and not down:
            if self.count < self.mask:
                self.count += 1
        elif down and not up:
            if self.count > 0:
                self.count -= 1
        return {
            "count_o": self.count,
            "at_min_o": int(self.count == 0),
            "at_max_o": int(self.count == self.mask),
        }


COUNTER_SATURATING_DEF = ComponentDef(
    id="counter_saturating",
    category="state",
    summary="Saturating bidirectional counter clamped at zero and maximum count",
    tags=["counter", "saturating", "sequential"],
    contract_anchor="counter_saturating",
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "32", "Counter width in bits", min_value=1, max_value=64),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("up_i", "in", None, "Increment enable"),
        PortDef("down_i", "in", None, "Decrement enable"),
        PortDef("clear_i", "in", None, "Synchronous clear"),
        PortDef("count_o", "out", "W-1:0", "Current count output"),
        PortDef("at_min_o", "out", None, "Clamped at zero flag"),
        PortDef("at_max_o", "out", None, "Clamped at maximum flag"),
    ],
    systemverilog="""localparam logic [W-1:0] MAX_VAL = '1;
always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        count_o <= '0;
    end else if (clear_i) begin
        count_o <= '0;
    end else if (up_i && !down_i) begin
        if (count_o != MAX_VAL) begin
            count_o <= count_o + 1'b1;
        end
    end else if (down_i && !up_i) begin
        if (count_o != '0) begin
            count_o <= count_o - 1'b1;
        end
    end
end
assign at_min_o = (count_o == '0);
assign at_max_o = (count_o == MAX_VAL);
""",
    presets={
        "default": {"W": "32"},
        "p1": {"W": "1"},
        "p2": {"W": "5"},
        "p3": {"W": "64"},
    },
    timing=TimingInfo(latency="1", throughput="1", reset="async active-low"),
    limitations=["Clamps rather than wrapping."],
    validate_params=_validate_counter_saturating,
    create_reference=lambda p: CounterSaturatingRef(p),
)


# -----------------------------------------------------------------------------
# 27. counter_modulo
# -----------------------------------------------------------------------------
def _validate_counter_modulo(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    mod = params.get("MODULUS", 0)
    if not (1 <= w <= 64):
        errors.append(f"W={w} out of range [1..64]")
    if not (2 <= mod <= (1 << w)):
        errors.append(f"MODULUS={mod} out of range [2..2**W]")
    return errors


class CounterModuloRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 8)
        self.modulus = params.get("MODULUS", 16)
        self.mask = (1 << self.w) - 1
        self.count = 0
        self.wrap = 0

    def reset(self) -> None:
        self.count = 0
        self.wrap = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        en = inputs.get("en_i", 0) & 1
        clr = inputs.get("clear_i", 0) & 1
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.count = 0
            self.wrap = 0
        elif clr:
            self.count = 0
            self.wrap = 0
        elif en:
            if self.count >= (self.modulus - 1):
                self.count = 0
                self.wrap = 1
            else:
                self.count += 1
                self.wrap = 0
        else:
            self.wrap = 0
        return {"count_o": self.count & self.mask, "wrap_o": self.wrap}


COUNTER_MODULO_DEF = ComponentDef(
    id="counter_modulo",
    category="state",
    summary="Modulo-N up counter with enable and terminal wrap pulse",
    tags=["counter", "modulo", "sequential"],
    contract_anchor="counter_modulo",
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "8", "Counter width in bits", min_value=1, max_value=64),
        ParamDef("MODULUS", "int unsigned", "16", "Counting modulus [2..2**W]", min_value=2, max_value=None),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("en_i", "in", None, "Count enable"),
        PortDef("clear_i", "in", None, "Synchronous clear"),
        PortDef("count_o", "out", "W-1:0", "Current count output"),
        PortDef("wrap_o", "out", None, "Terminal wrap pulse (MODULUS-1 -> 0)"),
    ],
    systemverilog="""localparam logic [W-1:0] TERMINAL = W'(MODULUS) - 1'b1;
always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        count_o <= '0;
        wrap_o <= 1'b0;
    end else if (clear_i) begin
        count_o <= '0;
        wrap_o <= 1'b0;
    end else if (en_i) begin
        if (count_o >= TERMINAL) begin
            count_o <= '0;
            wrap_o <= 1'b1;
        end else begin
            count_o <= count_o + 1'b1;
            wrap_o <= 1'b0;
        end
    end else begin
        wrap_o <= 1'b0;
    end
end
""",
    presets={
        "default": {"W": "8", "MODULUS": "16"},
        "p1": {"W": "1", "MODULUS": "2"},
        "p2": {"W": "5", "MODULUS": "7"},
        "p3": {"W": "64", "MODULUS": "17"},
    },
    timing=TimingInfo(latency="1", throughput="1", reset="async active-low"),
    limitations=["MODULUS must not exceed 2**W."],
    validate_params=_validate_counter_modulo,
    create_reference=lambda p: CounterModuloRef(p),
)


# -----------------------------------------------------------------------------
# 28. edge_detector
# -----------------------------------------------------------------------------
class EdgeDetectorRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.prev = 0

    def reset(self) -> None:
        self.prev = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        level = inputs.get("level_i", 0) & 1
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.prev = 0
            return {"rise_o": 0, "fall_o": 0}
        rise = int(level == 1 and self.prev == 0)
        fall = int(level == 0 and self.prev == 1)
        self.prev = level
        return {"rise_o": rise, "fall_o": fall}


EDGE_DETECTOR_DEF = ComponentDef(
    id="edge_detector",
    category="state",
    summary="Rising and falling edge detector generating single-edge pulses",
    tags=["edge_detector", "pulse", "sequential"],
    contract_anchor="edge_detector",
    is_stateful=True,
    parameters=[],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("level_i", "in", None, "Level input to sample"),
        PortDef("rise_o", "out", None, "Rising edge pulse"),
        PortDef("fall_o", "out", None, "Falling edge pulse"),
    ],
    systemverilog="""logic level_prev;
always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        level_prev <= 1'b0;
        rise_o <= 1'b0;
        fall_o <= 1'b0;
    end else begin
        level_prev <= level_i;
        rise_o <= level_i && !level_prev;
        fall_o <= !level_i && level_prev;
    end
end
""",
    presets={
        "default": {},
    },
    timing=TimingInfo(latency="1", throughput="1", reset="async active-low"),
    limitations=["Unparameterized; samples signal on rising clock edge."],
    validate_params=lambda p: [],
    create_reference=lambda p: EdgeDetectorRef(p),
)


# -----------------------------------------------------------------------------
# 29. pulse_stretcher
# -----------------------------------------------------------------------------
def _validate_pulse_stretcher(params: dict[str, int]) -> list[str]:
    errors = []
    cycles = params.get("CYCLES", 0)
    if not (1 <= cycles <= 256):
        errors.append(f"CYCLES={cycles} out of range [1..256]")
    return errors


class PulseStretcherRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.cycles = params.get("CYCLES", 4)
        self.count = 0

    def reset(self) -> None:
        self.count = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        pulse = inputs.get("pulse_i", 0) & 1
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.count = 0
            return {"pulse_o": 0}
        if pulse:
            self.count = self.cycles - 1
            return {"pulse_o": 1}
        if self.count > 0:
            self.count -= 1
            return {"pulse_o": 1}
        return {"pulse_o": 0}


PULSE_STRETCHER_DEF = ComponentDef(
    id="pulse_stretcher",
    category="state",
    summary="Retriggerable pulse stretcher holding output high for CYCLES edges",
    tags=["pulse", "pulse_stretcher", "sequential"],
    contract_anchor="pulse_stretcher",
    is_stateful=True,
    parameters=[
        ParamDef("CYCLES", "int unsigned", "4", "Pulse duration in clock cycles", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("pulse_i", "in", None, "Trigger pulse input"),
        PortDef("pulse_o", "out", None, "Stretched active-high pulse output"),
    ],
    systemverilog="""localparam int unsigned CNT_W = ((CYCLES)<=1 ? 1 : $clog2(CYCLES + 1));
logic [CNT_W-1:0] cnt;
always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        cnt <= '0;
        pulse_o <= 1'b0;
    end else if (pulse_i) begin
        cnt <= CNT_W'(CYCLES - 1);
        pulse_o <= 1'b1;
    end else if (cnt > '0) begin
        cnt <= cnt - 1'b1;
        pulse_o <= 1'b1;
    end else begin
        pulse_o <= 1'b0;
    end
end
""",
    presets={
        "default": {"CYCLES": "4"},
        "p1": {"CYCLES": "1"},
        "p2": {"CYCLES": "7"},
        "p3": {"CYCLES": "256"},
    },
    timing=TimingInfo(latency="1", throughput="1", reset="async active-low"),
    limitations=["Retriggerable; sustained input holds output high."],
    validate_params=_validate_pulse_stretcher,
    create_reference=lambda p: PulseStretcherRef(p),
)


# -----------------------------------------------------------------------------
# 30. timer
# -----------------------------------------------------------------------------
def _validate_timer(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 64):
        errors.append(f"W={w} out of range [1..64]")
    return errors


class TimerRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 16)
        self.mask = (1 << self.w) - 1
        self.count = 0
        self.busy = 0

    def reset(self) -> None:
        self.count = 0
        self.busy = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        start = inputs.get("start_i", 0) & 1
        cancel = inputs.get("cancel_i", 0) & 1
        load = inputs.get("load_i", 0) & self.mask
        rst_n = inputs.get("rst_ni", 1)
        done = 0

        if not rst_n:
            self.count = 0
            self.busy = 0
            return {"busy_o": 0, "done_o": 0}
        if cancel:
            self.count = 0
            self.busy = 0
            return {"busy_o": 0, "done_o": 0}
        if start:
            if load == 0:
                self.count = 0
                self.busy = 0
                done = 1
            else:
                self.count = load
                self.busy = 1
                done = 0
        elif self.busy:
            if self.count == 1:
                self.count = 0
                self.busy = 0
                done = 1
            else:
                self.count -= 1
                done = 0
        return {"busy_o": self.busy, "done_o": done}


TIMER_DEF = ComponentDef(
    id="timer",
    category="state",
    summary="Programmable countdown timer with busy and done indicators",
    tags=["countdown", "sequential", "timer"],
    contract_anchor="timer",
    is_stateful=True,
    parameters=[
        ParamDef("W", "int unsigned", "16", "Timer duration width in bits", min_value=1, max_value=64),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Asynchronous active-low reset"),
        PortDef("start_i", "in", None, "Start or restart timer"),
        PortDef("cancel_i", "in", None, "Cancel timer (priority over start)"),
        PortDef("load_i", "in", "W-1:0", "Initial countdown cycles"),
        PortDef("busy_o", "out", None, "Timer currently counting"),
        PortDef("done_o", "out", None, "Expiry pulse (one edge)"),
    ],
    systemverilog="""logic [W-1:0] count;
always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        count <= '0;
        busy_o <= 1'b0;
        done_o <= 1'b0;
    end else if (cancel_i) begin
        count <= '0;
        busy_o <= 1'b0;
        done_o <= 1'b0;
    end else if (start_i) begin
        if (load_i == '0) begin
            count <= '0;
            busy_o <= 1'b0;
            done_o <= 1'b1;
        end else begin
            count <= load_i;
            busy_o <= 1'b1;
            done_o <= 1'b0;
        end
    end else if (busy_o) begin
        if (count == W'(1)) begin
            count <= '0;
            busy_o <= 1'b0;
            done_o <= 1'b1;
        end else begin
            count <= count - 1'b1;
            done_o <= 1'b0;
        end
    end else begin
        done_o <= 1'b0;
    end
end
""",
    presets={
        "default": {"W": "16"},
        "p1": {"W": "1"},
        "p2": {"W": "3"},
        "p3": {"W": "64"},
    },
    timing=TimingInfo(latency="load edges", throughput="variable", reset="async active-low"),
    limitations=["Cancel wins over start without emitting done."],
    validate_params=_validate_timer,
    create_reference=lambda p: TimerRef(p),
)


# -----------------------------------------------------------------------------
# 31. binary_to_gray
# -----------------------------------------------------------------------------
def _validate_binary_to_gray(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 64):
        errors.append(f"W={w} out of range [1..64]")
    return errors


class BinaryToGrayRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 8)
        self.mask = (1 << self.w) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        b = inputs.get("binary_i", 0) & self.mask
        return {"gray_o": (b ^ (b >> 1)) & self.mask}


BINARY_TO_GRAY_DEF = ComponentDef(
    id="binary_to_gray",
    category="logic",
    summary="Binary to standard reflected Gray code converter",
    tags=["cdc", "combinational", "converter", "gray_code"],
    contract_anchor="binary_to_gray",
    parameters=[
        ParamDef("W", "int unsigned", "8", "Code width in bits", min_value=1, max_value=64),
    ],
    ports=[
        PortDef("binary_i", "in", "W-1:0", "Standard binary input"),
        PortDef("gray_o", "out", "W-1:0", "Reflected Gray code output"),
    ],
    systemverilog="assign gray_o = binary_i ^ (binary_i >> 1);\n",
    presets={
        "default": {"W": "8"},
        "p1": {"W": "1"},
        "p2": {"W": "7"},
        "p3": {"W": "64"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only."],
    validate_params=_validate_binary_to_gray,
    create_reference=lambda p: BinaryToGrayRef(p),
)


# -----------------------------------------------------------------------------
# 32. gray_to_binary
# -----------------------------------------------------------------------------
def _validate_gray_to_binary(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 64):
        errors.append(f"W={w} out of range [1..64]")
    return errors


class GrayToBinaryRef:
    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 8)
        self.mask = (1 << self.w) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        g = inputs.get("gray_i", 0) & self.mask
        acc = 0
        b = 0
        for j in reversed(range(self.w)):
            acc ^= (g >> j) & 1
            b |= acc << j
        return {"binary_o": b & self.mask}


GRAY_TO_BINARY_DEF = ComponentDef(
    id="gray_to_binary",
    category="logic",
    summary="Reflected Gray code to standard binary converter",
    tags=["cdc", "combinational", "converter", "gray_code"],
    contract_anchor="gray_to_binary",
    parameters=[
        ParamDef("W", "int unsigned", "8", "Code width in bits", min_value=1, max_value=64),
    ],
    ports=[
        PortDef("gray_i", "in", "W-1:0", "Reflected Gray code input"),
        PortDef("binary_o", "out", "W-1:0", "Standard binary output"),
    ],
    systemverilog="""always_comb begin
    for (int unsigned i = 0; i < W; i++) begin
        logic bit_acc;
        bit_acc = 1'b0;
        for (int unsigned k = 0; k < W; k++) begin
            if (k >= i) begin
                bit_acc = bit_acc ^ gray_i[k];
            end
        end
        binary_o[i] = bit_acc;
    end
end
""",
    presets={
        "default": {"W": "8"},
        "p1": {"W": "1"},
        "p2": {"W": "7"},
        "p3": {"W": "64"},
    },
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    limitations=["Combinational only."],
    validate_params=_validate_gray_to_binary,
    create_reference=lambda p: GrayToBinaryRef(p),
)


PHASE1_COMPONENTS: list[ComponentDef] = [
    MUX_DEF,
    DEMUX_DEF,
    PRIORITY_MUX_DEF,
    BINARY_DECODER_DEF,
    ONEHOT_ENCODER_DEF,
    PRIORITY_ENCODER_DEF,
    ONEHOT_CHECKER_DEF,
    LEADING_ZERO_COUNT_DEF,
    TRAILING_ZERO_COUNT_DEF,
    POPULATION_COUNT_DEF,
    BIT_REVERSE_DEF,
    BYTE_REVERSE_DEF,
    BARREL_SHIFT_DEF,
    ROTATE_DEF,
    SIGN_EXTEND_DEF,
    ZERO_EXTEND_DEF,
    BIT_MASK_DEF,
    REGISTER_DEF,
    REGISTER_ENABLE_DEF,
    REGISTER_SYNC_RESET_DEF,
    REGISTER_ASYNC_RESET_DEF,
    SHIFT_REGISTER_DEF,
    PIPELINE_DELAY_DEF,
    COUNTER_UP_DEF,
    COUNTER_UP_DOWN_DEF,
    COUNTER_SATURATING_DEF,
    COUNTER_MODULO_DEF,
    EDGE_DETECTOR_DEF,
    PULSE_STRETCHER_DEF,
    TIMER_DEF,
    BINARY_TO_GRAY_DEF,
    GRAY_TO_BINARY_DEF,
]

PHASE1_COMPONENTS_BY_ID: dict[str, ComponentDef] = {c.id: c for c in PHASE1_COMPONENTS}

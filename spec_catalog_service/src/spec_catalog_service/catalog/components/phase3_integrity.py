"""Phase 3 Integrity & ECC component definitions (Batch 3: 6 components).

Includes:
1. parity: Configurable width parity generator & checker
2. crc_serial: Bit-serial CRC engine with programmable polynomial and width
3. crc_parallel: Byte/word-parallel CRC generator
4. lfsr: Configurable linear feedback shift register
5. secded_encode: Hamming/Hsiao SECDED encoder
6. secded_decode: SECDED decoder with syndrome generation and error correction/detection
"""

from __future__ import annotations

from spec_catalog_service.catalog.components.models import ComponentDef, ParamDef, PortDef, TimingInfo
from spec_catalog_service.catalog.components.phase3_models import (
    CrcParallelRef,
    CrcSerialRef,
    LfsrRef,
    ParityRef,
    SecdedDecodeRef,
    SecdedEncodeRef,
)


# -----------------------------------------------------------------------------
# 1. parity
# -----------------------------------------------------------------------------
def _validate_parity(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 256):
        errors.append(f"W={w} out of range [1..256]")
    return errors


PARITY_DEF = ComponentDef(
    id="parity",
    category="integrity_control",
    phase=3,
    implementation="composite",
    summary="Configurable width parity generator and even-parity checker",
    tags=["integrity", "parity", "checksum", "ecc", "combinational"],
    contract_anchor="parity",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Input data width in bits", min_value=1, max_value=256),
    ],
    ports=[
        PortDef("data_i", "in", "W-1:0", "Input data word"),
        PortDef("parity_i", "in", None, "Received parity bit to check"),
        PortDef("even_parity_o", "out", None, "Calculated even parity bit (XOR of data_i)"),
        PortDef("odd_parity_o", "out", None, "Calculated odd parity bit (~even_parity_o)"),
        PortDef("error_o", "out", None, "Asserted iff even_parity_o != parity_i"),
    ],
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    presets={
        "default": {"W": "32"},
        "w_1": {"W": "1"},
        "w_8": {"W": "8"},
        "w_256": {"W": "256"},
    },
    limitations=[
        "Purely combinational calculation with zero latency.",
        "Error check evaluates even-parity conformance (error iff XOR(data_i) != parity_i).",
    ],
    is_stateful=False,
    validate_params=_validate_parity,
    create_reference=lambda params: ParityRef(params),
    systemverilog="""    assign even_parity_o = ^data_i;
    assign odd_parity_o = ~even_parity_o;
    assign error_o = even_parity_o ^ parity_i;
""",
)


# -----------------------------------------------------------------------------
# 2. crc_serial
# -----------------------------------------------------------------------------
def _validate_crc_serial(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("WIDTH", 0)
    poly = params.get("POLY", 0)
    init = params.get("INIT", 0)
    xorout = params.get("XOROUT", 0)
    if not (8 <= w <= 32):
        errors.append(f"WIDTH={w} out of range [8..32]")
    max_val = (1 << w) - 1 if (1 <= w <= 64) else 0
    if not (1 <= poly <= max_val):
        errors.append(f"POLY={poly} out of range [1..{max_val}]")
    elif poly % 2 == 0:
        errors.append(f"POLY={poly} must be odd")
    if not (0 <= init <= max_val):
        errors.append(f"INIT={init} out of range [0..{max_val}]")
    if not (0 <= xorout <= max_val):
        errors.append(f"XOROUT={xorout} out of range [0..{max_val}]")
    return errors


CRC_SERIAL_DEF = ComponentDef(
    id="crc_serial",
    category="integrity_control",
    phase=3,
    implementation="composite",
    summary="Bit-serial CRC engine with programmable polynomial and initial/xorout values",
    tags=["integrity", "crc", "checksum", "serial", "fsm"],
    contract_anchor="crc_serial",
    parameters=[
        ParamDef("WIDTH", "int unsigned", "32", "CRC width in bits", min_value=8, max_value=32),
        ParamDef("POLY", "logic [WIDTH-1:0]", "WIDTH'(79764919)", "Generator polynomial"),
        ParamDef("INIT", "logic [WIDTH-1:0]", "WIDTH'(4294967295)", "Initial register state"),
        ParamDef("XOROUT", "logic [WIDTH-1:0]", "WIDTH'(4294967295)", "Final XOR mask applied to output"),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("clear_i", "in", None, "Synchronous clear/reinitialization to INIT"),
        PortDef("valid_i", "in", None, "Input bit valid"),
        PortDef("bit_i", "in", None, "Input data bit (MSB-first processing)"),
        PortDef("crc_o", "out", "WIDTH-1:0", "Current computed CRC checksum"),
    ],
    timing=TimingInfo(latency="1", throughput="1", reset="rst_ni"),
    presets={
        "default": {"WIDTH": "32", "POLY": "79764919", "INIT": "4294967295", "XOROUT": "4294967295"},
        "crc8": {"WIDTH": "8", "POLY": "7", "INIT": "0", "XOROUT": "0"},
        "crc16": {"WIDTH": "16", "POLY": "4129", "INIT": "65535", "XOROUT": "0"},
        "crc32_zero": {"WIDTH": "32", "POLY": "79764919", "INIT": "4294967295", "XOROUT": "0"},
    },
    limitations=[
        "Non-reflected, MSB-first serial CRC computation.",
        "Synchronous clear_i wins over valid_i and restores INIT.",
    ],
    is_stateful=True,
    validate_params=_validate_crc_serial,
    create_reference=lambda params: CrcSerialRef(params),
    systemverilog="""    logic [WIDTH-1:0] state_q;
    wire feedback = state_q[WIDTH-1] ^ bit_i;
    wire [WIDTH-1:0] next_shifted = (state_q << 1) ^ (feedback ? POLY : '0);

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state_q <= INIT;
        end else if (clear_i) begin
            state_q <= INIT;
        end else if (valid_i) begin
            state_q <= next_shifted;
        end
    end

    assign crc_o = state_q ^ XOROUT;
""",
)


# -----------------------------------------------------------------------------
# 3. crc_parallel
# -----------------------------------------------------------------------------
def _validate_crc_parallel(params: dict[str, int]) -> list[str]:
    errors = _validate_crc_serial(params)
    b = params.get("BYTES", 0)
    if not (1 <= b <= 16):
        errors.append(f"BYTES={b} out of range [1..16]")
    return errors


CRC_PARALLEL_DEF = ComponentDef(
    id="crc_parallel",
    category="integrity_control",
    phase=3,
    implementation="composite",
    summary="Byte/word-parallel CRC generator with configurable lane count and polynomial",
    tags=["integrity", "crc", "checksum", "parallel", "streaming"],
    contract_anchor="crc_parallel",
    parameters=[
        ParamDef("WIDTH", "int unsigned", "32", "CRC width in bits", min_value=8, max_value=32),
        ParamDef("POLY", "logic [WIDTH-1:0]", "WIDTH'(79764919)", "Generator polynomial"),
        ParamDef("INIT", "logic [WIDTH-1:0]", "WIDTH'(4294967295)", "Initial register state"),
        ParamDef("XOROUT", "logic [WIDTH-1:0]", "WIDTH'(4294967295)", "Final XOR mask applied to output"),
        ParamDef("BYTES", "int unsigned", "4", "Number of parallel input bytes per cycle", min_value=1, max_value=16),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("clear_i", "in", None, "Synchronous clear/reinitialization to INIT"),
        PortDef("valid_i", "in", None, "Input data valid"),
        PortDef("data_i", "in", "(8*BYTES)-1:0", "Parallel byte array in ascending lane order"),
        PortDef("crc_o", "out", "WIDTH-1:0", "Current computed CRC checksum"),
    ],
    timing=TimingInfo(latency="1", throughput="1", reset="rst_ni"),
    presets={
        "default": {"WIDTH": "32", "POLY": "79764919", "INIT": "4294967295", "XOROUT": "4294967295", "BYTES": "4"},
        "crc8_b1": {"WIDTH": "8", "POLY": "7", "INIT": "0", "XOROUT": "0", "BYTES": "1"},
        "crc16_b3": {"WIDTH": "16", "POLY": "4129", "INIT": "65535", "XOROUT": "0", "BYTES": "3"},
        "crc32_b16": {"WIDTH": "32", "POLY": "79764919", "INIT": "4294967295", "XOROUT": "4294967295", "BYTES": "16"},
    },
    limitations=[
        "Processes bytes in ascending lane order (lane 0 in data_i[7:0]), MSB-first within each byte.",
        "Synchronous clear_i wins over valid_i and restores INIT.",
    ],
    is_stateful=True,
    validate_params=_validate_crc_parallel,
    create_reference=lambda params: CrcParallelRef(params),
    systemverilog="""    function automatic logic [WIDTH-1:0] calc_parallel_crc(
        input logic [WIDTH-1:0] cur_state,
        input logic [(8*BYTES)-1:0] in_data
    );
        logic [WIDTH-1:0] s;
        logic [7:0] byte_val;
        logic fb;
        s = cur_state;
        for (int b = 0; b < BYTES; b = b + 1) begin
            byte_val = in_data[b*8 +: 8];
            for (int k = 7; k >= 0; k = k - 1) begin
                fb = s[WIDTH-1] ^ byte_val[k];
                s = (s << 1) ^ (fb ? POLY : '0);
            end
        end
        return s;
    endfunction

    logic [WIDTH-1:0] state_q;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state_q <= INIT;
        end else if (clear_i) begin
            state_q <= INIT;
        end else if (valid_i) begin
            state_q <= calc_parallel_crc(state_q, data_i);
        end
    end

    assign crc_o = state_q ^ XOROUT;
""",
)


# -----------------------------------------------------------------------------
# 4. lfsr
# -----------------------------------------------------------------------------
def _validate_lfsr(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    taps = params.get("TAPS", 0)
    seed = params.get("SEED", 0)
    if not (2 <= w <= 64):
        errors.append(f"W={w} out of range [2..64]")
    max_val = (1 << w) - 1 if (1 <= w <= 64) else 0
    if not (1 <= taps <= max_val):
        errors.append(f"TAPS={taps} out of range [1..{max_val}]")
    if not (1 <= seed <= max_val):
        errors.append(f"SEED={seed} out of range [1..{max_val}]")
    return errors


LFSR_DEF = ComponentDef(
    id="lfsr",
    category="integrity_control",
    phase=3,
    implementation="composite",
    summary="Linear feedback shift register with runtime seed load and zero rejection",
    tags=["integrity", "lfsr", "prng", "sequence", "shift_register"],
    contract_anchor="lfsr",
    parameters=[
        ParamDef("W", "int unsigned", "16", "LFSR state width in bits", min_value=2, max_value=64),
        ParamDef("TAPS", "logic [W-1:0]", "W'(45)", "Feedback tap mask"),
        ParamDef("SEED", "logic [W-1:0]", "W'(1)", "Power-on and reset initial seed"),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("en_i", "in", None, "Shift enable"),
        PortDef("load_i", "in", None, "Load new seed"),
        PortDef("seed_i", "in", "W-1:0", "Seed to load (must be non-zero)"),
        PortDef("state_o", "out", "W-1:0", "Current LFSR register state"),
        PortDef("seed_error_o", "out", None, "Asserted iff attempt was made to load zero seed"),
    ],
    timing=TimingInfo(latency="1", throughput="1", reset="rst_ni"),
    presets={
        "default": {"W": "16", "TAPS": "45", "SEED": "1"},
        "w2": {"W": "2", "TAPS": "3", "SEED": "1"},
        "w4": {"W": "4", "TAPS": "12", "SEED": "1"},
        "w64": {"W": "64", "TAPS": "27", "SEED": "1"},
    },
    limitations=[
        "Fibonacci topology: next = ((state << 1) | parity(state & TAPS)) masked to W.",
        "Zero seed load is rejected, state is held, and seed_error_o pulses high for that cycle.",
    ],
    is_stateful=True,
    validate_params=_validate_lfsr,
    create_reference=lambda params: LfsrRef(params),
    systemverilog="""    logic [W-1:0] state_q;
    logic seed_error_q;
    wire feedback = ^(state_q & TAPS);

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state_q <= SEED;
            seed_error_q <= 1'b0;
        end else begin
            seed_error_q <= 1'b0;
            if (load_i) begin
                if (seed_i == '0) begin
                    seed_error_q <= 1'b1;
                end else begin
                    state_q <= seed_i;
                end
            end else if (en_i) begin
                state_q <= {state_q[W-2:0], feedback};
            end
        end
    end

    assign state_o = state_q;
    assign seed_error_o = seed_error_q;
""",
)


# -----------------------------------------------------------------------------
# 5. secded_encode
# -----------------------------------------------------------------------------
def _validate_secded(params: dict[str, int]) -> list[str]:
    errors = []
    dw = params.get("DATA_W", 0)
    if dw not in {8, 16, 32, 64}:
        errors.append(f"DATA_W={dw} must be one of [8, 16, 32, 64]")
    return errors


SECDED_ENCODE_DEF = ComponentDef(
    id="secded_encode",
    category="integrity_control",
    phase=3,
    implementation="composite",
    summary="Shortened extended Hamming SECDED encoder with overall parity",
    tags=["integrity", "secded", "hamming", "ecc", "encoder"],
    contract_anchor="secded_encode",
    parameters=[
        ParamDef("DATA_W", "int unsigned", "32", "Data word width (8, 16, 32, or 64)", min_value=8, max_value=64),
    ],
    ports=[
        PortDef("data_i", "in", "DATA_W-1:0", "Input unencoded data word"),
        PortDef(
            "code_o",
            "out",
            "(DATA_W + (DATA_W == 8 ? 4 : (DATA_W == 16 ? 5 : (DATA_W == 32 ? 6 : 7)))):0",
            "Extended Hamming SECDED codeword with overall parity",
        ),
    ],
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    presets={
        "default": {"DATA_W": "32"},
        "w8": {"DATA_W": "8"},
        "w16": {"DATA_W": "16"},
        "w64": {"DATA_W": "64"},
    },
    limitations=[
        "Combinational encoding with 0 cycle latency.",
        "Generates extended Hamming codeword with even parity over the code.",
    ],
    is_stateful=False,
    validate_params=_validate_secded,
    create_reference=lambda params: SecdedEncodeRef(params),
    systemverilog="""    localparam int unsigned P = (DATA_W == 8) ? 4 :
                                (DATA_W == 16) ? 5 :
                                (DATA_W == 32) ? 6 : 7;
    localparam int unsigned H = DATA_W + P;
    localparam int unsigned CODE_W = H + 1;

    function automatic logic [CODE_W-1:0] encode_secded(input logic [DATA_W-1:0] d_in);
        logic [CODE_W-1:0] c;
        int d_idx;
        c = '0;
        d_idx = 0;
        for (int k = 1; k <= H; k = k + 1) begin
            if ((k & (k - 1)) != 0) begin
                c[k-1] = d_in[d_idx];
                d_idx = d_idx + 1;
            end
        end
        for (int j = 0; j < P; j = j + 1) begin
            int pos;
            logic par;
            pos = 1 << j;
            par = 1'b0;
            for (int k = 1; k <= H; k = k + 1) begin
                if (k != pos && (k & pos) != 0) begin
                    par = par ^ c[k-1];
                end
            end
            c[pos-1] = par;
        end
        c[H] = ^c[H-1:0];
        return c;
    endfunction

    assign code_o = encode_secded(data_i);
""",
)


# -----------------------------------------------------------------------------
# 6. secded_decode
# -----------------------------------------------------------------------------
SECDED_DECODE_DEF = ComponentDef(
    id="secded_decode",
    category="integrity_control",
    phase=3,
    implementation="composite",
    summary="Shortened extended Hamming SECDED decoder with single-error correction and double-error detection",
    tags=["integrity", "secded", "hamming", "ecc", "decoder", "correction"],
    contract_anchor="secded_decode",
    parameters=[
        ParamDef("DATA_W", "int unsigned", "32", "Data word width (8, 16, 32, or 64)", min_value=8, max_value=64),
    ],
    ports=[
        PortDef(
            "code_i",
            "in",
            "(DATA_W + (DATA_W == 8 ? 4 : (DATA_W == 16 ? 5 : (DATA_W == 32 ? 6 : 7)))):0",
            "Extended Hamming SECDED input codeword",
        ),
        PortDef("data_o", "out", "DATA_W-1:0", "Decoded and corrected data word"),
        PortDef("single_error_o", "out", None, "Asserted iff single-bit error was detected and corrected"),
        PortDef("double_error_o", "out", None, "Asserted iff double-bit error was detected (uncorrectable)"),
    ],
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    presets={
        "default": {"DATA_W": "32"},
        "w8": {"DATA_W": "8"},
        "w16": {"DATA_W": "16"},
        "w64": {"DATA_W": "64"},
    },
    limitations=[
        "Combinational decoding with 0 cycle latency.",
        "single_error_o and double_error_o flags are mutually exclusive.",
        "On double_error_o, uncorrected raw data is output.",
    ],
    is_stateful=False,
    validate_params=_validate_secded,
    create_reference=lambda params: SecdedDecodeRef(params),
    systemverilog="""    localparam int unsigned P = (DATA_W == 8) ? 4 :
                                (DATA_W == 16) ? 5 :
                                (DATA_W == 32) ? 6 : 7;
    localparam int unsigned H = DATA_W + P;
    localparam int unsigned CODE_W = H + 1;

    logic [7:0] syn;
    logic overall_check;
    logic single_err;
    logic double_err;
    logic [CODE_W-1:0] corrected_code;
    logic [DATA_W-1:0] extracted_data;

    always_comb begin
        syn = '0;
        for (int k = 1; k <= H; k = k + 1) begin
            if (code_i[k-1]) begin
                syn = syn ^ 8'(k);
            end
        end

        overall_check = ^code_i;

        single_err = 1'b0;
        double_err = 1'b0;
        corrected_code = code_i;

        if (syn == 8'd0 && overall_check == 1'b0) begin
            single_err = 1'b0;
            double_err = 1'b0;
        end else if (syn == 8'd0 && overall_check == 1'b1) begin
            single_err = 1'b1;
            double_err = 1'b0;
        end else if (syn >= 8'd1 && syn <= 8'(H) && overall_check == 1'b1) begin
            single_err = 1'b1;
            double_err = 1'b0;
            corrected_code[syn - 1] = ~code_i[syn - 1];
        end else if (syn != 8'd0 && overall_check == 1'b0) begin
            single_err = 1'b0;
            double_err = 1'b1;
        end else if (syn > 8'(H) && overall_check == 1'b1) begin
            single_err = 1'b0;
            double_err = 1'b1;
        end

        begin
            int d_idx;
            d_idx = 0;
            extracted_data = '0;
            for (int k = 1; k <= H; k = k + 1) begin
                if ((k & (k - 1)) != 0) begin
                    extracted_data[d_idx] = double_err ? code_i[k-1] : corrected_code[k-1];
                    d_idx = d_idx + 1;
                end
            end
        end
    end

    assign data_o = extracted_data;
    assign single_error_o = single_err;
    assign double_error_o = double_err;
""",
)

PHASE3_INTEGRITY_COMPONENTS: list[ComponentDef] = [
    PARITY_DEF,
    CRC_SERIAL_DEF,
    CRC_PARALLEL_DEF,
    LFSR_DEF,
    SECDED_ENCODE_DEF,
    SECDED_DECODE_DEF,
]

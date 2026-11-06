"""Normative Component definitions and reference models for Phase 3 Batch 1 (Fixed-Point & DSP).

Components:
1. fixed_round
2. fixed_saturate
3. fixed_scale
4. dot_product
5. fir_filter
6. cic_decimator
7. cic_interpolator
"""

from __future__ import annotations

from spec_catalog_service.catalog.components.models import ComponentDef, ParamDef, PortDef
from spec_catalog_service.catalog.components.phase3_models import (
    CicDecimatorRef,
    CicInterpolatorRef,
    DotProductRef,
    FirFilterRef,
    FixedRoundRef,
    FixedSaturateRef,
    FixedScaleRef,
)
from spec_catalog_service.catalog.schemas import TimingInfo


# -----------------------------------------------------------------------------
# 1. fixed_round
# -----------------------------------------------------------------------------
def _validate_fixed_round(params: dict[str, int]) -> list[str]:
    errors = []
    iw = params.get("IW", 0)
    ow = params.get("OW", 0)
    drop = params.get("DROP", 0)
    if not (2 <= iw <= 64):
        errors.append(f"IW={iw} out of range [2..64]")
    if not (1 <= ow <= iw):
        errors.append(f"OW={ow} out of range [1..IW={iw}]")
    if not (0 <= drop <= iw - 1):
        errors.append(f"DROP={drop} out of range [0..IW-1={iw-1}]")
    return errors


FIXED_ROUND_DEF = ComponentDef(
    id="fixed_round",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Signed integer scaling by power of two with nearest-even rounding",
    tags=["fixed_point", "rounding", "scale", "dsp"],
    contract_anchor="fixed_round",
    parameters=[
        ParamDef("IW", "int unsigned", "32", "Input data width in bits", min_value=2, max_value=64),
        ParamDef("OW", "int unsigned", "16", "Output data width in bits", min_value=1, max_value=64),
        ParamDef("DROP", "int unsigned", "8", "Fractional bits to drop (divide by 2**DROP)", min_value=0, max_value=63),
    ],
    ports=[
        PortDef("data_i", "in", "IW-1:0", "Signed input data"),
        PortDef("data_o", "out", "OW-1:0", "Rounded output integer (wrapped to OW bits)"),
        PortDef("overflow_o", "out", None, "Asserted iff rounded result exceeds signed OW range"),
    ],
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    presets={
        "default": {"IW": "32", "OW": "16", "DROP": "8"},
        "drop0": {"IW": "8", "OW": "8", "DROP": "0"},
        "iw8_ow4_drop3": {"IW": "8", "OW": "4", "DROP": "3"},
        "iw64_ow32_drop31": {"IW": "64", "OW": "32", "DROP": "31"},
    },
    limitations=[
        "Combinational rounding logic.",
        "Nearest-even rounding on exact halfway ties.",
        "Wraps to OW bits on overflow; overflow_o flags out-of-range condition.",
    ],
    is_stateful=False,
    validate_params=_validate_fixed_round,
    create_reference=lambda params: FixedRoundRef(params),
    systemverilog="""    localparam int unsigned REM_W = (DROP > 0) ? DROP : 1;
    localparam logic signed [65:0] MIN_BOUND = (OW == 1) ? -66'sd1 : -(66'sd1 <<< (OW - 1));
    localparam logic signed [65:0] MAX_BOUND = (OW == 1) ? 66'sd0 : (66'sd1 <<< (OW - 1)) - 66'sd1;

    logic signed [IW-1:0] s_data;
    logic signed [IW-1:0] shifted;
    logic signed [IW+1:0] rounded;
    logic [REM_W-1:0] rem_slice;
    logic [REM_W-1:0] half_val;

    always_comb begin
        s_data = $signed(data_i);
        rem_slice = (DROP > 0) ? data_i[REM_W-1:0] : {REM_W{1'b0}};
        half_val = (DROP > 0) ? (REM_W'(1'b1) << (DROP - 1)) : {REM_W{1'b0}};

        if (DROP == 0) begin
            rounded = {{(2){s_data[IW-1]}}, s_data};
        end else begin
            shifted = s_data >>> DROP;
            if (rem_slice > half_val) begin
                rounded = {{(2){shifted[IW-1]}}, shifted} + 1'b1;
            end else if (rem_slice < half_val) begin
                rounded = {{(2){shifted[IW-1]}}, shifted};
            end else begin
                // Tie: round to even
                if (shifted[0]) begin
                    rounded = {{(2){shifted[IW-1]}}, shifted} + 1'b1;
                end else begin
                    rounded = {{(2){shifted[IW-1]}}, shifted};
                end
            end
        end

        data_o = rounded[OW-1:0];
        overflow_o = (66'(rounded) < MIN_BOUND) || (66'(rounded) > MAX_BOUND);
    end
""",
)


# -----------------------------------------------------------------------------
# 2. fixed_saturate
# -----------------------------------------------------------------------------
def _validate_fixed_saturate(params: dict[str, int]) -> list[str]:
    errors = []
    iw = params.get("IW", 0)
    ow = params.get("OW", 0)
    if not (2 <= iw <= 64):
        errors.append(f"IW={iw} out of range [2..64]")
    if not (1 <= ow <= iw):
        errors.append(f"OW={ow} out of range [1..IW={iw}]")
    return errors


FIXED_SATURATE_DEF = ComponentDef(
    id="fixed_saturate",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Signed integer clamp to signed OW-bit limits with clipped flag",
    tags=["fixed_point", "saturation", "clamp", "dsp"],
    contract_anchor="fixed_saturate",
    parameters=[
        ParamDef("IW", "int unsigned", "32", "Input data width in bits", min_value=2, max_value=64),
        ParamDef("OW", "int unsigned", "16", "Output data width in bits", min_value=1, max_value=64),
    ],
    ports=[
        PortDef("data_i", "in", "IW-1:0", "Signed input data"),
        PortDef("data_o", "out", "OW-1:0", "Clamped signed output data"),
        PortDef("clipped_o", "out", None, "Asserted iff input value was clamped"),
    ],
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    presets={
        "default": {"IW": "32", "OW": "16"},
        "iw2_ow1": {"IW": "2", "OW": "1"},
        "iw8_ow4": {"IW": "8", "OW": "4"},
        "iw64_ow32": {"IW": "64", "OW": "32"},
    },
    limitations=[
        "Combinational saturation logic without scaling.",
        "Signed two's-complement clamping only.",
    ],
    is_stateful=False,
    validate_params=_validate_fixed_saturate,
    create_reference=lambda params: FixedSaturateRef(params),
    systemverilog="""    localparam logic signed [65:0] MIN_VAL = (OW == 1) ? -66'sd1 : -(66'sd1 <<< (OW - 1));
    localparam logic signed [65:0] MAX_VAL = (OW == 1) ? 66'sd0 : (66'sd1 <<< (OW - 1)) - 66'sd1;

    logic signed [IW-1:0] s_in;
    logic signed [65:0] s_ext;

    always_comb begin
        s_in = $signed(data_i);
        s_ext = 66'(s_in);
        if (s_ext > MAX_VAL) begin
            data_o = MAX_VAL[OW-1:0];
            clipped_o = 1'b1;
        end else if (s_ext < MIN_VAL) begin
            data_o = MIN_VAL[OW-1:0];
            clipped_o = 1'b1;
        end else begin
            data_o = s_in[OW-1:0];
            clipped_o = 1'b0;
        end
    end
""",
)


# -----------------------------------------------------------------------------
# 3. fixed_scale
# -----------------------------------------------------------------------------
def _validate_fixed_scale(params: dict[str, int]) -> list[str]:
    errors = []
    iw = params.get("IW", 0)
    ow = params.get("OW", 0)
    cw = params.get("COEFF_W", 0)
    frac = params.get("FRAC", 0)
    gain = params.get("GAIN", 0)
    if not (2 <= iw <= 32):
        errors.append(f"IW={iw} out of range [2..32]")
    if not (2 <= ow <= 32):
        errors.append(f"OW={ow} out of range [2..32]")
    if not (2 <= cw <= 32):
        errors.append(f"COEFF_W={cw} out of range [2..32]")
    if not (0 <= frac <= cw - 1):
        errors.append(f"FRAC={frac} out of range [0..COEFF_W-1={cw-1}]")
    min_gain = -(1 << (cw - 1))
    max_gain = (1 << (cw - 1)) - 1
    if not (min_gain <= gain <= max_gain):
        errors.append(f"GAIN={gain} out of signed {cw}-bit range [{min_gain}..{max_gain}]")
    return errors


FIXED_SCALE_DEF = ComponentDef(
    id="fixed_scale",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Signed scaling by constant integer gain with nearest-even round and saturation",
    tags=["fixed_point", "scale", "gain", "dsp"],
    contract_anchor="fixed_scale",
    parameters=[
        ParamDef("IW", "int unsigned", "16", "Input data width in bits", min_value=2, max_value=32),
        ParamDef("OW", "int unsigned", "16", "Output data width in bits", min_value=2, max_value=32),
        ParamDef("COEFF_W", "int unsigned", "16", "Gain coefficient width in bits", min_value=2, max_value=32),
        ParamDef("FRAC", "int unsigned", "8", "Fractional bits to divide by 2**FRAC", min_value=0, max_value=31),
        ParamDef("GAIN", "int signed", "256", "Signed scaling gain factor"),
    ],
    ports=[
        PortDef("data_i", "in", "IW-1:0", "Signed input data"),
        PortDef("data_o", "out", "OW-1:0", "Scaled, rounded, and saturated output"),
        PortDef("clipped_o", "out", None, "Asserted iff saturation clamped the value"),
    ],
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    presets={
        "default": {"IW": "16", "OW": "16", "COEFF_W": "16", "FRAC": "8", "GAIN": "256"},
        "preset1": {"IW": "8", "OW": "8", "COEFF_W": "8", "FRAC": "4", "GAIN": "16"},
        "preset2": {"IW": "8", "OW": "4", "COEFF_W": "8", "FRAC": "3", "GAIN": "-7"},
        "preset3": {"IW": "32", "OW": "32", "COEFF_W": "32", "FRAC": "16", "GAIN": "65536"},
    },
    limitations=[
        "Combinational multiply-scale-saturate path.",
        "Nearest-even rounding on division by 2**FRAC.",
        "Clamps cleanly to signed OW range on overflow.",
    ],
    is_stateful=False,
    validate_params=_validate_fixed_scale,
    create_reference=lambda params: FixedScaleRef(params),
    systemverilog="""    localparam int unsigned PROD_W = IW + COEFF_W;
    localparam int unsigned FRAC_W = (FRAC > 0) ? FRAC : 1;
    localparam logic signed [65:0] MIN_VAL = (OW == 1) ? -66'sd1 : -(66'sd1 <<< (OW - 1));
    localparam logic signed [65:0] MAX_VAL = (OW == 1) ? 66'sd0 : (66'sd1 <<< (OW - 1)) - 66'sd1;

    logic signed [IW-1:0] s_in;
    logic signed [COEFF_W-1:0] s_gain;
    logic signed [PROD_W-1:0] prod;
    logic signed [PROD_W-1:0] shifted;
    logic signed [PROD_W+1:0] rounded;
    logic [FRAC_W-1:0] rem_slice;
    logic [FRAC_W-1:0] half_val;
    logic signed [65:0] r_ext;

    always_comb begin
        s_in = $signed(data_i);
        s_gain = COEFF_W'($signed(GAIN));
        prod = s_in * s_gain;

        rem_slice = (FRAC > 0) ? prod[FRAC_W-1:0] : {FRAC_W{1'b0}};
        half_val = (FRAC > 0) ? (FRAC_W'(1'b1) << (FRAC - 1)) : {FRAC_W{1'b0}};

        if (FRAC == 0) begin
            rounded = {{(2){prod[PROD_W-1]}}, prod};
        end else begin
            shifted = prod >>> FRAC;
            if (rem_slice > half_val) begin
                rounded = {{(2){shifted[PROD_W-1]}}, shifted} + 1'b1;
            end else if (rem_slice < half_val) begin
                rounded = {{(2){shifted[PROD_W-1]}}, shifted};
            end else begin
                // Tie: round to even
                if (shifted[0]) begin
                    rounded = {{(2){shifted[PROD_W-1]}}, shifted} + 1'b1;
                end else begin
                    rounded = {{(2){shifted[PROD_W-1]}}, shifted};
                end
            end
        end

        r_ext = 66'(rounded);
        if (r_ext > MAX_VAL) begin
            data_o = MAX_VAL[OW-1:0];
            clipped_o = 1'b1;
        end else if (r_ext < MIN_VAL) begin
            data_o = MIN_VAL[OW-1:0];
            clipped_o = 1'b1;
        end else begin
            data_o = rounded[OW-1:0];
            clipped_o = 1'b0;
        end
    end
""",
)


# -----------------------------------------------------------------------------
# 4. dot_product
# -----------------------------------------------------------------------------
def _validate_dot_product(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    n = params.get("N", 0)
    out_w = params.get("OUT_W", 0)
    if not (2 <= w <= 32):
        errors.append(f"W={w} out of range [2..32]")
    if not (1 <= n <= 16):
        errors.append(f"N={n} out of range [1..16]")
    if not (5 <= out_w <= 128):
        errors.append(f"OUT_W={out_w} out of range [5..128]")
    return errors


DOT_PRODUCT_DEF = ComponentDef(
    id="dot_product",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Iterative signed vector dot product accumulator",
    tags=["dsp", "dot_product", "vector", "iterative", "arithmetic"],
    contract_anchor="dot_product",
    parameters=[
        ParamDef("W", "int unsigned", "16", "Vector element data width in bits", min_value=2, max_value=32),
        ParamDef("N", "int unsigned", "4", "Number of vector elements", min_value=1, max_value=16),
        ParamDef("OUT_W", "int unsigned", "40", "Accumulated sum output width", min_value=5, max_value=128),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("req_valid_i", "in", None, "Request transfer valid"),
        PortDef("req_ready_o", "out", None, "Request transfer ready"),
        PortDef("a_i", "in", "(N*W)-1:0", "Packed vector A elements (lane 0 in LSBs)"),
        PortDef("b_i", "in", "(N*W)-1:0", "Packed vector B elements (lane 0 in LSBs)"),
        PortDef("rsp_valid_o", "out", None, "Response transfer valid"),
        PortDef("rsp_ready_i", "in", None, "Response transfer ready"),
        PortDef("sum_o", "out", "OUT_W-1:0", "Accumulated dot product sum"),
    ],
    timing=TimingInfo(latency="N+1", throughput="1/(N+1)", reset="rst_ni"),
    presets={
        "default": {"W": "16", "N": "4", "OUT_W": "40"},
        "n1": {"W": "2", "N": "1", "OUT_W": "5"},
        "w7_n3": {"W": "7", "N": "3", "OUT_W": "16"},
        "w32_n16": {"W": "32", "N": "16", "OUT_W": "68"},
    },
    limitations=[
        "One pair processed per active edge.",
        "Transfer latency is N+1 active edges without stall.",
        "Single outstanding request at a time.",
    ],
    is_stateful=True,
    validate_params=_validate_dot_product,
    create_reference=lambda params: DotProductRef(params),
    systemverilog="""    typedef enum logic [1:0] {
        IDLE = 2'd0,
        CALC = 2'd1,
        DONE = 2'd2
    } state_t;

    state_t state_q, state_d;
    logic [N*W-1:0] a_q, a_d;
    logic [N*W-1:0] b_q, b_d;
    logic [31:0] count_q, count_d;
    logic signed [OUT_W-1:0] sum_q, sum_d;

    logic signed [W-1:0] curr_a;
    logic signed [W-1:0] curr_b;
    logic signed [2*W-1:0] prod;

    always_comb begin
        curr_a = '0;
        curr_b = '0;
        for (int i = 0; i < N; i++) begin
            if (count_q == i) begin
                curr_a = a_q[i*W +: W];
                curr_b = b_q[i*W +: W];
            end
        end
        prod = curr_a * curr_b;
    end

    always_comb begin
        state_d = state_q;
        a_d = a_q;
        b_d = b_q;
        count_d = count_q;
        sum_d = sum_q;

        case (state_q)
            IDLE: begin
                if (req_valid_i) begin
                    a_d = a_i;
                    b_d = b_i;
                    count_d = '0;
                    sum_d = '0;
                    state_d = CALC;
                end
            end

            CALC: begin
                sum_d = sum_q + OUT_W'(prod);
                count_d = count_q + 1'b1;
                if (count_q == N - 1) begin
                    state_d = DONE;
                end
            end

            DONE: begin
                if (rsp_ready_i) begin
                    if (req_valid_i) begin
                        a_d = a_i;
                        b_d = b_i;
                        count_d = '0;
                        sum_d = '0;
                        state_d = CALC;
                    end else begin
                        state_d = IDLE;
                    end
                end
            end

            default: state_d = IDLE;
        endcase
    end

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state_q <= IDLE;
            a_q <= '0;
            b_q <= '0;
            count_q <= '0;
            sum_q <= '0;
        end else begin
            state_q <= state_d;
            a_q <= a_d;
            b_q <= b_d;
            count_q <= count_d;
            sum_q <= sum_d;
        end
    end

    assign req_ready_o = (state_q == IDLE) || (state_q == DONE && rsp_ready_i);
    assign rsp_valid_o = (state_q == DONE);
    assign sum_o = (state_q == DONE) ? sum_q : '0;
""",
)


# -----------------------------------------------------------------------------
# 5. fir_filter
# -----------------------------------------------------------------------------
def _validate_fir_filter(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    taps = params.get("TAPS", 0)
    cw = params.get("CW", 0)
    frac = params.get("FRAC", 0)
    ow = params.get("OW", 0)
    if not (2 <= w <= 32):
        errors.append(f"W={w} out of range [2..32]")
    if not (1 <= taps <= 16):
        errors.append(f"TAPS={taps} out of range [1..16]")
    if not (2 <= cw <= 32):
        errors.append(f"CW={cw} out of range [2..32]")
    if not (0 <= frac <= cw - 1):
        errors.append(f"FRAC={frac} out of range [0..CW-1={cw-1}]")
    if not (2 <= ow <= 64):
        errors.append(f"OW={ow} out of range [2..64]")
    return errors


FIR_FILTER_DEF = ComponentDef(
    id="fir_filter",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Pipelined streaming FIR filter with signed history and elastic output",
    tags=["dsp", "fir", "filter", "streaming", "convolution"],
    contract_anchor="fir_filter",
    parameters=[
        ParamDef("W", "int unsigned", "16", "Input sample width in bits", min_value=2, max_value=32),
        ParamDef("TAPS", "int unsigned", "4", "Number of filter taps", min_value=1, max_value=16),
        ParamDef("CW", "int unsigned", "16", "Coefficient lane width in bits", min_value=2, max_value=32),
        ParamDef("FRAC", "int unsigned", "8", "Fractional bits dropped with nearest-even round", min_value=0, max_value=31),
        ParamDef("COEFFS", "logic [(TAPS*CW)-1:0]", "(TAPS*CW)'(256)", "Packed coefficient array (lane 0 in LSBs)"),
        ParamDef("OW", "int unsigned", "16", "Output sample width in bits", min_value=2, max_value=64),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("s_valid_i", "in", None, "Input stream valid"),
        PortDef("s_ready_o", "out", None, "Input stream ready"),
        PortDef("s_data_i", "in", "W-1:0", "Signed input sample"),
        PortDef("m_valid_o", "out", None, "Output stream valid"),
        PortDef("m_ready_i", "in", None, "Output stream ready"),
        PortDef("m_data_o", "out", "OW-1:0", "Filtered and saturated output sample"),
        PortDef("clipped_o", "out", None, "Asserted iff output was clipped by saturation"),
    ],
    timing=TimingInfo(latency="1", throughput="1", reset="rst_ni"),
    presets={
        "default": {"W": "16", "TAPS": "4", "CW": "16", "FRAC": "8", "COEFFS": "256", "OW": "16"},
        "taps1": {"W": "8", "TAPS": "1", "CW": "8", "FRAC": "4", "COEFFS": "16", "OW": "8"},
        "taps3": {"W": "8", "TAPS": "3", "CW": "8", "FRAC": "4", "COEFFS": "66040", "OW": "16"},
        "w32_taps16": {"W": "32", "TAPS": "16", "CW": "32", "FRAC": "16", "COEFFS": "65536", "OW": "64"},
    },
    limitations=[
        "One elastic output register with latency 1.",
        "Input accepted only when output stage is free or consumed.",
        "Signed saturation cleanly clamps to signed OW limits.",
    ],
    is_stateful=True,
    validate_params=_validate_fir_filter,
    create_reference=lambda params: FirFilterRef(params),
    systemverilog="""    localparam int unsigned ACC_W = W + CW + 16;
    localparam int unsigned ACC_EXT_W = ACC_W + 2;
    localparam logic signed [ACC_EXT_W-1:0] MIN_VAL = (OW == 1) ? -ACC_EXT_W'(1) : -(ACC_EXT_W'(1) <<< (OW - 1));
    localparam logic signed [ACC_EXT_W-1:0] MAX_VAL = (OW == 1) ? ACC_EXT_W'(0) : (ACC_EXT_W'(1) <<< (OW - 1)) - ACC_EXT_W'(1);
    localparam int unsigned FRAC_W = (FRAC > 0) ? FRAC : 1;

    logic signed [W-1:0] history_q [TAPS];
    logic signed [CW-1:0] coeffs [TAPS];

    logic m_valid_q;
    logic [OW-1:0] m_data_q;
    logic clipped_q;

    logic can_accept;
    logic signed [ACC_W-1:0] acc;
    logic signed [ACC_W-1:0] shifted;
    logic signed [ACC_EXT_W-1:0] rounded;
    logic [FRAC_W-1:0] rem_slice;
    logic [FRAC_W-1:0] half_val;
    logic [OW-1:0] sat_data;
    logic sat_clipped;

    always_comb begin
        for (int i = 0; i < TAPS; i++) begin
            coeffs[i] = COEFFS[i*CW +: CW];
        end

        can_accept = (!m_valid_q || m_ready_i);

        // Accumulate newest sample with coeff[0] and shifted history with remaining coeffs
        acc = ACC_W'($signed(s_data_i)) * ACC_W'(coeffs[0]);
        for (int i = 1; i < TAPS; i++) begin
            acc = acc + (ACC_W'(history_q[i-1]) * ACC_W'(coeffs[i]));
        end

        rem_slice = (FRAC > 0) ? acc[FRAC_W-1:0] : {FRAC_W{1'b0}};
        half_val = (FRAC > 0) ? (FRAC_W'(1'b1) << (FRAC - 1)) : {FRAC_W{1'b0}};

        if (FRAC == 0) begin
            rounded = {{(2){acc[ACC_W-1]}}, acc};
        end else begin
            shifted = acc >>> FRAC;
            if (rem_slice > half_val) begin
                rounded = {{(2){shifted[ACC_W-1]}}, shifted} + 1'b1;
            end else if (rem_slice < half_val) begin
                rounded = {{(2){shifted[ACC_W-1]}}, shifted};
            end else begin
                if (shifted[0]) begin
                    rounded = {{(2){shifted[ACC_W-1]}}, shifted} + 1'b1;
                end else begin
                    rounded = {{(2){shifted[ACC_W-1]}}, shifted};
                end
            end
        end

        if (rounded > MAX_VAL) begin
            sat_data = MAX_VAL[OW-1:0];
            sat_clipped = 1'b1;
        end else if (rounded < MIN_VAL) begin
            sat_data = MIN_VAL[OW-1:0];
            sat_clipped = 1'b1;
        end else begin
            sat_data = rounded[OW-1:0];
            sat_clipped = 1'b0;
        end
    end

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            for (int i = 0; i < TAPS; i++) begin
                history_q[i] <= '0;
            end
            m_valid_q <= 1'b0;
            m_data_q <= '0;
            clipped_q <= 1'b0;
        end else begin
            if (can_accept && s_valid_i) begin
                history_q[0] <= s_data_i;
                for (int i = 1; i < TAPS; i++) begin
                    history_q[i] <= history_q[i-1];
                end
                m_valid_q <= 1'b1;
                m_data_q <= sat_data;
                clipped_q <= sat_clipped;
            end else if (m_ready_i && m_valid_q) begin
                m_valid_q <= 1'b0;
            end
        end
    end

    assign s_ready_o = can_accept;
    assign m_valid_o = m_valid_q;
    assign m_data_o = m_valid_q ? m_data_q : '0;
    assign clipped_o = m_valid_q ? clipped_q : 1'b0;
""",
)


# -----------------------------------------------------------------------------
# 6. cic_decimator
# -----------------------------------------------------------------------------
def _validate_cic_decimator(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    r = params.get("R", 0)
    order = params.get("ORDER", 0)
    if not (2 <= w <= 24):
        errors.append(f"W={w} out of range [2..24]")
    if not (2 <= r <= 16):
        errors.append(f"R={r} out of range [2..16]")
    if not (1 <= order <= 4):
        errors.append(f"ORDER={order} out of range [1..4]")
    return errors


CIC_DECIMATOR_DEF = ComponentDef(
    id="cic_decimator",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Cascaded Integrator-Comb (CIC) decimation filter with differential delay 1",
    tags=["dsp", "cic", "decimator", "multirate", "filter"],
    contract_anchor="cic_decimator",
    parameters=[
        ParamDef("W", "int unsigned", "16", "Input sample data width", min_value=2, max_value=24),
        ParamDef("R", "int unsigned", "4", "Decimation rate ratio", min_value=2, max_value=16),
        ParamDef("ORDER", "int unsigned", "2", "Number of integrator and comb stages", min_value=1, max_value=4),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("s_valid_i", "in", None, "Input sample stream valid"),
        PortDef("s_ready_o", "out", None, "Input sample stream ready"),
        PortDef("s_data_i", "in", "W-1:0", "Signed input sample"),
        PortDef("m_valid_o", "out", None, "Decimated output stream valid"),
        PortDef("m_ready_i", "in", None, "Decimated output stream ready"),
        PortDef("m_data_o", "out", "(W+ORDER*$clog2(R))-1:0", "Decimated signed sample output"),
    ],
    timing=TimingInfo(latency="1", throughput="1/R", reset="rst_ni"),
    presets={
        "default": {"W": "16", "R": "4", "ORDER": "2"},
        "order1": {"W": "2", "R": "2", "ORDER": "1"},
        "order3": {"W": "7", "R": "3", "ORDER": "3"},
        "max": {"W": "24", "R": "16", "ORDER": "4"},
    },
    limitations=[
        "Internal bit growth B = W + ORDER * clog2(R) prevents overflow.",
        "Differential delay fixed at 1.",
        "Stalls input when output register is occupied and not consumed.",
    ],
    is_stateful=True,
    validate_params=_validate_cic_decimator,
    create_reference=lambda params: CicDecimatorRef(params),
    systemverilog="""    localparam int unsigned CLOG2_R = (R > 1) ? $clog2(R) : 1;
    localparam int unsigned B = W + ORDER * CLOG2_R;

    logic signed [B-1:0] integrators_q [ORDER];
    logic signed [B-1:0] comb_prev_q [ORDER];
    logic [31:0] count_q;

    logic m_valid_q;
    logic [B-1:0] m_data_q;

    logic can_accept;

    logic signed [B-1:0] int_val [ORDER];
    logic signed [B-1:0] comb_val [ORDER];

    always_comb begin
        can_accept = (!m_valid_q || m_ready_i);

        int_val[0] = integrators_q[0] + B'($signed(s_data_i));
        for (int i = 1; i < ORDER; i++) begin
            int_val[i] = integrators_q[i] + int_val[i-1];
        end

        comb_val[0] = int_val[ORDER-1] - comb_prev_q[0];
        for (int i = 1; i < ORDER; i++) begin
            comb_val[i] = comb_val[i-1] - comb_prev_q[i];
        end
    end

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            for (int i = 0; i < ORDER; i++) begin
                integrators_q[i] <= '0;
                comb_prev_q[i] <= '0;
            end
            count_q <= '0;
            m_valid_q <= 1'b0;
            m_data_q <= '0;
        end else begin
            if (m_ready_i && m_valid_q) begin
                m_valid_q <= 1'b0;
            end

            if (can_accept && s_valid_i) begin
                for (int i = 0; i < ORDER; i++) begin
                    integrators_q[i] <= int_val[i];
                end

                if (count_q == R - 1) begin
                    comb_prev_q[0] <= int_val[ORDER-1];
                    for (int i = 1; i < ORDER; i++) begin
                        comb_prev_q[i] <= comb_val[i-1];
                    end
                    m_valid_q <= 1'b1;
                    m_data_q <= comb_val[ORDER-1];
                    count_q <= '0;
                end else begin
                    count_q <= count_q + 1'b1;
                end
            end
        end
    end

    assign s_ready_o = can_accept;
    assign m_valid_o = m_valid_q;
    assign m_data_o = m_valid_q ? m_data_q : '0;
""",
)


# -----------------------------------------------------------------------------
# 7. cic_interpolator
# -----------------------------------------------------------------------------
def _validate_cic_interpolator(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    r = params.get("R", 0)
    order = params.get("ORDER", 0)
    if not (2 <= w <= 24):
        errors.append(f"W={w} out of range [2..24]")
    if not (2 <= r <= 16):
        errors.append(f"R={r} out of range [2..16]")
    if not (1 <= order <= 4):
        errors.append(f"ORDER={order} out of range [1..4]")
    return errors


CIC_INTERPOLATOR_DEF = ComponentDef(
    id="cic_interpolator",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Cascaded Integrator-Comb (CIC) interpolation filter with differential delay 1",
    tags=["dsp", "cic", "interpolator", "multirate", "filter"],
    contract_anchor="cic_interpolator",
    parameters=[
        ParamDef("W", "int unsigned", "16", "Input sample data width", min_value=2, max_value=24),
        ParamDef("R", "int unsigned", "4", "Interpolation rate ratio", min_value=2, max_value=16),
        ParamDef("ORDER", "int unsigned", "2", "Number of comb and integrator stages", min_value=1, max_value=4),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("s_valid_i", "in", None, "Input sample stream valid"),
        PortDef("s_ready_o", "out", None, "Input sample stream ready"),
        PortDef("s_data_i", "in", "W-1:0", "Signed input sample"),
        PortDef("m_valid_o", "out", None, "Interpolated output stream valid"),
        PortDef("m_ready_i", "in", None, "Interpolated output stream ready"),
        PortDef("m_data_o", "out", "(W+ORDER*$clog2(R))-1:0", "Interpolated signed sample output"),
    ],
    timing=TimingInfo(latency="1", throughput="R", reset="rst_ni"),
    presets={
        "default": {"W": "16", "R": "4", "ORDER": "2"},
        "order1": {"W": "2", "R": "2", "ORDER": "1"},
        "order3": {"W": "7", "R": "3", "ORDER": "3"},
        "max": {"W": "24", "R": "16", "ORDER": "4"},
    },
    limitations=[
        "Internal bit growth B = W + ORDER * clog2(R).",
        "Differential delay fixed at 1.",
        "Emits exactly R output samples per accepted input.",
    ],
    is_stateful=True,
    validate_params=_validate_cic_interpolator,
    create_reference=lambda params: CicInterpolatorRef(params),
    systemverilog="""    localparam int unsigned CLOG2_R = (R > 1) ? $clog2(R) : 1;
    localparam int unsigned B = W + ORDER * CLOG2_R;

    logic signed [B-1:0] comb_prev_q [ORDER];
    logic signed [B-1:0] integrators_q [ORDER];
    logic [31:0] count_q;
    logic active_q;

    logic m_valid_q;
    logic [B-1:0] m_data_q;

    logic can_accept;

    logic signed [B-1:0] comb_diff [ORDER];
    logic signed [B-1:0] int_next [ORDER];
    logic signed [B-1:0] int_step [ORDER];

    always_comb begin
        can_accept = (!active_q || (m_valid_q && m_ready_i && (count_q + 1'b1 >= R))) && (!m_valid_q || m_ready_i);

        comb_diff[0] = B'($signed(s_data_i)) - comb_prev_q[0];
        for (int i = 1; i < ORDER; i++) begin
            comb_diff[i] = comb_diff[i-1] - comb_prev_q[i];
        end

        // First sample: feed comb_diff to integrators
        int_next[0] = integrators_q[0] + comb_diff[ORDER-1];
        for (int i = 1; i < ORDER; i++) begin
            int_next[i] = integrators_q[i] + int_next[i-1];
        end

        // Remaining samples: input 0 to integrators
        int_step[0] = integrators_q[0];
        for (int i = 1; i < ORDER; i++) begin
            int_step[i] = integrators_q[i] + int_step[i-1];
        end
    end

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            for (int i = 0; i < ORDER; i++) begin
                comb_prev_q[i] <= '0;
                integrators_q[i] <= '0;
            end
            count_q <= '0;
            active_q <= 1'b0;
            m_valid_q <= 1'b0;
            m_data_q <= '0;
        end else begin
            if (m_valid_q && m_ready_i) begin
                m_valid_q <= 1'b0;
                if (count_q + 1'b1 >= R) begin
                    active_q <= 1'b0;
                    count_q <= '0;
                end else begin
                    count_q <= count_q + 1'b1;
                    for (int i = 0; i < ORDER; i++) begin
                        integrators_q[i] <= int_step[i];
                    end
                    m_valid_q <= 1'b1;
                    m_data_q <= int_step[ORDER-1];
                end
            end

            if (can_accept && s_valid_i) begin
                comb_prev_q[0] <= B'($signed(s_data_i));
                for (int i = 1; i < ORDER; i++) begin
                    comb_prev_q[i] <= comb_diff[i-1];
                end
                for (int i = 0; i < ORDER; i++) begin
                    integrators_q[i] <= int_next[i];
                end
                m_valid_q <= 1'b1;
                m_data_q <= int_next[ORDER-1];
                active_q <= 1'b1;
                count_q <= '0;
            end
        end
    end

    assign s_ready_o = can_accept;
    assign m_valid_o = m_valid_q;
    assign m_data_o = m_valid_q ? m_data_q : '0;
""",
)

PHASE3_DSP_COMPONENTS: list[ComponentDef] = [
    FIXED_ROUND_DEF,
    FIXED_SATURATE_DEF,
    FIXED_SCALE_DEF,
    DOT_PRODUCT_DEF,
    FIR_FILTER_DEF,
    CIC_DECIMATOR_DEF,
    CIC_INTERPOLATOR_DEF,
]

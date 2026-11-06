"""Normative Component definitions and reference models for Phase 3 Group B (Multipliers, Dividers & Roots).

Components:
6. multiplier_comb
7. multiplier_pipeline
8. multiplier_iterative
9. mac
10. divider_iterative
11. divider_pipeline
12. integer_sqrt
"""

from __future__ import annotations

from spec_catalog_service.catalog.components.models import ComponentDef, ParamDef, PortDef
from spec_catalog_service.catalog.components.phase3_models import (
    DividerIterativeRef,
    DividerPipelineRef,
    IntegerSqrtRef,
    MacRef,
    MultiplierCombRef,
    MultiplierIterativeRef,
    MultiplierPipelineRef,
)
from spec_catalog_service.catalog.schemas import TimingInfo


# -----------------------------------------------------------------------------
# 6. multiplier_comb
# -----------------------------------------------------------------------------
def _validate_multiplier_comb(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    signed_val = params.get("SIGNED", 0)
    if not (1 <= w <= 32):
        errors.append(f"W={w} out of range [1..32]")
    if signed_val not in (0, 1):
        errors.append(f"SIGNED={signed_val} must be 0 or 1")
    return errors


MULTIPLIER_COMB_DEF = ComponentDef(
    id="multiplier_comb",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Combinational full-precision multiplier (signed or unsigned)",
    tags=["arithmetic", "multiplier", "combinational"],
    contract_anchor="multiplier_comb",
    parameters=[
        ParamDef("W", "int unsigned", "16", "Operand data width in bits", min_value=1, max_value=32),
        ParamDef("SIGNED", "int unsigned", "0", "1 for signed two's complement, 0 for unsigned", min_value=0, max_value=1),
    ],
    ports=[
        PortDef("a_i", "in", "W-1:0", "First multiplicand operand"),
        PortDef("b_i", "in", "W-1:0", "Second multiplicand operand"),
        PortDef("product_o", "out", "(2*W)-1:0", "Full-width product result"),
    ],
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    presets={
        "default": {"W": "16", "SIGNED": "0"},
        "w1_signed": {"W": "1", "SIGNED": "1"},
        "w4_unsigned": {"W": "4", "SIGNED": "0"},
        "w32_signed": {"W": "32", "SIGNED": "1"},
    },
    limitations=[
        "Full precision output with no truncation (width 2*W).",
        "Purely combinational calculation.",
    ],
    is_stateful=False,
    validate_params=_validate_multiplier_comb,
    create_reference=lambda params: MultiplierCombRef(params),
    systemverilog="""    always_comb begin
        if (SIGNED != 0) begin
            product_o = (2*W)'($signed(a_i) * $signed(b_i));
        end else begin
            product_o = (2*W)'(a_i) * (2*W)'(b_i);
        end
    end
""",
)


# -----------------------------------------------------------------------------
# 7. multiplier_pipeline
# -----------------------------------------------------------------------------
def _validate_multiplier_pipeline(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    signed_val = params.get("SIGNED", 0)
    stages = params.get("STAGES", 0)
    if not (1 <= w <= 32):
        errors.append(f"W={w} out of range [1..32]")
    if signed_val not in (0, 1):
        errors.append(f"SIGNED={signed_val} must be 0 or 1")
    if not (1 <= stages <= 8):
        errors.append(f"STAGES={stages} out of range [1..8]")
    return errors


MULTIPLIER_PIPELINE_DEF = ComponentDef(
    id="multiplier_pipeline",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Fully-pipelined elastic multiplier with backpressure propagation",
    tags=["arithmetic", "multiplier", "pipelined", "elastic"],
    contract_anchor="multiplier_pipeline",
    parameters=[
        ParamDef("W", "int unsigned", "16", "Operand data width in bits", min_value=1, max_value=32),
        ParamDef("SIGNED", "int unsigned", "0", "1 for signed two's complement, 0 for unsigned", min_value=0, max_value=1),
        ParamDef("STAGES", "int unsigned", "3", "Pipeline register depth", min_value=1, max_value=8),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Rising-edge clock"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("req_valid_i", "in", None, "Request valid handshake input"),
        PortDef("req_ready_o", "out", None, "Request ready handshake output"),
        PortDef("a_i", "in", "W-1:0", "First multiplicand operand"),
        PortDef("b_i", "in", "W-1:0", "Second multiplicand operand"),
        PortDef("rsp_valid_o", "out", None, "Response valid handshake output"),
        PortDef("rsp_ready_i", "in", None, "Response ready handshake input"),
        PortDef("product_o", "out", "(2*W)-1:0", "Full-width product result"),
    ],
    timing=TimingInfo(latency="STAGES", throughput="1", reset="async_low"),
    presets={
        "default": {"W": "16", "SIGNED": "0", "STAGES": "3"},
        "w1_signed_s1": {"W": "1", "SIGNED": "1", "STAGES": "1"},
        "w7_unsigned_s2": {"W": "7", "SIGNED": "0", "STAGES": "2"},
        "w32_signed_s8": {"W": "32", "SIGNED": "1", "STAGES": "8"},
    },
    limitations=[
        "Latency is exactly STAGES clock cycles without stall.",
        "Backpressure propagates upstream without losing or reordering transactions.",
    ],
    is_stateful=True,
    validate_params=_validate_multiplier_pipeline,
    create_reference=lambda params: MultiplierPipelineRef(params),
    systemverilog="""    logic [2*W-1:0] mult_comb;

    always_comb begin
        if (SIGNED != 0) begin
            mult_comb = (2*W)'($signed(a_i) * $signed(b_i));
        end else begin
            mult_comb = (2*W)'(a_i) * (2*W)'(b_i);
        end
    end

    logic [STAGES-1:0] pipe_valid_q;
    logic [2*W-1:0] pipe_data_q [0:STAGES-1];
    logic can_advance;

    assign can_advance = rsp_ready_i || !pipe_valid_q[STAGES-1];
    assign req_ready_o = can_advance;
    assign rsp_valid_o = pipe_valid_q[STAGES-1];
    assign product_o = pipe_valid_q[STAGES-1] ? pipe_data_q[STAGES-1] : '0;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            pipe_valid_q <= '0;
            for (int k = 0; k < STAGES; k = k + 1) begin
                pipe_data_q[k] <= '0;
            end
        end else if (can_advance) begin
            pipe_valid_q[0] <= req_valid_i;
            if (req_valid_i) begin
                pipe_data_q[0] <= mult_comb;
            end else begin
                pipe_data_q[0] <= '0;
            end

            for (int j = 1; j < STAGES; j = j + 1) begin
                pipe_valid_q[j] <= pipe_valid_q[j-1];
                pipe_data_q[j] <= pipe_data_q[j-1];
            end
        end
    end
""",
)


# -----------------------------------------------------------------------------
# 8. multiplier_iterative
# -----------------------------------------------------------------------------
def _validate_multiplier_iterative(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    signed_val = params.get("SIGNED", 0)
    if not (1 <= w <= 32):
        errors.append(f"W={w} out of range [1..32]")
    if signed_val not in (0, 1):
        errors.append(f"SIGNED={signed_val} must be 0 or 1")
    return errors


MULTIPLIER_ITERATIVE_DEF = ComponentDef(
    id="multiplier_iterative",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Multi-cycle shift-add iterative multiplier (REQ protocol, W+1 latency)",
    tags=["arithmetic", "multiplier", "iterative", "multi-cycle"],
    contract_anchor="multiplier_iterative",
    parameters=[
        ParamDef("W", "int unsigned", "16", "Operand data width in bits", min_value=1, max_value=32),
        ParamDef("SIGNED", "int unsigned", "0", "1 for signed two's complement, 0 for unsigned", min_value=0, max_value=1),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Rising-edge clock"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("req_valid_i", "in", None, "Request valid handshake input"),
        PortDef("req_ready_o", "out", None, "Request ready handshake output"),
        PortDef("a_i", "in", "W-1:0", "First multiplicand operand"),
        PortDef("b_i", "in", "W-1:0", "Second multiplicand operand"),
        PortDef("rsp_valid_o", "out", None, "Response valid handshake output"),
        PortDef("rsp_ready_i", "in", None, "Response ready handshake input"),
        PortDef("product_o", "out", "(2*W)-1:0", "Full-width product result"),
    ],
    timing=TimingInfo(latency="W+1", throughput="1/(W+1)", reset="async_low"),
    presets={
        "default": {"W": "16", "SIGNED": "0"},
        "w1_signed": {"W": "1", "SIGNED": "1"},
        "w7_unsigned": {"W": "7", "SIGNED": "0"},
        "w32_signed": {"W": "32", "SIGNED": "1"},
    },
    limitations=[
        "One outstanding request at a time (non-pipelined).",
        "Fixed transfer latency W+1 cycles without stall.",
    ],
    is_stateful=True,
    validate_params=_validate_multiplier_iterative,
    create_reference=lambda params: MultiplierIterativeRef(params),
    systemverilog="""    typedef enum logic [1:0] {
        ST_IDLE = 2'd0,
        ST_CALC = 2'd1,
        ST_DONE = 2'd2
    } state_e;

    state_e state_q;
    logic [5:0] count_q;
    logic [2*W-1:0] accum_q;
    logic [2*W-1:0] mplier_q;
    logic [2*W-1:0] mcand_q;
    logic neg_res_q;

    logic [W-1:0] a_mag, b_mag;
    logic a_neg, b_neg;

    always_comb begin
        a_neg = (SIGNED != 0) && a_i[W-1];
        b_neg = (SIGNED != 0) && b_i[W-1];
        a_mag = a_neg ? -a_i : a_i;
        b_mag = b_neg ? -b_i : b_i;
    end

    assign req_ready_o = (state_q == ST_IDLE) || (state_q == ST_DONE && rsp_ready_i);
    assign rsp_valid_o = (state_q == ST_DONE);
    assign product_o = rsp_valid_o ? accum_q : '0;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state_q <= ST_IDLE;
            count_q <= '0;
            accum_q <= '0;
            mplier_q <= '0;
            mcand_q <= '0;
            neg_res_q <= 1'b0;
        end else begin
            case (state_q)
                ST_IDLE: begin
                    if (req_valid_i) begin
                        mcand_q <= {{(W){1'b0}}, a_mag};
                        mplier_q <= {{(W){1'b0}}, b_mag};
                        accum_q <= '0;
                        neg_res_q <= (a_neg ^ b_neg);
                        count_q <= 6'd1;
                        state_q <= ST_CALC;
                    end
                end

                ST_CALC: begin
                    logic [2*W-1:0] next_accum;
                    next_accum = mplier_q[0] ? (accum_q + mcand_q) : accum_q;

                    mcand_q <= mcand_q << 1;
                    mplier_q <= mplier_q >> 1;
                    count_q <= count_q + 6'd1;

                    if (count_q == 6'(W)) begin
                        state_q <= ST_DONE;
                        accum_q <= neg_res_q ? -next_accum : next_accum;
                    end else begin
                        accum_q <= next_accum;
                    end
                end

                ST_DONE: begin
                    if (rsp_ready_i) begin
                        if (req_valid_i) begin
                            mcand_q <= {{(W){1'b0}}, a_mag};
                            mplier_q <= {{(W){1'b0}}, b_mag};
                            accum_q <= '0;
                            neg_res_q <= (a_neg ^ b_neg);
                            count_q <= 6'd1;
                            state_q <= ST_CALC;
                        end else begin
                            state_q <= ST_IDLE;
                        end
                    end
                end

                default: state_q <= ST_IDLE;
            endcase
        end
    end
""",
)


# -----------------------------------------------------------------------------
# 9. mac
# -----------------------------------------------------------------------------
def _validate_mac(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    acc_w = params.get("ACC_W", 0)
    signed_val = params.get("SIGNED", 0)
    if not (1 <= w <= 32):
        errors.append(f"W={w} out of range [1..32]")
    if not (2 * w <= acc_w <= 128):
        errors.append(f"ACC_W={acc_w} out of range [2*W..128]")
    if signed_val not in (0, 1):
        errors.append(f"SIGNED={signed_val} must be 0 or 1")
    return errors


MAC_DEF = ComponentDef(
    id="mac",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Multiply-accumulate unit with accumulator, clear, and elastic output",
    tags=["arithmetic", "mac", "multiply-accumulate", "dsp"],
    contract_anchor="mac",
    parameters=[
        ParamDef("W", "int unsigned", "16", "Operand data width in bits", min_value=1, max_value=32),
        ParamDef("ACC_W", "int unsigned", "40", "Accumulator width in bits", min_value=2, max_value=128),
        ParamDef("SIGNED", "int unsigned", "1", "1 for signed two's complement, 0 for unsigned", min_value=0, max_value=1),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Rising-edge clock"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("req_valid_i", "in", None, "Request valid handshake input"),
        PortDef("req_ready_o", "out", None, "Request ready handshake output"),
        PortDef("a_i", "in", "W-1:0", "First multiplicand operand"),
        PortDef("b_i", "in", "W-1:0", "Second multiplicand operand"),
        PortDef("clear_i", "in", None, "When asserted, resets accumulator before product add"),
        PortDef("rsp_valid_o", "out", None, "Response valid handshake output"),
        PortDef("rsp_ready_i", "in", None, "Response ready handshake input"),
        PortDef("sum_o", "out", "ACC_W-1:0", "Accumulated sum result"),
    ],
    timing=TimingInfo(latency="1", throughput="1", reset="async_low"),
    presets={
        "default": {"W": "16", "ACC_W": "40", "SIGNED": "1"},
        "w1_acc2_unsigned": {"W": "1", "ACC_W": "2", "SIGNED": "0"},
        "w7_acc20_signed": {"W": "7", "ACC_W": "20", "SIGNED": "1"},
        "w32_acc128_signed": {"W": "32", "ACC_W": "128", "SIGNED": "1"},
    },
    limitations=[
        "Accumulator wraps modulo 2**ACC_W.",
        "Response latency is 1 clock cycle; backpressure holds accumulator state.",
    ],
    is_stateful=True,
    validate_params=_validate_mac,
    create_reference=lambda params: MacRef(params),
    systemverilog="""    logic signed [ACC_W-1:0] a_ext, b_ext;
    logic [ACC_W-1:0] acc_q;
    logic [ACC_W-1:0] prod_ext;
    logic out_valid_q;
    logic can_advance;

    always_comb begin
        if (SIGNED != 0) begin
            a_ext = signed'(ACC_W'($signed(a_i)));
            b_ext = signed'(ACC_W'($signed(b_i)));
            prod_ext = a_ext * b_ext;
        end else begin
            prod_ext = ACC_W'(a_i) * ACC_W'(b_i);
        end
    end

    assign can_advance = rsp_ready_i || !out_valid_q;
    assign req_ready_o = can_advance;
    assign rsp_valid_o = out_valid_q;
    assign sum_o = out_valid_q ? acc_q : '0;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            acc_q <= '0;
            out_valid_q <= 1'b0;
        end else if (can_advance) begin
            if (req_valid_i) begin
                if (clear_i) begin
                    acc_q <= prod_ext;
                end else begin
                    acc_q <= acc_q + prod_ext;
                end
                out_valid_q <= 1'b1;
            end else begin
                out_valid_q <= 1'b0;
            end
        end
    end
""",
)


# -----------------------------------------------------------------------------
# 10. divider_iterative
# -----------------------------------------------------------------------------
def _validate_divider_iterative(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    signed_val = params.get("SIGNED", 0)
    if not (2 <= w <= 32):
        errors.append(f"W={w} out of range [2..32]")
    if signed_val not in (0, 1):
        errors.append(f"SIGNED={signed_val} must be 0 or 1")
    return errors


DIVIDER_ITERATIVE_DEF = ComponentDef(
    id="divider_iterative",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Multi-cycle restoring divider with quotient, remainder, div-zero, overflow",
    tags=["arithmetic", "divider", "restoring", "multi-cycle"],
    contract_anchor="divider_iterative",
    parameters=[
        ParamDef("W", "int unsigned", "16", "Operand and result data width in bits", min_value=2, max_value=32),
        ParamDef("SIGNED", "int unsigned", "0", "1 for signed two's complement, 0 for unsigned", min_value=0, max_value=1),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Rising-edge clock"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("req_valid_i", "in", None, "Request valid handshake input"),
        PortDef("req_ready_o", "out", None, "Request ready handshake output"),
        PortDef("dividend_i", "in", "W-1:0", "Dividend operand"),
        PortDef("divisor_i", "in", "W-1:0", "Divisor operand"),
        PortDef("rsp_valid_o", "out", None, "Response valid handshake output"),
        PortDef("rsp_ready_i", "in", None, "Response ready handshake input"),
        PortDef("quotient_o", "out", "W-1:0", "Quotient result"),
        PortDef("remainder_o", "out", "W-1:0", "Remainder result"),
        PortDef("div_zero_o", "out", None, "Division by zero exception flag"),
        PortDef("overflow_o", "out", None, "Signed overflow exception flag (min / -1)"),
    ],
    timing=TimingInfo(latency="W+1", throughput="1/(W+1)", reset="async_low"),
    presets={
        "default": {"W": "16", "SIGNED": "0"},
        "w2_signed": {"W": "2", "SIGNED": "1"},
        "w4_unsigned": {"W": "4", "SIGNED": "0"},
        "w32_signed": {"W": "32", "SIGNED": "1"},
    },
    limitations=[
        "One restoring iteration per dividend bit; one outstanding request.",
        "Transfer latency W+1 cycles without stalls, including error cases.",
    ],
    is_stateful=True,
    validate_params=_validate_divider_iterative,
    create_reference=lambda params: DividerIterativeRef(params),
    systemverilog="""    typedef enum logic [1:0] {
        ST_IDLE = 2'd0,
        ST_CALC = 2'd1,
        ST_DONE = 2'd2
    } state_e;

    state_e state_q;
    logic [5:0] count_q;
    logic [W-1:0] quot_q, rem_q;
    logic div_zero_q, overflow_q;

    // Registers for restoring algorithm
    logic [W-1:0] d_reg;
    logic [2*W:0] rem_quot_reg;
    logic q_neg_q, r_neg_q;

    assign req_ready_o = (state_q == ST_IDLE) || (state_q == ST_DONE && rsp_ready_i);
    assign rsp_valid_o = (state_q == ST_DONE);
    assign quotient_o = rsp_valid_o ? quot_q : '0;
    assign remainder_o = rsp_valid_o ? rem_q : '0;
    assign div_zero_o = rsp_valid_o ? div_zero_q : 1'b0;
    assign overflow_o = rsp_valid_o ? overflow_q : 1'b0;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state_q <= ST_IDLE;
            count_q <= '0;
            quot_q <= '0;
            rem_q <= '0;
            div_zero_q <= 1'b0;
            overflow_q <= 1'b0;
            d_reg <= '0;
            rem_quot_reg <= '0;
            q_neg_q <= 1'b0;
            r_neg_q <= 1'b0;
        end else begin
            case (state_q)
                ST_IDLE: begin
                    if (req_valid_i) begin
                        count_q <= 6'd1;
                        state_q <= ST_CALC;

                        if (divisor_i == '0) begin
                            div_zero_q <= 1'b1;
                            overflow_q <= 1'b0;
                            quot_q <= '0;
                            rem_q <= dividend_i;
                            d_reg <= '0;
                            rem_quot_reg <= '0;
                        end else if ((SIGNED != 0) && (dividend_i == {1'b1, {(W-1){1'b0}}}) && (divisor_i == {W{1'b1}})) begin
                            div_zero_q <= 1'b0;
                            overflow_q <= 1'b1;
                            quot_q <= {1'b1, {(W-1){1'b0}}};
                            rem_q <= '0;
                            d_reg <= '0;
                            rem_quot_reg <= '0;
                        end else begin
                            logic [W-1:0] num_mag, den_mag;
                            logic num_s, den_s;
                            div_zero_q <= 1'b0;
                            overflow_q <= 1'b0;
                            num_s = (SIGNED != 0) && dividend_i[W-1];
                            den_s = (SIGNED != 0) && divisor_i[W-1];
                            num_mag = num_s ? -dividend_i : dividend_i;
                            den_mag = den_s ? -divisor_i : divisor_i;
                            q_neg_q <= num_s ^ den_s;
                            r_neg_q <= num_s;
                            d_reg <= den_mag;
                            rem_quot_reg <= {{(W+1){1'b0}}, num_mag};
                        end
                    end
                end

                ST_CALC: begin
                    count_q <= count_q + 6'd1;
                    if (!div_zero_q && !overflow_q) begin
                        logic [2*W:0] shifted;
                        logic [W:0] sub_trial;
                        logic [2*W:0] next_rem_quot;
                        shifted = rem_quot_reg << 1;
                        sub_trial = shifted[2*W:W] - {1'b0, d_reg};
                        if (!sub_trial[W]) begin
                            next_rem_quot = {sub_trial, shifted[W-1:1], 1'b1};
                        end else begin
                            next_rem_quot = shifted;
                        end
                        rem_quot_reg <= next_rem_quot;

                        if (count_q == 6'(W)) begin
                            state_q <= ST_DONE;
                            quot_q <= q_neg_q ? -next_rem_quot[W-1:0] : next_rem_quot[W-1:0];
                            rem_q <= r_neg_q ? -next_rem_quot[2*W-1:W] : next_rem_quot[2*W-1:W];
                        end
                    end else begin
                        if (count_q == 6'(W)) begin
                            state_q <= ST_DONE;
                        end
                    end
                end

                ST_DONE: begin
                    if (rsp_ready_i) begin
                        if (req_valid_i) begin
                            count_q <= 6'd1;
                            state_q <= ST_CALC;

                            if (divisor_i == '0) begin
                                div_zero_q <= 1'b1;
                                overflow_q <= 1'b0;
                                quot_q <= '0;
                                rem_q <= dividend_i;
                                d_reg <= '0;
                                rem_quot_reg <= '0;
                            end else if ((SIGNED != 0) && (dividend_i == {1'b1, {(W-1){1'b0}}}) && (divisor_i == {W{1'b1}})) begin
                                div_zero_q <= 1'b0;
                                overflow_q <= 1'b1;
                                quot_q <= {1'b1, {(W-1){1'b0}}};
                                rem_q <= '0;
                                d_reg <= '0;
                                rem_quot_reg <= '0;
                            end else begin
                                logic [W-1:0] num_mag, den_mag;
                                logic num_s, den_s;
                                div_zero_q <= 1'b0;
                                overflow_q <= 1'b0;
                                num_s = (SIGNED != 0) && dividend_i[W-1];
                                den_s = (SIGNED != 0) && divisor_i[W-1];
                                num_mag = num_s ? -dividend_i : dividend_i;
                                den_mag = den_s ? -divisor_i : divisor_i;
                                q_neg_q <= num_s ^ den_s;
                                r_neg_q <= num_s;
                                d_reg <= den_mag;
                                rem_quot_reg <= {{(W+1){1'b0}}, num_mag};
                            end
                        end else begin
                            state_q <= ST_IDLE;
                        end
                    end
                end

                default: state_q <= ST_IDLE;
            endcase
        end
    end
""",
)


# -----------------------------------------------------------------------------
# 11. divider_pipeline
# -----------------------------------------------------------------------------
def _validate_divider_pipeline(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    signed_val = params.get("SIGNED", 0)
    if not (2 <= w <= 32):
        errors.append(f"W={w} out of range [2..32]")
    if signed_val not in (0, 1):
        errors.append(f"SIGNED={signed_val} must be 0 or 1")
    return errors


DIVIDER_PIPELINE_DEF = ComponentDef(
    id="divider_pipeline",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Fully-staged restoring pipelined divider accepting 1 request per edge",
    tags=["arithmetic", "divider", "pipelined", "restoring"],
    contract_anchor="divider_pipeline",
    parameters=[
        ParamDef("W", "int unsigned", "16", "Operand and result data width in bits", min_value=2, max_value=32),
        ParamDef("SIGNED", "int unsigned", "0", "1 for signed two's complement, 0 for unsigned", min_value=0, max_value=1),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Rising-edge clock"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("req_valid_i", "in", None, "Request valid handshake input"),
        PortDef("req_ready_o", "out", None, "Request ready handshake output"),
        PortDef("dividend_i", "in", "W-1:0", "Dividend operand"),
        PortDef("divisor_i", "in", "W-1:0", "Divisor operand"),
        PortDef("rsp_valid_o", "out", None, "Response valid handshake output"),
        PortDef("rsp_ready_i", "in", None, "Response ready handshake input"),
        PortDef("quotient_o", "out", "W-1:0", "Quotient result"),
        PortDef("remainder_o", "out", "W-1:0", "Remainder result"),
        PortDef("div_zero_o", "out", None, "Division by zero exception flag"),
        PortDef("overflow_o", "out", None, "Signed overflow exception flag (min / -1)"),
    ],
    timing=TimingInfo(latency="W+1", throughput="1", reset="async_low"),
    presets={
        "default": {"W": "16", "SIGNED": "0"},
        "w2_signed": {"W": "2", "SIGNED": "1"},
        "w4_unsigned": {"W": "4", "SIGNED": "0"},
        "w32_signed": {"W": "32", "SIGNED": "1"},
    },
    limitations=[
        "Fully staged restoring division pipeline with latency W+1 cycles.",
        "One transaction per edge accepted and produced without backpressure.",
    ],
    is_stateful=True,
    validate_params=_validate_divider_pipeline,
    create_reference=lambda params: DividerPipelineRef(params),
    systemverilog="""    localparam int STAGES = W + 1;

    logic [STAGES-1:0] pipe_valid_q;
    logic [W-1:0] pipe_quot_q [0:STAGES-1];
    logic [W-1:0] pipe_rem_q [0:STAGES-1];
    logic [STAGES-1:0] pipe_dz_q;
    logic [STAGES-1:0] pipe_ov_q;
    logic can_advance;

    // Calculation intermediate registers across stages
    logic [W-1:0] pipe_d [0:STAGES-1];
    logic [2*W:0] pipe_rem_quot [0:STAGES-1];
    logic [STAGES-1:0] pipe_q_neg;
    logic [STAGES-1:0] pipe_r_neg;

    assign can_advance = rsp_ready_i || !pipe_valid_q[STAGES-1];
    assign req_ready_o = can_advance;
    assign rsp_valid_o = pipe_valid_q[STAGES-1];
    assign quotient_o = pipe_valid_q[STAGES-1] ? pipe_quot_q[STAGES-1] : '0;
    assign remainder_o = pipe_valid_q[STAGES-1] ? pipe_rem_q[STAGES-1] : '0;
    assign div_zero_o = pipe_valid_q[STAGES-1] ? pipe_dz_q[STAGES-1] : 1'b0;
    assign overflow_o = pipe_valid_q[STAGES-1] ? pipe_ov_q[STAGES-1] : 1'b0;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            pipe_valid_q <= '0;
            pipe_dz_q <= '0;
            pipe_ov_q <= '0;
            pipe_q_neg <= '0;
            pipe_r_neg <= '0;
            for (int k = 0; k < STAGES; k = k + 1) begin
                pipe_quot_q[k] <= '0;
                pipe_rem_q[k] <= '0;
                pipe_d[k] <= '0;
                pipe_rem_quot[k] <= '0;
            end
        end else if (can_advance) begin
            // Stage 0: Input latch & exception detect
            pipe_valid_q[0] <= req_valid_i;
            if (req_valid_i) begin
                if (divisor_i == '0) begin
                    pipe_dz_q[0] <= 1'b1;
                    pipe_ov_q[0] <= 1'b0;
                    pipe_quot_q[0] <= '0;
                    pipe_rem_q[0] <= dividend_i;
                    pipe_d[0] <= '0;
                    pipe_rem_quot[0] <= '0;
                    pipe_q_neg[0] <= 1'b0;
                    pipe_r_neg[0] <= 1'b0;
                end else if ((SIGNED != 0) && (dividend_i == {1'b1, {(W-1){1'b0}}}) && (divisor_i == {W{1'b1}})) begin
                    pipe_dz_q[0] <= 1'b0;
                    pipe_ov_q[0] <= 1'b1;
                    pipe_quot_q[0] <= {1'b1, {(W-1){1'b0}}};
                    pipe_rem_q[0] <= '0;
                    pipe_d[0] <= '0;
                    pipe_rem_quot[0] <= '0;
                    pipe_q_neg[0] <= 1'b0;
                    pipe_r_neg[0] <= 1'b0;
                end else begin
                    logic [W-1:0] num_mag, den_mag;
                    logic num_s, den_s;
                    pipe_dz_q[0] <= 1'b0;
                    pipe_ov_q[0] <= 1'b0;
                    num_s = (SIGNED != 0) && dividend_i[W-1];
                    den_s = (SIGNED != 0) && divisor_i[W-1];
                    num_mag = num_s ? -dividend_i : dividend_i;
                    den_mag = den_s ? -divisor_i : divisor_i;
                    pipe_q_neg[0] <= num_s ^ den_s;
                    pipe_r_neg[0] <= num_s;
                    pipe_d[0] <= den_mag;
                    pipe_rem_quot[0] <= {{(W+1){1'b0}}, num_mag};
                end
            end else begin
                pipe_dz_q[0] <= 1'b0;
                pipe_ov_q[0] <= 1'b0;
                pipe_quot_q[0] <= '0;
                pipe_rem_q[0] <= '0;
                pipe_d[0] <= '0;
                pipe_rem_quot[0] <= '0;
                pipe_q_neg[0] <= 1'b0;
                pipe_r_neg[0] <= 1'b0;
            end

            // Stages 1 .. W-1: Restoring iterations
            for (int s = 1; s < W; s = s + 1) begin
                pipe_valid_q[s] <= pipe_valid_q[s-1];
                pipe_dz_q[s] <= pipe_dz_q[s-1];
                pipe_ov_q[s] <= pipe_ov_q[s-1];
                pipe_quot_q[s] <= pipe_quot_q[s-1];
                pipe_rem_q[s] <= pipe_rem_q[s-1];
                pipe_q_neg[s] <= pipe_q_neg[s-1];
                pipe_r_neg[s] <= pipe_r_neg[s-1];
                pipe_d[s] <= pipe_d[s-1];

                if (pipe_valid_q[s-1] && !pipe_dz_q[s-1] && !pipe_ov_q[s-1]) begin
                    logic [2*W:0] shifted;
                    logic [W:0] sub_trial;
                    shifted = pipe_rem_quot[s-1] << 1;
                    sub_trial = shifted[2*W:W] - {1'b0, pipe_d[s-1]};
                    if (!sub_trial[W]) begin
                        pipe_rem_quot[s] <= {sub_trial, shifted[W-1:1], 1'b1};
                    end else begin
                        pipe_rem_quot[s] <= shifted;
                    end
                end else begin
                    pipe_rem_quot[s] <= '0;
                end
            end

            // Final Stage W (index STAGES-1): Last restoring iteration & output resolve
            pipe_valid_q[STAGES-1] <= pipe_valid_q[STAGES-2];
            pipe_dz_q[STAGES-1] <= pipe_dz_q[STAGES-2];
            pipe_ov_q[STAGES-1] <= pipe_ov_q[STAGES-2];

            if (pipe_dz_q[STAGES-2] || pipe_ov_q[STAGES-2]) begin
                pipe_quot_q[STAGES-1] <= pipe_quot_q[STAGES-2];
                pipe_rem_q[STAGES-1] <= pipe_rem_q[STAGES-2];
            end else if (pipe_valid_q[STAGES-2]) begin
                logic [2*W:0] shifted;
                logic [W:0] sub_trial;
                logic [W-1:0] final_q, final_r;
                shifted = pipe_rem_quot[STAGES-2] << 1;
                sub_trial = shifted[2*W:W] - {1'b0, pipe_d[STAGES-2]};
                if (!sub_trial[W]) begin
                    final_q = {shifted[W-1:1], 1'b1};
                    final_r = sub_trial[W-1:0];
                end else begin
                    final_q = shifted[W-1:0];
                    final_r = shifted[2*W-1:W];
                end
                pipe_quot_q[STAGES-1] <= pipe_q_neg[STAGES-2] ? -final_q : final_q;
                pipe_rem_q[STAGES-1] <= pipe_r_neg[STAGES-2] ? -final_r : final_r;
            end else begin
                pipe_quot_q[STAGES-1] <= '0;
                pipe_rem_q[STAGES-1] <= '0;
            end
        end
    end
""",
)


# -----------------------------------------------------------------------------
# 12. integer_sqrt
# -----------------------------------------------------------------------------
def _validate_integer_sqrt(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (2 <= w <= 64):
        errors.append(f"W={w} out of range [2..64]")
    if w % 2 != 0:
        errors.append(f"W={w} must be an even integer")
    return errors


INTEGER_SQRT_DEF = ComponentDef(
    id="integer_sqrt",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Digit-pair restoring integer square root (W/2+1 latency, REQ protocol)",
    tags=["arithmetic", "sqrt", "square_root", "restoring", "multi-cycle"],
    contract_anchor="integer_sqrt",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Radicand data width in bits (must be even)", min_value=2, max_value=64),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Rising-edge clock"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("req_valid_i", "in", None, "Request valid handshake input"),
        PortDef("req_ready_o", "out", None, "Request ready handshake output"),
        PortDef("radicand_i", "in", "W-1:0", "Unsigned radicand input"),
        PortDef("rsp_valid_o", "out", None, "Response valid handshake output"),
        PortDef("rsp_ready_i", "in", None, "Response ready handshake input"),
        PortDef("root_o", "out", "(W/2)-1:0", "Unsigned integer square root floor result"),
        PortDef("remainder_o", "out", "W-1:0", "Remainder (radicand - root**2)"),
    ],
    timing=TimingInfo(latency="(W/2)+1", throughput="1/((W/2)+1)", reset="async_low"),
    presets={
        "default": {"W": "32"},
        "w2": {"W": "2"},
        "w8": {"W": "8"},
        "w64": {"W": "64"},
    },
    limitations=[
        "Unsigned floor square root; invariant root**2 <= radicand < (root+1)**2.",
        "Fixed latency W/2+1 cycles without stall.",
    ],
    is_stateful=True,
    validate_params=_validate_integer_sqrt,
    create_reference=lambda params: IntegerSqrtRef(params),
    systemverilog="""    localparam int HALF_W = W / 2;

    typedef enum logic [1:0] {
        ST_IDLE = 2'd0,
        ST_CALC = 2'd1,
        ST_DONE = 2'd2
    } state_e;

    state_e state_q;
    logic [5:0] count_q;
    logic [HALF_W-1:0] root_q;
    logic [W-1:0] rem_q;

    // Digit-pair working registers
    logic [W-1:0] rad_shift_reg;
    logic [W+1:0] rem_work_reg;
    logic [HALF_W-1:0] root_work_reg;

    assign req_ready_o = (state_q == ST_IDLE) || (state_q == ST_DONE && rsp_ready_i);
    assign rsp_valid_o = (state_q == ST_DONE);
    assign root_o = rsp_valid_o ? root_q : '0;
    assign remainder_o = rsp_valid_o ? rem_q : '0;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state_q <= ST_IDLE;
            count_q <= '0;
            root_q <= '0;
            rem_q <= '0;
            rad_shift_reg <= '0;
            rem_work_reg <= '0;
            root_work_reg <= '0;
        end else begin
            case (state_q)
                ST_IDLE: begin
                    if (req_valid_i) begin
                        count_q <= '0;
                        rad_shift_reg <= radicand_i;
                        rem_work_reg <= '0;
                        root_work_reg <= '0;
                        state_q <= ST_CALC;
                    end
                end

                ST_CALC: begin
                    logic [1:0] pair;
                    logic [W+1:0] next_rem;
                    logic [W+1:0] trial;
                    logic [W+1:0] sub_res;

                    pair = rad_shift_reg[W-1:W-2];
                    next_rem = (rem_work_reg << 2) | {{(W){1'b0}}, pair};
                    trial = {{(W+2-HALF_W-2){1'b0}}, root_work_reg, 2'b01};
                    sub_res = next_rem - trial;

                    if (!sub_res[W+1]) begin
                        rem_work_reg <= sub_res;
                        root_work_reg <= (root_work_reg << 1) | HALF_W'(1);
                    end else begin
                        rem_work_reg <= next_rem;
                        root_work_reg <= (root_work_reg << 1);
                    end

                    rad_shift_reg <= rad_shift_reg << 2;
                    count_q <= count_q + 6'd1;

                    if (count_q == 6'(HALF_W - 1)) begin
                        state_q <= ST_DONE;
                        if (!sub_res[W+1]) begin
                            root_q <= (root_work_reg << 1) | HALF_W'(1);
                            rem_q <= sub_res[W-1:0];
                        end else begin
                            root_q <= (root_work_reg << 1);
                            rem_q <= next_rem[W-1:0];
                        end
                    end
                end

                ST_DONE: begin
                    if (rsp_ready_i) begin
                        if (req_valid_i) begin
                            count_q <= '0;
                            rad_shift_reg <= radicand_i;
                            rem_work_reg <= '0;
                            root_work_reg <= '0;
                            state_q <= ST_CALC;
                        end else begin
                            state_q <= ST_IDLE;
                        end
                    end
                end

                default: state_q <= ST_IDLE;
            endcase
        end
    end
""",
)

PHASE3_MULT_DIV_COMPONENTS: list[ComponentDef] = [
    MULTIPLIER_COMB_DEF,
    MULTIPLIER_PIPELINE_DEF,
    MULTIPLIER_ITERATIVE_DEF,
    MAC_DEF,
    DIVIDER_ITERATIVE_DEF,
    DIVIDER_PIPELINE_DEF,
    INTEGER_SQRT_DEF,
]

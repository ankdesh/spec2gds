"""Phase 3 CORDIC component definitions (Batch 2: 2 components).

Includes:
- cordic_rotate: Iterative circular CORDIC vector rotation with fixed-point angle turns
- cordic_vector: Iterative circular CORDIC vectoring (rectangular to polar conversion)
"""

from __future__ import annotations

from spec_catalog_service.catalog.components.models import ComponentDef, ParamDef, PortDef, TimingInfo
from spec_catalog_service.catalog.components.phase3_models import (
    CordicRotateRef,
    CordicVectorRef,
)


def _validate_cordic(params: dict[str, int]) -> list[str]:
    """Validate common CORDIC parameter constraints."""
    errors = []
    w = params.get("W", 0)
    it = params.get("ITER", 0)
    if not (16 <= w <= 32):
        errors.append(f"W={w} out of range [16..32]")
    if not (8 <= it <= 29):
        errors.append(f"ITER={it} out of range [8..29]")
    if it > w - 3:
        errors.append(f"ITER={it} exceeds W-3={w-3}")
    return errors


# -----------------------------------------------------------------------------
# 1. cordic_rotate
# -----------------------------------------------------------------------------
CORDIC_ROTATE_DEF = ComponentDef(
    id="cordic_rotate",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Iterative circular CORDIC vector rotation with fixed-point angle turns",
    tags=["dsp", "cordic", "rotation", "trigonometric", "vector"],
    contract_anchor="cordic_rotate",
    parameters=[
        ParamDef("W", "int unsigned", "24", "Cartesian and angle data width in bits", min_value=16, max_value=32),
        ParamDef("ITER", "int unsigned", "16", "Number of CORDIC iterations", min_value=8, max_value=29),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("req_valid_i", "in", None, "Request transfer valid"),
        PortDef("req_ready_o", "out", None, "Request transfer ready"),
        PortDef("x_i", "in", "W-1:0", "Signed Cartesian X coordinate (F=W-3 fractional bits)"),
        PortDef("y_i", "in", "W-1:0", "Signed Cartesian Y coordinate (F=W-3 fractional bits)"),
        PortDef("angle_i", "in", "W-1:0", "Signed angle in turns [-0.25, +0.25]"),
        PortDef("rsp_valid_o", "out", None, "Response transfer valid"),
        PortDef("rsp_ready_i", "in", None, "Response transfer ready"),
        PortDef("x_o", "out", "W-1:0", "Rotated signed Cartesian X coordinate"),
        PortDef("y_o", "out", "W-1:0", "Rotated signed Cartesian Y coordinate"),
        PortDef("angle_o", "out", "W-1:0", "Residual angle in turns"),
        PortDef("range_error_o", "out", None, "Asserted iff input exceeded legal domain"),
    ],
    timing=TimingInfo(latency="ITER+2", throughput="1", reset="rst_ni"),
    presets={
        "default": {"W": "24", "ITER": "16"},
        "preset1": {"W": "16", "ITER": "8"},
        "preset2": {"W": "24", "ITER": "12"},
        "preset3": {"W": "32", "ITER": "24"},
    },
    limitations=[
        "Cartesian inputs must satisfy abs(x) <= 2**(W-4) and abs(y) <= 2**(W-4).",
        "Angle input must satisfy abs(angle) <= 2**(W-2) (-0.25 to +0.25 turns).",
        "Out of range inputs return zero coordinates and assert range_error_o.",
        "Transfer latency is exactly ITER+2 clock cycles.",
    ],
    is_stateful=True,
    validate_params=_validate_cordic,
    create_reference=lambda params: CordicRotateRef(params),
    systemverilog="""    localparam int unsigned EW = W + 4;
    localparam int unsigned F = W - 3;
    localparam logic signed [W-1:0] MAX_CART = (W'(1) <<< (F - 1));
    localparam logic signed [W-1:0] MIN_CART = -(W'(1) <<< (F - 1));
    localparam logic signed [W-1:0] MAX_ANG = (W'(1) <<< (W - 2));
    localparam logic signed [W-1:0] MIN_ANG = -(W'(1) <<< (W - 2));

    /* verilator lint_off UNUSEDSIGNAL */
    function automatic logic signed [EW-1:0] cordic_angle(input int unsigned w_val, input int unsigned idx);
        logic signed [63:0] val;
        case (w_val)
            16: begin
                case (idx)
                    0: val = 64'sd8192;
                    1: val = 64'sd4836;
                    2: val = 64'sd2555;
                    3: val = 64'sd1297;
                    4: val = 64'sd651;
                    5: val = 64'sd326;
                    6: val = 64'sd163;
                    7: val = 64'sd81;
                    8: val = 64'sd41;
                    9: val = 64'sd20;
                    10: val = 64'sd10;
                    11: val = 64'sd5;
                    12: val = 64'sd3;
                    default: val = 64'sd0;
                endcase
            end
            24: begin
                case (idx)
                    0: val = 64'sd2097152;
                    1: val = 64'sd1238021;
                    2: val = 64'sd654136;
                    3: val = 64'sd332050;
                    4: val = 64'sd166669;
                    5: val = 64'sd83416;
                    6: val = 64'sd41718;
                    7: val = 64'sd20860;
                    8: val = 64'sd10430;
                    9: val = 64'sd5215;
                    10: val = 64'sd2608;
                    11: val = 64'sd1304;
                    12: val = 64'sd652;
                    13: val = 64'sd326;
                    14: val = 64'sd163;
                    15: val = 64'sd81;
                    16: val = 64'sd41;
                    17: val = 64'sd20;
                    18: val = 64'sd10;
                    19: val = 64'sd5;
                    20: val = 64'sd3;
                    default: val = 64'sd0;
                endcase
            end
            32: begin
                case (idx)
                    0: val = 64'sd536870912;
                    1: val = 64'sd316933406;
                    2: val = 64'sd167458907;
                    3: val = 64'sd85004756;
                    4: val = 64'sd42667331;
                    5: val = 64'sd21354465;
                    6: val = 64'sd10679838;
                    7: val = 64'sd5340245;
                    8: val = 64'sd2670163;
                    9: val = 64'sd1335087;
                    10: val = 64'sd667544;
                    11: val = 64'sd333772;
                    12: val = 64'sd166886;
                    13: val = 64'sd83443;
                    14: val = 64'sd41722;
                    15: val = 64'sd20861;
                    16: val = 64'sd10430;
                    17: val = 64'sd5215;
                    18: val = 64'sd2608;
                    19: val = 64'sd1304;
                    20: val = 64'sd652;
                    21: val = 64'sd326;
                    22: val = 64'sd163;
                    23: val = 64'sd81;
                    24: val = 64'sd41;
                    25: val = 64'sd20;
                    26: val = 64'sd10;
                    27: val = 64'sd5;
                    28: val = 64'sd3;
                    default: val = 64'sd0;
                endcase
            end
            default: val = 64'sd0;
        endcase
        return EW'(val);
    endfunction
    /* verilator lint_on UNUSEDSIGNAL */

    function automatic logic signed [63:0] cordic_kraw(input int unsigned w_val, input int unsigned it_val);
        if (w_val == 24 && it_val == 16) return 64'sd163008219;
        if (w_val == 16 && it_val == 8) return 64'sd636757;
        if (w_val == 24 && it_val == 12) return 64'sd163008225;
        if (w_val == 32 && it_val == 24) return 64'sd41730103940;
        return 64'sd0;
    endfunction

    localparam logic signed [63:0] K_RAW = cordic_kraw(W, ITER);
    localparam int unsigned SHIFT = W + 4;

    typedef enum logic [1:0] {
        IDLE,
        SETUP,
        ITERATE,
        DONE
    } state_e;

    state_e state_q;
    logic [5:0] iter_q;
    logic signed [EW-1:0] x_q, y_q, z_q;
    logic range_err_q;

    logic [W-1:0] rsp_x_q, rsp_y_q, rsp_z_q;
    logic rsp_err_q;
    logic rsp_valid_q;

    // Registered capture of request inputs
    logic signed [W-1:0] cap_x_q, cap_y_q, cap_z_q;

    logic signed [W+63:0] prod_x, prod_y;
    logic signed [W+63:0] shift_x, shift_y;
    logic [SHIFT-1:0] rem_x, rem_y;
    logic [SHIFT-1:0] half_x;
    logic signed [EW-1:0] gain_x, gain_y;

    always_comb begin
        prod_x = {{64{cap_x_q[W-1]}}, cap_x_q} * K_RAW;
        prod_y = {{64{cap_y_q[W-1]}}, cap_y_q} * K_RAW;

        shift_x = prod_x >>> SHIFT;
        shift_y = prod_y >>> SHIFT;

        rem_x = prod_x[SHIFT-1:0];
        rem_y = prod_y[SHIFT-1:0];
        half_x = (SHIFT > 0) ? (EW'(1) <<< (SHIFT - 1)) : '0;

        if (rem_x > half_x) begin
            gain_x = EW'(shift_x + 1'b1);
        end else if (rem_x < half_x) begin
            gain_x = EW'(shift_x);
        end else begin
            gain_x = shift_x[0] ? EW'(shift_x + 1'b1) : EW'(shift_x);
        end

        if (rem_y > half_x) begin
            gain_y = EW'(shift_y + 1'b1);
        end else if (rem_y < half_x) begin
            gain_y = EW'(shift_y);
        end else begin
            gain_y = shift_y[0] ? EW'(shift_y + 1'b1) : EW'(shift_y);
        end
    end

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state_q <= IDLE;
            iter_q <= '0;
            x_q <= '0;
            y_q <= '0;
            z_q <= '0;
            range_err_q <= 1'b0;
            cap_x_q <= '0;
            cap_y_q <= '0;
            cap_z_q <= '0;
            rsp_x_q <= '0;
            rsp_y_q <= '0;
            rsp_z_q <= '0;
            rsp_err_q <= 1'b0;
            rsp_valid_q <= 1'b0;
        end else begin
            if (rsp_valid_q && rsp_ready_i) begin
                rsp_valid_q <= 1'b0;
            end

            case (state_q)
                IDLE: begin
                    if (req_valid_i) begin
                        cap_x_q <= $signed(x_i);
                        cap_y_q <= $signed(y_i);
                        cap_z_q <= $signed(angle_i);
                        state_q <= SETUP;
                    end
                end

                SETUP: begin
                    // Check legal range
                    if (!($signed(cap_x_q) >= MIN_CART && $signed(cap_x_q) <= MAX_CART &&
                          $signed(cap_y_q) >= MIN_CART && $signed(cap_y_q) <= MAX_CART &&
                          $signed(cap_z_q) >= MIN_ANG && $signed(cap_z_q) <= MAX_ANG)) begin
                        range_err_q <= 1'b1;
                    end else begin
                        range_err_q <= 1'b0;
                    end

                    x_q <= gain_x;
                    y_q <= gain_y;
                    z_q <= {{4{cap_z_q[W-1]}}, cap_z_q};
                    iter_q <= '0;
                    state_q <= ITERATE;
                end

                ITERATE: begin
                    if (z_q >= 0) begin
                        x_q <= x_q - (y_q >>> iter_q);
                        y_q <= y_q + (x_q >>> iter_q);
                        z_q <= z_q - cordic_angle(W, 32'(iter_q));
                    end else begin
                        x_q <= x_q + (y_q >>> iter_q);
                        y_q <= y_q - (x_q >>> iter_q);
                        z_q <= z_q + cordic_angle(W, 32'(iter_q));
                    end

                    if (32'(iter_q) == ITER - 1) begin
                        state_q <= DONE;
                    end else begin
                        iter_q <= iter_q + 1'b1;
                    end
                end

                DONE: begin
                    rsp_valid_q <= 1'b1;
                    rsp_err_q <= range_err_q;
                    rsp_x_q <= range_err_q ? '0 : x_q[W-1:0];
                    rsp_y_q <= range_err_q ? '0 : y_q[W-1:0];
                    rsp_z_q <= range_err_q ? '0 : z_q[W-1:0];

                    if (rsp_ready_i) begin
                        if (req_valid_i) begin
                            cap_x_q <= $signed(x_i);
                            cap_y_q <= $signed(y_i);
                            cap_z_q <= $signed(angle_i);
                            state_q <= SETUP;
                        end else begin
                            state_q <= IDLE;
                        end
                    end
                end

                default: state_q <= IDLE;
            endcase
        end
    end

    assign req_ready_o = (state_q == IDLE) || (state_q == DONE && rsp_ready_i);
    assign rsp_valid_o = rsp_valid_q;
    assign x_o = rsp_valid_q ? rsp_x_q : '0;
    assign y_o = rsp_valid_q ? rsp_y_q : '0;
    assign angle_o = rsp_valid_q ? rsp_z_q : '0;
    assign range_error_o = rsp_valid_q ? rsp_err_q : 1'b0;
""",
)


# -----------------------------------------------------------------------------
# 2. cordic_vector
# -----------------------------------------------------------------------------
CORDIC_VECTOR_DEF = ComponentDef(
    id="cordic_vector",
    category="arithmetic_dsp",
    phase=3,
    implementation="composite",
    summary="Iterative circular CORDIC vectoring (rectangular to polar conversion)",
    tags=["dsp", "cordic", "vectoring", "polar", "atan2", "magnitude"],
    contract_anchor="cordic_vector",
    parameters=[
        ParamDef("W", "int unsigned", "24", "Cartesian and angle data width in bits", min_value=16, max_value=32),
        ParamDef("ITER", "int unsigned", "16", "Number of CORDIC iterations", min_value=8, max_value=29),
    ],
    ports=[
        PortDef("clk_i", "in", None, "Clock input"),
        PortDef("rst_ni", "in", None, "Active-low asynchronous reset"),
        PortDef("req_valid_i", "in", None, "Request transfer valid"),
        PortDef("req_ready_o", "out", None, "Request transfer ready"),
        PortDef("x_i", "in", "W-1:0", "Signed Cartesian X coordinate (F=W-3 fractional bits)"),
        PortDef("y_i", "in", "W-1:0", "Signed Cartesian Y coordinate (F=W-3 fractional bits)"),
        PortDef("rsp_valid_o", "out", None, "Response transfer valid"),
        PortDef("rsp_ready_i", "in", None, "Response transfer ready"),
        PortDef("magnitude_o", "out", "W-1:0", "Vector magnitude"),
        PortDef("angle_o", "out", "W-1:0", "Vector phase angle in turns [-0.5, +0.5)"),
        PortDef("range_error_o", "out", None, "Asserted iff input exceeded legal domain"),
    ],
    timing=TimingInfo(latency="ITER+2", throughput="1", reset="rst_ni"),
    presets={
        "default": {"W": "24", "ITER": "16"},
        "preset1": {"W": "16", "ITER": "8"},
        "preset2": {"W": "24", "ITER": "12"},
        "preset3": {"W": "32", "ITER": "24"},
    },
    limitations=[
        "Cartesian inputs must satisfy abs(x) <= 2**(W-4) and abs(y) <= 2**(W-4).",
        "Out of range inputs return zero magnitude/angle and assert range_error_o.",
        "Input (0,0) special-cases to magnitude 0, angle 0 with no error.",
        "Transfer latency is exactly ITER+2 clock cycles.",
    ],
    is_stateful=True,
    validate_params=_validate_cordic,
    create_reference=lambda params: CordicVectorRef(params),
    systemverilog="""    localparam int unsigned EW = W + 4;
    localparam int unsigned F = W - 3;
    localparam logic signed [W-1:0] MAX_CART = (W'(1) <<< (F - 1));
    localparam logic signed [W-1:0] MIN_CART = -(W'(1) <<< (F - 1));

    /* verilator lint_off UNUSEDSIGNAL */
    function automatic logic signed [EW-1:0] cordic_angle(input int unsigned w_val, input int unsigned idx);
        logic signed [63:0] val;
        case (w_val)
            16: begin
                case (idx)
                    0: val = 64'sd8192;
                    1: val = 64'sd4836;
                    2: val = 64'sd2555;
                    3: val = 64'sd1297;
                    4: val = 64'sd651;
                    5: val = 64'sd326;
                    6: val = 64'sd163;
                    7: val = 64'sd81;
                    8: val = 64'sd41;
                    9: val = 64'sd20;
                    10: val = 64'sd10;
                    11: val = 64'sd5;
                    12: val = 64'sd3;
                    default: val = 64'sd0;
                endcase
            end
            24: begin
                case (idx)
                    0: val = 64'sd2097152;
                    1: val = 64'sd1238021;
                    2: val = 64'sd654136;
                    3: val = 64'sd332050;
                    4: val = 64'sd166669;
                    5: val = 64'sd83416;
                    6: val = 64'sd41718;
                    7: val = 64'sd20860;
                    8: val = 64'sd10430;
                    9: val = 64'sd5215;
                    10: val = 64'sd2608;
                    11: val = 64'sd1304;
                    12: val = 64'sd652;
                    13: val = 64'sd326;
                    14: val = 64'sd163;
                    15: val = 64'sd81;
                    16: val = 64'sd41;
                    17: val = 64'sd20;
                    18: val = 64'sd10;
                    19: val = 64'sd5;
                    20: val = 64'sd3;
                    default: val = 64'sd0;
                endcase
            end
            32: begin
                case (idx)
                    0: val = 64'sd536870912;
                    1: val = 64'sd316933406;
                    2: val = 64'sd167458907;
                    3: val = 64'sd85004756;
                    4: val = 64'sd42667331;
                    5: val = 64'sd21354465;
                    6: val = 64'sd10679838;
                    7: val = 64'sd5340245;
                    8: val = 64'sd2670163;
                    9: val = 64'sd1335087;
                    10: val = 64'sd667544;
                    11: val = 64'sd333772;
                    12: val = 64'sd166886;
                    13: val = 64'sd83443;
                    14: val = 64'sd41722;
                    15: val = 64'sd20861;
                    16: val = 64'sd10430;
                    17: val = 64'sd5215;
                    18: val = 64'sd2608;
                    19: val = 64'sd1304;
                    20: val = 64'sd652;
                    21: val = 64'sd326;
                    22: val = 64'sd163;
                    23: val = 64'sd81;
                    24: val = 64'sd41;
                    25: val = 64'sd20;
                    26: val = 64'sd10;
                    27: val = 64'sd5;
                    28: val = 64'sd3;
                    default: val = 64'sd0;
                endcase
            end
            default: val = 64'sd0;
        endcase
        return EW'(val);
    endfunction
    /* verilator lint_on UNUSEDSIGNAL */

    function automatic logic signed [63:0] cordic_kraw(input int unsigned w_val, input int unsigned it_val);
        if (w_val == 24 && it_val == 16) return 64'sd163008219;
        if (w_val == 16 && it_val == 8) return 64'sd636757;
        if (w_val == 24 && it_val == 12) return 64'sd163008225;
        if (w_val == 32 && it_val == 24) return 64'sd41730103940;
        return 64'sd0;
    endfunction

    localparam logic signed [63:0] K_RAW = cordic_kraw(W, ITER);
    localparam int unsigned SHIFT = W + 4;

    typedef enum logic [1:0] {
        IDLE,
        SETUP,
        ITERATE,
        DONE
    } state_e;

    state_e state_q;
    logic [5:0] iter_q;
    logic signed [EW-1:0] x_q, y_q, z_q;
    logic range_err_q;
    logic is_zero_q;

    logic [W-1:0] rsp_mag_q, rsp_ang_q;
    logic rsp_err_q;
    logic rsp_valid_q;

    // Registered capture of request inputs
    logic signed [W-1:0] cap_x_q, cap_y_q;

    logic signed [W+63:0] prod_x, prod_y;
    logic signed [W+63:0] shift_x, shift_y;
    logic [SHIFT-1:0] rem_x, rem_y;
    logic [SHIFT-1:0] half_x;
    logic signed [EW-1:0] gain_x, gain_y;

    always_comb begin
        prod_x = {{64{cap_x_q[W-1]}}, cap_x_q} * K_RAW;
        prod_y = {{64{cap_y_q[W-1]}}, cap_y_q} * K_RAW;

        shift_x = prod_x >>> SHIFT;
        shift_y = prod_y >>> SHIFT;

        rem_x = prod_x[SHIFT-1:0];
        rem_y = prod_y[SHIFT-1:0];
        half_x = (SHIFT > 0) ? (EW'(1) <<< (SHIFT - 1)) : '0;

        if (rem_x > half_x) begin
            gain_x = EW'(shift_x + 1'b1);
        end else if (rem_x < half_x) begin
            gain_x = EW'(shift_x);
        end else begin
            gain_x = shift_x[0] ? EW'(shift_x + 1'b1) : EW'(shift_x);
        end

        if (rem_y > half_x) begin
            gain_y = EW'(shift_y + 1'b1);
        end else if (rem_y < half_x) begin
            gain_y = EW'(shift_y);
        end else begin
            gain_y = shift_y[0] ? EW'(shift_y + 1'b1) : EW'(shift_y);
        end
    end

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state_q <= IDLE;
            iter_q <= '0;
            x_q <= '0;
            y_q <= '0;
            z_q <= '0;
            range_err_q <= 1'b0;
            is_zero_q <= 1'b0;
            cap_x_q <= '0;
            cap_y_q <= '0;
            rsp_mag_q <= '0;
            rsp_ang_q <= '0;
            rsp_err_q <= 1'b0;
            rsp_valid_q <= 1'b0;
        end else begin
            if (rsp_valid_q && rsp_ready_i) begin
                rsp_valid_q <= 1'b0;
            end

            case (state_q)
                IDLE: begin
                    if (req_valid_i) begin
                        cap_x_q <= $signed(x_i);
                        cap_y_q <= $signed(y_i);
                        state_q <= SETUP;
                    end
                end

                SETUP: begin
                    // Check legal range
                    if (!($signed(cap_x_q) >= MIN_CART && $signed(cap_x_q) <= MAX_CART &&
                          $signed(cap_y_q) >= MIN_CART && $signed(cap_y_q) <= MAX_CART)) begin
                        range_err_q <= 1'b1;
                        is_zero_q <= 1'b0;
                    end else if (cap_x_q == '0 && cap_y_q == '0) begin
                        range_err_q <= 1'b0;
                        is_zero_q <= 1'b1;
                    end else begin
                        range_err_q <= 1'b0;
                        is_zero_q <= 1'b0;
                    end

                    if (gain_x < 0) begin
                        x_q <= -gain_x;
                        y_q <= -gain_y;
                        z_q <= (gain_y >= 0) ? (EW'(1) <<< (W - 1)) : -(EW'(1) <<< (W - 1));
                    end else begin
                        x_q <= gain_x;
                        y_q <= gain_y;
                        z_q <= '0;
                    end

                    iter_q <= '0;
                    state_q <= ITERATE;
                end

                ITERATE: begin
                    if (y_q >= 0) begin
                        x_q <= x_q + (y_q >>> iter_q);
                        y_q <= y_q - (x_q >>> iter_q);
                        z_q <= z_q + cordic_angle(W, 32'(iter_q));
                    end else begin
                        x_q <= x_q - (y_q >>> iter_q);
                        y_q <= y_q + (x_q >>> iter_q);
                        z_q <= z_q - cordic_angle(W, 32'(iter_q));
                    end

                    if (32'(iter_q) == ITER - 1) begin
                        state_q <= DONE;
                    end else begin
                        iter_q <= iter_q + 1'b1;
                    end
                end

                DONE: begin
                    rsp_valid_q <= 1'b1;
                    rsp_err_q <= range_err_q;
                    if (range_err_q || is_zero_q) begin
                        rsp_mag_q <= '0;
                        rsp_ang_q <= '0;
                    end else begin
                        rsp_mag_q <= x_q[W-1:0];
                        rsp_ang_q <= z_q[W-1:0];
                    end

                    if (rsp_ready_i) begin
                        if (req_valid_i) begin
                            cap_x_q <= $signed(x_i);
                            cap_y_q <= $signed(y_i);
                            state_q <= SETUP;
                        end else begin
                            state_q <= IDLE;
                        end
                    end
                end

                default: state_q <= IDLE;
            endcase
        end
    end

    assign req_ready_o = (state_q == IDLE) || (state_q == DONE && rsp_ready_i);
    assign rsp_valid_o = rsp_valid_q;
    assign magnitude_o = rsp_valid_q ? rsp_mag_q : '0;
    assign angle_o = rsp_valid_q ? rsp_ang_q : '0;
    assign range_error_o = rsp_valid_q ? rsp_err_q : 1'b0;
""",
)

PHASE3_CORDIC_COMPONENTS: list[ComponentDef] = [
    CORDIC_ROTATE_DEF,
    CORDIC_VECTOR_DEF,
]

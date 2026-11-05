"""Normative Component definitions and reference models for Phase 3 Group A (Basic & Saturating Arithmetic).

Components:
1. add_sub
2. saturating_add_sub
3. comparator
4. min_max
5. absolute_value
"""

from __future__ import annotations

from spec_catalog_service.catalog.components.models import ComponentDef, ParamDef, PortDef
from spec_catalog_service.catalog.components.phase3_models import (
    AbsoluteValueRef,
    AddSubRef,
    ComparatorRef,
    MinMaxRef,
    SaturatingAddSubRef,
)
from spec_catalog_service.catalog.schemas import TimingInfo


# -----------------------------------------------------------------------------
# 1. add_sub
# -----------------------------------------------------------------------------
def _validate_add_sub(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (1 <= w <= 64):
        errors.append(f"W={w} out of range [1..64]")
    return errors


ADD_SUB_DEF = ComponentDef(
    id="add_sub",
    category="arithmetic_dsp",
    phase=3,
    summary="Parameterized adder/subtractor with carry-out, borrow flag, and signed overflow",
    tags=["arithmetic", "adder", "subtractor", "combinational"],
    contract_anchor="add_sub",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Operand and result data width", min_value=1, max_value=64),
    ],
    ports=[
        PortDef("a_i", "in", "W-1:0", "First operand"),
        PortDef("b_i", "in", "W-1:0", "Second operand"),
        PortDef("sub_i", "in", None, "Subtract select (0: add, 1: subtract)"),
        PortDef("result_o", "out", "W-1:0", "Arithmetic result"),
        PortDef("carry_o", "out", None, "Carry-out (add) or no-borrow (sub, a >= b)"),
        PortDef("overflow_o", "out", None, "Signed two's-complement overflow"),
    ],
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    presets={
        "default": {"W": "32"},
        "w1": {"W": "1"},
        "w4": {"W": "4"},
        "w64": {"W": "64"},
    },
    limitations=[
        "Combinational path from operands to result, carry, and overflow.",
        "Unsigned carry_o semantics: sum carry-out for addition, not-borrow for subtraction.",
    ],
    is_stateful=False,
    validate_params=_validate_add_sub,
    create_reference=lambda params: AddSubRef(params),
    systemverilog="""    logic [W:0] sum_full;
    logic sa, sb, sr;

    always_comb begin
        sa = a_i[W-1];
        sb = b_i[W-1];
        if (sub_i) begin
            sum_full = {1'b0, a_i} - {1'b0, b_i};
            result_o = sum_full[W-1:0];
            carry_o = (a_i >= b_i);
            sr = result_o[W-1];
            overflow_o = (sa != sb) && (sr != sa);
        end else begin
            sum_full = {1'b0, a_i} + {1'b0, b_i};
            result_o = sum_full[W-1:0];
            carry_o = sum_full[W];
            sr = result_o[W-1];
            overflow_o = (sa == sb) && (sr != sa);
        end
    end
""",
)


# -----------------------------------------------------------------------------
# 2. saturating_add_sub
# -----------------------------------------------------------------------------
def _validate_saturating_add_sub(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    signed_val = params.get("SIGNED", 0)
    if not (2 <= w <= 64):
        errors.append(f"W={w} out of range [2..64]")
    if signed_val not in (0, 1):
        errors.append(f"SIGNED={signed_val} must be 0 or 1")
    return errors


SATURATING_ADD_SUB_DEF = ComponentDef(
    id="saturating_add_sub",
    category="arithmetic_dsp",
    phase=3,
    summary="Signed/unsigned adder/subtractor with automatic saturation clamping",
    tags=["arithmetic", "saturation", "clamp", "combinational"],
    contract_anchor="saturating_add_sub",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Operand and result data width", min_value=2, max_value=64),
        ParamDef("SIGNED", "int unsigned", "1", "1 for signed two's complement, 0 for unsigned", min_value=0, max_value=1),
    ],
    ports=[
        PortDef("a_i", "in", "W-1:0", "First operand"),
        PortDef("b_i", "in", "W-1:0", "Second operand"),
        PortDef("sub_i", "in", None, "Subtract select (0: add, 1: subtract)"),
        PortDef("result_o", "out", "W-1:0", "Clamped arithmetic result"),
        PortDef("saturated_o", "out", None, "High iff the result was clamped to bounds"),
    ],
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    presets={
        "default": {"W": "32", "SIGNED": "1"},
        "w2_unsigned": {"W": "2", "SIGNED": "0"},
        "w4_signed": {"W": "4", "SIGNED": "1"},
        "w64_unsigned": {"W": "64", "SIGNED": "0"},
    },
    limitations=[
        "Signed mode clamps to [-(2**(W-1)), 2**(W-1) - 1].",
        "Unsigned mode clamps to [0, 2**W - 1].",
    ],
    is_stateful=False,
    validate_params=_validate_saturating_add_sub,
    create_reference=lambda params: SaturatingAddSubRef(params),
    systemverilog="""    logic signed [W:0] s_a, s_b, s_res;
    logic [W:0] u_a, u_b, u_res;
    logic signed [W-1:0] s_max, s_min;
    logic [W-1:0] u_max;

    always_comb begin
        s_max = {1'b0, {(W-1){1'b1}}};
        s_min = {1'b1, {(W-1){1'b0}}};
        u_max = {W{1'b1}};
        s_a = '0;
        s_b = '0;
        s_res = '0;
        u_a = '0;
        u_b = '0;
        u_res = '0;

        if (SIGNED != 0) begin
            s_a = {{1{a_i[W-1]}}, a_i};
            s_b = {{1{b_i[W-1]}}, b_i};
            s_res = sub_i ? (s_a - s_b) : (s_a + s_b);

            if (s_res > $signed({{1{s_max[W-1]}}, s_max})) begin
                result_o = s_max;
                saturated_o = 1'b1;
            end else if (s_res < $signed({{1{s_min[W-1]}}, s_min})) begin
                result_o = s_min;
                saturated_o = 1'b1;
            end else begin
                result_o = s_res[W-1:0];
                saturated_o = 1'b0;
            end
        end else begin
            u_a = {1'b0, a_i};
            u_b = {1'b0, b_i};
            if (sub_i) begin
                if (a_i < b_i) begin
                    result_o = '0;
                    saturated_o = 1'b1;
                end else begin
                    result_o = a_i - b_i;
                    saturated_o = 1'b0;
                end
            end else begin
                u_res = u_a + u_b;
                if (u_res[W]) begin
                    result_o = u_max;
                    saturated_o = 1'b1;
                end else begin
                    result_o = u_res[W-1:0];
                    saturated_o = 1'b0;
                end
            end
        end
    end
""",
)


# -----------------------------------------------------------------------------
# 3. comparator
# -----------------------------------------------------------------------------
def _validate_comparator(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    signed_val = params.get("SIGNED", 0)
    if not (1 <= w <= 64):
        errors.append(f"W={w} out of range [1..64]")
    if signed_val not in (0, 1):
        errors.append(f"SIGNED={signed_val} must be 0 or 1")
    return errors


COMPARATOR_DEF = ComponentDef(
    id="comparator",
    category="arithmetic_dsp",
    phase=3,
    summary="Signed/unsigned magnitude comparator with mutually exclusive lt, eq, and gt flags",
    tags=["arithmetic", "comparator", "magnitude", "combinational"],
    contract_anchor="comparator",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Operand data width in bits", min_value=1, max_value=64),
        ParamDef("SIGNED", "int unsigned", "0", "1 for signed two's complement, 0 for unsigned", min_value=0, max_value=1),
    ],
    ports=[
        PortDef("a_i", "in", "W-1:0", "First operand"),
        PortDef("b_i", "in", "W-1:0", "Second operand"),
        PortDef("lt_o", "out", None, "Asserted iff a < b"),
        PortDef("eq_o", "out", None, "Asserted iff a == b"),
        PortDef("gt_o", "out", None, "Asserted iff a > b"),
    ],
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    presets={
        "default": {"W": "32", "SIGNED": "0"},
        "w1_signed": {"W": "1", "SIGNED": "1"},
        "w4_unsigned": {"W": "4", "SIGNED": "0"},
        "w64_signed": {"W": "64", "SIGNED": "1"},
    },
    limitations=[
        "Exactly one output flag is high for any legal input pair.",
        "Zero latency purely combinational comparison.",
    ],
    is_stateful=False,
    validate_params=_validate_comparator,
    create_reference=lambda params: ComparatorRef(params),
    systemverilog="""    always_comb begin
        if (SIGNED != 0) begin
            lt_o = ($signed(a_i) < $signed(b_i));
            eq_o = ($signed(a_i) == $signed(b_i));
            gt_o = ($signed(a_i) > $signed(b_i));
        end else begin
            lt_o = (a_i < b_i);
            eq_o = (a_i == b_i);
            gt_o = (a_i > b_i);
        end
    end
""",
)


# -----------------------------------------------------------------------------
# 4. min_max
# -----------------------------------------------------------------------------
def _validate_min_max(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    signed_val = params.get("SIGNED", 0)
    if not (1 <= w <= 64):
        errors.append(f"W={w} out of range [1..64]")
    if signed_val not in (0, 1):
        errors.append(f"SIGNED={signed_val} must be 0 or 1")
    return errors


MIN_MAX_DEF = ComponentDef(
    id="min_max",
    category="arithmetic_dsp",
    phase=3,
    summary="Simultaneous minimum and maximum selector with tie-breaking and lane indication",
    tags=["arithmetic", "min", "max", "combinational"],
    contract_anchor="min_max",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Operand data width in bits", min_value=1, max_value=64),
        ParamDef("SIGNED", "int unsigned", "0", "1 for signed two's complement, 0 for unsigned", min_value=0, max_value=1),
    ],
    ports=[
        PortDef("a_i", "in", "W-1:0", "First input operand"),
        PortDef("b_i", "in", "W-1:0", "Second input operand"),
        PortDef("min_o", "out", "W-1:0", "Minimum value"),
        PortDef("max_o", "out", "W-1:0", "Maximum value"),
        PortDef("min_from_b_o", "out", None, "High iff b_i was strictly less than a_i"),
    ],
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    presets={
        "default": {"W": "32", "SIGNED": "0"},
        "w1_signed": {"W": "1", "SIGNED": "1"},
        "w4_unsigned": {"W": "4", "SIGNED": "0"},
        "w64_signed": {"W": "64", "SIGNED": "1"},
    },
    limitations=[
        "Ties select a_i for minimum, b_i for maximum, and clear min_from_b_o to 0.",
        "Zero latency purely combinational.",
    ],
    is_stateful=False,
    validate_params=_validate_min_max,
    create_reference=lambda params: MinMaxRef(params),
    systemverilog="""    logic a_le_b;

    always_comb begin
        if (SIGNED != 0) begin
            a_le_b = ($signed(a_i) <= $signed(b_i));
        end else begin
            a_le_b = (a_i <= b_i);
        end

        if (a_le_b) begin
            min_o = a_i;
            max_o = b_i;
            min_from_b_o = 1'b0;
        end else begin
            min_o = b_i;
            max_o = a_i;
            min_from_b_o = 1'b1;
        end
    end
""",
)


# -----------------------------------------------------------------------------
# 5. absolute_value
# -----------------------------------------------------------------------------
def _validate_absolute_value(params: dict[str, int]) -> list[str]:
    errors = []
    w = params.get("W", 0)
    if not (2 <= w <= 64):
        errors.append(f"W={w} out of range [2..64]")
    return errors


ABSOLUTE_VALUE_DEF = ComponentDef(
    id="absolute_value",
    category="arithmetic_dsp",
    phase=3,
    summary="Two's-complement to unsigned magnitude converter with most-negative flag",
    tags=["arithmetic", "absolute_value", "magnitude", "combinational"],
    contract_anchor="absolute_value",
    parameters=[
        ParamDef("W", "int unsigned", "32", "Signed input and unsigned output data width", min_value=2, max_value=64),
    ],
    ports=[
        PortDef("data_i", "in", "W-1:0", "Signed two's-complement input"),
        PortDef("magnitude_o", "out", "W-1:0", "Unsigned magnitude result"),
        PortDef("min_value_o", "out", None, "Asserted iff input is the most negative value -(2**(W-1))"),
    ],
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    presets={
        "default": {"W": "32"},
        "w2": {"W": "2"},
        "w4": {"W": "4"},
        "w64": {"W": "64"},
    },
    limitations=[
        "Input is signed two's-complement; output magnitude is unsigned.",
        "Most-negative input -(2**(W-1)) yields magnitude 2**(W-1) and min_value_o=1.",
    ],
    is_stateful=False,
    validate_params=_validate_absolute_value,
    create_reference=lambda params: AbsoluteValueRef(params),
    systemverilog="""    logic is_min;

    always_comb begin
        is_min = data_i[W-1] && (data_i[W-2:0] == '0);
        min_value_o = is_min;
        if (is_min) begin
            magnitude_o = {1'b1, {(W-1){1'b0}}};
        end else if (data_i[W-1]) begin
            magnitude_o = -data_i;
        end else begin
            magnitude_o = data_i;
        end
    end
""",
)

PHASE3_ARITHMETIC_COMPONENTS: list[ComponentDef] = [
    ADD_SUB_DEF,
    SATURATING_ADD_SUB_DEF,
    COMPARATOR_DEF,
    MIN_MAX_DEF,
    ABSOLUTE_VALUE_DEF,
]

"""Golden independent Python reference models for Phase 3 arithmetic components.

These models evaluate the exact numeric rules defined in docs/TEMP_spec_library_plan/plans/phase-3.md
independently of SystemVerilog lines.
"""

from __future__ import annotations

import math
from typing import Any


def to_signed(val: int, width: int) -> int:
    """Convert an unsigned integer to a two's-complement signed integer."""
    val = val & ((1 << width) - 1)
    if val >= (1 << (width - 1)):
        return val - (1 << width)
    return val


def to_unsigned(val: int, width: int) -> int:
    """Mask integer into a width-bit unsigned value."""
    return val & ((1 << width) - 1)


class AddSubRef:
    """Bit-exact reference model for add_sub."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.w_mask = (1 << self.w) - 1
        self.sign_bit = 1 << (self.w - 1)

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        a = inputs.get("a_i", 0) & self.w_mask
        b = inputs.get("b_i", 0) & self.w_mask
        sub = inputs.get("sub_i", 0) & 1

        sa = (a >> (self.w - 1)) & 1
        sb = (b >> (self.w - 1)) & 1

        if sub == 0:
            full_res = a + b
            result = full_res & self.w_mask
            carry = 1 if full_res >= (1 << self.w) else 0
            sr = (result >> (self.w - 1)) & 1
            overflow = 1 if (sa == sb) and (sr != sa) else 0
        else:
            full_res = a - b
            result = full_res & self.w_mask
            carry = 1 if a >= b else 0
            sr = (result >> (self.w - 1)) & 1
            overflow = 1 if (sa != sb) and (sr != sa) else 0

        return {
            "result_o": result,
            "carry_o": carry,
            "overflow_o": overflow,
        }


class SaturatingAddSubRef:
    """Bit-exact reference model for saturating_add_sub."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.signed = params.get("SIGNED", 1)
        self.w_mask = (1 << self.w) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        a = inputs.get("a_i", 0) & self.w_mask
        b = inputs.get("b_i", 0) & self.w_mask
        sub = inputs.get("sub_i", 0) & 1

        if self.signed:
            sa = to_signed(a, self.w)
            sb = to_signed(b, self.w)
            res = (sa - sb) if sub else (sa + sb)
            max_val = (1 << (self.w - 1)) - 1
            min_val = -(1 << (self.w - 1))

            if res > max_val:
                return {"result_o": max_val & self.w_mask, "saturated_o": 1}
            elif res < min_val:
                return {"result_o": min_val & self.w_mask, "saturated_o": 1}
            else:
                return {"result_o": res & self.w_mask, "saturated_o": 0}
        else:
            res = (a - b) if sub else (a + b)
            max_val = (1 << self.w) - 1
            min_val = 0

            if res > max_val:
                return {"result_o": max_val, "saturated_o": 1}
            elif res < min_val:
                return {"result_o": min_val, "saturated_o": 1}
            else:
                return {"result_o": res, "saturated_o": 0}


class ComparatorRef:
    """Bit-exact reference model for comparator."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.signed = params.get("SIGNED", 0)
        self.w_mask = (1 << self.w) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        a = inputs.get("a_i", 0) & self.w_mask
        b = inputs.get("b_i", 0) & self.w_mask

        val_a = to_signed(a, self.w) if self.signed else a
        val_b = to_signed(b, self.w) if self.signed else b

        lt = 1 if val_a < val_b else 0
        eq = 1 if val_a == val_b else 0
        gt = 1 if val_a > val_b else 0

        return {"lt_o": lt, "eq_o": eq, "gt_o": gt}


class MinMaxRef:
    """Bit-exact reference model for min_max."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.signed = params.get("SIGNED", 0)
        self.w_mask = (1 << self.w) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        a = inputs.get("a_i", 0) & self.w_mask
        b = inputs.get("b_i", 0) & self.w_mask

        val_a = to_signed(a, self.w) if self.signed else a
        val_b = to_signed(b, self.w) if self.signed else b

        if val_a <= val_b:
            return {"min_o": a, "max_o": b, "min_from_b_o": 0}
        else:
            return {"min_o": b, "max_o": a, "min_from_b_o": 1}


class AbsoluteValueRef:
    """Bit-exact reference model for absolute_value."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.w_mask = (1 << self.w) - 1
        self.min_val_signed = -(1 << (self.w - 1))

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data = inputs.get("data_i", 0) & self.w_mask
        s_data = to_signed(data, self.w)

        if s_data == self.min_val_signed:
            return {
                "magnitude_o": (1 << (self.w - 1)),
                "min_value_o": 1,
            }
        elif s_data < 0:
            return {
                "magnitude_o": (-s_data) & self.w_mask,
                "min_value_o": 0,
            }
        else:
            return {
                "magnitude_o": s_data & self.w_mask,
                "min_value_o": 0,
            }


class MultiplierCombRef:
    """Bit-exact reference model for multiplier_comb."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 16)
        self.signed = params.get("SIGNED", 0)
        self.in_mask = (1 << self.w) - 1
        self.out_mask = (1 << (2 * self.w)) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        a = inputs.get("a_i", 0) & self.in_mask
        b = inputs.get("b_i", 0) & self.in_mask

        if self.signed:
            sa = to_signed(a, self.w)
            sb = to_signed(b, self.w)
            prod = sa * sb
            return {"product_o": prod & self.out_mask}
        else:
            prod = a * b
            return {"product_o": prod & self.out_mask}


class MultiplierPipelineRef:
    """Bit-exact stateful reference model for multiplier_pipeline."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 16)
        self.signed = params.get("SIGNED", 0)
        self.stages = params.get("STAGES", 3)
        self.in_mask = (1 << self.w) - 1
        self.out_mask = (1 << (2 * self.w)) - 1
        self.pipeline: list[tuple[int, int] | None] = [None] * self.stages  # (valid, product)

    def reset(self) -> None:
        self.pipeline = [None] * self.stages

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"req_ready_o": 1, "rsp_valid_o": 0, "product_o": 0}

        req_valid = inputs.get("req_valid_i", 0) & 1
        rsp_ready = inputs.get("rsp_ready_i", 0) & 1

        # Elastic backpressure evaluation
        # If output stage has valid response and rsp_ready is low, pipeline stalls
        can_advance = (rsp_ready == 1) or (self.pipeline[-1] is None)

        if can_advance:
            # Advance pipeline
            out_stage = self.pipeline[-1]
            for i in range(self.stages - 1, 0, -1):
                self.pipeline[i] = self.pipeline[i - 1]

            if req_valid:
                a = inputs.get("a_i", 0) & self.in_mask
                b = inputs.get("b_i", 0) & self.in_mask
                if self.signed:
                    prod = (to_signed(a, self.w) * to_signed(b, self.w)) & self.out_mask
                else:
                    prod = (a * b) & self.out_mask
                self.pipeline[0] = (1, prod)
            else:
                self.pipeline[0] = None

        next_ready = 1 if ((rsp_ready == 1) or (self.pipeline[-1] is None)) else 0
        rsp_valid = 1 if (self.pipeline[-1] is not None) else 0
        product = self.pipeline[-1][1] if (self.pipeline[-1] is not None) else 0

        return {
            "req_ready_o": next_ready,
            "rsp_valid_o": rsp_valid,
            "product_o": product,
        }


class MultiplierIterativeRef:
    """Bit-exact stateful reference model for multiplier_iterative."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 16)
        self.signed = params.get("SIGNED", 0)
        self.in_mask = (1 << self.w) - 1
        self.out_mask = (1 << (2 * self.w)) - 1
        self.state = "IDLE"  # "IDLE", "BUSY", "DONE"
        self.counter = 0
        self.latency = self.w + 1
        self.product = 0

    def reset(self) -> None:
        self.state = "IDLE"
        self.counter = 0
        self.product = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"req_ready_o": 1, "rsp_valid_o": 0, "product_o": 0}

        req_valid = inputs.get("req_valid_i", 0) & 1
        rsp_ready = inputs.get("rsp_ready_i", 0) & 1

        if self.state == "IDLE":
            if req_valid:
                a = inputs.get("a_i", 0) & self.in_mask
                b = inputs.get("b_i", 0) & self.in_mask
                if self.signed:
                    self.product = (to_signed(a, self.w) * to_signed(b, self.w)) & self.out_mask
                else:
                    self.product = (a * b) & self.out_mask
                self.counter = 1
                self.state = "BUSY" if self.latency > 1 else "DONE"

        elif self.state == "BUSY":
            self.counter += 1
            if self.counter >= self.latency:
                self.state = "DONE"

        elif self.state == "DONE":
            if rsp_ready:
                if req_valid:
                    a = inputs.get("a_i", 0) & self.in_mask
                    b = inputs.get("b_i", 0) & self.in_mask
                    if self.signed:
                        self.product = (to_signed(a, self.w) * to_signed(b, self.w)) & self.out_mask
                    else:
                        self.product = (a * b) & self.out_mask
                    self.counter = 1
                    self.state = "BUSY" if self.latency > 1 else "DONE"
                else:
                    self.state = "IDLE"

        req_ready = 1 if (self.state == "IDLE" or (self.state == "DONE" and rsp_ready == 1)) else 0
        rsp_valid = 1 if self.state == "DONE" else 0

        return {
            "req_ready_o": req_ready,
            "rsp_valid_o": rsp_valid,
            "product_o": self.product if rsp_valid else 0,
        }


class MacRef:
    """Bit-exact stateful reference model for mac."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 16)
        self.acc_w = params.get("ACC_W", 40)
        self.signed = params.get("SIGNED", 1)
        self.in_mask = (1 << self.w) - 1
        self.acc_mask = (1 << self.acc_w) - 1
        self.acc = 0
        self.out_valid = 0
        self.out_sum = 0

    def reset(self) -> None:
        self.acc = 0
        self.out_valid = 0
        self.out_sum = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"req_ready_o": 1, "rsp_valid_o": 0, "sum_o": 0}

        req_valid = inputs.get("req_valid_i", 0) & 1
        rsp_ready = inputs.get("rsp_ready_i", 0) & 1

        can_advance = (rsp_ready == 1) or (self.out_valid == 0)

        if can_advance:
            if req_valid:
                a = inputs.get("a_i", 0) & self.in_mask
                b = inputs.get("b_i", 0) & self.in_mask
                clear = inputs.get("clear_i", 0) & 1

                if self.signed:
                    prod = to_signed(a, self.w) * to_signed(b, self.w)
                else:
                    prod = a * b

                if clear:
                    next_acc = prod & self.acc_mask
                else:
                    next_acc = (self.acc + prod) & self.acc_mask

                self.acc = next_acc
                self.out_valid = 1
                self.out_sum = next_acc
            else:
                self.out_valid = 0

        next_ready = 1 if ((rsp_ready == 1) or (self.out_valid == 0)) else 0
        return {
            "req_ready_o": next_ready,
            "rsp_valid_o": self.out_valid,
            "sum_o": self.out_sum if self.out_valid else 0,
        }


def calc_division(num: int, den: int, w: int, signed: bool) -> tuple[int, int, int, int]:
    """Calculate restoring integer division according to normative Phase 3 rules.

    Returns (quotient, remainder, div_zero, overflow).
    """
    w_mask = (1 << w) - 1
    if den == 0:
        return 0, num & w_mask, 1, 0

    if not signed:
        quotient = (num // den) & w_mask
        remainder = (num % den) & w_mask
        return quotient, remainder, 0, 0
    else:
        s_num = to_signed(num, w)
        s_den = to_signed(den, w)
        min_signed = -(1 << (w - 1))

        if s_num == min_signed and s_den == -1:
            return min_signed & w_mask, 0, 0, 1

        abs_num = abs(s_num)
        abs_den = abs(s_den)
        q_mag = abs_num // abs_den
        r_mag = abs_num % abs_den

        q = -q_mag if ((s_num < 0) ^ (s_den < 0)) else q_mag
        r = -r_mag if (s_num < 0) else r_mag

        return q & w_mask, r & w_mask, 0, 0


class DividerIterativeRef:
    """Bit-exact reference model for divider_iterative."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 16)
        self.signed = bool(params.get("SIGNED", 0))
        self.latency = self.w + 1
        self.state = "IDLE"
        self.counter = 0
        self.q = 0
        self.r = 0
        self.div_zero = 0
        self.overflow = 0

    def reset(self) -> None:
        self.state = "IDLE"
        self.counter = 0
        self.q = 0
        self.r = 0
        self.div_zero = 0
        self.overflow = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {
                "req_ready_o": 1,
                "rsp_valid_o": 0,
                "quotient_o": 0,
                "remainder_o": 0,
                "div_zero_o": 0,
                "overflow_o": 0,
            }

        req_valid = inputs.get("req_valid_i", 0) & 1
        rsp_ready = inputs.get("rsp_ready_i", 0) & 1

        if self.state == "IDLE":
            if req_valid:
                num = inputs.get("dividend_i", 0)
                den = inputs.get("divisor_i", 0)
                self.q, self.r, self.div_zero, self.overflow = calc_division(num, den, self.w, self.signed)
                self.counter = 1
                self.state = "BUSY" if self.latency > 1 else "DONE"

        elif self.state == "BUSY":
            self.counter += 1
            if self.counter >= self.latency:
                self.state = "DONE"

        elif self.state == "DONE":
            if rsp_ready:
                if req_valid:
                    num = inputs.get("dividend_i", 0)
                    den = inputs.get("divisor_i", 0)
                    self.q, self.r, self.div_zero, self.overflow = calc_division(num, den, self.w, self.signed)
                    self.counter = 1
                    self.state = "BUSY" if self.latency > 1 else "DONE"
                else:
                    self.state = "IDLE"

        req_ready = 1 if (self.state == "IDLE" or (self.state == "DONE" and rsp_ready == 1)) else 0
        rsp_valid = 1 if self.state == "DONE" else 0

        return {
            "req_ready_o": req_ready,
            "rsp_valid_o": rsp_valid,
            "quotient_o": self.q if rsp_valid else 0,
            "remainder_o": self.r if rsp_valid else 0,
            "div_zero_o": self.div_zero if rsp_valid else 0,
            "overflow_o": self.overflow if rsp_valid else 0,
        }


class DividerPipelineRef:
    """Bit-exact stateful reference model for divider_pipeline."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 16)
        self.signed = bool(params.get("SIGNED", 0))
        self.stages = self.w + 1
        self.pipeline: list[tuple[int, int, int, int, int] | None] = [None] * self.stages  # (valid, q, r, dz, ov)

    def reset(self) -> None:
        self.pipeline = [None] * self.stages

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {
                "req_ready_o": 1,
                "rsp_valid_o": 0,
                "quotient_o": 0,
                "remainder_o": 0,
                "div_zero_o": 0,
                "overflow_o": 0,
            }

        req_valid = inputs.get("req_valid_i", 0) & 1
        rsp_ready = inputs.get("rsp_ready_i", 0) & 1

        can_advance = (rsp_ready == 1) or (self.pipeline[-1] is None)

        if can_advance:
            for i in range(self.stages - 1, 0, -1):
                self.pipeline[i] = self.pipeline[i - 1]

            if req_valid:
                num = inputs.get("dividend_i", 0)
                den = inputs.get("divisor_i", 0)
                q, r, dz, ov = calc_division(num, den, self.w, self.signed)
                self.pipeline[0] = (1, q, r, dz, ov)
            else:
                self.pipeline[0] = None

        next_ready = 1 if ((rsp_ready == 1) or (self.pipeline[-1] is None)) else 0
        rsp_valid = 1 if (self.pipeline[-1] is not None) else 0
        if rsp_valid and self.pipeline[-1] is not None:
            _, q, r, dz, ov = self.pipeline[-1]
        else:
            q, r, dz, ov = 0, 0, 0, 0

        return {
            "req_ready_o": next_ready,
            "rsp_valid_o": rsp_valid,
            "quotient_o": q,
            "remainder_o": r,
            "div_zero_o": dz,
            "overflow_o": ov,
        }


class IntegerSqrtRef:
    """Bit-exact reference model for integer_sqrt."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.latency = (self.w // 2) + 1
        self.w_mask = (1 << self.w) - 1
        self.root_mask = (1 << (self.w // 2)) - 1
        self.state = "IDLE"
        self.counter = 0
        self.root = 0
        self.rem = 0

    def reset(self) -> None:
        self.state = "IDLE"
        self.counter = 0
        self.root = 0
        self.rem = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {
                "req_ready_o": 1,
                "rsp_valid_o": 0,
                "root_o": 0,
                "remainder_o": 0,
            }

        req_valid = inputs.get("req_valid_i", 0) & 1
        rsp_ready = inputs.get("rsp_ready_i", 0) & 1

        if self.state == "IDLE":
            if req_valid:
                radicand = inputs.get("radicand_i", 0) & self.w_mask
                root = math.isqrt(radicand)
                rem = radicand - (root * root)
                self.root = root & self.root_mask
                self.rem = rem & self.w_mask
                self.counter = 1
                self.state = "BUSY" if self.latency > 1 else "DONE"

        elif self.state == "BUSY":
            self.counter += 1
            if self.counter >= self.latency:
                self.state = "DONE"

        elif self.state == "DONE":
            if rsp_ready:
                if req_valid:
                    radicand = inputs.get("radicand_i", 0) & self.w_mask
                    root = math.isqrt(radicand)
                    rem = radicand - (root * root)
                    self.root = root & self.root_mask
                    self.rem = rem & self.w_mask
                    self.counter = 1
                    self.state = "BUSY" if self.latency > 1 else "DONE"
                else:
                    self.state = "IDLE"

        req_ready = 1 if (self.state == "IDLE" or (self.state == "DONE" and rsp_ready == 1)) else 0
        rsp_valid = 1 if self.state == "DONE" else 0

        return {
            "req_ready_o": req_ready,
            "rsp_valid_o": rsp_valid,
            "root_o": self.root if rsp_valid else 0,
            "remainder_o": self.rem if rsp_valid else 0,
        }


# =============================================================================
# Helper Arithmetic Utilities
# =============================================================================

def round_nearest_even(val: int, drop: int) -> int:
    """Divide signed val by 2**drop, rounding to nearest with exact halfway ties to even."""
    if drop <= 0:
        return val
    shifted = val >> drop
    rem = val & ((1 << drop) - 1)
    half = 1 << (drop - 1)
    if rem > half:
        return shifted + 1
    elif rem < half:
        return shifted
    else:
        # Tie: round to even
        return shifted + 1 if (shifted & 1) else shifted


def saturate_signed(val: int, ow: int) -> tuple[int, int]:
    """Clamp signed val to signed ow-bit range. Returns (clamped_unsigned, clipped_flag)."""
    if ow == 1:
        min_v = -1
        max_v = 0
    else:
        min_v = -(1 << (ow - 1))
        max_v = (1 << (ow - 1)) - 1
    ow_mask = (1 << ow) - 1
    if val > max_v:
        return max_v & ow_mask, 1
    elif val < min_v:
        return min_v & ow_mask, 1
    else:
        return val & ow_mask, 0


# =============================================================================
# Phase 3 Batch 1 (Fixed-Point & DSP Reference Models)
# =============================================================================

class FixedRoundRef:
    """Bit-exact reference model for fixed_round."""

    def __init__(self, params: dict[str, int]) -> None:
        self.iw = params.get("IW", 32)
        self.ow = params.get("OW", 16)
        self.drop = params.get("DROP", 8)
        self.ow_mask = (1 << self.ow) - 1
        if self.ow == 1:
            self.min_val = -1
            self.max_val = 0
        else:
            self.min_val = -(1 << (self.ow - 1))
            self.max_val = (1 << (self.ow - 1)) - 1

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        raw_in = inputs.get("data_i", 0)
        s_in = to_signed(raw_in, self.iw)
        rounded = round_nearest_even(s_in, self.drop)
        overflow = 1 if (rounded < self.min_val or rounded > self.max_val) else 0
        return {
            "data_o": rounded & self.ow_mask,
            "overflow_o": overflow,
        }


class FixedSaturateRef:
    """Bit-exact reference model for fixed_saturate."""

    def __init__(self, params: dict[str, int]) -> None:
        self.iw = params.get("IW", 32)
        self.ow = params.get("OW", 16)

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        raw_in = inputs.get("data_i", 0)
        s_in = to_signed(raw_in, self.iw)
        clamped, clipped = saturate_signed(s_in, self.ow)
        return {
            "data_o": clamped,
            "clipped_o": clipped,
        }


class FixedScaleRef:
    """Bit-exact reference model for fixed_scale."""

    def __init__(self, params: dict[str, int]) -> None:
        self.iw = params.get("IW", 16)
        self.ow = params.get("OW", 16)
        self.coeff_w = params.get("COEFF_W", 16)
        self.frac = params.get("FRAC", 8)
        raw_gain = params.get("GAIN", 256)
        self.gain = to_signed(raw_gain, self.coeff_w)

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        raw_in = inputs.get("data_i", 0)
        s_in = to_signed(raw_in, self.iw)
        prod = s_in * self.gain
        rounded = round_nearest_even(prod, self.frac)
        clamped, clipped = saturate_signed(rounded, self.ow)
        return {
            "data_o": clamped,
            "clipped_o": clipped,
        }


class DotProductRef:
    """Bit-exact reference model for dot_product."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 16)
        self.n = params.get("N", 4)
        self.out_w = params.get("OUT_W", 40)
        self.out_mask = (1 << self.out_w) - 1
        self.state = "IDLE"
        self.counter = 0
        self.sum = 0
        self.a_lanes: list[int] = []
        self.b_lanes: list[int] = []

    def reset(self) -> None:
        self.state = "IDLE"
        self.counter = 0
        self.sum = 0
        self.a_lanes = []
        self.b_lanes = []

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"req_ready_o": 1, "rsp_valid_o": 0, "sum_o": 0}

        req_valid = inputs.get("req_valid_i", 0) & 1
        rsp_ready = inputs.get("rsp_ready_i", 0) & 1

        if self.state == "IDLE":
            if req_valid:
                a_raw = inputs.get("a_i", 0)
                b_raw = inputs.get("b_i", 0)
                lane_mask = (1 << self.w) - 1
                self.a_lanes = [to_signed((a_raw >> (i * self.w)) & lane_mask, self.w) for i in range(self.n)]
                self.b_lanes = [to_signed((b_raw >> (i * self.w)) & lane_mask, self.w) for i in range(self.n)]
                self.sum = 0
                self.counter = 0
                self.state = "CALC"

        elif self.state == "CALC":
            if self.counter < self.n:
                self.sum += self.a_lanes[self.counter] * self.b_lanes[self.counter]
                self.counter += 1
            if self.counter >= self.n:
                self.state = "DONE"

        elif self.state == "DONE":
            if rsp_ready:
                if req_valid:
                    a_raw = inputs.get("a_i", 0)
                    b_raw = inputs.get("b_i", 0)
                    lane_mask = (1 << self.w) - 1
                    self.a_lanes = [to_signed((a_raw >> (i * self.w)) & lane_mask, self.w) for i in range(self.n)]
                    self.b_lanes = [to_signed((b_raw >> (i * self.w)) & lane_mask, self.w) for i in range(self.n)]
                    self.sum = 0
                    self.counter = 0
                    self.state = "CALC"
                else:
                    self.state = "IDLE"

        req_ready = 1 if (self.state == "IDLE" or (self.state == "DONE" and rsp_ready == 1)) else 0
        rsp_valid = 1 if self.state == "DONE" else 0

        return {
            "req_ready_o": req_ready,
            "rsp_valid_o": rsp_valid,
            "sum_o": (self.sum & self.out_mask) if rsp_valid else 0,
        }


class FirFilterRef:
    """Bit-exact reference model for fir_filter."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 16)
        self.taps = params.get("TAPS", 4)
        self.cw = params.get("CW", 16)
        self.frac = params.get("FRAC", 8)
        self.ow = params.get("OW", 16)
        coeffs_raw = params.get("COEFFS", 256)
        coeff_mask = (1 << self.cw) - 1
        self.coeffs = [to_signed((coeffs_raw >> (i * self.cw)) & coeff_mask, self.cw) for i in range(self.taps)]
        self.history: list[int] = [0] * self.taps
        self.out_valid = 0
        self.out_data = 0
        self.out_clipped = 0

    def reset(self) -> None:
        self.history = [0] * self.taps
        self.out_valid = 0
        self.out_data = 0
        self.out_clipped = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0, "clipped_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        m_ready = inputs.get("m_ready_i", 0) & 1

        can_accept = (self.out_valid == 0) or (m_ready == 1)

        next_valid = self.out_valid
        next_data = self.out_data
        next_clipped = self.out_clipped

        if can_accept and s_valid:
            s_raw = inputs.get("s_data_i", 0)
            s_val = to_signed(s_raw, self.w)
            acc = s_val * self.coeffs[0] + sum(self.history[i - 1] * self.coeffs[i] for i in range(1, self.taps))
            self.history = [s_val] + self.history[:-1]
            rounded = round_nearest_even(acc, self.frac)
            data_sat, clipped = saturate_signed(rounded, self.ow)
            next_valid = 1
            next_data = data_sat
            next_clipped = clipped
        elif m_ready and (self.out_valid == 1):
            next_valid = 0

        self.out_valid = next_valid
        self.out_data = next_data
        self.out_clipped = next_clipped

        next_ready = int((not self.out_valid) or m_ready)
        return {
            "s_ready_o": next_ready,
            "m_valid_o": self.out_valid,
            "m_data_o": self.out_data if self.out_valid else 0,
            "clipped_o": self.out_clipped if self.out_valid else 0,
        }


class CicDecimatorRef:
    """Bit-exact reference model for cic_decimator."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 16)
        self.r = params.get("R", 4)
        self.order = params.get("ORDER", 2)
        self.clog2_r = math.ceil(math.log2(self.r)) if self.r > 1 else 1
        self.b = self.w + self.order * self.clog2_r
        self.b_mask = (1 << self.b) - 1

        self.integrators = [0] * self.order
        self.comb_prev = [0] * self.order
        self.count = 0
        self.out_valid = 0
        self.out_data = 0

    def reset(self) -> None:
        self.integrators = [0] * self.order
        self.comb_prev = [0] * self.order
        self.count = 0
        self.out_valid = 0
        self.out_data = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        m_ready = inputs.get("m_ready_i", 0) & 1

        can_accept = (self.out_valid == 0) or (m_ready == 1)

        next_valid = self.out_valid
        next_data = self.out_data

        if m_ready and self.out_valid:
            next_valid = 0

        if can_accept and s_valid:
            s_val = to_signed(inputs.get("s_data_i", 0), self.w)
            val = s_val & self.b_mask
            for k in range(self.order):
                self.integrators[k] = (self.integrators[k] + val) & self.b_mask
                val = self.integrators[k]

            if self.count == self.r - 1:
                comb_in = self.integrators[-1]
                for k in range(self.order):
                    diff = (comb_in - self.comb_prev[k]) & self.b_mask
                    self.comb_prev[k] = comb_in
                    comb_in = diff

                next_valid = 1
                next_data = comb_in
                self.count = 0
            else:
                self.count += 1

        self.out_valid = next_valid
        self.out_data = next_data

        next_ready = int((not self.out_valid) or m_ready)
        return {
            "s_ready_o": next_ready,
            "m_valid_o": self.out_valid,
            "m_data_o": self.out_data if self.out_valid else 0,
        }


class CicInterpolatorRef:
    """Bit-exact reference model for cic_interpolator."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 16)
        self.r = params.get("R", 4)
        self.order = params.get("ORDER", 2)
        self.clog2_r = math.ceil(math.log2(self.r)) if self.r > 1 else 1
        self.b = self.w + self.order * self.clog2_r
        self.b_mask = (1 << self.b) - 1

        self.comb_prev = [0] * self.order
        self.integrators = [0] * self.order
        self.count = 0
        self.comb_out = 0
        self.active_group = False
        self.out_valid = 0
        self.out_data = 0

    def reset(self) -> None:
        self.comb_prev = [0] * self.order
        self.integrators = [0] * self.order
        self.count = 0
        self.comb_out = 0
        self.active_group = False
        self.out_valid = 0
        self.out_data = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {"s_ready_o": 1, "m_valid_o": 0, "m_data_o": 0}

        s_valid = inputs.get("s_valid_i", 0) & 1
        m_ready = inputs.get("m_ready_i", 0) & 1

        can_accept = (not self.active_group or (self.out_valid and m_ready and self.count + 1 >= self.r)) and (not self.out_valid or m_ready)

        next_valid = self.out_valid
        next_data = self.out_data

        if self.out_valid and m_ready:
            next_valid = 0
            if self.count + 1 >= self.r:
                self.active_group = False
                self.count = 0
            else:
                self.count += 1
                inp = 0
                for k in range(self.order):
                    self.integrators[k] = (self.integrators[k] + inp) & self.b_mask
                    inp = self.integrators[k]
                next_valid = 1
                next_data = inp

        if can_accept and s_valid:
            s_val = to_signed(inputs.get("s_data_i", 0), self.w)
            comb_in = s_val & self.b_mask
            for k in range(self.order):
                diff = (comb_in - self.comb_prev[k]) & self.b_mask
                self.comb_prev[k] = comb_in
                comb_in = diff

            inp = comb_in
            for k in range(self.order):
                self.integrators[k] = (self.integrators[k] + inp) & self.b_mask
                inp = self.integrators[k]
            next_valid = 1
            next_data = inp
            self.active_group = True
            self.count = 0

        self.out_valid = next_valid
        self.out_data = next_data

        next_can_accept = (not self.active_group or (self.out_valid and m_ready and self.count + 1 >= self.r)) and (not self.out_valid or m_ready)
        return {
            "s_ready_o": int(next_can_accept),
            "m_valid_o": self.out_valid,
            "m_data_o": self.out_data if self.out_valid else 0,
        }


def get_cordic_constants(w: int, iter_val: int) -> tuple[list[int], int]:
    """Compute exact Decimal 80 CORDIC angle constants A[i] and gain Kraw."""
    import decimal
    from decimal import Decimal, ROUND_HALF_EVEN

    ctx = decimal.Context(prec=85)

    def calc_atan(x: Decimal) -> Decimal:
        total = Decimal(0)
        x_power = x
        x_squared = ctx.multiply(x, x)
        k = 0
        while True:
            term = ctx.divide(x_power, Decimal(2 * k + 1))
            if k % 2 == 1:
                total = ctx.subtract(total, term)
            else:
                total = ctx.add(total, term)
            if abs(term) < Decimal("1e-78"):
                break
            x_power = ctx.multiply(x_power, x_squared)
            k += 1
        return total

    atan_fifth = calc_atan(ctx.divide(Decimal(1), Decimal(5)))
    atan_239 = calc_atan(ctx.divide(Decimal(1), Decimal(239)))
    pi = ctx.subtract(ctx.multiply(Decimal(16), atan_fifth), ctx.multiply(Decimal(4), atan_239))

    def round_even(d: Decimal) -> int:
        return int(d.to_integral_exact(rounding=ROUND_HALF_EVEN, context=ctx))

    angles = []
    for i in range(iter_val):
        if i == 0:
            at = ctx.divide(pi, Decimal(4))
        else:
            at = calc_atan(ctx.divide(Decimal(1), Decimal(2**i)))
        turn = ctx.divide(at, ctx.multiply(Decimal(2), pi))
        scaled = ctx.multiply(turn, Decimal(2**w))
        angles.append(round_even(scaled))

    k_val = Decimal(1)
    for i in range(iter_val):
        factor = ctx.add(Decimal(1), Decimal(2**(-2 * i)))
        sqrt_factor = ctx.sqrt(factor)
        k_val = ctx.multiply(k_val, ctx.divide(Decimal(1), sqrt_factor))

    kraw = round_even(ctx.multiply(k_val, Decimal(2**(w + 4))))
    return angles, kraw


class CordicRotateRef:
    """Bit-exact reference model for cordic_rotate."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 24)
        self.iter = params.get("ITER", 16)
        self.angles, self.kraw = get_cordic_constants(self.w, self.iter)
        self.f = self.w - 3
        self.shift = self.w + 4
        self.w_mask = (1 << self.w) - 1

        self.max_cart = 1 << (self.f - 1)
        self.min_cart = -(1 << (self.f - 1))
        self.max_ang = 1 << (self.w - 2)
        self.min_ang = -(1 << (self.w - 2))

        self.state = "IDLE"
        self.cap_x = 0
        self.cap_y = 0
        self.cap_z = 0
        self.x = 0
        self.y = 0
        self.z = 0
        self.iter_cnt = 0
        self.range_err = 0
        self.out_valid = 0
        self.out_x = 0
        self.out_y = 0
        self.out_z = 0
        self.out_err = 0

    def reset(self) -> None:
        self.state = "IDLE"
        self.cap_x = 0
        self.cap_y = 0
        self.cap_z = 0
        self.x = 0
        self.y = 0
        self.z = 0
        self.iter_cnt = 0
        self.range_err = 0
        self.out_valid = 0
        self.out_x = 0
        self.out_y = 0
        self.out_z = 0
        self.out_err = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {
                "req_ready_o": 1,
                "rsp_valid_o": 0,
                "x_o": 0,
                "y_o": 0,
                "angle_o": 0,
                "range_error_o": 0,
            }

        req_valid = inputs.get("req_valid_i", 0) & 1
        rsp_ready = inputs.get("rsp_ready_i", 0) & 1

        if self.out_valid and rsp_ready:
            self.out_valid = 0

        if self.state == "IDLE":
            if req_valid:
                self.cap_x = to_signed(inputs.get("x_i", 0), self.w)
                self.cap_y = to_signed(inputs.get("y_i", 0), self.w)
                self.cap_z = to_signed(inputs.get("angle_i", 0), self.w)
                self.state = "SETUP"

        elif self.state == "SETUP":
            if not (self.min_cart <= self.cap_x <= self.max_cart and
                    self.min_cart <= self.cap_y <= self.max_cart and
                    self.min_ang <= self.cap_z <= self.max_ang):
                self.range_err = 1
            else:
                self.range_err = 0

            self.x = round_nearest_even(self.cap_x * self.kraw, self.shift)
            self.y = round_nearest_even(self.cap_y * self.kraw, self.shift)
            self.z = self.cap_z
            self.iter_cnt = 0
            self.state = "ITERATE"

        elif self.state == "ITERATE":
            d = 1 if self.z >= 0 else -1
            next_x = self.x - d * (self.y >> self.iter_cnt)
            next_y = self.y + d * (self.x >> self.iter_cnt)
            next_z = self.z - d * self.angles[self.iter_cnt]
            self.x = next_x
            self.y = next_y
            self.z = next_z

            if self.iter_cnt == self.iter - 1:
                self.state = "DONE"
            else:
                self.iter_cnt += 1

        elif self.state == "DONE":
            self.out_valid = 1
            self.out_err = self.range_err
            if self.range_err:
                self.out_x = 0
                self.out_y = 0
                self.out_z = 0
            else:
                self.out_x = self.x & self.w_mask
                self.out_y = self.y & self.w_mask
                self.out_z = self.z & self.w_mask

            if rsp_ready:
                if req_valid:
                    self.cap_x = to_signed(inputs.get("x_i", 0), self.w)
                    self.cap_y = to_signed(inputs.get("y_i", 0), self.w)
                    self.cap_z = to_signed(inputs.get("angle_i", 0), self.w)
                    self.state = "SETUP"
                else:
                    self.state = "IDLE"

        req_ready = 1 if (self.state == "IDLE" or (self.state == "DONE" and rsp_ready == 1)) else 0
        return {
            "req_ready_o": req_ready,
            "rsp_valid_o": self.out_valid,
            "x_o": self.out_x if self.out_valid else 0,
            "y_o": self.out_y if self.out_valid else 0,
            "angle_o": self.out_z if self.out_valid else 0,
            "range_error_o": self.out_err if self.out_valid else 0,
        }


class CordicVectorRef:
    """Bit-exact reference model for cordic_vector."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 24)
        self.iter = params.get("ITER", 16)
        self.angles, self.kraw = get_cordic_constants(self.w, self.iter)
        self.f = self.w - 3
        self.shift = self.w + 4
        self.w_mask = (1 << self.w) - 1

        self.max_cart = 1 << (self.f - 1)
        self.min_cart = -(1 << (self.f - 1))

        self.state = "IDLE"
        self.cap_x = 0
        self.cap_y = 0
        self.x = 0
        self.y = 0
        self.z = 0
        self.iter_cnt = 0
        self.range_err = 0
        self.is_zero = 0
        self.out_valid = 0
        self.out_mag = 0
        self.out_ang = 0
        self.out_err = 0

    def reset(self) -> None:
        self.state = "IDLE"
        self.cap_x = 0
        self.cap_y = 0
        self.x = 0
        self.y = 0
        self.z = 0
        self.iter_cnt = 0
        self.range_err = 0
        self.is_zero = 0
        self.out_valid = 0
        self.out_mag = 0
        self.out_ang = 0
        self.out_err = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        rst_n = inputs.get("rst_ni", 1)
        if not rst_n:
            self.reset()
            return {
                "req_ready_o": 1,
                "rsp_valid_o": 0,
                "magnitude_o": 0,
                "angle_o": 0,
                "range_error_o": 0,
            }

        req_valid = inputs.get("req_valid_i", 0) & 1
        rsp_ready = inputs.get("rsp_ready_i", 0) & 1

        if self.out_valid and rsp_ready:
            self.out_valid = 0

        if self.state == "IDLE":
            if req_valid:
                self.cap_x = to_signed(inputs.get("x_i", 0), self.w)
                self.cap_y = to_signed(inputs.get("y_i", 0), self.w)
                self.state = "SETUP"

        elif self.state == "SETUP":
            if not (self.min_cart <= self.cap_x <= self.max_cart and
                    self.min_cart <= self.cap_y <= self.max_cart):
                self.range_err = 1
                self.is_zero = 0
            elif self.cap_x == 0 and self.cap_y == 0:
                self.range_err = 0
                self.is_zero = 1
            else:
                self.range_err = 0
                self.is_zero = 0

            gx = round_nearest_even(self.cap_x * self.kraw, self.shift)
            gy = round_nearest_even(self.cap_y * self.kraw, self.shift)

            if gx < 0:
                self.x = -gx
                self.y = -gy
                self.z = (1 << (self.w - 1)) if gy >= 0 else -(1 << (self.w - 1))
            else:
                self.x = gx
                self.y = gy
                self.z = 0

            self.iter_cnt = 0
            self.state = "ITERATE"

        elif self.state == "ITERATE":
            d = 1 if self.y >= 0 else -1
            next_x = self.x + d * (self.y >> self.iter_cnt)
            next_y = self.y - d * (self.x >> self.iter_cnt)
            next_z = self.z + d * self.angles[self.iter_cnt]
            self.x = next_x
            self.y = next_y
            self.z = next_z

            if self.iter_cnt == self.iter - 1:
                self.state = "DONE"
            else:
                self.iter_cnt += 1

        elif self.state == "DONE":
            self.out_valid = 1
            self.out_err = self.range_err
            if self.range_err or self.is_zero:
                self.out_mag = 0
                self.out_ang = 0
            else:
                self.out_mag = self.x & self.w_mask
                self.out_ang = self.z & self.w_mask

            if rsp_ready:
                if req_valid:
                    self.cap_x = to_signed(inputs.get("x_i", 0), self.w)
                    self.cap_y = to_signed(inputs.get("y_i", 0), self.w)
                    self.state = "SETUP"
                else:
                    self.state = "IDLE"

        req_ready = 1 if (self.state == "IDLE" or (self.state == "DONE" and rsp_ready == 1)) else 0
        return {
            "req_ready_o": req_ready,
            "rsp_valid_o": self.out_valid,
            "magnitude_o": self.out_mag if self.out_valid else 0,
            "angle_o": self.out_ang if self.out_valid else 0,
            "range_error_o": self.out_err if self.out_valid else 0,
        }



# -----------------------------------------------------------------------------
# Batch 3: Integrity & ECC Reference Models
# -----------------------------------------------------------------------------


class ParityRef:
    """Bit-exact reference model for parity."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)

    def reset(self) -> None:
        pass

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data = inputs.get("data_i", 0) & ((1 << self.w) - 1)
        parity_in = inputs.get("parity_i", 0) & 1

        even_parity = bin(data).count("1") % 2
        odd_parity = 1 - even_parity
        error = even_parity ^ parity_in

        return {
            "even_parity_o": even_parity,
            "odd_parity_o": odd_parity,
            "error_o": error,
        }


class CrcSerialRef:
    """Bit-exact reference model for crc_serial."""

    def __init__(self, params: dict[str, int]) -> None:
        self.width = params.get("WIDTH", 32)
        self.poly = params.get("POLY", 79764919)
        self.init = params.get("INIT", 4294967295)
        self.xorout = params.get("XOROUT", 4294967295)
        self.mask = (1 << self.width) - 1
        self.msb_mask = 1 << (self.width - 1)
        self.state = self.init & self.mask

    def reset(self) -> None:
        self.state = self.init & self.mask

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        clear = inputs.get("clear_i", 0) & 1
        valid = inputs.get("valid_i", 0) & 1
        bit = inputs.get("bit_i", 0) & 1

        if clear:
            self.state = self.init & self.mask
        elif valid:
            feedback = (1 if (self.state & self.msb_mask) else 0) ^ bit
            shifted = (self.state << 1) & self.mask
            if feedback:
                self.state = shifted ^ (self.poly & self.mask)
            else:
                self.state = shifted

        return {
            "crc_o": (self.state ^ self.xorout) & self.mask,
        }

    eval = step


class CrcParallelRef:
    """Bit-exact reference model for crc_parallel."""

    def __init__(self, params: dict[str, int]) -> None:
        self.width = params.get("WIDTH", 32)
        self.poly = params.get("POLY", 79764919)
        self.init = params.get("INIT", 4294967295)
        self.xorout = params.get("XOROUT", 4294967295)
        self.bytes = params.get("BYTES", 4)
        self.mask = (1 << self.width) - 1
        self.msb_mask = 1 << (self.width - 1)
        self.state = self.init & self.mask

    def reset(self) -> None:
        self.state = self.init & self.mask

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        clear = inputs.get("clear_i", 0) & 1
        valid = inputs.get("valid_i", 0) & 1
        data = inputs.get("data_i", 0) & ((1 << (8 * self.bytes)) - 1)

        if clear:
            self.state = self.init & self.mask
        elif valid:
            for b in range(self.bytes):
                byte_val = (data >> (8 * b)) & 0xFF
                for k in range(7, -1, -1):
                    bit = (byte_val >> k) & 1
                    feedback = (1 if (self.state & self.msb_mask) else 0) ^ bit
                    shifted = (self.state << 1) & self.mask
                    if feedback:
                        self.state = shifted ^ (self.poly & self.mask)
                    else:
                        self.state = shifted

        return {
            "crc_o": (self.state ^ self.xorout) & self.mask,
        }

    eval = step


class LfsrRef:
    """Bit-exact reference model for lfsr."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 16)
        self.taps = params.get("TAPS", 45)
        self.seed = params.get("SEED", 1)
        self.w_mask = (1 << self.w) - 1
        self.state = self.seed & self.w_mask
        self.seed_error = 0

    def reset(self) -> None:
        self.state = self.seed & self.w_mask
        self.seed_error = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        load = inputs.get("load_i", 0) & 1
        en = inputs.get("en_i", 0) & 1
        seed_in = inputs.get("seed_i", 0) & self.w_mask

        self.seed_error = 0
        if load:
            if seed_in == 0:
                self.seed_error = 1
            else:
                self.state = seed_in
        elif en:
            feedback = bin(self.state & self.taps).count("1") % 2
            self.state = ((self.state << 1) | feedback) & self.w_mask

        return {
            "state_o": self.state,
            "seed_error_o": self.seed_error,
        }

    eval = step


def get_secded_params(data_w: int) -> tuple[int, int]:
    """Calculate P (parity bits) and H (Hamming code length) for given data width."""
    p = 1
    while (1 << p) < (data_w + p + 1):
        p += 1
    return p, data_w + p


def get_secded_positions(data_w: int) -> tuple[list[int], list[int], int, int]:
    """Return (data_positions, parity_positions, p, h) using 1-based Hamming positions."""
    p, h = get_secded_params(data_w)
    parity_positions = [1 << j for j in range(p)]
    data_positions = [k for k in range(1, h + 1) if (k & (k - 1)) != 0]
    return data_positions, parity_positions, p, h


class SecdedEncodeRef:
    """Bit-exact reference model for secded_encode."""

    def __init__(self, params: dict[str, int]) -> None:
        self.data_w = params.get("DATA_W", 32)
        self.dp, self.pp, self.p, self.h = get_secded_positions(self.data_w)
        self.code_w = self.h + 1

    def reset(self) -> None:
        pass

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        data = inputs.get("data_i", 0) & ((1 << self.data_w) - 1)
        code = [0] * self.code_w

        for i in range(self.data_w):
            code[self.dp[i] - 1] = (data >> i) & 1

        for j in range(self.p):
            pos = self.pp[j]
            par = 0
            for k in range(1, self.h + 1):
                if k != pos and (k & pos) != 0:
                    par ^= code[k - 1]
            code[pos - 1] = par

        overall = 0
        for k in range(self.h):
            overall ^= code[k]
        code[self.h] = overall

        code_val = sum(code[i] << i for i in range(self.code_w))
        return {
            "code_o": code_val,
        }


class SecdedDecodeRef:
    """Bit-exact reference model for secded_decode."""

    def __init__(self, params: dict[str, int]) -> None:
        self.data_w = params.get("DATA_W", 32)
        self.dp, self.pp, self.p, self.h = get_secded_positions(self.data_w)
        self.code_w = self.h + 1
        self.code_mask = (1 << self.code_w) - 1

    def reset(self) -> None:
        pass

    def eval(self, inputs: dict[str, int]) -> dict[str, int]:
        code_val = inputs.get("code_i", 0) & self.code_mask

        syn = 0
        for k in range(1, self.h + 1):
            if (code_val >> (k - 1)) & 1:
                syn ^= k

        overall_check = bin(code_val).count("1") % 2

        single_err = 0
        double_err = 0
        corrected = code_val
        if syn == 0 and overall_check == 0:
            pass
        elif syn == 0 and overall_check == 1:
            single_err = 1
        elif 1 <= syn <= self.h and overall_check == 1:
            single_err = 1
            corrected ^= (1 << (syn - 1))
        elif syn != 0 and overall_check == 0:
            double_err = 1
        elif syn > self.h and overall_check == 1:
            double_err = 1

        data_val = 0
        effective_code = code_val if double_err else corrected
        for i, pos in enumerate(self.dp):
            bit = (effective_code >> (pos - 1)) & 1
            data_val |= (bit << i)

        return {
            "data_o": data_val,
            "single_error_o": single_err,
            "double_error_o": double_err,
        }


# -----------------------------------------------------------------------------
# Batch 4: Monitoring & Control Reference Models
# -----------------------------------------------------------------------------


def _clog2(val: int) -> int:
    if val <= 1:
        return 1
    return (val - 1).bit_length()


class WatchdogRef:
    """Bit-exact reference model for watchdog."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 16)
        self.mask = (1 << self.w) - 1
        self.count = 0
        self.expired = 0

    def reset(self) -> None:
        self.count = 0
        self.expired = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        en = inputs.get("enable_i", 0) & 1
        kick = inputs.get("kick_i", 0) & 1
        clear = inputs.get("clear_i", 0) & 1
        limit = inputs.get("limit_i", 0) & self.mask

        if clear:
            self.count = 0
            self.expired = 0
        elif not en:
            self.count = 0
        elif kick:
            self.count = 0
        else:
            if self.count >= limit:
                self.expired = 1
            else:
                self.count = (self.count + 1) & self.mask
                if self.count >= limit:
                    self.expired = 1

        return {
            "expired_o": self.expired,
            "count_o": self.count,
        }

    eval = step


class TimeoutMonitorRef:
    """Bit-exact reference model for timeout_monitor."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 16)
        self.mask = (1 << self.w) - 1
        self.busy = 0
        self.timeout = 0
        self.count = 0
        self.captured_limit = 0

    def reset(self) -> None:
        self.busy = 0
        self.timeout = 0
        self.count = 0
        self.captured_limit = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        start = inputs.get("start_i", 0) & 1
        complete = inputs.get("complete_i", 0) & 1
        cancel = inputs.get("cancel_i", 0) & 1
        limit = inputs.get("limit_i", 0) & self.mask

        self.timeout = 0

        if cancel:
            self.busy = 0
            self.count = 0
        elif complete:
            self.busy = 0
            self.count = 0
        elif start:
            self.captured_limit = limit
            if limit == 0:
                self.timeout = 1
                self.busy = 0
                self.count = 0
            else:
                self.busy = 1
                self.count = 0
        elif self.busy:
            if self.count + 1 >= self.captured_limit:
                self.timeout = 1
                self.busy = 0
                self.count = 0
            else:
                self.count = (self.count + 1) & self.mask

        return {
            "busy_o": self.busy,
            "timeout_o": self.timeout,
        }

    eval = step


class InterruptControllerRef:
    """Bit-exact reference model for interrupt_controller."""

    def __init__(self, params: dict[str, int]) -> None:
        self.n = params.get("N", 8)
        self.n_mask = (1 << self.n) - 1
        self.idx_w = _clog2(self.n)
        self.pending = 0

    def reset(self) -> None:
        self.pending = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        irq = inputs.get("irq_i", 0) & self.n_mask
        en = inputs.get("enable_i", 0) & self.n_mask
        clear = inputs.get("clear_i", 0) & self.n_mask

        self.pending = ((self.pending & ~clear) | irq) & self.n_mask

        eligible = self.pending & en
        if eligible != 0:
            lowest_bit = (eligible & -eligible).bit_length() - 1
            irq_out = 1
            valid_out = 1
            index_out = lowest_bit
        else:
            irq_out = 0
            valid_out = 0
            index_out = 0

        return {
            "pending_o": self.pending,
            "irq_o": irq_out,
            "index_o": index_out,
            "valid_o": valid_out,
        }

    eval = step


class FaultCollectorRef:
    """Bit-exact reference model for fault_collector."""

    def __init__(self, params: dict[str, int]) -> None:
        self.n = params.get("N", 8)
        self.n_mask = (1 << self.n) - 1
        self.idx_w = _clog2(self.n)
        self.sticky = 0
        self.first_valid = 0
        self.first_index = 0

    def reset(self) -> None:
        self.sticky = 0
        self.first_valid = 0
        self.first_index = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        fault = inputs.get("fault_i", 0) & self.n_mask
        clear = inputs.get("clear_i", 0) & self.n_mask

        was_empty = (self.sticky == 0)
        next_sticky = ((self.sticky & ~clear) | fault) & self.n_mask

        if was_empty and fault != 0:
            lowest_bit = (fault & -fault).bit_length() - 1
            self.first_index = lowest_bit
            self.first_valid = 1
        elif next_sticky == 0:
            self.first_valid = 0
            self.first_index = 0

        self.sticky = next_sticky

        return {
            "sticky_o": self.sticky,
            "any_o": 1 if self.sticky != 0 else 0,
            "first_valid_o": self.first_valid,
            "first_index_o": self.first_index,
        }

    eval = step


class LockstepCompareRef:
    """Bit-exact reference model for lockstep_compare."""

    def __init__(self, params: dict[str, int]) -> None:
        self.w = params.get("W", 32)
        self.mask = (1 << self.w) - 1
        self.mismatch = 0
        self.sticky = 0

    def reset(self) -> None:
        self.mismatch = 0
        self.sticky = 0

    def step(self, inputs: dict[str, int]) -> dict[str, int]:
        va = inputs.get("valid_a_i", 0) & 1
        da = inputs.get("data_a_i", 0) & self.mask
        vb = inputs.get("valid_b_i", 0) & 1
        db = inputs.get("data_b_i", 0) & self.mask
        clear = inputs.get("clear_i", 0) & 1

        mismatch_now = 0
        if va != vb:
            mismatch_now = 1
        elif va and vb and (da != db):
            mismatch_now = 1

        self.mismatch = mismatch_now
        if mismatch_now:
            self.sticky = 1
        elif clear:
            self.sticky = 0

        return {
            "mismatch_o": self.mismatch,
            "sticky_o": self.sticky,
        }

    eval = step

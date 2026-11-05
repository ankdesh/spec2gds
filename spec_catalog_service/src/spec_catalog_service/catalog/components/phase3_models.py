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

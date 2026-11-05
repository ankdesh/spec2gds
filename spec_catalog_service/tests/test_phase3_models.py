"""Unit tests for Phase 3 arithmetic Python reference models."""

import pytest

from spec_catalog_service.catalog.components.phase3_models import (
    AddSubRef,
    SaturatingAddSubRef,
    ComparatorRef,
    MinMaxRef,
    AbsoluteValueRef,
    MultiplierCombRef,
    MultiplierPipelineRef,
    MultiplierIterativeRef,
    MacRef,
    DividerIterativeRef,
    DividerPipelineRef,
    IntegerSqrtRef,
    calc_division,
)


def test_add_sub_identities() -> None:
    # W = 4
    ref = AddSubRef({"W": 4})
    # 3 + 2 = 5, carry=0, ovf=0
    r = ref.eval({"a_i": 3, "b_i": 2, "sub_i": 0})
    assert r == {"result_o": 5, "carry_o": 0, "overflow_o": 0}

    # 15 + 1 = 0, carry=1, ovf=0
    r = ref.eval({"a_i": 15, "b_i": 1, "sub_i": 0})
    assert r == {"result_o": 0, "carry_o": 1, "overflow_o": 0}

    # 7 + 1 = 8 (-8 in 4-bit 2's comp), carry=0, ovf=1
    r = ref.eval({"a_i": 7, "b_i": 1, "sub_i": 0})
    assert r == {"result_o": 8, "carry_o": 0, "overflow_o": 1}

    # 5 - 2 = 3, carry=1 (no borrow), ovf=0
    r = ref.eval({"a_i": 5, "b_i": 2, "sub_i": 1})
    assert r == {"result_o": 3, "carry_o": 1, "overflow_o": 0}

    # 2 - 5 = 13 (-3), carry=0 (borrow), ovf=0
    r = ref.eval({"a_i": 2, "b_i": 5, "sub_i": 1})
    assert r == {"result_o": 13, "carry_o": 0, "overflow_o": 0}

    # -8 - 1 = 7 (-8 is 8, 1 is 1), 8 - 1 = 7, carry=1, ovf=1
    r = ref.eval({"a_i": 8, "b_i": 1, "sub_i": 1})
    assert r == {"result_o": 7, "carry_o": 1, "overflow_o": 1}


def test_saturating_add_sub_identities() -> None:
    # W=4, SIGNED=1 (Range: -8 to 7)
    s_ref = SaturatingAddSubRef({"W": 4, "SIGNED": 1})
    # 5 + 3 = 8 -> clamp to 7, sat=1
    r = s_ref.eval({"a_i": 5, "b_i": 3, "sub_i": 0})
    assert r == {"result_o": 7, "saturated_o": 1}

    # -6 - 4 = -10 -> clamp to -8 (8), sat=1
    r = s_ref.eval({"a_i": 10, "b_i": 4, "sub_i": 1})  # 10 is -6
    assert r == {"result_o": 8, "saturated_o": 1}

    # 2 + 3 = 5, sat=0
    r = s_ref.eval({"a_i": 2, "b_i": 3, "sub_i": 0})
    assert r == {"result_o": 5, "saturated_o": 0}

    # W=4, SIGNED=0 (Range: 0 to 15)
    u_ref = SaturatingAddSubRef({"W": 4, "SIGNED": 0})
    # 10 + 7 = 17 -> clamp to 15, sat=1
    r = u_ref.eval({"a_i": 10, "b_i": 7, "sub_i": 0})
    assert r == {"result_o": 15, "saturated_o": 1}

    # 3 - 5 = -2 -> clamp to 0, sat=1
    r = u_ref.eval({"a_i": 3, "b_i": 5, "sub_i": 1})
    assert r == {"result_o": 0, "saturated_o": 1}


def test_comparator_and_min_max() -> None:
    # Unsigned W=4
    cmp_u = ComparatorRef({"W": 4, "SIGNED": 0})
    assert cmp_u.eval({"a_i": 5, "b_i": 10}) == {"lt_o": 1, "eq_o": 0, "gt_o": 0}
    assert cmp_u.eval({"a_i": 10, "b_i": 10}) == {"lt_o": 0, "eq_o": 1, "gt_o": 0}
    assert cmp_u.eval({"a_i": 12, "b_i": 5}) == {"lt_o": 0, "eq_o": 0, "gt_o": 1}

    # Signed W=4 (12 is -4, 5 is +5 -> 12 < 5)
    cmp_s = ComparatorRef({"W": 4, "SIGNED": 1})
    assert cmp_s.eval({"a_i": 12, "b_i": 5}) == {"lt_o": 1, "eq_o": 0, "gt_o": 0}

    # Min/Max ties select a
    mm = MinMaxRef({"W": 4, "SIGNED": 0})
    assert mm.eval({"a_i": 5, "b_i": 5}) == {"min_o": 5, "max_o": 5, "min_from_b_o": 0}
    assert mm.eval({"a_i": 8, "b_i": 3}) == {"min_o": 3, "max_o": 8, "min_from_b_o": 1}


def test_absolute_value() -> None:
    # W=4 (Signed: -8..7)
    ref = AbsoluteValueRef({"W": 4})
    # 0 -> 0
    assert ref.eval({"data_i": 0}) == {"magnitude_o": 0, "min_value_o": 0}
    # 5 -> 5
    assert ref.eval({"data_i": 5}) == {"magnitude_o": 5, "min_value_o": 0}
    # -3 (13) -> 3
    assert ref.eval({"data_i": 13}) == {"magnitude_o": 3, "min_value_o": 0}
    # -8 (8) -> magnitude 8, min_value 1
    assert ref.eval({"data_i": 8}) == {"magnitude_o": 8, "min_value_o": 1}


def test_multiplier_comb() -> None:
    # W=4, unsigned
    m_u = MultiplierCombRef({"W": 4, "SIGNED": 0})
    assert m_u.eval({"a_i": 15, "b_i": 15}) == {"product_o": 225}

    # W=4, signed (-1 * -1 = 1) -> a=15, b=15 -> 1
    m_s = MultiplierCombRef({"W": 4, "SIGNED": 1})
    assert m_s.eval({"a_i": 15, "b_i": 15}) == {"product_o": 1}
    # -8 * -8 = 64
    assert m_s.eval({"a_i": 8, "b_i": 8}) == {"product_o": 64}


def test_mac_step() -> None:
    mac = MacRef({"W": 4, "ACC_W": 8, "SIGNED": 0})
    # clear=1, 3 * 4 = 12
    r = mac.step({"rst_ni": 1, "req_valid_i": 1, "rsp_ready_i": 1, "a_i": 3, "b_i": 4, "clear_i": 1})
    assert r["rsp_valid_o"] == 1
    assert r["sum_o"] == 12

    # clear=0, + 2 * 5 = 12 + 10 = 22
    r = mac.step({"rst_ni": 1, "req_valid_i": 1, "rsp_ready_i": 1, "a_i": 2, "b_i": 5, "clear_i": 0})
    assert r["rsp_valid_o"] == 1
    assert r["sum_o"] == 22


def test_division_calc_and_invariants() -> None:
    # Unsigned 4-bit
    q, r, dz, ov = calc_division(7, 3, 4, False)
    assert (q, r, dz, ov) == (2, 1, 0, 0)
    assert 2 * 3 + 1 == 7

    # Div by zero
    q, r, dz, ov = calc_division(7, 0, 4, False)
    assert (q, r, dz, ov) == (0, 7, 1, 0)

    # Signed 4-bit: 7 / -3 -> q = -2 (14), r = +1
    q, r, dz, ov = calc_division(7, 13, 4, True)  # 13 is -3
    assert (q, r, dz, ov) == (14, 1, 0, 0)

    # Signed 4-bit: -7 / 3 -> q = -2 (14), r = -1 (15)
    q, r, dz, ov = calc_division(9, 3, 4, True)  # 9 is -7
    assert (q, r, dz, ov) == (14, 15, 0, 0)

    # Signed overflow: -8 / -1 -> ovf=1, q=-8 (8), r=0
    q, r, dz, ov = calc_division(8, 15, 4, True)  # 8 is -8, 15 is -1
    assert (q, r, dz, ov) == (8, 0, 0, 1)


def test_integer_sqrt() -> None:
    sqrt_ref = IntegerSqrtRef({"W": 8})
    for x in range(256):
        sqrt_ref.reset()
        # Request in cycle 0
        out = sqrt_ref.step({"rst_ni": 1, "req_valid_i": 1, "rsp_ready_i": 1, "radicand_i": x})
        # Step until response valid
        while out["rsp_valid_o"] == 0:
            out = sqrt_ref.step({"rst_ni": 1, "req_valid_i": 0, "rsp_ready_i": 1, "radicand_i": 0})

        root = out["root_o"]
        rem = out["remainder_o"]
        # Invariant: root**2 <= x < (root + 1)**2 and rem = x - root**2
        assert rem == x - (root * root)
        assert (root * root) <= x < ((root + 1) * (root + 1))

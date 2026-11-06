"""Unit and reference model tests for Phase 3 Batch 1 (Fixed-Point & DSP)."""

from __future__ import annotations

import pytest

from spec_catalog_service.catalog.components.phase3_dsp import (
    CIC_DECIMATOR_DEF,
    CIC_INTERPOLATOR_DEF,
    DOT_PRODUCT_DEF,
    FIR_FILTER_DEF,
    FIXED_ROUND_DEF,
    FIXED_SATURATE_DEF,
    FIXED_SCALE_DEF,
)
from spec_catalog_service.catalog.components.phase3_models import (
    CicDecimatorRef,
    CicInterpolatorRef,
    DotProductRef,
    FirFilterRef,
    FixedRoundRef,
    FixedSaturateRef,
    FixedScaleRef,
    round_nearest_even,
    saturate_signed,
)


def test_round_nearest_even():
    # Tie cases: 0.5 ties round to even
    assert round_nearest_even(1, 1) == 0  # 1/2 = 0.5 -> 0 (even)
    assert round_nearest_even(3, 1) == 2  # 3/2 = 1.5 -> 2 (even)
    assert round_nearest_even(-1, 1) == 0  # -0.5 -> 0 (even)
    assert round_nearest_even(-3, 1) == -2  # -1.5 -> -2 (even)

    # Non-tie cases
    assert round_nearest_even(5, 2) == 1  # 5/4 = 1.25 -> 1
    assert round_nearest_even(7, 2) == 2  # 7/4 = 1.75 -> 2


def test_saturate_signed():
    # 4-bit signed: [-8, 7]
    assert saturate_signed(5, 4) == (5, 0)
    assert saturate_signed(7, 4) == (7, 0)
    assert saturate_signed(8, 4) == (7, 1)
    assert saturate_signed(100, 4) == (7, 1)
    assert saturate_signed(-8, 4) == (8, 0)  # -8 in 4-bit unsigned is 0b1000 = 8
    assert saturate_signed(-9, 4) == (8, 1)
    assert saturate_signed(-50, 4) == (8, 1)


def test_fixed_round_ref():
    ref = FixedRoundRef({"IW": 8, "OW": 4, "DROP": 3})
    # 8-bit input to 4-bit output dropping 3 bits (divide by 8)
    # OW=4 signed range is [-8, 7]
    res = ref.eval({"data_i": 16})  # 16/8 = 2
    assert res["data_o"] == 2
    assert res["overflow_o"] == 0

    res_ov = ref.eval({"data_i": 120})  # 120/8 = 15 > 7
    assert res_ov["overflow_o"] == 1


def test_fixed_saturate_ref():
    ref = FixedSaturateRef({"IW": 8, "OW": 4})
    assert ref.eval({"data_i": 5}) == {"data_o": 5, "clipped_o": 0}
    assert ref.eval({"data_i": 12}) == {"data_o": 7, "clipped_o": 1}
    assert ref.eval({"data_i": 240}) == {"data_o": 8, "clipped_o": 1}  # 240 is -16, clamped to -8 (8)


def test_fixed_scale_ref():
    # IW=8, OW=8, COEFF_W=8, FRAC=4, GAIN=16 (unity gain since 16/2**4 = 1)
    ref = FixedScaleRef({"IW": 8, "OW": 8, "COEFF_W": 8, "FRAC": 4, "GAIN": 16})
    assert ref.eval({"data_i": 42})["data_o"] == 42
    assert ref.eval({"data_i": 42})["clipped_o"] == 0


def test_dot_product_ref():
    # W=4, N=2, OUT_W=16
    ref = DotProductRef({"W": 4, "N": 2, "OUT_W": 16})
    ref.reset()
    # a = [2, 3] (packed: 3<<4 | 2 = 0x32), b = [4, 5] (packed: 5<<4 | 4 = 0x54)
    # dot product = 2*4 + 3*5 = 8 + 15 = 23
    r1 = ref.step({"rst_ni": 1, "req_valid_i": 1, "rsp_ready_i": 1, "a_i": 0x32, "b_i": 0x54})
    assert r1["req_ready_o"] == 0
    # cycle 1
    r2 = ref.step({"rst_ni": 1, "req_valid_i": 0, "rsp_ready_i": 1})
    # cycle 2
    r3 = ref.step({"rst_ni": 1, "req_valid_i": 0, "rsp_ready_i": 1})
    assert r3["rsp_valid_o"] == 1
    assert r3["sum_o"] == 23


def test_fir_filter_ref():
    # TAPS=2, W=8, CW=8, FRAC=0, COEFFS=(1<<8)|1 = [1, 1], OW=8
    ref = FirFilterRef({"W": 8, "TAPS": 2, "CW": 8, "FRAC": 0, "COEFFS": (1 << 8) | 1, "OW": 8})
    ref.reset()
    # Sample 1: 5 -> out = 1*5 + 1*0 = 5
    s1 = ref.step({"rst_ni": 1, "s_valid_i": 1, "m_ready_i": 1, "s_data_i": 5})
    assert s1["m_valid_o"] == 1
    assert s1["m_data_o"] == 5
    # Sample 2: 3 -> out = 1*3 + 1*5 = 8
    s2 = ref.step({"rst_ni": 1, "s_valid_i": 1, "m_ready_i": 1, "s_data_i": 3})
    assert s2["m_valid_o"] == 1
    assert s2["m_data_o"] == 8


def test_cic_decimator_ref():
    ref = CicDecimatorRef({"W": 8, "R": 2, "ORDER": 1})
    ref.reset()
    # Feed 2 samples, decimator emits output on 2nd sample
    r1 = ref.step({"rst_ni": 1, "s_valid_i": 1, "m_ready_i": 1, "s_data_i": 10})
    assert r1["m_valid_o"] == 0
    r2 = ref.step({"rst_ni": 1, "s_valid_i": 1, "m_ready_i": 1, "s_data_i": 10})
    assert r2["m_valid_o"] == 1


def test_cic_interpolator_ref():
    ref = CicInterpolatorRef({"W": 8, "R": 2, "ORDER": 1})
    ref.reset()
    # Feed 1 sample, interpolator emits 2 samples
    r1 = ref.step({"rst_ni": 1, "s_valid_i": 1, "m_ready_i": 1, "s_data_i": 10})
    assert r1["m_valid_o"] == 1
    r2 = ref.step({"rst_ni": 1, "s_valid_i": 0, "m_ready_i": 1})
    assert r2["m_valid_o"] == 1

"""Unit tests for Phase 3 CORDIC reference models and numeric bounds."""

import math
from spec_catalog_service.catalog.components.phase3_models import (
    CordicRotateRef,
    CordicVectorRef,
    get_cordic_constants,
)


def test_cordic_constants_machin():
    """Verify Decimal 80 Machin formula constants match normative values."""
    angles, kraw = get_cordic_constants(24, 16)
    assert kraw == 163008219
    assert angles[0] == 2097152
    assert angles[1] == 1238021
    assert len(angles) == 16


def test_cordic_rotate_accuracy():
    """Verify cordic_rotate against math.cos and math.sin."""
    ref = CordicRotateRef({"W": 24, "ITER": 16})
    w = 24
    f = w - 3
    # Rotate (0.3, 0.2) by +0.125 turns (pi/4)
    x_in = int(0.3 * (1 << f))
    y_in = int(0.2 * (1 << f))
    ang_in = int(0.125 * (1 << w))

    ref.reset()
    # Step 1: IDLE -> req (handshake occurs, post-edge state is SETUP so req_ready is 0)
    res = ref.step({"req_valid_i": 1, "x_i": x_in, "y_i": y_in, "angle_i": ang_in, "rsp_ready_i": 1})
    assert res["req_ready_o"] == 0
    # Step 2: SETUP
    ref.step({"req_valid_i": 0, "rsp_ready_i": 1})
    # Step 3..18: 16 ITERATE steps
    for _ in range(16):
        ref.step({"req_valid_i": 0, "rsp_ready_i": 1})
    # Step 19: DONE
    res = ref.step({"req_valid_i": 0, "rsp_ready_i": 1})
    assert res["rsp_valid_o"] == 1
    assert res["range_error_o"] == 0

    x_out_real = (res["x_o"] - (1 << w if res["x_o"] >= (1 << (w - 1)) else 0)) / (1 << f)
    y_out_real = (res["y_o"] - (1 << w if res["y_o"] >= (1 << (w - 1)) else 0)) / (1 << f)

    theta = 0.125 * 2 * math.pi
    exp_x = 0.3 * math.cos(theta) - 0.2 * math.sin(theta)
    exp_y = 0.3 * math.sin(theta) + 0.2 * math.cos(theta)

    assert abs(x_out_real - exp_x) < 1e-4
    assert abs(y_out_real - exp_y) < 1e-4


def test_cordic_vector_accuracy():
    """Verify cordic_vector against math.hypot and math.atan2."""
    ref = CordicVectorRef({"W": 24, "ITER": 16})
    w = 24
    f = w - 3
    # Vector (-0.3, 0.4)
    x_in = (int(-0.3 * (1 << f))) & ((1 << w) - 1)
    y_in = (int(0.4 * (1 << f))) & ((1 << w) - 1)

    ref.reset()
    ref.step({"req_valid_i": 1, "x_i": x_in, "y_i": y_in, "rsp_ready_i": 1})
    ref.step({"req_valid_i": 0, "rsp_ready_i": 1})
    for _ in range(16):
        ref.step({"req_valid_i": 0, "rsp_ready_i": 1})
    res = ref.step({"req_valid_i": 0, "rsp_ready_i": 1})
    assert res["rsp_valid_o"] == 1
    assert res["range_error_o"] == 0

    mag_real = res["magnitude_o"] / (1 << f)
    ang_turns = (res["angle_o"] - (1 << w if res["angle_o"] >= (1 << (w - 1)) else 0)) / (1 << w)

    exp_mag = math.hypot(-0.3, 0.4)
    exp_ang = math.atan2(0.4, -0.3) / (2 * math.pi)

    assert abs(mag_real - exp_mag) < 1e-4
    assert abs(ang_turns - exp_ang) < 1e-4


def test_cordic_vector_zero():
    """Verify (0, 0) special case in cordic_vector."""
    ref = CordicVectorRef({"W": 24, "ITER": 16})
    ref.reset()
    ref.step({"req_valid_i": 1, "x_i": 0, "y_i": 0, "rsp_ready_i": 1})
    ref.step({"req_valid_i": 0, "rsp_ready_i": 1})
    for _ in range(16):
        ref.step({"req_valid_i": 0, "rsp_ready_i": 1})
    res = ref.step({"req_valid_i": 0, "rsp_ready_i": 1})
    assert res["rsp_valid_o"] == 1
    assert res["magnitude_o"] == 0
    assert res["angle_o"] == 0
    assert res["range_error_o"] == 0


def test_cordic_rotate_range_error():
    """Verify out-of-range inputs trigger range_error_o."""
    ref = CordicRotateRef({"W": 16, "ITER": 8})
    ref.reset()
    # Out of range Cartesian x
    ref.step({"req_valid_i": 1, "x_i": 10000, "y_i": 0, "angle_i": 0, "rsp_ready_i": 1})
    ref.step({"req_valid_i": 0, "rsp_ready_i": 1})
    for _ in range(8):
        ref.step({"req_valid_i": 0, "rsp_ready_i": 1})
    res = ref.step({"req_valid_i": 0, "rsp_ready_i": 1})
    assert res["rsp_valid_o"] == 1
    assert res["range_error_o"] == 1
    assert res["x_o"] == 0
    assert res["y_o"] == 0
    assert res["angle_o"] == 0

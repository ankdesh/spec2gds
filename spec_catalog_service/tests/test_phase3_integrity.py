"""Unit tests for Phase 3 Batch 3 (Integrity & ECC) reference models."""

from itertools import combinations
from spec_catalog_service.catalog.components.phase3_models import (
    ParityRef,
    CrcSerialRef,
    CrcParallelRef,
    LfsrRef,
    SecdedEncodeRef,
    SecdedDecodeRef,
    get_secded_params,
)


def test_parity_ref():
    ref = ParityRef({"W": 8})
    # even parity test
    res = ref.eval({"data_i": 0b00000000, "parity_i": 0})
    assert res == {"even_parity_o": 0, "odd_parity_o": 1, "error_o": 0}

    res = ref.eval({"data_i": 0b00000001, "parity_i": 0})
    assert res == {"even_parity_o": 1, "odd_parity_o": 0, "error_o": 1}

    res = ref.eval({"data_i": 0b00000001, "parity_i": 1})
    assert res == {"even_parity_o": 1, "odd_parity_o": 0, "error_o": 0}


def test_crc_serial_ref():
    ref = CrcSerialRef({"WIDTH": 32, "POLY": 79764919, "INIT": 4294967295, "XOROUT": 0})
    # "123456789"
    for b in b"123456789":
        for k in range(7, -1, -1):
            bit = (b >> k) & 1
            res = ref.eval({"valid_i": 1, "bit_i": bit, "clear_i": 0})
    assert res["crc_o"] == 0x0376e6e7

    # With default XOROUT
    ref_default = CrcSerialRef({"WIDTH": 32, "POLY": 79764919, "INIT": 4294967295, "XOROUT": 4294967295})
    for b in b"123456789":
        for k in range(7, -1, -1):
            bit = (b >> k) & 1
            res_def = ref_default.eval({"valid_i": 1, "bit_i": bit, "clear_i": 0})
    assert res_def["crc_o"] == 0xfc891918


def test_crc_parallel_ref():
    ref = CrcParallelRef({"WIDTH": 32, "POLY": 79764919, "INIT": 4294967295, "XOROUT": 0, "BYTES": 3})
    # Feed 9 bytes as 3 chunks of 3 bytes
    msg = b"123456789"
    for chunk_idx in range(3):
        chunk = msg[chunk_idx * 3 : (chunk_idx + 1) * 3]
        data_int = chunk[0] | (chunk[1] << 8) | (chunk[2] << 16)
        res = ref.eval({"valid_i": 1, "data_i": data_int, "clear_i": 0})
    assert res["crc_o"] == 0x0376e6e7


def test_lfsr_ref():
    ref = LfsrRef({"W": 4, "TAPS": 12, "SEED": 1})
    seen = [ref.state]
    for _ in range(16):
        res = ref.eval({"en_i": 1, "load_i": 0, "seed_i": 0})
        seen.append(res["state_o"])
    # Period should be 15 (returns to 1 on step 15)
    cycle = seen.index(1, 1)
    assert cycle == 15

    # Zero seed rejection
    res = ref.eval({"en_i": 0, "load_i": 1, "seed_i": 0})
    assert res["seed_error_o"] == 1
    assert res["state_o"] == seen[-1]


def test_secded_ref():
    data_w = 8
    enc = SecdedEncodeRef({"DATA_W": data_w})
    dec = SecdedDecodeRef({"DATA_W": data_w})
    p, h = get_secded_params(data_w)
    total_bits = h + 1

    for d in range(256):
        c = enc.eval({"data_i": d})["code_o"]
        # No error
        r0 = dec.eval({"code_i": c})
        assert r0 == {"data_o": d, "single_error_o": 0, "double_error_o": 0}

        # Single error
        for bit in range(total_bits):
            c1 = c ^ (1 << bit)
            r1 = dec.eval({"code_i": c1})
            assert r1 == {"data_o": d, "single_error_o": 1, "double_error_o": 0}

        # Double error
        for b1, b2 in [(0, 1), (0, 7), (3, 11), (5, 12)]:
            c2 = c ^ (1 << b1) ^ (1 << b2)
            r2 = dec.eval({"code_i": c2})
            assert r2["single_error_o"] == 0 and r2["double_error_o"] == 1

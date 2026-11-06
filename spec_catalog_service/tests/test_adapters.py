"""Tests for stream pack/unpack adapters and mixed-phase composition contracts."""

import random
from spec_catalog_service.catalog.authoring import build_component_spec
from spec_catalog_service.catalog.components.adapters import (
    DividerStreamAdapterRef,
    MultiplierStreamAdapterRef,
    DIVIDER_STREAM_ADAPTER_DEF,
    MULTIPLIER_STREAM_ADAPTER_DEF,
)
from spec2gds.spec.spec_format.ir import SpecRevision


def test_multiplier_stream_adapter_ref_roundtrip():
    """Verify bit-exact request and response pack/unpack for multipliers."""
    rng = random.Random(42)
    for w in (4, 8, 16, 32):
        mask = (1 << w) - 1
        for _ in range(50):
            a = rng.randint(0, mask)
            b = rng.randint(0, mask)
            packed = MultiplierStreamAdapterRef.pack_request(a, b, w)
            unpacked_a, unpacked_b = MultiplierStreamAdapterRef.unpack_request(packed, w)
            assert unpacked_a == a
            assert unpacked_b == b

            # Response
            prod = rng.randint(0, (1 << (2 * w)) - 1)
            packed_prod = MultiplierStreamAdapterRef.pack_response(prod, w)
            assert MultiplierStreamAdapterRef.unpack_response(packed_prod, w) == prod


def test_divider_stream_adapter_ref_roundtrip():
    """Verify bit-exact request and response pack/unpack for dividers including exception flags."""
    rng = random.Random(1337)
    for w in (4, 8, 16, 32):
        mask = (1 << w) - 1
        for _ in range(50):
            dividend = rng.randint(0, mask)
            divisor = rng.randint(0, mask)
            packed_req = DividerStreamAdapterRef.pack_request(dividend, divisor, w)
            unpacked_num, unpacked_den = DividerStreamAdapterRef.unpack_request(packed_req, w)
            assert unpacked_num == dividend
            assert unpacked_den == divisor

            # Response with flags
            quotient = rng.randint(0, mask)
            remainder = rng.randint(0, mask)
            div_zero = rng.choice([0, 1])
            overflow = rng.choice([0, 1])
            packed_rsp = DividerStreamAdapterRef.pack_response(quotient, remainder, div_zero, overflow, w)
            q, r, dz, ov = DividerStreamAdapterRef.unpack_response(packed_rsp, w)
            assert q == quotient
            assert r == remainder
            assert dz == div_zero
            assert ov == overflow


def test_multiplier_adapter_package_validity():
    """Verify multiplier_stream_adapter generates a valid, self-contained SpecPackage."""
    pkg = build_component_spec(MULTIPLIER_STREAM_ADAPTER_DEF)
    pkg.require_valid()
    rev = SpecRevision.from_package(pkg)
    assert len(rev.components) == 1
    root = rev.components[0]
    assert root.vlnv == "spec2gds.local:arithmetic_dsp:multiplier_stream_adapter:1.0.0"
    sections = rev.entity_sections_for(root.ref)
    assert any(s.section_type == "sv" and "s_data_i[W-1:0]" in s.content for s in sections)


def test_divider_adapter_package_validity():
    """Verify divider_stream_adapter generates a valid, self-contained SpecPackage."""
    pkg = build_component_spec(DIVIDER_STREAM_ADAPTER_DEF)
    pkg.require_valid()
    rev = SpecRevision.from_package(pkg)
    assert len(rev.components) == 1
    root = rev.components[0]
    assert root.vlnv == "spec2gds.local:arithmetic_dsp:divider_stream_adapter:1.0.0"
    sections = rev.entity_sections_for(root.ref)
    assert any(s.section_type == "sv" and "{overflow_i, div_zero_i, remainder_i, quotient_i}" in s.content for s in sections)

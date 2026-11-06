"""Integration and interoperability tests for mixed Phase 2/3 compositions.

Validates that arithmetic pipelines (Phase 3) compose safely with stream
queues/buffers (Phase 2) using reviewed adapters, preserving all results and
exception flags across backpressure, stalls, and resets.
"""

from __future__ import annotations

import json
from pathlib import Path

from spec_catalog_service.catalog.authoring import build_component_spec
from spec_catalog_service.catalog.components.adapters import (
    DividerStreamAdapterRef,
    MultiplierStreamAdapterRef,
    DIVIDER_STREAM_ADAPTER_DEF,
    MULTIPLIER_STREAM_ADAPTER_DEF,
)
from spec_catalog_service.catalog.components.phase2_storage import FIFO_SYNC_DEF
from spec_catalog_service.catalog.components.phase3_mult_div import DIVIDER_PIPELINE_DEF, MULTIPLIER_PIPELINE_DEF
from spec_catalog_service.catalog.components.phase3_models import DividerPipelineRef, MultiplierPipelineRef
from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.catalog_import import CatalogImportRequest, prepare_import
from spec2gds.spec.spec_format.channels import (
    load_component_channels,
    upsert_component_channels,
)
from spec_catalog_service.catalog.channel_profiles import (
    make_divider_channels,
    make_multiplier_channels,
    make_stream_channels,
)
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.models import EntityRef, sha256_digest


def test_multiplier_pipeline_composed_with_stream_adapter_and_fifo():
    """Verify stream -> multiplier_stream_adapter -> multiplier_pipeline -> stream."""
    w = 16
    mul_ref = MultiplierPipelineRef({"W": w, "SIGNED": 0, "STAGES": 3})

    # Prepare input stream of 10 operand pairs
    requests = [(i * 3 + 1, i * 7 + 2) for i in range(10)]
    packed_stream_in = [MultiplierStreamAdapterRef.pack_request(a, b, w) for a, b in requests]

    # Step through pipeline with FIFO buffering
    fifo_mem: list[int] = []
    results: list[int] = []

    # Push requests through adapter into multiplier pipeline
    for packed_req in packed_stream_in:
        a, b = MultiplierStreamAdapterRef.unpack_request(packed_req, w)
        # Advance pipeline
        step_res = mul_ref.step({
            "clk_i": 1,
            "rst_ni": 1,
            "req_valid_i": 1,
            "a_i": a,
            "b_i": b,
            "rsp_ready_i": 1,
        })
        if step_res["rsp_valid_o"]:
            packed_rsp = MultiplierStreamAdapterRef.pack_response(step_res["product_o"], w)
            fifo_mem.append(packed_rsp)

    # Flush remaining pipeline stages
    for _ in range(5):
        step_res = mul_ref.step({
            "clk_i": 1,
            "rst_ni": 1,
            "req_valid_i": 0,
            "a_i": 0,
            "b_i": 0,
            "rsp_ready_i": 1,
        })
        if step_res["rsp_valid_o"]:
            packed_rsp = MultiplierStreamAdapterRef.pack_response(step_res["product_o"], w)
            fifo_mem.append(packed_rsp)

    # Pop and unpack from output FIFO
    for packed_rsp in fifo_mem:
        prod = MultiplierStreamAdapterRef.unpack_response(packed_rsp, w)
        results.append(prod)

    expected = [a * b for a, b in requests]
    assert results == expected


def test_divider_pipeline_flags_preserved_through_adapter_and_queue():
    """Verify divide-by-zero and overflow flags remain bundled with quotient through queue."""
    w = 8
    div_ref = DividerPipelineRef({"W": w, "SIGNED": 1})

    # Test cases: normal, divide-by-zero, signed overflow (-128 / -1)
    test_cases = [
        (40, 5),     # normal: 40 / 5 = 8, rem 0
        (50, 0),     # div-by-zero: 50 / 0 -> div_zero=1
        (-128, -1),  # signed overflow: -128 / -1 -> overflow=1
        (25, 4),     # normal: 25 / 4 = 6, rem 1
    ]

    # Convert negative operands to two's-complement unsigned bits
    mask = (1 << w) - 1
    packed_inputs = [
        DividerStreamAdapterRef.pack_request(num & mask, den & mask, w)
        for num, den in test_cases
    ]

    fifo_queue: list[int] = []

    # Step through pipeline (latency is W cycles = 8)
    for packed_req in packed_inputs:
        num, den = DividerStreamAdapterRef.unpack_request(packed_req, w)
        out = div_ref.step({
            "clk_i": 1,
            "rst_ni": 1,
            "req_valid_i": 1,
            "dividend_i": num,
            "divisor_i": den,
            "rsp_ready_i": 1,
        })
        if out["rsp_valid_o"]:
            packed_rsp = DividerStreamAdapterRef.pack_response(
                out["quotient_o"], out["remainder_o"], out["div_zero_o"], out["overflow_o"], w
            )
            fifo_queue.append(packed_rsp)

    # Flush pipeline
    for _ in range(12):
        out = div_ref.step({
            "clk_i": 1,
            "rst_ni": 1,
            "req_valid_i": 0,
            "dividend_i": 0,
            "divisor_i": 0,
            "rsp_ready_i": 1,
        })
        if out["rsp_valid_o"]:
            packed_rsp = DividerStreamAdapterRef.pack_response(
                out["quotient_o"], out["remainder_o"], out["div_zero_o"], out["overflow_o"], w
            )
            fifo_queue.append(packed_rsp)

    assert len(fifo_queue) == len(test_cases)

    # Unpack from FIFO queue and verify all fields
    # Case 0: 40 / 5 = 8, rem 0, dz=0, ov=0
    q0, r0, dz0, ov0 = DividerStreamAdapterRef.unpack_response(fifo_queue[0], w)
    assert (q0, r0, dz0, ov0) == (8, 0, 0, 0)

    # Case 1: 50 / 0 -> div_zero=1
    q1, r1, dz1, ov1 = DividerStreamAdapterRef.unpack_response(fifo_queue[1], w)
    assert dz1 == 1

    # Case 2: -128 / -1 -> overflow=1
    q2, r2, dz2, ov2 = DividerStreamAdapterRef.unpack_response(fifo_queue[2], w)
    assert ov2 == 1

    # Case 3: 25 / 4 = 6, rem 1
    q3, r3, dz3, ov3 = DividerStreamAdapterRef.unpack_response(fifo_queue[3], w)
    assert (q3, r3, dz3, ov3) == (6, 1, 0, 0)


def test_mixed_phase_spec_package_channels_and_origins():
    """Verify that importing Phase 2 and Phase 3 packages into a single SpecRevision succeeds."""
    dest_rev = SpecRevision.from_package(SpecPackage.create(title="Mixed Phase Pipeline"))

    # Build and import FIFO (Phase 2)
    fifo_pkg = build_component_spec(FIFO_SYNC_DEF)
    fifo_meta = json.loads(fifo_pkg.files[fifo_pkg.manifest.assets[0].path].decode("utf-8"))
    fifo_details = {
        "metadata": fifo_meta,
        "package_sha256": sha256_digest(fifo_pkg.to_bytes()),
    }
    fifo_req = CatalogImportRequest(
        component_key="fifo_sync",
        version="1.0.0",
        package_sha256=fifo_details["package_sha256"],
        expected_source_revision_hash=dest_rev.source_revision_hash,
    )
    p1, candidate1 = prepare_import(dest_rev, SpecRevision.from_package(fifo_pkg), fifo_details, fifo_req)
    assert p1["can_import"] is True

    # Build and import Multiplier Pipeline (Phase 3)
    mul_pkg = build_component_spec(MULTIPLIER_PIPELINE_DEF)
    mul_meta = json.loads(mul_pkg.files[mul_pkg.manifest.assets[0].path].decode("utf-8"))
    mul_details = {
        "metadata": mul_meta,
        "package_sha256": sha256_digest(mul_pkg.to_bytes()),
    }
    mul_req = CatalogImportRequest(
        component_key="multiplier_pipeline",
        version="1.0.0",
        package_sha256=mul_details["package_sha256"],
        expected_source_revision_hash=candidate1.source_revision_hash,
    )
    p2, candidate2 = prepare_import(candidate1, SpecRevision.from_package(mul_pkg), mul_details, mul_req)
    assert p2["can_import"] is True

    # Verify candidate2 contains both components and their origins
    comp_vlnvs = [c.vlnv for c in candidate2.components]
    assert any("fifo_sync" in vlnv for vlnv in comp_vlnvs)
    assert any("multiplier_pipeline" in vlnv for vlnv in comp_vlnvs)

    # Save to package and require valid
    saved_pkg = candidate2.to_package()
    saved_pkg.require_valid()


def test_skid_buffer_vs_register_timing_and_backpressure_characterization():
    """Verify timing, capacity, and backpressure isolation difference between skid buffer and register."""
    from spec_catalog_service.catalog.components.phase2_streams import (
        StreamRegisterRef,
        StreamSkidBufferRef,
    )
    from spec2gds.spec.spec_format.channels import (
        create_channel_connection_preview,
        ComponentChannelV1,
        ChannelFieldMappingV1,
    )

    skid = StreamSkidBufferRef({"W": 32})
    reg = StreamRegisterRef({"W": 32})

    # Step 1: Push first word while downstream stalls (m_ready_i = 0)
    # Skid buffer accepts and keeps s_ready_o = 1 because capacity is 2
    skid_out1 = skid.step({"rst_ni": 1, "s_valid_i": 1, "s_data_i": 0xAAAA, "m_ready_i": 0})
    assert skid_out1["m_valid_o"] == 1
    assert skid_out1["m_data_o"] == 0xAAAA
    assert skid_out1["s_ready_o"] == 1  # Still has room for 1 more word!

    # Register accepts, but immediately drives s_ready_o = 0 because m_ready_i = 0
    reg_out1 = reg.step({"rst_ni": 1, "s_valid_i": 1, "s_data_i": 0xAAAA, "m_ready_i": 0})
    assert reg_out1["m_valid_o"] == 1
    assert reg_out1["m_data_o"] == 0xAAAA
    assert reg_out1["s_ready_o"] == 0  # Stalled!

    # Step 2: Push second word to skid buffer while downstream still stalls
    skid_out2 = skid.step({"rst_ni": 1, "s_valid_i": 1, "s_data_i": 0xBBBB, "m_ready_i": 0})
    assert skid_out2["m_valid_o"] == 1
    assert skid_out2["m_data_o"] == 0xAAAA
    assert skid_out2["s_ready_o"] == 0  # Now full (capacity 2 reached)

    # Step 3: Verify channel connection preview when connecting skid buffer to multiplier adapter
    skid_m_channel = ComponentChannelV1(
        id="m_stream",
        profile="stream_source",
        direction="producer",
        valid_port="m_valid_o",
        ready_port="m_ready_i",
        clock_port="clk_i",
        reset_port="rst_ni",
        fields=(ChannelFieldMappingV1(name="data", port="m_data_o", field_role="result"),),
    )
    adapter_s_channel = ComponentChannelV1(
        id="s_stream",
        profile="stream_sink",
        direction="consumer",
        valid_port="s_valid_i",
        ready_port="s_ready_o",
        clock_port="clk_i",
        reset_port="rst_ni",
        fields=(ChannelFieldMappingV1(name="data", port="s_data_i", field_role="operand"),),
    )
    preview = create_channel_connection_preview(skid_m_channel, adapter_s_channel)
    assert preview.compatible is True
    assert preview.requires_adapter is False
    assert ("m_valid_o", "s_valid_i") in preview.port_mappings
    assert ("s_ready_o", "m_ready_i") in preview.port_mappings
    assert ("m_data_o", "s_data_i") in preview.port_mappings

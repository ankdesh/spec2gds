"""Unit and integration tests for Component channel annotations (spec2gds.channels v1)."""

from __future__ import annotations

import json
import pytest

from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.channels import (
    CHANNEL_NAMESPACE,
    ChannelFieldMappingV1,
    ChannelTransferContractV1,
    ComponentChannelV1,
    ComponentChannelsV1,
    delete_component_channels,
    load_component_channels,
    upsert_component_channels,
    validate_channel_annotations,
)
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.models import EntityRef


def test_channel_models_validation():
    ref = EntityRef(document_id="doc1", entity_id="comp1", entity_kind="component")
    
    # Valid request channel
    req_chan = ComponentChannelV1(
        id="req",
        profile="request",
        direction="consumer",
        valid_port="req_valid_i",
        ready_port="req_ready_o",
        clock_port="clk_i",
        reset_port="rst_ni",
        fields=(
            ChannelFieldMappingV1(name="a", port="a_i", field_role="operand"),
            ChannelFieldMappingV1(name="b", port="b_i", field_role="operand"),
        ),
        contract=ChannelTransferContractV1(min_latency=3, acceptance_interval=1),
    )
    
    # Valid response channel with combinational dependency on req
    rsp_chan = ComponentChannelV1(
        id="rsp",
        profile="response",
        direction="producer",
        valid_port="rsp_valid_o",
        ready_port="rsp_ready_i",
        fields=(
            ChannelFieldMappingV1(name="product", port="product_o", field_role="result"),
        ),
        combinational_dependencies=("req",),
    )

    channels = ComponentChannelsV1(
        component=ref,
        channels=(req_chan, rsp_chan),
    )
    assert len(channels.channels) == 2
    assert channels.channels[0].id == "req"
    assert channels.channels[1].combinational_dependencies == ("req",)


def test_channel_models_reject_duplicates_and_missing_dependencies():
    ref = EntityRef(document_id="doc1", entity_id="comp1", entity_kind="component")
    
    # Duplicate field names
    with pytest.raises(ValueError, match="duplicate field names"):
        ComponentChannelV1(
            id="test",
            profile="stream_sink",
            direction="consumer",
            valid_port="v_i",
            ready_port="r_o",
            fields=(
                ChannelFieldMappingV1(name="data", port="d1_i"),
                ChannelFieldMappingV1(name="data", port="d2_i"),
            ),
        )

    # Elastic channel missing ready_port
    with pytest.raises(ValueError, match="must declare a ready_port"):
        ComponentChannelV1(
            id="test",
            profile="stream_sink",
            direction="consumer",
            valid_port="v_i",
            ready_port=None,
        )

    # Unknown combinational dependency
    valid_chan = ComponentChannelV1(
        id="c1",
        profile="combinational",
        direction="consumer",
        combinational_dependencies=("unknown_chan",),
    )
    with pytest.raises(ValueError, match="unknown dependency channel 'unknown_chan'"):
        ComponentChannelsV1(
            component=ref,
            channels=(valid_chan,),
        )


def test_channel_annotation_package_roundtrip():
    from spec_catalog_service.catalog.authoring import build_component_spec
    from spec_catalog_service.catalog.components.phase1 import MUX_DEF

    pkg = build_component_spec(MUX_DEF)
    comp_ref = pkg.manifest.documents[0].to_ref(pkg.manifest.document_id) if hasattr(pkg.manifest.documents[0], "to_ref") else EntityRef(
        document_id=pkg.manifest.document_id,
        entity_id=pkg.manifest.documents[0].entity_id,
        entity_kind="component",
    )

    chan = ComponentChannelV1(
        id="mux_in",
        profile="combinational",
        direction="consumer",
        fields=(
            ChannelFieldMappingV1(name="d", port="data_i", field_role="operand"),
            ChannelFieldMappingV1(name="sel", port="sel_i", field_role="control"),
        ),
    )
    channels = ComponentChannelsV1(
        component=comp_ref,
        channels=(chan,),
    )

    upsert_component_channels(pkg, channels)
    assert any(s.namespace == CHANNEL_NAMESPACE for s in pkg.manifest.annotation_schemas)

    # Validate through archive validator
    validate_channel_annotations(pkg.manifest, pkg.files)

    # Load back via SpecRevision
    rev = SpecRevision.from_package(pkg)
    loaded = load_component_channels(rev, comp_ref)
    assert loaded is not None
    assert len(loaded.channels) == 1
    assert loaded.channels[0].id == "mux_in"
    assert len(loaded.channels[0].fields) == 2

    # Delete
    delete_component_channels(pkg, comp_ref)
    assert not any(s.namespace == CHANNEL_NAMESPACE for s in pkg.manifest.annotation_schemas)
    assert f"annotations/channels/{comp_ref.entity_id}.json" not in pkg.files


def test_channel_annotation_import_preservation():
    from spec2gds.spec.spec_format.catalog_import import prepare_import, CatalogImportRequest
    from spec_catalog_service.catalog.authoring import build_component_spec
    from spec_catalog_service.catalog.components.phase1 import MUX_DEF
    from spec2gds.spec.spec_format.models import sha256_digest

    pkg = build_component_spec(MUX_DEF)
    comp_ref = EntityRef(
        document_id=pkg.manifest.document_id,
        entity_id=pkg.manifest.documents[0].entity_id,
        entity_kind="component",
    )

    chan = ComponentChannelV1(
        id="mux_in",
        profile="combinational",
        direction="consumer",
        fields=(
            ChannelFieldMappingV1(name="d", port="data_i", field_role="operand"),
            ChannelFieldMappingV1(name="sel", port="sel_i", field_role="control"),
        ),
    )
    upsert_component_channels(pkg, ComponentChannelsV1(component=comp_ref, channels=(chan,)))

    source_rev = SpecRevision.from_package(pkg)
    dest_rev = SpecRevision.from_package(SpecPackage.create(title="Destination"))

    meta = json.loads(pkg.files[pkg.manifest.assets[0].path].decode("utf-8"))
    details = {
        "metadata": meta,
        "package_sha256": sha256_digest(pkg.to_bytes()),
    }
    request = CatalogImportRequest(
        component_key="mux",
        version="1.0.0",
        package_sha256=details["package_sha256"],
        expected_source_revision_hash=dest_rev.source_revision_hash,
    )

    preview, candidate = prepare_import(dest_rev, source_rev, details, request)
    assert preview["can_import"] is True

    # Confirm channel annotation was preserved in candidate
    imported_root_ref = EntityRef.model_validate(preview["root"])
    imported_channels = load_component_channels(candidate, imported_root_ref)
    assert imported_channels is not None
    assert imported_channels.component == imported_root_ref
    assert len(imported_channels.channels) == 1
    assert imported_channels.channels[0].id == "mux_in"


def test_channel_connection_validation_and_preview():
    from spec2gds.spec.spec_format.channels import (
        validate_channel_connection,
        create_channel_connection_preview,
    )

    # 1. Direct compatible connection (producer stream -> consumer stream)
    prod = ComponentChannelV1(
        id="m_stream",
        profile="stream_source",
        direction="producer",
        valid_port="m_valid_o",
        ready_port="m_ready_i",
        clock_port="clk_i",
        reset_port="rst_ni",
        fields=(ChannelFieldMappingV1(name="data", port="m_data_o", field_role="result"),),
    )
    cons = ComponentChannelV1(
        id="s_stream",
        profile="stream_sink",
        direction="consumer",
        valid_port="s_valid_i",
        ready_port="s_ready_o",
        clock_port="clk_i",
        reset_port="rst_ni",
        fields=(ChannelFieldMappingV1(name="data", port="s_data_i", field_role="operand"),),
    )

    preview = create_channel_connection_preview(prod, cons)
    assert preview.compatible is True
    assert preview.requires_adapter is False
    assert ("m_valid_o", "s_valid_i") in preview.port_mappings
    assert ("s_ready_o", "m_ready_i") in preview.port_mappings
    assert ("m_data_o", "s_data_i") in preview.port_mappings

    # 2. Domain mismatch detection
    diags_domain = validate_channel_connection(
        prod, cons, producer_domain="clk_core", consumer_domain="clk_dsp"
    )
    assert any(d.code == "CLOCK_DOMAIN_MISMATCH" for d in diags_domain)

    # 3. Reset polarity mismatch
    cons_active_high = cons.model_copy(update={"reset_polarity": "active_high"})
    diags_rst = validate_channel_connection(prod, cons_active_high)
    assert any(d.code == "RESET_POLARITY_MISMATCH" for d in diags_rst)

    # 4. Multiplier adapter requirement
    mult_req = ComponentChannelV1(
        id="req",
        profile="request",
        direction="consumer",
        valid_port="req_valid_i",
        ready_port="req_ready_o",
        fields=(
            ChannelFieldMappingV1(name="a", port="a_i", field_role="operand"),
            ChannelFieldMappingV1(name="b", port="b_i", field_role="operand"),
        ),
    )
    prev_adapter = create_channel_connection_preview(prod, mult_req)
    assert prev_adapter.compatible is False
    assert prev_adapter.requires_adapter is True
    assert prev_adapter.recommended_adapter == "multiplier_stream_adapter"


def test_combinational_cycle_detection():
    from spec2gds.spec.spec_format.channels import detect_combinational_cycle

    # Acyclic graph: A -> B -> C
    acyclic_edges = [("A", "B"), ("B", "C")]
    assert detect_combinational_cycle(acyclic_edges) == []

    # Cyclic graph: A -> B -> C -> A
    cyclic_edges = [("A", "B"), ("B", "C"), ("C", "A")]
    cycles = detect_combinational_cycle(cyclic_edges)
    assert len(cycles) > 0
    assert cycles[0] == ["A", "B", "C", "A"] or cycles[0] == ["B", "C", "A", "B"] or cycles[0] == ["C", "A", "B", "C"]

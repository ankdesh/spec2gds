"""Reviewed channel profile factories for standard Spec Library components.

Generates validated ComponentChannelsV1 annotations for streams, queues, and
arithmetic pipelines.
"""

from __future__ import annotations

from spec2gds.spec.spec_format.channels import (
    ChannelFieldMappingV1,
    ChannelTransferContractV1,
    ComponentChannelV1,
    ComponentChannelsV1,
)
from spec2gds.spec.spec_format.models import EntityRef


def make_stream_channels(
    comp_ref: EntityRef,
    has_sink: bool = True,
    has_source: bool = True,
    clock_port: str = "clk_i",
    reset_port: str = "rst_ni",
    capacity: int = 1,
) -> ComponentChannelsV1:
    """Generate standard stream sink/source channels for elastic components."""
    channels: list[ComponentChannelV1] = []
    if has_sink:
        channels.append(
            ComponentChannelV1(
                id="s_stream",
                profile="stream_sink",
                direction="consumer",
                valid_port="s_valid_i",
                ready_port="s_ready_o",
                clock_port=clock_port,
                reset_port=reset_port,
                fields=(ChannelFieldMappingV1(name="data", port="s_data_i", field_role="operand"),),
                contract=ChannelTransferContractV1(capacity=capacity, acceptance_interval=1),
            )
        )
    if has_source:
        channels.append(
            ComponentChannelV1(
                id="m_stream",
                profile="stream_source",
                direction="producer",
                valid_port="m_valid_o",
                ready_port="m_ready_i",
                clock_port=clock_port,
                reset_port=reset_port,
                fields=(ChannelFieldMappingV1(name="data", port="m_data_o", field_role="result"),),
                contract=ChannelTransferContractV1(capacity=capacity, acceptance_interval=1),
                combinational_dependencies=("s_stream",) if has_sink else (),
            )
        )
    return ComponentChannelsV1(component=comp_ref, channels=tuple(channels))


def make_multiplier_channels(comp_ref: EntityRef, latency: int = 3) -> ComponentChannelsV1:
    """Generate request and response channels for multiplier_pipeline."""
    req = ComponentChannelV1(
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
        contract=ChannelTransferContractV1(min_latency=latency, acceptance_interval=1),
    )
    rsp = ComponentChannelV1(
        id="rsp",
        profile="response",
        direction="producer",
        valid_port="rsp_valid_o",
        ready_port="rsp_ready_i",
        clock_port="clk_i",
        reset_port="rst_ni",
        fields=(
            ChannelFieldMappingV1(name="product", port="product_o", field_role="result"),
        ),
        contract=ChannelTransferContractV1(min_latency=0, acceptance_interval=1),
        combinational_dependencies=("req",),
    )
    return ComponentChannelsV1(component=comp_ref, channels=(req, rsp))


def make_divider_channels(comp_ref: EntityRef, latency: int = 16) -> ComponentChannelsV1:
    """Generate request and response channels for divider_pipeline."""
    req = ComponentChannelV1(
        id="req",
        profile="request",
        direction="consumer",
        valid_port="req_valid_i",
        ready_port="req_ready_o",
        clock_port="clk_i",
        reset_port="rst_ni",
        fields=(
            ChannelFieldMappingV1(name="dividend", port="dividend_i", field_role="operand"),
            ChannelFieldMappingV1(name="divisor", port="divisor_i", field_role="operand"),
        ),
        contract=ChannelTransferContractV1(min_latency=latency, acceptance_interval=1),
    )
    rsp = ComponentChannelV1(
        id="rsp",
        profile="response",
        direction="producer",
        valid_port="rsp_valid_o",
        ready_port="rsp_ready_i",
        clock_port="clk_i",
        reset_port="rst_ni",
        fields=(
            ChannelFieldMappingV1(name="quotient", port="quotient_o", field_role="result"),
            ChannelFieldMappingV1(name="remainder", port="remainder_o", field_role="result"),
            ChannelFieldMappingV1(name="div_zero", port="div_zero_o", field_role="flag"),
            ChannelFieldMappingV1(name="overflow", port="overflow_o", field_role="flag"),
        ),
        contract=ChannelTransferContractV1(min_latency=0, acceptance_interval=1),
        combinational_dependencies=("req",),
    )
    return ComponentChannelsV1(component=comp_ref, channels=(req, rsp))


def make_dot_product_channels(comp_ref: EntityRef, latency: int = 5) -> ComponentChannelsV1:
    """Generate request and response channels for dot_product."""
    req = ComponentChannelV1(
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
        contract=ChannelTransferContractV1(min_latency=latency, acceptance_interval=latency),
    )
    rsp = ComponentChannelV1(
        id="rsp",
        profile="response",
        direction="producer",
        valid_port="rsp_valid_o",
        ready_port="rsp_ready_i",
        clock_port="clk_i",
        reset_port="rst_ni",
        fields=(
            ChannelFieldMappingV1(name="sum", port="sum_o", field_role="result"),
        ),
        contract=ChannelTransferContractV1(min_latency=0, acceptance_interval=1),
        combinational_dependencies=("req",),
    )
    return ComponentChannelsV1(component=comp_ref, channels=(req, rsp))


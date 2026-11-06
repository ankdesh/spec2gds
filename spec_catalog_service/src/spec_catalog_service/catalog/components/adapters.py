"""Arithmetic stream pack and unpack adapters (spec_catalog_service adapters).

These adapters provide reviewed, bit-exact payload packing and unpacking between
Phase 2 elastic stream channels and Phase 3 arithmetic pipelines.
"""

from __future__ import annotations

from typing import Any

from spec_catalog_service.catalog.components.models import ComponentDef, ParamDef, PortDef
from spec_catalog_service.catalog.schemas import TimingInfo


# =============================================================================
# Python Reference Models for Packing and Unpacking
# =============================================================================

class MultiplierStreamAdapterRef:
    """Golden packing and unpacking reference for multiplier transport."""

    @staticmethod
    def pack_request(a: int, b: int, w: int) -> int:
        mask = (1 << w) - 1
        return ((b & mask) << w) | (a & mask)

    @staticmethod
    def unpack_request(data: int, w: int) -> tuple[int, int]:
        mask = (1 << w) - 1
        a = data & mask
        b = (data >> w) & mask
        return a, b

    @staticmethod
    def pack_response(product: int, w: int) -> int:
        mask = (1 << (2 * w)) - 1
        return product & mask

    @staticmethod
    def unpack_response(data: int, w: int) -> int:
        mask = (1 << (2 * w)) - 1
        return data & mask


class DividerStreamAdapterRef:
    """Golden packing and unpacking reference for divider transport."""

    @staticmethod
    def pack_request(dividend: int, divisor: int, w: int) -> int:
        mask = (1 << w) - 1
        return ((divisor & mask) << w) | (dividend & mask)

    @staticmethod
    def unpack_request(data: int, w: int) -> tuple[int, int]:
        mask = (1 << w) - 1
        dividend = data & mask
        divisor = (data >> w) & mask
        return dividend, divisor

    @staticmethod
    def pack_response(quotient: int, remainder: int, div_zero: int, overflow: int, w: int) -> int:
        mask = (1 << w) - 1
        q_part = quotient & mask
        r_part = (remainder & mask) << w
        dz_part = (1 if div_zero else 0) << (2 * w)
        ov_part = (1 if overflow else 0) << (2 * w + 1)
        return ov_part | dz_part | r_part | q_part

    @staticmethod
    def unpack_response(data: int, w: int) -> tuple[int, int, int, int]:
        mask = (1 << w) - 1
        quotient = data & mask
        remainder = (data >> w) & mask
        div_zero = (data >> (2 * w)) & 1
        overflow = (data >> (2 * w + 1)) & 1
        return quotient, remainder, div_zero, overflow


# =============================================================================
# Component Definitions
# =============================================================================

def _validate_multiplier_adapter(params: dict[str, int]) -> list[str]:
    w = params.get("W", 0)
    if not (1 <= w <= 32):
        return [f"W={w} out of range [1..32]"]
    return []


MULTIPLIER_STREAM_ADAPTER_DEF = ComponentDef(
    id="multiplier_stream_adapter",
    category="arithmetic_dsp",
    phase=3,
    implementation="body_sv",
    summary="Elastic stream to arithmetic request/response pack/unpack adapter for multipliers",
    tags=["adapter", "stream", "multiplier", "transport"],
    contract_anchor="multiplier_stream_adapter",
    parameters=[
        ParamDef("W", "int unsigned", "16", "Operand data width in bits", min_value=1, max_value=32),
    ],
    ports=[
        # Upstream Stream In (packed operands a and b)
        PortDef("s_valid_i", "in", None, "Upstream stream valid"),
        PortDef("s_ready_o", "out", None, "Upstream stream ready"),
        PortDef("s_data_i", "in", "2*W-1:0", "Packed request: {b[W-1:0], a[W-1:0]}"),
        # Arithmetic Request Out (split operands)
        PortDef("req_valid_o", "out", None, "Arithmetic request valid"),
        PortDef("req_ready_i", "in", None, "Arithmetic request ready"),
        PortDef("a_o", "out", "W-1:0", "First operand to multiplier"),
        PortDef("b_o", "out", "W-1:0", "Second operand to multiplier"),
        # Arithmetic Response In
        PortDef("rsp_valid_i", "in", None, "Arithmetic response valid"),
        PortDef("rsp_ready_o", "out", None, "Arithmetic response ready"),
        PortDef("product_i", "in", "2*W-1:0", "Product result from multiplier"),
        # Downstream Stream Out
        PortDef("m_valid_o", "out", None, "Downstream stream valid"),
        PortDef("m_ready_i", "in", None, "Downstream stream ready"),
        PortDef("m_data_o", "out", "2*W-1:0", "Packed response data"),
    ],
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    presets={
        "default": {"W": "16"},
        "w8": {"W": "8"},
        "w32": {"W": "32"},
    },
    limitations=[
        "Pure combinational field map: zero latency in forward and backward directions.",
        "Both request and response transfers are atomic on their respective handshakes.",
    ],
    is_stateful=False,
    validate_params=_validate_multiplier_adapter,
    create_reference=lambda params: MultiplierStreamAdapterRef(),
    systemverilog="""    // Request channel field mapping: unpack s_data_i -> a_o, b_o
    assign req_valid_o = s_valid_i;
    assign s_ready_o   = req_ready_i;
    assign a_o         = s_data_i[W-1:0];
    assign b_o         = s_data_i[2*W-1:W];

    // Response channel field mapping: pass product_i -> m_data_o
    assign m_valid_o   = rsp_valid_i;
    assign rsp_ready_o = m_ready_i;
    assign m_data_o    = product_i;
""",
)


def _validate_divider_adapter(params: dict[str, int]) -> list[str]:
    w = params.get("W", 0)
    if not (2 <= w <= 32):
        return [f"W={w} out of range [2..32]"]
    return []


DIVIDER_STREAM_ADAPTER_DEF = ComponentDef(
    id="divider_stream_adapter",
    category="arithmetic_dsp",
    phase=3,
    implementation="body_sv",
    summary="Elastic stream to arithmetic request/response pack/unpack adapter for dividers",
    tags=["adapter", "stream", "divider", "transport"],
    contract_anchor="divider_stream_adapter",
    parameters=[
        ParamDef("W", "int unsigned", "16", "Operand data width in bits", min_value=2, max_value=32),
    ],
    ports=[
        # Upstream Stream In (packed operands dividend and divisor)
        PortDef("s_valid_i", "in", None, "Upstream stream valid"),
        PortDef("s_ready_o", "out", None, "Upstream stream ready"),
        PortDef("s_data_i", "in", "2*W-1:0", "Packed request: {divisor[W-1:0], dividend[W-1:0]}"),
        # Arithmetic Request Out (split operands)
        PortDef("req_valid_o", "out", None, "Arithmetic request valid"),
        PortDef("req_ready_i", "in", None, "Arithmetic request ready"),
        PortDef("dividend_o", "out", "W-1:0", "Dividend operand to divider"),
        PortDef("divisor_o", "out", "W-1:0", "Divisor operand to divider"),
        # Arithmetic Response In
        PortDef("rsp_valid_i", "in", None, "Arithmetic response valid"),
        PortDef("rsp_ready_o", "out", None, "Arithmetic response ready"),
        PortDef("quotient_i", "in", "W-1:0", "Quotient result from divider"),
        PortDef("remainder_i", "in", "W-1:0", "Remainder result from divider"),
        PortDef("div_zero_i", "in", None, "Divide-by-zero flag"),
        PortDef("overflow_i", "in", None, "Signed overflow flag"),
        # Downstream Stream Out
        PortDef("m_valid_o", "out", None, "Downstream stream valid"),
        PortDef("m_ready_i", "in", None, "Downstream stream ready"),
        PortDef("m_data_o", "out", "2*W+1:0", "Packed response: {overflow, div_zero, remainder, quotient}"),
    ],
    timing=TimingInfo(latency="0", throughput="1", reset="none"),
    presets={
        "default": {"W": "16"},
        "w8": {"W": "8"},
        "w32": {"W": "32"},
    },
    limitations=[
        "Pure combinational field map: zero latency in forward and backward directions.",
        "Response packing preserves quotient, remainder, div_zero, and overflow atomically.",
    ],
    is_stateful=False,
    validate_params=_validate_divider_adapter,
    create_reference=lambda params: DividerStreamAdapterRef(),
    systemverilog="""    // Request channel field mapping: unpack s_data_i -> dividend_o, divisor_o
    assign req_valid_o = s_valid_i;
    assign s_ready_o   = req_ready_i;
    assign dividend_o  = s_data_i[W-1:0];
    assign divisor_o   = s_data_i[2*W-1:W];

    // Response channel field mapping: pack quotient, remainder, div_zero, overflow -> m_data_o
    assign m_valid_o   = rsp_valid_i;
    assign rsp_ready_o = m_ready_i;
    assign m_data_o    = {overflow_i, div_zero_i, remainder_i, quotient_i};
""",
)

ADAPTER_COMPONENTS = [
    MULTIPLIER_STREAM_ADAPTER_DEF,
    DIVIDER_STREAM_ADAPTER_DEF,
]

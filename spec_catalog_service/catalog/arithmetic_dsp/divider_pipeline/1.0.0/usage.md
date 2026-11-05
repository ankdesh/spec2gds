# divider_pipeline

Fully-staged restoring pipelined divider accepting 1 request per edge

- **VLNV**: `spec2gds.local:arithmetic_dsp:divider_pipeline:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Rising-edge clock |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `req_valid_i` | `in` | `1 (scalar)` | Request valid handshake input |
| `req_ready_o` | `out` | `1 (scalar)` | Request ready handshake output |
| `dividend_i` | `in` | `[W-1:0]` | Dividend operand |
| `divisor_i` | `in` | `[W-1:0]` | Divisor operand |
| `rsp_valid_o` | `out` | `1 (scalar)` | Response valid handshake output |
| `rsp_ready_i` | `in` | `1 (scalar)` | Response ready handshake input |
| `quotient_o` | `out` | `[W-1:0]` | Quotient result |
| `remainder_o` | `out` | `[W-1:0]` | Remainder result |
| `div_zero_o` | `out` | `1 (scalar)` | Division by zero exception flag |
| `overflow_o` | `out` | `1 (scalar)` | Signed overflow exception flag (min / -1) |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `16` | Operand and result data width in bits |
| `SIGNED` | `int unsigned` | `0` | 1 for signed two's complement, 0 for unsigned |

## Timing Characteristics

- **Latency**: W+1
- **Throughput**: 1
- **Reset**: async_low

## Parameter Presets

- **`default`**: `SIGNED=0`, `W=16`
- **`w2_signed`**: `SIGNED=1`, `W=2`
- **`w4_unsigned`**: `SIGNED=0`, `W=4`
- **`w32_signed`**: `SIGNED=1`, `W=32`

## Implementation Limits & Notes

- Fully staged restoring division pipeline with latency W+1 cycles.
- One transaction per edge accepted and produced without backpressure.

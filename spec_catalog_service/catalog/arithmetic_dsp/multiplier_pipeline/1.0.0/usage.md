# multiplier_pipeline

Fully-pipelined elastic multiplier with backpressure propagation

- **VLNV**: `spec2gds.local:arithmetic_dsp:multiplier_pipeline:1.0.0`
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
| `a_i` | `in` | `[W-1:0]` | First multiplicand operand |
| `b_i` | `in` | `[W-1:0]` | Second multiplicand operand |
| `rsp_valid_o` | `out` | `1 (scalar)` | Response valid handshake output |
| `rsp_ready_i` | `in` | `1 (scalar)` | Response ready handshake input |
| `product_o` | `out` | `[(2*W)-1:0]` | Full-width product result |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `16` | Operand data width in bits |
| `SIGNED` | `int unsigned` | `0` | 1 for signed two's complement, 0 for unsigned |
| `STAGES` | `int unsigned` | `3` | Pipeline register depth |

## Timing Characteristics

- **Latency**: STAGES
- **Throughput**: 1
- **Reset**: async_low

## Parameter Presets

- **`default`**: `SIGNED=0`, `STAGES=3`, `W=16`
- **`w1_signed_s1`**: `SIGNED=1`, `STAGES=1`, `W=1`
- **`w7_unsigned_s2`**: `SIGNED=0`, `STAGES=2`, `W=7`
- **`w32_signed_s8`**: `SIGNED=1`, `STAGES=8`, `W=32`

## Implementation Limits & Notes

- Latency is exactly STAGES clock cycles without stall.
- Backpressure propagates upstream without losing or reordering transactions.

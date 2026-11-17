# mac

Multiply-accumulate unit with accumulator, clear, and elastic output

- **VLNV**: `spec2gds.local:arithmetic_dsp:mac:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `composite`
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
| `clear_i` | `in` | `1 (scalar)` | When asserted, resets accumulator before product add |
| `rsp_valid_o` | `out` | `1 (scalar)` | Response valid handshake output |
| `rsp_ready_i` | `in` | `1 (scalar)` | Response ready handshake input |
| `sum_o` | `out` | `[ACC_W-1:0]` | Accumulated sum result |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `16` | Operand data width in bits |
| `ACC_W` | `int unsigned` | `40` | Accumulator width in bits |
| `SIGNED` | `int unsigned` | `1` | 1 for signed two's complement, 0 for unsigned |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: async_low

## Parameter Presets

- **`default`**: `ACC_W=40`, `SIGNED=1`, `W=16`
- **`w1_acc2_unsigned`**: `ACC_W=2`, `SIGNED=0`, `W=1`
- **`w7_acc20_signed`**: `ACC_W=20`, `SIGNED=1`, `W=7`
- **`w32_acc128_signed`**: `ACC_W=128`, `SIGNED=1`, `W=32`

## Implementation Limits & Notes

- Accumulator wraps modulo 2**ACC_W.
- Response latency is 1 clock cycle; backpressure holds accumulator state.

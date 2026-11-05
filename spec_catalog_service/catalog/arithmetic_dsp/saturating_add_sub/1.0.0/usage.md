# saturating_add_sub

Signed/unsigned adder/subtractor with automatic saturation clamping

- **VLNV**: `spec2gds.local:arithmetic_dsp:saturating_add_sub:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `a_i` | `in` | `[W-1:0]` | First operand |
| `b_i` | `in` | `[W-1:0]` | Second operand |
| `sub_i` | `in` | `1 (scalar)` | Subtract select (0: add, 1: subtract) |
| `result_o` | `out` | `[W-1:0]` | Clamped arithmetic result |
| `saturated_o` | `out` | `1 (scalar)` | High iff the result was clamped to bounds |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Operand and result data width |
| `SIGNED` | `int unsigned` | `1` | 1 for signed two's complement, 0 for unsigned |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `SIGNED=1`, `W=32`
- **`w2_unsigned`**: `SIGNED=0`, `W=2`
- **`w4_signed`**: `SIGNED=1`, `W=4`
- **`w64_unsigned`**: `SIGNED=0`, `W=64`

## Implementation Limits & Notes

- Signed mode clamps to [-(2**(W-1)), 2**(W-1) - 1].
- Unsigned mode clamps to [0, 2**W - 1].

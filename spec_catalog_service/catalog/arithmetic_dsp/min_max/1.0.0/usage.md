# min_max

Simultaneous minimum and maximum selector with tie-breaking and lane indication

- **VLNV**: `spec2gds.local:arithmetic_dsp:min_max:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `a_i` | `in` | `[W-1:0]` | First input operand |
| `b_i` | `in` | `[W-1:0]` | Second input operand |
| `min_o` | `out` | `[W-1:0]` | Minimum value |
| `max_o` | `out` | `[W-1:0]` | Maximum value |
| `min_from_b_o` | `out` | `1 (scalar)` | High iff b_i was strictly less than a_i |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Operand data width in bits |
| `SIGNED` | `int unsigned` | `0` | 1 for signed two's complement, 0 for unsigned |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `SIGNED=0`, `W=32`
- **`w1_signed`**: `SIGNED=1`, `W=1`
- **`w4_unsigned`**: `SIGNED=0`, `W=4`
- **`w64_signed`**: `SIGNED=1`, `W=64`

## Implementation Limits & Notes

- Ties select a_i for minimum, b_i for maximum, and clear min_from_b_o to 0.
- Zero latency purely combinational.

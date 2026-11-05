# comparator

Signed/unsigned magnitude comparator with mutually exclusive lt, eq, and gt flags

- **VLNV**: `spec2gds.local:arithmetic_dsp:comparator:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `a_i` | `in` | `[W-1:0]` | First operand |
| `b_i` | `in` | `[W-1:0]` | Second operand |
| `lt_o` | `out` | `1 (scalar)` | Asserted iff a < b |
| `eq_o` | `out` | `1 (scalar)` | Asserted iff a == b |
| `gt_o` | `out` | `1 (scalar)` | Asserted iff a > b |

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

- Exactly one output flag is high for any legal input pair.
- Zero latency purely combinational comparison.

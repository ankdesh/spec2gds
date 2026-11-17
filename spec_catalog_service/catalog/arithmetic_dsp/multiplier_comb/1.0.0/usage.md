# multiplier_comb

Combinational full-precision multiplier (signed or unsigned)

- **VLNV**: `spec2gds.local:arithmetic_dsp:multiplier_comb:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `composite`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `a_i` | `in` | `[W-1:0]` | First multiplicand operand |
| `b_i` | `in` | `[W-1:0]` | Second multiplicand operand |
| `product_o` | `out` | `[(2*W)-1:0]` | Full-width product result |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `16` | Operand data width in bits |
| `SIGNED` | `int unsigned` | `0` | 1 for signed two's complement, 0 for unsigned |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `SIGNED=0`, `W=16`
- **`w1_signed`**: `SIGNED=1`, `W=1`
- **`w4_unsigned`**: `SIGNED=0`, `W=4`
- **`w32_signed`**: `SIGNED=1`, `W=32`

## Implementation Limits & Notes

- Full precision output with no truncation (width 2*W).
- Purely combinational calculation.

# add_sub

Parameterized adder/subtractor with carry-out, borrow flag, and signed overflow

- **VLNV**: `spec2gds.local:arithmetic_dsp:add_sub:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `a_i` | `in` | `[W-1:0]` | First operand |
| `b_i` | `in` | `[W-1:0]` | Second operand |
| `sub_i` | `in` | `1 (scalar)` | Subtract select (0: add, 1: subtract) |
| `result_o` | `out` | `[W-1:0]` | Arithmetic result |
| `carry_o` | `out` | `1 (scalar)` | Carry-out (add) or no-borrow (sub, a >= b) |
| `overflow_o` | `out` | `1 (scalar)` | Signed two's-complement overflow |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Operand and result data width |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `W=32`
- **`w1`**: `W=1`
- **`w4`**: `W=4`
- **`w64`**: `W=64`

## Implementation Limits & Notes

- Combinational path from operands to result, carry, and overflow.
- Unsigned carry_o semantics: sum carry-out for addition, not-borrow for subtraction.

# shift_register

Serial/parallel-tap shift register with enable

- **VLNV**: `spec2gds.local:state:shift_register:1.0.0`
- **Category**: `state`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `en_i` | `in` | `1 (scalar)` | Shift enable |
| `d_i` | `in` | `[W-1:0]` | Serial data input |
| `q_o` | `out` | `[W-1:0]` | Oldest stage output |
| `taps_o` | `out` | `[(STAGES*W)-1:0]` | Packed intermediate tap outputs |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Word width in bits |
| `STAGES` | `int unsigned` | `4` | Number of shift stages |

## Timing Characteristics

- **Latency**: STAGES
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `STAGES=4`, `W=32`
- **`p1`**: `STAGES=1`, `W=1`
- **`p2`**: `STAGES=3`, `W=7`
- **`p3`**: `STAGES=32`, `W=64`

## Implementation Limits & Notes

- Asynchronous reset clears all stages to zero.

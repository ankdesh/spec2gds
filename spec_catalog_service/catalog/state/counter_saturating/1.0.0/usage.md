# counter_saturating

Saturating bidirectional counter clamped at zero and maximum count

- **VLNV**: `spec2gds.local:state:counter_saturating:1.0.0`
- **Category**: `state`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `up_i` | `in` | `1 (scalar)` | Increment enable |
| `down_i` | `in` | `1 (scalar)` | Decrement enable |
| `clear_i` | `in` | `1 (scalar)` | Synchronous clear |
| `count_o` | `out` | `[W-1:0]` | Current count output |
| `at_min_o` | `out` | `1 (scalar)` | Clamped at zero flag |
| `at_max_o` | `out` | `1 (scalar)` | Clamped at maximum flag |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Counter width in bits |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `W=32`
- **`p1`**: `W=1`
- **`p2`**: `W=5`
- **`p3`**: `W=64`

## Implementation Limits & Notes

- Clamps rather than wrapping.

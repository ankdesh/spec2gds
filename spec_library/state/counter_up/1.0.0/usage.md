# counter_up

Binary up-counter with enable, synchronous clear, and wrap pulse

- **VLNV**: `spec2gds.local:state:counter_up:1.0.0`
- **Category**: `state`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `en_i` | `in` | `1 (scalar)` | Count enable |
| `clear_i` | `in` | `1 (scalar)` | Synchronous clear (priority over enable) |
| `count_o` | `out` | `[W-1:0]` | Current count output |
| `wrap_o` | `out` | `1 (scalar)` | Terminal wrap pulse (one edge at max -> 0) |

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

- Clear takes precedence over enable.

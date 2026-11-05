# fifo_fallthrough

Fall-through FIFO queue with zero-cycle latency when empty

- **VLNV**: `spec2gds.local:storage:fifo_fallthrough:1.0.0`
- **Category**: `storage`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `s_valid_i` | `in` | `1 (scalar)` | Input stream valid |
| `s_data_i` | `in` | `[W-1:0]` | Input stream data |
| `s_ready_o` | `out` | `1 (scalar)` | Input stream ready |
| `m_valid_o` | `out` | `1 (scalar)` | Output stream valid |
| `m_data_o` | `out` | `[W-1:0]` | Output stream data |
| `m_ready_i` | `in` | `1 (scalar)` | Output stream ready |
| `level_o` | `out` | `[(((DEPTH+1)<=1 ? 1 : $clog2(DEPTH+1)) - 1):0]` | Occupancy count of stored words |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Data width in bits |
| `DEPTH` | `int unsigned` | `4` | FIFO depth in words |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `DEPTH=4`, `W=32`
- **`p1`**: `DEPTH=1`, `W=1`
- **`p2`**: `DEPTH=3`, `W=7`
- **`p3`**: `DEPTH=256`, `W=64`

## Implementation Limits & Notes

- Combinational bypass when empty (latency 0).
- level_o reflects stored words only, not words undergoing zero-cycle bypass.

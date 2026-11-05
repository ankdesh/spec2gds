# fifo_packet

Packet FIFO that exposes words only after full packet commitment

- **VLNV**: `spec2gds.local:storage:fifo_packet:1.0.0`
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
| `s_last_i` | `in` | `1 (scalar)` | Input stream packet boundary |
| `s_ready_o` | `out` | `1 (scalar)` | Input stream ready |
| `m_valid_o` | `out` | `1 (scalar)` | Output stream valid |
| `m_data_o` | `out` | `[W-1:0]` | Output stream data |
| `m_last_o` | `out` | `1 (scalar)` | Output stream packet boundary |
| `m_ready_i` | `in` | `1 (scalar)` | Output stream ready |
| `level_o` | `out` | `[(((DEPTH+1)<=1 ? 1 : $clog2(DEPTH+1)) - 1):0]` | Total stored words count |
| `drop_o` | `out` | `1 (scalar)` | Oversized packet drop pulse |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Data width in bits |
| `DEPTH` | `int unsigned` | `16` | Capacity in words |

## Timing Characteristics

- **Latency**: packet
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `DEPTH=16`, `W=32`
- **`p1`**: `DEPTH=2`, `W=1`
- **`p2`**: `DEPTH=3`, `W=7`
- **`p3`**: `DEPTH=256`, `W=64`

## Implementation Limits & Notes

- Exposes only packets whose last word has been accepted.
- Oversized packets (>DEPTH words without last) are dropped with a 1-cycle drop_o pulse.

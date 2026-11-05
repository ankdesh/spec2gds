# stream_half_buffer

Half-throughput single-slot buffer preventing simultaneous push/pop replacement

- **VLNV**: `spec2gds.local:streams:stream_half_buffer:1.0.0`
- **Category**: `streams`
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

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Stream payload width in bits |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 0.5
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `W=32`
- **`p1`**: `W=1`
- **`p2`**: `W=7`
- **`p3`**: `W=256`

## Implementation Limits & Notes

- Maximum throughput is one word per two clock cycles.
- No simultaneous replacement: input accepts new word no earlier than edge after output transfer.

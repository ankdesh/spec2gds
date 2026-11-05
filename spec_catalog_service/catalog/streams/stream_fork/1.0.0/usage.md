# stream_fork

1-to-N stream replicating fork with per-sink pending completion tracking

- **VLNV**: `spec2gds.local:streams:stream_fork:1.0.0`
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
| `m_ready_i` | `in` | `[N-1:0]` | Output stream ready signals |
| `s_ready_o` | `out` | `1 (scalar)` | Input stream ready (empty and ready to capture) |
| `m_valid_o` | `out` | `[N-1:0]` | Output stream valid signals |
| `m_data_o` | `out` | `[(N*W)-1:0]` | Replicated output stream payloads |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Stream payload width in bits |
| `N` | `int unsigned` | `2` | Number of output stream sinks |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: variable
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `N=2`, `W=32`
- **`p1`**: `N=2`, `W=1`
- **`p2`**: `N=3`, `W=7`
- **`p3`**: `N=8`, `W=64`

## Implementation Limits & Notes

- Captures 1 word into register when empty; delivers exactly once to each sink.
- Input ready asserts only when all sinks have received the word (no same-edge replacement).

# stream_join

N-to-1 stream join synchronizing multiple lanes into a concatenated word

- **VLNV**: `spec2gds.local:streams:stream_join:1.0.0`
- **Category**: `streams`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `s_valid_i` | `in` | `[N-1:0]` | Input stream valid signals |
| `s_data_i` | `in` | `[(N*W)-1:0]` | Packed input stream payloads |
| `m_ready_i` | `in` | `1 (scalar)` | Output stream ready |
| `s_ready_o` | `out` | `[N-1:0]` | Input stream ready signals |
| `m_valid_o` | `out` | `1 (scalar)` | Output stream valid (all lanes present) |
| `m_data_o` | `out` | `[(N*W)-1:0]` | Joined output stream payload |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Lane payload width in bits |
| `N` | `int unsigned` | `2` | Number of input stream lanes |

## Timing Characteristics

- **Latency**: variable
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `N=2`, `W=32`
- **`p1`**: `N=2`, `W=1`
- **`p2`**: `N=3`, `W=7`
- **`p3`**: `N=8`, `W=64`

## Implementation Limits & Notes

- Each lane has an independent 1-slot capture buffer.
- Output valid asserts only when all N slots are occupied; flushed simultaneously.

# stream_demux

1-to-N stream demultiplexer with stall-locking routing

- **VLNV**: `spec2gds.local:streams:stream_demux:1.0.0`
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
| `sel_i` | `in` | `[(((N)<=1 ? 1 : $clog2(N)) - 1):0]` | Lane select input |
| `m_ready_i` | `in` | `[N-1:0]` | Output stream ready signals |
| `s_ready_o` | `out` | `1 (scalar)` | Input stream ready |
| `m_valid_o` | `out` | `[N-1:0]` | Output stream valid signals |
| `m_data_o` | `out` | `[(N*W)-1:0]` | Replicated output stream payloads |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Stream payload width in bits |
| `N` | `int unsigned` | `4` | Number of output stream lanes |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `N=4`, `W=32`
- **`p1`**: `N=2`, `W=1`
- **`p2`**: `N=3`, `W=7`
- **`p3`**: `N=16`, `W=64`

## Implementation Limits & Notes

- Selection is latched during a downstream stall to guarantee valid destination stability.
- Input payload is replicated to all output data lanes, but valid is asserted only on the selected lane.

# stream_mux

N-to-1 stream multiplexer with stall-locking lane selection

- **VLNV**: `spec2gds.local:streams:stream_mux:1.0.0`
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
| `sel_i` | `in` | `[(((N)<=1 ? 1 : $clog2(N)) - 1):0]` | Lane select input |
| `m_ready_i` | `in` | `1 (scalar)` | Output stream ready |
| `s_ready_o` | `out` | `[N-1:0]` | Input stream ready signals |
| `m_valid_o` | `out` | `1 (scalar)` | Output stream valid |
| `m_data_o` | `out` | `[W-1:0]` | Selected output payload |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Stream payload width in bits |
| `N` | `int unsigned` | `4` | Number of input stream lanes |

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

- Selection is latched during a downstream stall to guarantee payload stability.
- Invalid selection stalls all input lanes and deasserts output valid.

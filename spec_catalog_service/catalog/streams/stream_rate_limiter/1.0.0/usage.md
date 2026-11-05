# stream_rate_limiter

Zero-storage stream throttler enforcing an INTERVAL clock cycle minimum gap between transfers

- **VLNV**: `spec2gds.local:streams:stream_rate_limiter:1.0.0`
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
| `INTERVAL` | `int unsigned` | `4` | Minimum cycle interval between transfers |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1/INTERVAL
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `INTERVAL=4`, `W=32`
- **`p1`**: `INTERVAL=1`, `W=1`
- **`p2`**: `INTERVAL=3`, `W=7`
- **`p3`**: `INTERVAL=256`, `W=64`

## Implementation Limits & Notes

- Zero-storage combinational forwarding when cooldown is zero.
- Idle time accumulates no burst credit; INTERVAL=1 sustains full throughput.

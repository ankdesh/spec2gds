# fifo_async

Asynchronous dual-clock FIFO with Gray-coded pointer synchronization

- **VLNV**: `spec2gds.local:storage:fifo_async:1.0.0`
- **Category**: `storage`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `wclk_i` | `in` | `1 (scalar)` | Write clock |
| `wrst_ni` | `in` | `1 (scalar)` | Write domain asynchronous active-low reset |
| `s_valid_i` | `in` | `1 (scalar)` | Write stream valid |
| `s_data_i` | `in` | `[W-1:0]` | Write stream data |
| `s_ready_o` | `out` | `1 (scalar)` | Write stream ready |
| `rclk_i` | `in` | `1 (scalar)` | Read clock |
| `rrst_ni` | `in` | `1 (scalar)` | Read domain asynchronous active-low reset |
| `m_valid_o` | `out` | `1 (scalar)` | Read stream valid |
| `m_data_o` | `out` | `[W-1:0]` | Read stream data |
| `m_ready_i` | `in` | `1 (scalar)` | Read stream ready |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Data width in bits |
| `DEPTH` | `int unsigned` | `8` | Power-of-two FIFO depth |

## Timing Characteristics

- **Latency**: 2
- **Throughput**: 1
- **Reset**: async active-low coordinated

## Parameter Presets

- **`default`**: `DEPTH=8`, `W=32`
- **`p1`**: `DEPTH=2`, `W=1`
- **`p2`**: `DEPTH=4`, `W=7`
- **`p3`**: `DEPTH=256`, `W=64`

## Implementation Limits & Notes

- DEPTH must be a power of two.
- Both resets must be asserted together; each domain releases synchronously.
- Digital simulation cannot model analog metastability; MTBF sign-off is not claimed.

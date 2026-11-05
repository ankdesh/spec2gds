# stream_credit_adapter

Adapts ready/valid streaming to a credit-based downstream flow control interface

- **VLNV**: `spec2gds.local:streams:stream_credit_adapter:1.0.0`
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
| `credit_return_i` | `in` | `1 (scalar)` | Credit return pulse from receiver |
| `s_ready_o` | `out` | `1 (scalar)` | Input stream ready (credits available) |
| `tx_valid_o` | `out` | `1 (scalar)` | Transmitted credit stream valid |
| `tx_data_o` | `out` | `[W-1:0]` | Transmitted credit stream payload |
| `credits_o` | `out` | `[(((CREDITS+1)<=1 ? 1 : $clog2(CREDITS+1)) - 1):0]` | Available credits |
| `error_o` | `out` | `1 (scalar)` | Credit overflow error pulse |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Stream payload width in bits |
| `CREDITS` | `int unsigned` | `4` | Maximum credit capacity |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `CREDITS=4`, `W=32`
- **`p1`**: `CREDITS=1`, `W=1`
- **`p2`**: `CREDITS=3`, `W=7`
- **`p3`**: `CREDITS=256`, `W=64`

## Implementation Limits & Notes

- Downstream receiver must always be able to accept tx_valid_o.
- Credit return when credits is already at CREDITS pulses error_o and clamps.

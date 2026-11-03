# register

Basic boundary-reset D flip-flop register

- **VLNV**: `spec2gds.local:state:register:1.0.0`
- **Category**: `state`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `d_i` | `in` | `[W-1:0]` | Data input |
| `q_o` | `out` | `[W-1:0]` | Registered data output |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Register width in bits |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `W=32`
- **`p1`**: `W=1`
- **`p2`**: `W=7`
- **`p3`**: `W=256`

## Implementation Limits & Notes

- Asynchronous active-low reset; single clock domain.

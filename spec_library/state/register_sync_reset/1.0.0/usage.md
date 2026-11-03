# register_sync_reset

Register with synchronous active-low reset and custom reset value

- **VLNV**: `spec2gds.local:state:register_sync_reset:1.0.0`
- **Category**: `state`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Synchronous active-low reset |
| `d_i` | `in` | `[W-1:0]` | Data input |
| `q_o` | `out` | `[W-1:0]` | Registered data output |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Register width in bits |
| `RESET_VALUE` | `int unsigned` | `0` | Reset value |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: sync active-low

## Parameter Presets

- **`default`**: `RESET_VALUE=0`, `W=32`
- **`p1`**: `RESET_VALUE=1`, `W=1`
- **`p2`**: `RESET_VALUE=85`, `W=7`
- **`p3`**: `RESET_VALUE=0`, `W=256`

## Implementation Limits & Notes

- Reset is evaluated strictly at the rising clock edge.

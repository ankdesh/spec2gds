# edge_detector

Rising and falling edge detector generating single-edge pulses

- **VLNV**: `spec2gds.local:state:edge_detector:1.0.0`
- **Category**: `state`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `level_i` | `in` | `1 (scalar)` | Level input to sample |
| `rise_o` | `out` | `1 (scalar)` | Rising edge pulse |
| `fall_o` | `out` | `1 (scalar)` | Falling edge pulse |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| - | - | - | No configurable parameters |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: default parameters

## Implementation Limits & Notes

- Unparameterized; samples signal on rising clock edge.

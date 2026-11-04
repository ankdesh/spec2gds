# pipeline_delay

Unstalled multi-stage pipeline delay with valid framing

- **VLNV**: `spec2gds.local:state:pipeline_delay:1.0.0`
- **Category**: `state`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `valid_i` | `in` | `1 (scalar)` | Input valid framing |
| `data_i` | `in` | `[W-1:0]` | Input payload data |
| `valid_o` | `out` | `1 (scalar)` | Delayed output valid |
| `data_o` | `out` | `[W-1:0]` | Delayed output data |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Payload width in bits |
| `STAGES` | `int unsigned` | `2` | Number of delay stages |

## Timing Characteristics

- **Latency**: STAGES
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `STAGES=2`, `W=32`
- **`p1`**: `STAGES=1`, `W=1`
- **`p2`**: `STAGES=3`, `W=7`
- **`p3`**: `STAGES=16`, `W=64`

## Implementation Limits & Notes

- Unstalled pipeline; cannot backpressure producer.

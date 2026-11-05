# stream_upsizer

Packs RATIO narrow stream words into a wider output stream word

- **VLNV**: `spec2gds.local:streams:stream_upsizer:1.0.0`
- **Category**: `streams`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `s_valid_i` | `in` | `1 (scalar)` | Input narrow stream valid |
| `s_data_i` | `in` | `[IW-1:0]` | Input narrow stream payload |
| `s_ready_o` | `out` | `1 (scalar)` | Input narrow stream ready |
| `m_valid_o` | `out` | `1 (scalar)` | Output wide stream valid |
| `m_data_o` | `out` | `[(IW*RATIO)-1:0]` | Output wide stream payload |
| `m_ready_i` | `in` | `1 (scalar)` | Output wide stream ready |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `IW` | `int unsigned` | `8` | Input word width in bits |
| `RATIO` | `int unsigned` | `4` | Grouping aggregation factor |

## Timing Characteristics

- **Latency**: RATIO
- **Throughput**: 1/RATIO
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `IW=8`, `RATIO=4`
- **`p1`**: `IW=1`, `RATIO=2`
- **`p2`**: `IW=7`, `RATIO=3`
- **`p3`**: `IW=16`, `RATIO=16`

## Implementation Limits & Notes

- Publishes only complete groups of RATIO words; earliest word packed into lowest lane.
- Input blocked while output group is held, including the output transfer edge.

# stream_downsizer

Serializes a wide stream word into RATIO narrow stream words

- **VLNV**: `spec2gds.local:streams:stream_downsizer:1.0.0`
- **Category**: `streams`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `s_valid_i` | `in` | `1 (scalar)` | Input wide stream valid |
| `s_data_i` | `in` | `[(OW*RATIO)-1:0]` | Input wide stream payload |
| `s_ready_o` | `out` | `1 (scalar)` | Input wide stream ready |
| `m_valid_o` | `out` | `1 (scalar)` | Output narrow stream valid |
| `m_data_o` | `out` | `[OW-1:0]` | Output narrow stream payload |
| `m_ready_i` | `in` | `1 (scalar)` | Output narrow stream ready |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `OW` | `int unsigned` | `8` | Output narrow word width in bits |
| `RATIO` | `int unsigned` | `4` | Serialization division factor |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: RATIO
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `OW=8`, `RATIO=4`
- **`p1`**: `OW=1`, `RATIO=2`
- **`p2`**: `OW=7`, `RATIO=3`
- **`p3`**: `OW=16`, `RATIO=16`

## Implementation Limits & Notes

- Captures wide word and emits exactly RATIO low-first lanes.
- Input blocked while held, including the final output word edge.

# pulse_stretcher

Retriggerable pulse stretcher holding output high for CYCLES edges

- **VLNV**: `spec2gds.local:state:pulse_stretcher:1.0.0`
- **Category**: `state`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `pulse_i` | `in` | `1 (scalar)` | Trigger pulse input |
| `pulse_o` | `out` | `1 (scalar)` | Stretched active-high pulse output |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `CYCLES` | `int unsigned` | `4` | Pulse duration in clock cycles |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `CYCLES=4`
- **`p1`**: `CYCLES=1`
- **`p2`**: `CYCLES=7`
- **`p3`**: `CYCLES=256`

## Implementation Limits & Notes

- Retriggerable; sustained input holds output high.

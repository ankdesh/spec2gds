# input_deglitch

Input synchronizer and deglitch filter requiring STABLE consecutive samples to transition

- **VLNV**: `spec2gds.local:cdc_reset:input_deglitch:1.0.0`
- **Category**: `cdc_reset`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `async_i` | `in` | `1 (scalar)` | Asynchronous input with potential glitches |
| `level_o` | `out` | `1 (scalar)` | Filtered stable output level |
| `rise_o` | `out` | `1 (scalar)` | Single-cycle pulse on rising transition |
| `fall_o` | `out` | `1 (scalar)` | Single-cycle pulse on falling transition |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `STABLE` | `int unsigned` | `4` | Number of consecutive identical clock samples required |

## Timing Characteristics

- **Latency**: 2 + STABLE
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `STABLE=4`
- **`p1`**: `STABLE=1`
- **`p2`**: `STABLE=7`
- **`p3`**: `STABLE=256`

## Implementation Limits & Notes

- Requires STABLE consecutive clock cycles of new value to filter subthreshold noise glitches.
- Generates registered one-cycle rise_o and fall_o pulses on accepted transitions.

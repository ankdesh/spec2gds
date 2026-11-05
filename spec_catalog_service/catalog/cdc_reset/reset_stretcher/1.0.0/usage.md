# reset_stretcher

Stretches active-low reset assertion for a minimum number of clock cycles

- **VLNV**: `spec2gds.local:cdc_reset:reset_stretcher:1.0.0`
- **Category**: `cdc_reset`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `async_rst_ni` | `in` | `1 (scalar)` | Asynchronous raw active-low reset input |
| `rst_no` | `out` | `1 (scalar)` | Stretched active-low reset output |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `CYCLES` | `int unsigned` | `4` | Number of clock cycles to hold reset asserted |

## Timing Characteristics

- **Latency**: CYCLES
- **Throughput**: 1
- **Reset**: async assert, counter deassert

## Parameter Presets

- **`default`**: `CYCLES=4`
- **`p1`**: `CYCLES=1`
- **`p2`**: `CYCLES=7`
- **`p3`**: `CYCLES=256`

## Implementation Limits & Notes

- Input deassertion must satisfy clock recovery/removal or use reset_sync upstream.
- Reassertion restarts the count from CYCLES.

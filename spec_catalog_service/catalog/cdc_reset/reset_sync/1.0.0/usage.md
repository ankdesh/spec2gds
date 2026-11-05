# reset_sync

Asynchronous assert, synchronous release reset synchronizer

- **VLNV**: `spec2gds.local:cdc_reset:reset_sync:1.0.0`
- **Category**: `cdc_reset`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `async_rst_ni` | `in` | `1 (scalar)` | Asynchronous raw active-low reset input |
| `rst_no` | `out` | `1 (scalar)` | Synchronously deasserted active-low reset output |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `STAGES` | `int unsigned` | `2` | Number of flip-flop synchronization stages |

## Timing Characteristics

- **Latency**: STAGES
- **Throughput**: 1
- **Reset**: async assert, sync deassert

## Parameter Presets

- **`default`**: `STAGES=2`
- **`p1`**: `STAGES=3`
- **`p2`**: `STAGES=4`

## Implementation Limits & Notes

- Asserts reset output asynchronously 0 immediately upon input assertion.
- Releases reset high only after STAGES clock rising edges following deassertion.

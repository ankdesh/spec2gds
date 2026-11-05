# cdc_level_sync

Multi-stage flip-flop synchronizer for asynchronous single-bit control levels

- **VLNV**: `spec2gds.local:cdc_reset:cdc_level_sync:1.0.0`
- **Category**: `cdc_reset`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Destination clock |
| `rst_ni` | `in` | `1 (scalar)` | Destination asynchronous active-low reset |
| `async_i` | `in` | `1 (scalar)` | Asynchronous input level signal |
| `sync_o` | `out` | `1 (scalar)` | Synchronized destination level signal |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `STAGES` | `int unsigned` | `2` | Number of flip-flop synchronization stages |
| `RESET_VALUE` | `int unsigned` | `0` | Initial reset value (0 or 1) |

## Timing Characteristics

- **Latency**: STAGES
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `RESET_VALUE=0`, `STAGES=2`
- **`p1`**: `RESET_VALUE=1`, `STAGES=2`
- **`p2`**: `RESET_VALUE=0`, `STAGES=4`

## Implementation Limits & Notes

- Intended for quasi-static single-bit levels only; never synchronize multi-bit data buses through independent synchronizers.
- Digital simulation models ideal latency; analog metastability cannot be simulated in digital RTL.

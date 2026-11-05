# reset_sequencer

Sequences the staggered deassertion of N active-low reset outputs with GAP spacing

- **VLNV**: `spec2gds.local:cdc_reset:reset_sequencer:1.0.0`
- **Category**: `cdc_reset`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Master asynchronous active-low reset |
| `enable_i` | `in` | `1 (scalar)` | Sequencer enable control |
| `resets_no` | `out` | `[N-1:0]` | Sequenced active-low domain resets |
| `done_o` | `out` | `1 (scalar)` | All domain resets released completion flag |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `N` | `int unsigned` | `3` | Number of reset domains to sequence |
| `GAP` | `int unsigned` | `4` | Clock cycles gap between successive releases |

## Timing Characteristics

- **Latency**: N*GAP cycles
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `GAP=4`, `N=3`
- **`p1`**: `GAP=1`, `N=2`
- **`p2`**: `GAP=3`, `N=4`
- **`p3`**: `GAP=256`, `N=8`

## Implementation Limits & Notes

- Deasserting enable_i immediately and synchronously resets all outputs low.
- Outputs stay high indefinitely until enable_i is removed or rst_ni asserts.

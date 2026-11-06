# fault_collector

Sticky fault accumulator with lowest first-fault index capture and hold

- **VLNV**: `spec2gds.local:integrity_control:fault_collector:1.0.0`
- **Category**: `integrity_control`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `fault_i` | `in` | `[N-1:0]` | Input fault detection lines |
| `clear_i` | `in` | `[N-1:0]` | Fault sticky clear lines |
| `sticky_o` | `out` | `[N-1:0]` | Accumulated sticky fault register |
| `any_o` | `out` | `1 (scalar)` | Asserted iff any sticky fault bit is set |
| `first_valid_o` | `out` | `1 (scalar)` | Asserted iff first_index_o is valid |
| `first_index_o` | `out` | `[(N > 1 ? ($clog2(N)-1) : 0):0]` | Captured index of first occurred fault |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `N` | `int unsigned` | `8` | Number of fault input lines |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: rst_ni

## Parameter Presets

- **`default`**: `N=8`
- **`n1`**: `N=1`
- **`n3`**: `N=3`
- **`n64`**: `N=64`

## Implementation Limits & Notes

- Sticky bits use set-wins-clear.
- Captures lowest fault index on first fault after no sticky bits remain.
- Retains first_index_o while any sticky bit remains, even if its own bit clears.
- Clears first_valid_o when all resulting sticky bits become zero.

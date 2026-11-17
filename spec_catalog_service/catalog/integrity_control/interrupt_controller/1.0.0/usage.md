# interrupt_controller

Maskable fixed-priority interrupt controller with lowest-index arbitration

- **VLNV**: `spec2gds.local:integrity_control:interrupt_controller:1.0.0`
- **Category**: `integrity_control`
- **Implementation**: `composite`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `irq_i` | `in` | `[N-1:0]` | Input interrupt request lines |
| `enable_i` | `in` | `[N-1:0]` | Interrupt enable mask |
| `clear_i` | `in` | `[N-1:0]` | Synchronous interrupt clear lines |
| `pending_o` | `out` | `[N-1:0]` | Interrupt pending register state |
| `irq_o` | `out` | `1 (scalar)` | Aggregated interrupt request to CPU |
| `index_o` | `out` | `[(N > 1 ? ($clog2(N)-1) : 0):0]` | Index of lowest active enabled interrupt |
| `valid_o` | `out` | `1 (scalar)` | Asserted iff index_o contains a valid interrupt index |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `N` | `int unsigned` | `8` | Number of interrupt lines |

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

- Pending update: set (irq_i) wins over clear (clear_i).
- Mask (enable_i) affects aggregate irq_o and index_o only, not capture in pending_o.
- Lowest enabled pending bit wins arbitration; index_o=0 and valid_o=0 when no eligible source.

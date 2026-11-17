# timeout_monitor

Transaction timeout monitor with cancel, complete, and restart priorities

- **VLNV**: `spec2gds.local:integrity_control:timeout_monitor:1.0.0`
- **Category**: `integrity_control`
- **Implementation**: `composite`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `start_i` | `in` | `1 (scalar)` | Start timeout monitor and capture limit |
| `complete_i` | `in` | `1 (scalar)` | Monitored operation completion (cancels timer) |
| `cancel_i` | `in` | `1 (scalar)` | Cancel timeout monitor |
| `limit_i` | `in` | `[W-1:0]` | Timeout limit in clock cycles |
| `busy_o` | `out` | `1 (scalar)` | Asserted while monitor is actively timing |
| `timeout_o` | `out` | `1 (scalar)` | One-cycle pulse asserted when timeout expires |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `16` | Timer count and limit width in bits |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: rst_ni

## Parameter Presets

- **`default`**: `W=16`
- **`w1`**: `W=1`
- **`w4`**: `W=4`
- **`w32`**: `W=32`

## Implementation Limits & Notes

- Priority order: cancel_i wins, then complete_i, then start_i.
- Start with limit_i=0 pulses timeout_o immediately (busy_o remains 0).
- Start while busy restarts count with newly captured limit.
- Completion on expiry edge wins over timeout.

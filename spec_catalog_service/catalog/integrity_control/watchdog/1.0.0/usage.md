# watchdog

Watchdog timer with pet/kick, sticky expiry flag, and runtime limit reduction support

- **VLNV**: `spec2gds.local:integrity_control:watchdog:1.0.0`
- **Category**: `integrity_control`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `enable_i` | `in` | `1 (scalar)` | Watchdog count enable |
| `kick_i` | `in` | `1 (scalar)` | Watchdog timer kick/pet (clears count) |
| `limit_i` | `in` | `[W-1:0]` | Watchdog expiry limit threshold |
| `clear_i` | `in` | `1 (scalar)` | Synchronous clear (clears count and sticky expired) |
| `expired_o` | `out` | `1 (scalar)` | Sticky expiry flag |
| `count_o` | `out` | `[W-1:0]` | Current watchdog timer count value |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `16` | Counter and limit width in bits |

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

- clear_i wins over enable/kick and clears both count and expired flag.
- Disabling clears count but preserves sticky expired flag.
- Runtime limit reduction below current count expires on next non-kick edge without wrapping.

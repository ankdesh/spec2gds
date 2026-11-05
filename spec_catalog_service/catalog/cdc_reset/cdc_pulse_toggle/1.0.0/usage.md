# cdc_pulse_toggle

Pulse synchronizer using toggle encoding across clock domains

- **VLNV**: `spec2gds.local:cdc_reset:cdc_pulse_toggle:1.0.0`
- **Category**: `cdc_reset`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `src_clk_i` | `in` | `1 (scalar)` | Source clock |
| `src_rst_ni` | `in` | `1 (scalar)` | Source domain asynchronous active-low reset |
| `pulse_i` | `in` | `1 (scalar)` | Source pulse input |
| `dst_clk_i` | `in` | `1 (scalar)` | Destination clock |
| `dst_rst_ni` | `in` | `1 (scalar)` | Destination domain asynchronous active-low reset |
| `pulse_o` | `out` | `1 (scalar)` | Destination synchronized one-cycle pulse output |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| - | - | - | No configurable parameters |

## Timing Characteristics

- **Latency**: 2-3 dst cycles
- **Throughput**: variable
- **Reset**: async active-low coordinated

## Parameter Presets

- **`default`**: default parameters

## Implementation Limits & Notes

- Consecutive source pulses must be spaced by at least 4 destination clock cycles.
- Unacknowledged transfer: pulses arriving too close may merge and be lost.

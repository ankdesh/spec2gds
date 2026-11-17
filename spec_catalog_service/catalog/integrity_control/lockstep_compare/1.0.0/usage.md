# lockstep_compare

Dual-channel payload and valid lockstep comparison monitor with sticky flag

- **VLNV**: `spec2gds.local:integrity_control:lockstep_compare:1.0.0`
- **Category**: `integrity_control`
- **Implementation**: `composite`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `valid_a_i` | `in` | `1 (scalar)` | Channel A valid |
| `data_a_i` | `in` | `[W-1:0]` | Channel A data payload |
| `valid_b_i` | `in` | `1 (scalar)` | Channel B valid |
| `data_b_i` | `in` | `[W-1:0]` | Channel B data payload |
| `clear_i` | `in` | `1 (scalar)` | Synchronous clear of sticky mismatch flag |
| `mismatch_o` | `out` | `1 (scalar)` | Cycle-accurate registered comparison mismatch |
| `sticky_o` | `out` | `1 (scalar)` | Accumulated sticky mismatch flag |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Monitored payload data width in bits |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: rst_ni

## Parameter Presets

- **`default`**: `W=32`
- **`w1`**: `W=1`
- **`w7`**: `W=7`
- **`w256`**: `W=256`

## Implementation Limits & Notes

- Registers mismatch when valids differ or when both are valid and payloads differ.
- When both are invalid, payloads are ignored and mismatch is not asserted.
- Sticky mismatch flag: set wins over clear.

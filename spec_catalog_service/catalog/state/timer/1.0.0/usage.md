# timer

Programmable countdown timer with busy and done indicators

- **VLNV**: `spec2gds.local:state:timer:1.0.0`
- **Category**: `state`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `start_i` | `in` | `1 (scalar)` | Start or restart timer |
| `cancel_i` | `in` | `1 (scalar)` | Cancel timer (priority over start) |
| `load_i` | `in` | `[W-1:0]` | Initial countdown cycles |
| `busy_o` | `out` | `1 (scalar)` | Timer currently counting |
| `done_o` | `out` | `1 (scalar)` | Expiry pulse (one edge) |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `16` | Timer duration width in bits |

## Timing Characteristics

- **Latency**: load edges
- **Throughput**: variable
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `W=16`
- **`p1`**: `W=1`
- **`p2`**: `W=3`
- **`p3`**: `W=64`

## Implementation Limits & Notes

- Cancel wins over start without emitting done.

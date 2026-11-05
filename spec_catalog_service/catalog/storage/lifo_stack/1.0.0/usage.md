# lifo_stack

Last-in-first-out stack with combinational top visibility and error flags

- **VLNV**: `spec2gds.local:storage:lifo_stack:1.0.0`
- **Category**: `storage`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `push_i` | `in` | `1 (scalar)` | Push enable |
| `pop_i` | `in` | `1 (scalar)` | Pop enable |
| `data_i` | `in` | `[W-1:0]` | Push data input |
| `data_o` | `out` | `[W-1:0]` | Top of stack data output |
| `valid_o` | `out` | `1 (scalar)` | Stack non-empty valid flag |
| `level_o` | `out` | `[(((DEPTH+1)<=1 ? 1 : $clog2(DEPTH+1)) - 1):0]` | Occupancy count |
| `overflow_o` | `out` | `1 (scalar)` | Overflow error pulse |
| `underflow_o` | `out` | `1 (scalar)` | Underflow error pulse |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Data width in bits |
| `DEPTH` | `int unsigned` | `4` | Stack capacity in words |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `DEPTH=4`, `W=32`
- **`p1`**: `DEPTH=1`, `W=1`
- **`p2`**: `DEPTH=3`, `W=7`
- **`p3`**: `DEPTH=256`, `W=64`

## Implementation Limits & Notes

- Top is combinationally visible when non-empty.
- Error pulses last exactly one clock cycle.

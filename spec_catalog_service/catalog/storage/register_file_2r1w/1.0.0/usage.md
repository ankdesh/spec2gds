# register_file_2r1w

Two read ports, one write port register file with optional zero register

- **VLNV**: `spec2gds.local:storage:register_file_2r1w:1.0.0`
- **Category**: `storage`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `we_i` | `in` | `1 (scalar)` | Synchronous write enable |
| `waddr_i` | `in` | `[(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0]` | Write address |
| `wdata_i` | `in` | `[W-1:0]` | Write data |
| `raddr_a_i` | `in` | `[(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0]` | Read port A address |
| `raddr_b_i` | `in` | `[(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0]` | Read port B address |
| `rdata_a_o` | `out` | `[W-1:0]` | Read port A data output |
| `rdata_b_o` | `out` | `[W-1:0]` | Read port B data output |
| `rvalid_a_o` | `out` | `1 (scalar)` | Read port A address valid |
| `rvalid_b_o` | `out` | `1 (scalar)` | Read port B address valid |
| `write_error_o` | `out` | `1 (scalar)` | Write address error pulse |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Register width in bits |
| `DEPTH` | `int unsigned` | `16` | Number of registers |
| `ZERO_REG` | `int unsigned` | `1` | Register 0 wired to zero flag (0 or 1) |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `DEPTH=16`, `W=32`, `ZERO_REG=1`
- **`p1`**: `DEPTH=2`, `W=1`, `ZERO_REG=0`
- **`p2`**: `DEPTH=3`, `W=7`, `ZERO_REG=1`
- **`p3`**: `DEPTH=256`, `W=64`, `ZERO_REG=0`

## Implementation Limits & Notes

- Asynchronous combinational reads; synchronous registered write.
- If ZERO_REG=1, register 0 always evaluates to zero and ignores writes.

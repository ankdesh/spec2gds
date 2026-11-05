# ram_2rw

True dual-port synchronous RAM with write collision rejection

- **VLNV**: `spec2gds.local:storage:ram_2rw:1.0.0`
- **Category**: `storage`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset (controls flags only) |
| `a_en_i` | `in` | `1 (scalar)` | Port A enable |
| `a_we_i` | `in` | `1 (scalar)` | Port A write enable |
| `a_addr_i` | `in` | `[(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0]` | Port A address |
| `a_wdata_i` | `in` | `[W-1:0]` | Port A write data |
| `a_be_i` | `in` | `[(W/8)-1:0]` | Port A byte enables |
| `a_rvalid_o` | `out` | `1 (scalar)` | Port A read valid flag |
| `a_rdata_o` | `out` | `[W-1:0]` | Port A read data |
| `a_error_o` | `out` | `1 (scalar)` | Port A error pulse |
| `b_en_i` | `in` | `1 (scalar)` | Port B enable |
| `b_we_i` | `in` | `1 (scalar)` | Port B write enable |
| `b_addr_i` | `in` | `[(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0]` | Port B address |
| `b_wdata_i` | `in` | `[W-1:0]` | Port B write data |
| `b_be_i` | `in` | `[(W/8)-1:0]` | Port B byte enables |
| `b_rvalid_o` | `out` | `1 (scalar)` | Port B read valid flag |
| `b_rdata_o` | `out` | `[W-1:0]` | Port B read data |
| `b_error_o` | `out` | `1 (scalar)` | Port B error pulse |
| `collision_o` | `out` | `1 (scalar)` | Simultaneous write collision pulse |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Data width in bits (multiple of 8) |
| `DEPTH` | `int unsigned` | `16` | Memory depth in words |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: async active-low control only

## Parameter Presets

- **`default`**: `DEPTH=16`, `W=32`
- **`p1`**: `DEPTH=2`, `W=8`
- **`p2`**: `DEPTH=3`, `W=24`
- **`p3`**: `DEPTH=1024`, `W=256`

## Implementation Limits & Notes

- Simultaneous writes to the exact same address reject both writes and pulse collision_o.
- Read+write on same address returns pre-edge old data to reader.

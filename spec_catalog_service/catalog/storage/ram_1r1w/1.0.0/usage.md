# ram_1r1w

Simple dual-port synchronous RAM with independent read and write ports

- **VLNV**: `spec2gds.local:storage:ram_1r1w:1.0.0`
- **Category**: `storage`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset (controls flags only) |
| `we_i` | `in` | `1 (scalar)` | Write enable |
| `waddr_i` | `in` | `[(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0]` | Write address |
| `wdata_i` | `in` | `[W-1:0]` | Write data |
| `be_i` | `in` | `[(W/8)-1:0]` | Write byte enables |
| `re_i` | `in` | `1 (scalar)` | Read enable |
| `raddr_i` | `in` | `[(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0]` | Read address |
| `rvalid_o` | `out` | `1 (scalar)` | Read data valid flag |
| `rdata_o` | `out` | `[W-1:0]` | Read data output |
| `write_error_o` | `out` | `1 (scalar)` | Write address error pulse |
| `read_error_o` | `out` | `1 (scalar)` | Read address error pulse |

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

- Same-address read/write collision returns pre-edge old data.
- RAM storage array is not reset.

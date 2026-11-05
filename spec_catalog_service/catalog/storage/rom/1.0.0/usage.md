# rom

Synchronous ROM initialized from packed parameter INIT

- **VLNV**: `spec2gds.local:storage:rom:1.0.0`
- **Category**: `storage`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `en_i` | `in` | `1 (scalar)` | Read enable |
| `addr_i` | `in` | `[(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0]` | Read address |
| `valid_o` | `out` | `1 (scalar)` | Read data valid flag |
| `data_o` | `out` | `[W-1:0]` | Read data output |
| `error_o` | `out` | `1 (scalar)` | Out-of-range address error flag |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Word width in bits |
| `DEPTH` | `int unsigned` | `16` | Memory depth in words |
| `INIT` | `bit [(W*DEPTH)-1:0]` | `0` | Packed memory initial contents |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `DEPTH=16`, `INIT=0`, `W=32`
- **`p1`**: `DEPTH=2`, `INIT=2`, `W=1`
- **`p2`**: `DEPTH=3`, `INIT=197121`, `W=8`
- **`p3`**: `DEPTH=256`, `INIT=0`, `W=64`

## Implementation Limits & Notes

- Packed parameter INIT stores image directly; no external files or network access.
- Disabled hold preserves last registered data output.

# ring_buffer

Circular history ring buffer retaining the newest DEPTH words

- **VLNV**: `spec2gds.local:storage:ring_buffer:1.0.0`
- **Category**: `storage`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `write_i` | `in` | `1 (scalar)` | Write enable |
| `data_i` | `in` | `[W-1:0]` | Data to append |
| `index_i` | `in` | `[(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0]` | Relative index (0=newest) |
| `data_o` | `out` | `[W-1:0]` | Indexed historical word |
| `valid_o` | `out` | `1 (scalar)` | Valid index flag |
| `count_o` | `out` | `[(((DEPTH+1)<=1 ? 1 : $clog2(DEPTH+1)) - 1):0]` | Count of valid stored words |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Data width in bits |
| `DEPTH` | `int unsigned` | `8` | Capacity in words |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `DEPTH=8`, `W=32`
- **`p1`**: `DEPTH=1`, `W=1`
- **`p2`**: `DEPTH=3`, `W=7`
- **`p3`**: `DEPTH=256`, `W=64`

## Implementation Limits & Notes

- Index 0 is newest recorded word; index 1 is previous.
- Overwrites oldest entry when capacity is exceeded.

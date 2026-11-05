# cam_binary

Binary content-addressable memory with priority index search

- **VLNV**: `spec2gds.local:storage:cam_binary:1.0.0`
- **Category**: `storage`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `write_i` | `in` | `1 (scalar)` | Write entry enable |
| `delete_i` | `in` | `1 (scalar)` | Delete entry enable (priority over write) |
| `index_i` | `in` | `[(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0]` | Entry slot index |
| `key_i` | `in` | `[KEY_W-1:0]` | Key to write |
| `value_i` | `in` | `[VALUE_W-1:0]` | Value to write |
| `search_i` | `in` | `[KEY_W-1:0]` | Search key input |
| `hit_o` | `out` | `1 (scalar)` | Search match flag |
| `multi_o` | `out` | `1 (scalar)` | Multiple matches flag |
| `index_o` | `out` | `[(((DEPTH)<=1 ? 1 : $clog2(DEPTH)) - 1):0]` | Lowest matching entry index |
| `value_o` | `out` | `[VALUE_W-1:0]` | Value of lowest matching entry |
| `error_o` | `out` | `1 (scalar)` | Out-of-range index error pulse |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `KEY_W` | `int unsigned` | `16` | Key width in bits |
| `VALUE_W` | `int unsigned` | `32` | Payload value width in bits |
| `DEPTH` | `int unsigned` | `8` | Capacity in entries |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `DEPTH=8`, `KEY_W=16`, `VALUE_W=32`
- **`p1`**: `DEPTH=2`, `KEY_W=1`, `VALUE_W=1`
- **`p2`**: `DEPTH=3`, `KEY_W=7`, `VALUE_W=9`
- **`p3`**: `DEPTH=64`, `KEY_W=64`, `VALUE_W=64`

## Implementation Limits & Notes

- Combinational search resolves lowest matching index when multiple keys match.
- Delete operation has priority over write operation.

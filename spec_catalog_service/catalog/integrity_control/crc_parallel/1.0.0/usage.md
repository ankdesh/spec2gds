# crc_parallel

Byte/word-parallel CRC generator with configurable lane count and polynomial

- **VLNV**: `spec2gds.local:integrity_control:crc_parallel:1.0.0`
- **Category**: `integrity_control`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `clear_i` | `in` | `1 (scalar)` | Synchronous clear/reinitialization to INIT |
| `valid_i` | `in` | `1 (scalar)` | Input data valid |
| `data_i` | `in` | `[(8*BYTES)-1:0]` | Parallel byte array in ascending lane order |
| `crc_o` | `out` | `[WIDTH-1:0]` | Current computed CRC checksum |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `WIDTH` | `int unsigned` | `32` | CRC width in bits |
| `POLY` | `logic [WIDTH-1:0]` | `WIDTH'(79764919)` | Generator polynomial |
| `INIT` | `logic [WIDTH-1:0]` | `WIDTH'(4294967295)` | Initial register state |
| `XOROUT` | `logic [WIDTH-1:0]` | `WIDTH'(4294967295)` | Final XOR mask applied to output |
| `BYTES` | `int unsigned` | `4` | Number of parallel input bytes per cycle |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: rst_ni

## Parameter Presets

- **`default`**: `BYTES=4`, `INIT=4294967295`, `POLY=79764919`, `WIDTH=32`, `XOROUT=4294967295`
- **`crc8_b1`**: `BYTES=1`, `INIT=0`, `POLY=7`, `WIDTH=8`, `XOROUT=0`
- **`crc16_b3`**: `BYTES=3`, `INIT=65535`, `POLY=4129`, `WIDTH=16`, `XOROUT=0`
- **`crc32_b16`**: `BYTES=16`, `INIT=4294967295`, `POLY=79764919`, `WIDTH=32`, `XOROUT=4294967295`

## Implementation Limits & Notes

- Processes bytes in ascending lane order (lane 0 in data_i[7:0]), MSB-first within each byte.
- Synchronous clear_i wins over valid_i and restores INIT.

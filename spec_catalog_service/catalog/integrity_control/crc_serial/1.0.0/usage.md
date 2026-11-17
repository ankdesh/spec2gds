# crc_serial

Bit-serial CRC engine with programmable polynomial and initial/xorout values

- **VLNV**: `spec2gds.local:integrity_control:crc_serial:1.0.0`
- **Category**: `integrity_control`
- **Implementation**: `composite`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `clear_i` | `in` | `1 (scalar)` | Synchronous clear/reinitialization to INIT |
| `valid_i` | `in` | `1 (scalar)` | Input bit valid |
| `bit_i` | `in` | `1 (scalar)` | Input data bit (MSB-first processing) |
| `crc_o` | `out` | `[WIDTH-1:0]` | Current computed CRC checksum |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `WIDTH` | `int unsigned` | `32` | CRC width in bits |
| `POLY` | `logic [WIDTH-1:0]` | `WIDTH'(79764919)` | Generator polynomial |
| `INIT` | `logic [WIDTH-1:0]` | `WIDTH'(4294967295)` | Initial register state |
| `XOROUT` | `logic [WIDTH-1:0]` | `WIDTH'(4294967295)` | Final XOR mask applied to output |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: rst_ni

## Parameter Presets

- **`default`**: `INIT=4294967295`, `POLY=79764919`, `WIDTH=32`, `XOROUT=4294967295`
- **`crc8`**: `INIT=0`, `POLY=7`, `WIDTH=8`, `XOROUT=0`
- **`crc16`**: `INIT=65535`, `POLY=4129`, `WIDTH=16`, `XOROUT=0`
- **`crc32_zero`**: `INIT=4294967295`, `POLY=79764919`, `WIDTH=32`, `XOROUT=0`

## Implementation Limits & Notes

- Non-reflected, MSB-first serial CRC computation.
- Synchronous clear_i wins over valid_i and restores INIT.

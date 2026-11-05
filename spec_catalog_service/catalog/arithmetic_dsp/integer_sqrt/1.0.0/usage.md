# integer_sqrt

Digit-pair restoring integer square root (W/2+1 latency, REQ protocol)

- **VLNV**: `spec2gds.local:arithmetic_dsp:integer_sqrt:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Rising-edge clock |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `req_valid_i` | `in` | `1 (scalar)` | Request valid handshake input |
| `req_ready_o` | `out` | `1 (scalar)` | Request ready handshake output |
| `radicand_i` | `in` | `[W-1:0]` | Unsigned radicand input |
| `rsp_valid_o` | `out` | `1 (scalar)` | Response valid handshake output |
| `rsp_ready_i` | `in` | `1 (scalar)` | Response ready handshake input |
| `root_o` | `out` | `[(W/2)-1:0]` | Unsigned integer square root floor result |
| `remainder_o` | `out` | `[W-1:0]` | Remainder (radicand - root**2) |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Radicand data width in bits (must be even) |

## Timing Characteristics

- **Latency**: (W/2)+1
- **Throughput**: 1/((W/2)+1)
- **Reset**: async_low

## Parameter Presets

- **`default`**: `W=32`
- **`w2`**: `W=2`
- **`w8`**: `W=8`
- **`w64`**: `W=64`

## Implementation Limits & Notes

- Unsigned floor square root; invariant root**2 <= radicand < (root+1)**2.
- Fixed latency W/2+1 cycles without stall.

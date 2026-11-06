# secded_encode

Shortened extended Hamming SECDED encoder with overall parity

- **VLNV**: `spec2gds.local:integrity_control:secded_encode:1.0.0`
- **Category**: `integrity_control`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[DATA_W-1:0]` | Input unencoded data word |
| `code_o` | `out` | `[(DATA_W + (DATA_W == 8 ? 4 : (DATA_W == 16 ? 5 : (DATA_W == 32 ? 6 : 7)))):0]` | Extended Hamming SECDED codeword with overall parity |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `DATA_W` | `int unsigned` | `32` | Data word width (8, 16, 32, or 64) |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `DATA_W=32`
- **`w8`**: `DATA_W=8`
- **`w16`**: `DATA_W=16`
- **`w64`**: `DATA_W=64`

## Implementation Limits & Notes

- Combinational encoding with 0 cycle latency.
- Generates extended Hamming codeword with even parity over the code.

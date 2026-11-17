# secded_decode

Shortened extended Hamming SECDED decoder with single-error correction and double-error detection

- **VLNV**: `spec2gds.local:integrity_control:secded_decode:1.0.0`
- **Category**: `integrity_control`
- **Implementation**: `composite`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `code_i` | `in` | `[(DATA_W + (DATA_W == 8 ? 4 : (DATA_W == 16 ? 5 : (DATA_W == 32 ? 6 : 7)))):0]` | Extended Hamming SECDED input codeword |
| `data_o` | `out` | `[DATA_W-1:0]` | Decoded and corrected data word |
| `single_error_o` | `out` | `1 (scalar)` | Asserted iff single-bit error was detected and corrected |
| `double_error_o` | `out` | `1 (scalar)` | Asserted iff double-bit error was detected (uncorrectable) |

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

- Combinational decoding with 0 cycle latency.
- single_error_o and double_error_o flags are mutually exclusive.
- On double_error_o, uncorrected raw data is output.

# parity

Configurable width parity generator and even-parity checker

- **VLNV**: `spec2gds.local:integrity_control:parity:1.0.0`
- **Category**: `integrity_control`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[W-1:0]` | Input data word |
| `parity_i` | `in` | `1 (scalar)` | Received parity bit to check |
| `even_parity_o` | `out` | `1 (scalar)` | Calculated even parity bit (XOR of data_i) |
| `odd_parity_o` | `out` | `1 (scalar)` | Calculated odd parity bit (~even_parity_o) |
| `error_o` | `out` | `1 (scalar)` | Asserted iff even_parity_o != parity_i |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Input data width in bits |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `W=32`
- **`w_1`**: `W=1`
- **`w_8`**: `W=8`
- **`w_256`**: `W=256`

## Implementation Limits & Notes

- Purely combinational calculation with zero latency.
- Error check evaluates even-parity conformance (error iff XOR(data_i) != parity_i).

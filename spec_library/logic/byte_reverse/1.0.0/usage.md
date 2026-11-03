# byte_reverse

Byte order reversal preserving bit order within each byte

- **VLNV**: `spec2gds.local:logic:byte_reverse:1.0.0`
- **Category**: `logic`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[(8*BYTES)-1:0]` | Input bytes |
| `data_o` | `out` | `[(8*BYTES)-1:0]` | Byte-reversed output |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `BYTES` | `int unsigned` | `4` | Number of bytes |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `BYTES=4`
- **`p1`**: `BYTES=1`
- **`p2`**: `BYTES=3`
- **`p3`**: `BYTES=32`

## Implementation Limits & Notes

- Pure wire permutation; assumes 8-bit bytes.

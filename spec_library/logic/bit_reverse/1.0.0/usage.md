# bit_reverse

Bit reversal reflecting bit order across the word width

- **VLNV**: `spec2gds.local:logic:bit_reverse:1.0.0`
- **Category**: `logic`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[W-1:0]` | Input word |
| `data_o` | `out` | `[W-1:0]` | Bit-reversed output word |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Data width in bits |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `W=32`
- **`p1`**: `W=1`
- **`p2`**: `W=7`
- **`p3`**: `W=256`

## Implementation Limits & Notes

- Pure wire permutation.

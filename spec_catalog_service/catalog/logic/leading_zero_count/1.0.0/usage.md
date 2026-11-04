# leading_zero_count

Leading zero counter from MSB with zero detection flag

- **VLNV**: `spec2gds.local:logic:leading_zero_count:1.0.0`
- **Category**: `logic`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[W-1:0]` | Input data word |
| `count_o` | `out` | `[(((W+1)<=1 ? 1 : $clog2(W+1)) - 1):0]` | Leading zero count |
| `zero_o` | `out` | `1 (scalar)` | Input is all zero |

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
- **`p2`**: `W=8`
- **`p3`**: `W=256`

## Implementation Limits & Notes

- Combinational only.

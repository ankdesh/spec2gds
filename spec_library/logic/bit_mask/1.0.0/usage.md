# bit_mask

Contiguous bit mask generator with start index and length

- **VLNV**: `spec2gds.local:logic:bit_mask:1.0.0`
- **Category**: `logic`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `start_i` | `in` | `[(((W)<=1 ? 1 : $clog2(W)) - 1):0]` | Starting bit position |
| `length_i` | `in` | `[(((W+1)<=1 ? 1 : $clog2(W+1)) - 1):0]` | Number of bits to set |
| `mask_o` | `out` | `[W-1:0]` | Generated bit mask |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Mask width in bits |

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

- Combinational only; start positions out of range return zero.

# fixed_saturate

Signed integer clamp to signed OW-bit limits with clipped flag

- **VLNV**: `spec2gds.local:arithmetic_dsp:fixed_saturate:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `composite`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[IW-1:0]` | Signed input data |
| `data_o` | `out` | `[OW-1:0]` | Clamped signed output data |
| `clipped_o` | `out` | `1 (scalar)` | Asserted iff input value was clamped |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `IW` | `int unsigned` | `32` | Input data width in bits |
| `OW` | `int unsigned` | `16` | Output data width in bits |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `IW=32`, `OW=16`
- **`iw2_ow1`**: `IW=2`, `OW=1`
- **`iw8_ow4`**: `IW=8`, `OW=4`
- **`iw64_ow32`**: `IW=64`, `OW=32`

## Implementation Limits & Notes

- Combinational saturation logic without scaling.
- Signed two's-complement clamping only.

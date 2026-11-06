# fixed_scale

Signed scaling by constant integer gain with nearest-even round and saturation

- **VLNV**: `spec2gds.local:arithmetic_dsp:fixed_scale:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[IW-1:0]` | Signed input data |
| `data_o` | `out` | `[OW-1:0]` | Scaled, rounded, and saturated output |
| `clipped_o` | `out` | `1 (scalar)` | Asserted iff saturation clamped the value |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `IW` | `int unsigned` | `16` | Input data width in bits |
| `OW` | `int unsigned` | `16` | Output data width in bits |
| `COEFF_W` | `int unsigned` | `16` | Gain coefficient width in bits |
| `FRAC` | `int unsigned` | `8` | Fractional bits to divide by 2**FRAC |
| `GAIN` | `int signed` | `256` | Signed scaling gain factor |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `COEFF_W=16`, `FRAC=8`, `GAIN=256`, `IW=16`, `OW=16`
- **`preset1`**: `COEFF_W=8`, `FRAC=4`, `GAIN=16`, `IW=8`, `OW=8`
- **`preset2`**: `COEFF_W=8`, `FRAC=3`, `GAIN=-7`, `IW=8`, `OW=4`
- **`preset3`**: `COEFF_W=32`, `FRAC=16`, `GAIN=65536`, `IW=32`, `OW=32`

## Implementation Limits & Notes

- Combinational multiply-scale-saturate path.
- Nearest-even rounding on division by 2**FRAC.
- Clamps cleanly to signed OW range on overflow.

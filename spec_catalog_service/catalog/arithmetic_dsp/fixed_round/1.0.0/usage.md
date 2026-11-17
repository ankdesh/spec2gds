# fixed_round

Signed integer scaling by power of two with nearest-even rounding

- **VLNV**: `spec2gds.local:arithmetic_dsp:fixed_round:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `composite`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[IW-1:0]` | Signed input data |
| `data_o` | `out` | `[OW-1:0]` | Rounded output integer (wrapped to OW bits) |
| `overflow_o` | `out` | `1 (scalar)` | Asserted iff rounded result exceeds signed OW range |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `IW` | `int unsigned` | `32` | Input data width in bits |
| `OW` | `int unsigned` | `16` | Output data width in bits |
| `DROP` | `int unsigned` | `8` | Fractional bits to drop (divide by 2**DROP) |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `DROP=8`, `IW=32`, `OW=16`
- **`drop0`**: `DROP=0`, `IW=8`, `OW=8`
- **`iw8_ow4_drop3`**: `DROP=3`, `IW=8`, `OW=4`
- **`iw64_ow32_drop31`**: `DROP=31`, `IW=64`, `OW=32`

## Implementation Limits & Notes

- Combinational rounding logic.
- Nearest-even rounding on exact halfway ties.
- Wraps to OW bits on overflow; overflow_o flags out-of-range condition.

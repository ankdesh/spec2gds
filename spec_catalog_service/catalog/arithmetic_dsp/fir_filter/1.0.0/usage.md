# fir_filter

Pipelined streaming FIR filter with signed history and elastic output

- **VLNV**: `spec2gds.local:arithmetic_dsp:fir_filter:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `s_valid_i` | `in` | `1 (scalar)` | Input stream valid |
| `s_ready_o` | `out` | `1 (scalar)` | Input stream ready |
| `s_data_i` | `in` | `[W-1:0]` | Signed input sample |
| `m_valid_o` | `out` | `1 (scalar)` | Output stream valid |
| `m_ready_i` | `in` | `1 (scalar)` | Output stream ready |
| `m_data_o` | `out` | `[OW-1:0]` | Filtered and saturated output sample |
| `clipped_o` | `out` | `1 (scalar)` | Asserted iff output was clipped by saturation |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `16` | Input sample width in bits |
| `TAPS` | `int unsigned` | `4` | Number of filter taps |
| `CW` | `int unsigned` | `16` | Coefficient lane width in bits |
| `FRAC` | `int unsigned` | `8` | Fractional bits dropped with nearest-even round |
| `COEFFS` | `logic [(TAPS*CW)-1:0]` | `(TAPS*CW)'(256)` | Packed coefficient array (lane 0 in LSBs) |
| `OW` | `int unsigned` | `16` | Output sample width in bits |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: rst_ni

## Parameter Presets

- **`default`**: `COEFFS=256`, `CW=16`, `FRAC=8`, `OW=16`, `TAPS=4`, `W=16`
- **`taps1`**: `COEFFS=16`, `CW=8`, `FRAC=4`, `OW=8`, `TAPS=1`, `W=8`
- **`taps3`**: `COEFFS=66040`, `CW=8`, `FRAC=4`, `OW=16`, `TAPS=3`, `W=8`
- **`w32_taps16`**: `COEFFS=65536`, `CW=32`, `FRAC=16`, `OW=64`, `TAPS=16`, `W=32`

## Implementation Limits & Notes

- One elastic output register with latency 1.
- Input accepted only when output stage is free or consumed.
- Signed saturation cleanly clamps to signed OW limits.

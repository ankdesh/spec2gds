# cic_interpolator

Cascaded Integrator-Comb (CIC) interpolation filter with differential delay 1

- **VLNV**: `spec2gds.local:arithmetic_dsp:cic_interpolator:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `s_valid_i` | `in` | `1 (scalar)` | Input sample stream valid |
| `s_ready_o` | `out` | `1 (scalar)` | Input sample stream ready |
| `s_data_i` | `in` | `[W-1:0]` | Signed input sample |
| `m_valid_o` | `out` | `1 (scalar)` | Interpolated output stream valid |
| `m_ready_i` | `in` | `1 (scalar)` | Interpolated output stream ready |
| `m_data_o` | `out` | `[(W+ORDER*$clog2(R))-1:0]` | Interpolated signed sample output |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `16` | Input sample data width |
| `R` | `int unsigned` | `4` | Interpolation rate ratio |
| `ORDER` | `int unsigned` | `2` | Number of comb and integrator stages |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: R
- **Reset**: rst_ni

## Parameter Presets

- **`default`**: `ORDER=2`, `R=4`, `W=16`
- **`order1`**: `ORDER=1`, `R=2`, `W=2`
- **`order3`**: `ORDER=3`, `R=3`, `W=7`
- **`max`**: `ORDER=4`, `R=16`, `W=24`

## Implementation Limits & Notes

- Internal bit growth B = W + ORDER * clog2(R).
- Differential delay fixed at 1.
- Emits exactly R output samples per accepted input.

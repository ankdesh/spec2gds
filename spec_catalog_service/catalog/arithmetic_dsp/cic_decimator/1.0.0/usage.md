# cic_decimator

Cascaded Integrator-Comb (CIC) decimation filter with differential delay 1

- **VLNV**: `spec2gds.local:arithmetic_dsp:cic_decimator:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `composite`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `s_valid_i` | `in` | `1 (scalar)` | Input sample stream valid |
| `s_ready_o` | `out` | `1 (scalar)` | Input sample stream ready |
| `s_data_i` | `in` | `[W-1:0]` | Signed input sample |
| `m_valid_o` | `out` | `1 (scalar)` | Decimated output stream valid |
| `m_ready_i` | `in` | `1 (scalar)` | Decimated output stream ready |
| `m_data_o` | `out` | `[(W+ORDER*$clog2(R))-1:0]` | Decimated signed sample output |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `16` | Input sample data width |
| `R` | `int unsigned` | `4` | Decimation rate ratio |
| `ORDER` | `int unsigned` | `2` | Number of integrator and comb stages |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1/R
- **Reset**: rst_ni

## Parameter Presets

- **`default`**: `ORDER=2`, `R=4`, `W=16`
- **`order1`**: `ORDER=1`, `R=2`, `W=2`
- **`order3`**: `ORDER=3`, `R=3`, `W=7`
- **`max`**: `ORDER=4`, `R=16`, `W=24`

## Implementation Limits & Notes

- Internal bit growth B = W + ORDER * clog2(R) prevents overflow.
- Differential delay fixed at 1.
- Stalls input when output register is occupied and not consumed.

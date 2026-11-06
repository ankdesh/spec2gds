# cordic_vector

Iterative circular CORDIC vectoring (rectangular to polar conversion)

- **VLNV**: `spec2gds.local:arithmetic_dsp:cordic_vector:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `req_valid_i` | `in` | `1 (scalar)` | Request transfer valid |
| `req_ready_o` | `out` | `1 (scalar)` | Request transfer ready |
| `x_i` | `in` | `[W-1:0]` | Signed Cartesian X coordinate (F=W-3 fractional bits) |
| `y_i` | `in` | `[W-1:0]` | Signed Cartesian Y coordinate (F=W-3 fractional bits) |
| `rsp_valid_o` | `out` | `1 (scalar)` | Response transfer valid |
| `rsp_ready_i` | `in` | `1 (scalar)` | Response transfer ready |
| `magnitude_o` | `out` | `[W-1:0]` | Vector magnitude |
| `angle_o` | `out` | `[W-1:0]` | Vector phase angle in turns [-0.5, +0.5) |
| `range_error_o` | `out` | `1 (scalar)` | Asserted iff input exceeded legal domain |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `24` | Cartesian and angle data width in bits |
| `ITER` | `int unsigned` | `16` | Number of CORDIC iterations |

## Timing Characteristics

- **Latency**: ITER+2
- **Throughput**: 1
- **Reset**: rst_ni

## Parameter Presets

- **`default`**: `ITER=16`, `W=24`
- **`preset1`**: `ITER=8`, `W=16`
- **`preset2`**: `ITER=12`, `W=24`
- **`preset3`**: `ITER=24`, `W=32`

## Implementation Limits & Notes

- Cartesian inputs must satisfy abs(x) <= 2**(W-4) and abs(y) <= 2**(W-4).
- Out of range inputs return zero magnitude/angle and assert range_error_o.
- Input (0,0) special-cases to magnitude 0, angle 0 with no error.
- Transfer latency is exactly ITER+2 clock cycles.

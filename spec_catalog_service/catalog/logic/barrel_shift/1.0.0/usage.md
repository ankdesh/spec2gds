# barrel_shift

Universal barrel shifter with direction and arithmetic mode controls

- **VLNV**: `spec2gds.local:logic:barrel_shift:1.0.0`
- **Category**: `logic`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[W-1:0]` | Data to shift |
| `amount_i` | `in` | `[(((W+1)<=1 ? 1 : $clog2(W+1)) - 1):0]` | Shift amount |
| `right_i` | `in` | `1 (scalar)` | Direction control: 1=right, 0=left |
| `arith_i` | `in` | `1 (scalar)` | Arithmetic mode: 1=sign extend right shifts |
| `data_o` | `out` | `[W-1:0]` | Shifted output |

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

- Combinational only.

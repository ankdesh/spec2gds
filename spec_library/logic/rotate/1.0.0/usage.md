# rotate

Bitwise rotator with direction control and modulo shift

- **VLNV**: `spec2gds.local:logic:rotate:1.0.0`
- **Category**: `logic`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[W-1:0]` | Data to rotate |
| `amount_i` | `in` | `[(((W)<=1 ? 1 : $clog2(W)) - 1):0]` | Rotation amount |
| `right_i` | `in` | `1 (scalar)` | Direction control: 1=right, 0=left |
| `data_o` | `out` | `[W-1:0]` | Rotated output |

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

- Combinational only; W=1 is identity.

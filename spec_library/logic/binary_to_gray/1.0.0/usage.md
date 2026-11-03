# binary_to_gray

Binary to standard reflected Gray code converter

- **VLNV**: `spec2gds.local:logic:binary_to_gray:1.0.0`
- **Category**: `logic`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `binary_i` | `in` | `[W-1:0]` | Standard binary input |
| `gray_o` | `out` | `[W-1:0]` | Reflected Gray code output |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `8` | Code width in bits |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `W=8`
- **`p1`**: `W=1`
- **`p2`**: `W=7`
- **`p3`**: `W=64`

## Implementation Limits & Notes

- Combinational only.

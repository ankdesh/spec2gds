# mux

N-to-1 multiplexer with parameterized data width

- **VLNV**: `spec2gds.local:logic:mux:1.0.0`
- **Category**: `logic`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[(N*W)-1:0]` | Packed input data lanes |
| `sel_i` | `in` | `[(((N)<=1 ? 1 : $clog2(N)) - 1):0]` | Lane select input |
| `data_o` | `out` | `[W-1:0]` | Selected output lane |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Data width in bits |
| `N` | `int unsigned` | `4` | Number of input lanes |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `N=4`, `W=32`
- **`p1`**: `N=2`, `W=1`
- **`p2`**: `N=3`, `W=7`
- **`p3`**: `N=16`, `W=256`

## Implementation Limits & Notes

- Combinational only; does not infer latches or register stages.

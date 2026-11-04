# priority_mux

Priority multiplexer where lowest requested lane wins

- **VLNV**: `spec2gds.local:logic:priority_mux:1.0.0`
- **Category**: `logic`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[(N*W)-1:0]` | Packed input data lanes |
| `req_i` | `in` | `[N-1:0]` | Request vector |
| `data_o` | `out` | `[W-1:0]` | Selected winning data lane |
| `valid_o` | `out` | `1 (scalar)` | Valid output indicator |
| `index_o` | `out` | `[(((N)<=1 ? 1 : $clog2(N)) - 1):0]` | Index of winning lane |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Data width in bits |
| `N` | `int unsigned` | `4` | Number of input request lanes |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `N=4`, `W=32`
- **`p1`**: `N=2`, `W=1`
- **`p2`**: `N=3`, `W=7`
- **`p3`**: `N=16`, `W=64`

## Implementation Limits & Notes

- Combinational priority resolution.

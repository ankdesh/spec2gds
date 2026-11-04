# priority_encoder

Priority encoder where lowest set request bit wins

- **VLNV**: `spec2gds.local:logic:priority_encoder:1.0.0`
- **Category**: `logic`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `req_i` | `in` | `[N-1:0]` | Request vector |
| `index_o` | `out` | `[(((N)<=1 ? 1 : $clog2(N)) - 1):0]` | Lowest set index |
| `valid_o` | `out` | `1 (scalar)` | Valid request indicator |
| `grant_o` | `out` | `[N-1:0]` | One-hot grant vector |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `N` | `int unsigned` | `8` | Number of request inputs |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `N=8`
- **`p1`**: `N=2`
- **`p2`**: `N=3`
- **`p3`**: `N=256`

## Implementation Limits & Notes

- Combinational priority resolution.

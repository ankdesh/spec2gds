# onehot_encoder

Strict one-hot to binary index encoder

- **VLNV**: `spec2gds.local:logic:onehot_encoder:1.0.0`
- **Category**: `logic`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `onehot_i` | `in` | `[N-1:0]` | One-hot input vector |
| `index_o` | `out` | `[(((N)<=1 ? 1 : $clog2(N)) - 1):0]` | Binary encoded index |
| `valid_o` | `out` | `1 (scalar)` | Valid indicator (high only for exactly one bit set) |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `N` | `int unsigned` | `8` | Number of input bits |

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

- Combinational only; rejects zero or multiple active bits.

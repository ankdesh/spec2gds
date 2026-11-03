# binary_decoder

Binary index to one-hot decoder with enable

- **VLNV**: `spec2gds.local:logic:binary_decoder:1.0.0`
- **Category**: `logic`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `index_i` | `in` | `[(((N)<=1 ? 1 : $clog2(N)) - 1):0]` | Binary index input |
| `en_i` | `in` | `1 (scalar)` | Enable input |
| `onehot_o` | `out` | `[N-1:0]` | One-hot decoded output |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `N` | `int unsigned` | `8` | Number of decoded outputs |

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

- Combinational only.

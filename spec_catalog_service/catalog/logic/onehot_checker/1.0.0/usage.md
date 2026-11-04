# onehot_checker

One-hot and one-hot-or-zero property checker

- **VLNV**: `spec2gds.local:logic:onehot_checker:1.0.0`
- **Category**: `logic`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[N-1:0]` | Input vector |
| `onehot_o` | `out` | `1 (scalar)` | Exactly one bit set |
| `onehot0_o` | `out` | `1 (scalar)` | Zero or one bit set |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `N` | `int unsigned` | `8` | Input vector width |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `N=8`
- **`p1`**: `N=1`
- **`p2`**: `N=3`
- **`p3`**: `N=256`

## Implementation Limits & Notes

- Combinational only.

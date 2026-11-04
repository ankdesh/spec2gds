# zero_extend

Zero extender inserting zero bits above lower lanes

- **VLNV**: `spec2gds.local:logic:zero_extend:1.0.0`
- **Category**: `logic`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[IW-1:0]` | Narrow input word |
| `data_o` | `out` | `[OW-1:0]` | Zero-extended output word |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `IW` | `int unsigned` | `8` | Input data width |
| `OW` | `int unsigned` | `32` | Output data width (>= IW) |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `IW=8`, `OW=32`
- **`p1`**: `IW=1`, `OW=1`
- **`p2`**: `IW=7`, `OW=13`
- **`p3`**: `IW=128`, `OW=256`

## Implementation Limits & Notes

- Combinational only; OW must be greater than or equal to IW.

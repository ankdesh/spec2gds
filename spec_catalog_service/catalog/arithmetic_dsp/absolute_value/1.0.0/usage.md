# absolute_value

Two's-complement to unsigned magnitude converter with most-negative flag

- **VLNV**: `spec2gds.local:arithmetic_dsp:absolute_value:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `data_i` | `in` | `[W-1:0]` | Signed two's-complement input |
| `magnitude_o` | `out` | `[W-1:0]` | Unsigned magnitude result |
| `min_value_o` | `out` | `1 (scalar)` | Asserted iff input is the most negative value -(2**(W-1)) |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Signed input and unsigned output data width |

## Timing Characteristics

- **Latency**: 0
- **Throughput**: 1
- **Reset**: none

## Parameter Presets

- **`default`**: `W=32`
- **`w2`**: `W=2`
- **`w4`**: `W=4`
- **`w64`**: `W=64`

## Implementation Limits & Notes

- Input is signed two's-complement; output magnitude is unsigned.
- Most-negative input -(2**(W-1)) yields magnitude 2**(W-1) and min_value_o=1.

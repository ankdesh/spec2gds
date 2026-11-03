# counter_modulo

Modulo-N up counter with enable and terminal wrap pulse

- **VLNV**: `spec2gds.local:state:counter_modulo:1.0.0`
- **Category**: `state`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Asynchronous active-low reset |
| `en_i` | `in` | `1 (scalar)` | Count enable |
| `clear_i` | `in` | `1 (scalar)` | Synchronous clear |
| `count_o` | `out` | `[W-1:0]` | Current count output |
| `wrap_o` | `out` | `1 (scalar)` | Terminal wrap pulse (MODULUS-1 -> 0) |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `8` | Counter width in bits |
| `MODULUS` | `int unsigned` | `16` | Counting modulus [2..2**W] |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: async active-low

## Parameter Presets

- **`default`**: `MODULUS=16`, `W=8`
- **`p1`**: `MODULUS=2`, `W=1`
- **`p2`**: `MODULUS=7`, `W=5`
- **`p3`**: `MODULUS=17`, `W=64`

## Implementation Limits & Notes

- MODULUS must not exceed 2**W.

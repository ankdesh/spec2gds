# dot_product

Iterative signed vector dot product accumulator

- **VLNV**: `spec2gds.local:arithmetic_dsp:dot_product:1.0.0`
- **Category**: `arithmetic_dsp`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `req_valid_i` | `in` | `1 (scalar)` | Request transfer valid |
| `req_ready_o` | `out` | `1 (scalar)` | Request transfer ready |
| `a_i` | `in` | `[(N*W)-1:0]` | Packed vector A elements (lane 0 in LSBs) |
| `b_i` | `in` | `[(N*W)-1:0]` | Packed vector B elements (lane 0 in LSBs) |
| `rsp_valid_o` | `out` | `1 (scalar)` | Response transfer valid |
| `rsp_ready_i` | `in` | `1 (scalar)` | Response transfer ready |
| `sum_o` | `out` | `[OUT_W-1:0]` | Accumulated dot product sum |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `16` | Vector element data width in bits |
| `N` | `int unsigned` | `4` | Number of vector elements |
| `OUT_W` | `int unsigned` | `40` | Accumulated sum output width |

## Timing Characteristics

- **Latency**: N+1
- **Throughput**: 1/(N+1)
- **Reset**: rst_ni

## Parameter Presets

- **`default`**: `N=4`, `OUT_W=40`, `W=16`
- **`n1`**: `N=1`, `OUT_W=5`, `W=2`
- **`w7_n3`**: `N=3`, `OUT_W=16`, `W=7`
- **`w32_n16`**: `N=16`, `OUT_W=68`, `W=32`

## Implementation Limits & Notes

- One pair processed per active edge.
- Transfer latency is N+1 active edges without stall.
- Single outstanding request at a time.

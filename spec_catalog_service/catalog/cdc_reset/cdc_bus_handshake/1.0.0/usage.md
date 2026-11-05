# cdc_bus_handshake

Bundled-data bus synchronizer with full request/acknowledge handshake flow control

- **VLNV**: `spec2gds.local:cdc_reset:cdc_bus_handshake:1.0.0`
- **Category**: `cdc_reset`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `src_clk_i` | `in` | `1 (scalar)` | Source clock |
| `src_rst_ni` | `in` | `1 (scalar)` | Source domain asynchronous active-low reset |
| `s_valid_i` | `in` | `1 (scalar)` | Source stream valid |
| `s_data_i` | `in` | `[W-1:0]` | Source stream data |
| `s_ready_o` | `out` | `1 (scalar)` | Source stream ready |
| `dst_clk_i` | `in` | `1 (scalar)` | Destination clock |
| `dst_rst_ni` | `in` | `1 (scalar)` | Destination domain asynchronous active-low reset |
| `m_valid_o` | `out` | `1 (scalar)` | Destination stream valid |
| `m_data_o` | `out` | `[W-1:0]` | Destination stream data |
| `m_ready_i` | `in` | `1 (scalar)` | Destination stream ready |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `32` | Bus data width in bits |

## Timing Characteristics

- **Latency**: round-trip
- **Throughput**: variable
- **Reset**: async active-low coordinated

## Parameter Presets

- **`default`**: `W=32`
- **`p1`**: `W=1`
- **`p2`**: `W=7`
- **`p3`**: `W=256`

## Implementation Limits & Notes

- Bundled data assumption: source payload remains stable throughout request/acknowledge exchange.
- Individual data bits must not be synchronized separately.

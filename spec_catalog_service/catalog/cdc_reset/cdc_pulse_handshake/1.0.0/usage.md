# cdc_pulse_handshake

Full request/acknowledge handshake pulse synchronizer with overflow rejection

- **VLNV**: `spec2gds.local:cdc_reset:cdc_pulse_handshake:1.0.0`
- **Category**: `cdc_reset`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `src_clk_i` | `in` | `1 (scalar)` | Source clock |
| `src_rst_ni` | `in` | `1 (scalar)` | Source domain asynchronous active-low reset |
| `pulse_i` | `in` | `1 (scalar)` | Source pulse input |
| `ready_o` | `out` | `1 (scalar)` | Source domain ready for next pulse |
| `overflow_o` | `out` | `1 (scalar)` | Pulse rejected while busy error flag |
| `dst_clk_i` | `in` | `1 (scalar)` | Destination clock |
| `dst_rst_ni` | `in` | `1 (scalar)` | Destination domain asynchronous active-low reset |
| `pulse_o` | `out` | `1 (scalar)` | Destination synchronized one-cycle pulse output |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| - | - | - | No configurable parameters |

## Timing Characteristics

- **Latency**: round-trip
- **Throughput**: variable
- **Reset**: async active-low coordinated

## Parameter Presets

- **`default`**: default parameters

## Implementation Limits & Notes

- Handshake ensures safe crossing at arbitrary source/destination frequency ratios.
- Input pulse while busy is dropped and signaled via overflow_o.

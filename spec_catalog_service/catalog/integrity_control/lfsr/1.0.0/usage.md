# lfsr

Linear feedback shift register with runtime seed load and zero rejection

- **VLNV**: `spec2gds.local:integrity_control:lfsr:1.0.0`
- **Category**: `integrity_control`
- **Implementation**: `body_sv`
- **Licence**: `NOASSERTION`

## Interface Ports

| Port | Direction | Width / Range | Description |
| --- | --- | --- | --- |
| `clk_i` | `in` | `1 (scalar)` | Clock input |
| `rst_ni` | `in` | `1 (scalar)` | Active-low asynchronous reset |
| `en_i` | `in` | `1 (scalar)` | Shift enable |
| `load_i` | `in` | `1 (scalar)` | Load new seed |
| `seed_i` | `in` | `[W-1:0]` | Seed to load (must be non-zero) |
| `state_o` | `out` | `[W-1:0]` | Current LFSR register state |
| `seed_error_o` | `out` | `1 (scalar)` | Asserted iff attempt was made to load zero seed |

## Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `W` | `int unsigned` | `16` | LFSR state width in bits |
| `TAPS` | `logic [W-1:0]` | `W'(45)` | Feedback tap mask |
| `SEED` | `logic [W-1:0]` | `W'(1)` | Power-on and reset initial seed |

## Timing Characteristics

- **Latency**: 1
- **Throughput**: 1
- **Reset**: rst_ni

## Parameter Presets

- **`default`**: `SEED=1`, `TAPS=45`, `W=16`
- **`w2`**: `SEED=1`, `TAPS=3`, `W=2`
- **`w4`**: `SEED=1`, `TAPS=12`, `W=4`
- **`w64`**: `SEED=1`, `TAPS=27`, `W=64`

## Implementation Limits & Notes

- Fibonacci topology: next = ((state << 1) | parity(state & TAPS)) masked to W.
- Zero seed load is rejected, state is held, and seed_error_o pulses high for that cycle.

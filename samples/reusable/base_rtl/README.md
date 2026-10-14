# Reusable RTL: two-zone RGB instrument panel

A small instrument might have a system-status LED (green when ready, red on a
fault) and an activity LED (blue while processing). This toy design drives both
RGB LEDs with independent brightness controls, using just three module types.

```text
dual_rgb_panel
├── status_led : rgb_led
│   ├── red   : pwm_channel
│   ├── green : pwm_channel
│   └── blue  : pwm_channel
└── activity_led : rgb_led
    ├── red   : pwm_channel
    ├── green : pwm_channel
    └── blue  : pwm_channel
```

`rgb_led` is instantiated twice; `pwm_channel` is instantiated six times across
those two instances. Each instance has its own phase counter and duty input.
There is one clock domain and no derived clocks. The three files
`pwm_channel.sv`, `rgb_led.sv`, and `dual_rgb_panel.sv` are synthesizable RTL;
`dual_rgb_panel` is the top module. The testbench is simulation-only.

## Interface and behavior

- `PWM_BITS` defaults to 8 and must be at least 1. One PWM period lasts
  `2**PWM_BITS` input clock cycles. For example, a 1 MHz clock gives about
  3.9 kHz PWM at the default width.
- Each duty input is `PWM_BITS + 1` bits wide. At the default width, 0 means
  off, 64 means 25%, 128 means 50%, and 256 means fully on. Higher values
  saturate to fully on.
- Both three-bit outputs use `{red, green, blue}` order and are active high.
  For example, set status duties to `(0, 128, 0)` for half-brightness green,
  and activity duties to `(0, 0, 64)` for quarter-brightness blue.
- `rst` is active high. It immediately blanks the outputs and clears all
  phase counters on the rising clock edge. Hold it for at least one edge.
- Duty inputs must be synchronous to `clk`. They affect the comparator
  immediately; keep them stable for a complete period to obtain the stated
  duty ratio. This example has no bus interface, palette logic, or buffering
  of brightness updates. A physical LED needs an appropriate external driver
  and current limiting.

## Run the simulation

With Verilator 5+, Make, and a C++ compiler installed, run from the repository root:

```bash
bash tests/reusable/run.sh
```

The script lints the default-width RTL, then simulates a shorter 16-cycle PWM
period. It checks all six channels independently, zero and full brightness,
intermediate duties, changed palettes, saturation above full scale, and reset
alignment. A successful run prints `PASS`. Build and simulation logs remain in
the temporary evidence directory printed by the script. No Python packages or
`uv` are needed.

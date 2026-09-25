# spec2gds.local:work:top_design:1.0 RTL project

This deterministic SystemVerilog 2017 project combines IP-XACT module
boundaries, instance hierarchy, and direct wire connections with stored
component/design SystemVerilog module-body semantics. Components without an
active body retain compile-safe leaf defaults. Every file is replaced on
regeneration.

## Verify

Install Verilator 5.x and GNU Make, then run:

```bash
make lint
```

The selected top module is `top_design_top`.

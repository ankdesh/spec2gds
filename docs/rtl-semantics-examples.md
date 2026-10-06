# RTL semantics examples

The minimal samples demonstrate how a component keeps its interface in
IP-XACT while storing only its SystemVerilog section in a Component.
The `rtl.generate` Activity assembles the two sources into a complete module.

## Included examples

| Example | Source package | Behavior |
| --- | --- | --- |
| One cycle | `samples/minimal/single_component_with_rtl.spec` | Asynchronously clears `data_out`; captures `data_in` on a rising edge when `valid_in` is high; otherwise holds the previous output. |
| Two cycles | `samples/minimal/single_component_with_2cycle_rtl.spec` | Captures data and valid into an internal stage, then updates `data_out` from that stage on the following rising edge; otherwise holds the previous output. |

Cycle count means the number of rising-edge register stages. If a valid input
is present before edge E, the one-cycle component exposes it after edge E. The
two-cycle component captures it internally at E and exposes it after E+1. Both
use the existing asynchronous active-low `rst_n` interface. There is no output
valid signal because IP-XACT does not declare one.

## Body-only source contract

Open either package in Spec Editor and inspect the component's inline
**SystemVerilog** section. The stored text may contain declarations and
behavior such as `logic` and `always_ff`, but it does not contain `module`,
`endmodule`, or port declarations. The Activity obtains `clk`, `rst_n`,
`data_in`, `valid_in`, and `data_out` from IP-XACT and emits those declarations
exactly once.

Add or edit the section through **Options → Add section → SystemVerilog**. Run
**Options → More actions… → Launch activity… → Generate RTL** on the entry design to publish a
fresh project beside the active `.spec` package. The separate helper below uses
the configured Activity scratch directory.

## Generate and verify output

Generated RTL is Activity-owned output, not source under `samples/`. The helper
loads the same service registry as Spec Editor and publishes below
`activities.workspace_root` from `config/services.json` (the tracked default is
`generated/`). From the repository root:

```bash
uv run python scripts/generate_rtl_examples.py --check
uv run python scripts/generate_rtl_examples.py --update
```

`--update` preserves existing package identities and topology, refreshes their
component-owned SV bodies, and runs `rtl.generate` into the configured
workspace. It prints each absolute generated project path; run `make lint` in
those directories. `--check` is read-only and fails when either `.spec` package
or configured generated project is missing or stale. Set
`SPEC2GDS_SERVICE_CONFIG` to use a different registry without changing the
script. The Python RTL tests generate into temporary workspaces and simulate
reset, valid/hold behavior, and both pipeline latencies with Verilator 5.x.

Public project paths use readable names, for example
`generated/rtl/single-component-3/top-design/`. Exact identities remain in ownership
manifests. Name collisions receive numeric suffixes; generated files keep their
existing hardware symbols. See [Names and identifiers](naming-and-identifiers.md).

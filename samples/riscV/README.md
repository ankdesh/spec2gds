# Fixed-width five-stage RISC-V Spec

Open `riscv5_fixed.spec` in Spec Editor with **File → Open Spec**. Select
`riscv5_system` or the entry Design `riscv5_system_design`, then choose
**Options → Generate RTL**. The generated top module is `riscv5_system`.

The `.spec` file was created through the running Spec Editor HTTP APIs:
`POST /documents/create`, a revision-checked `POST /transactions`, and
`POST /documents/open`. RTL was exported through
`POST /entities/design/riscv5_system_design/activities/rtl.generate/executions`.
The API export is in `rtl/five-stage-risc-v-fixed-widths/riscv5-system-design/`.

The Spec contains 18 Components and one entry Design. Seventeen Components
have body-only SystemVerilog sections. The `riscv5_system` Component is a
structural wrapper: its internal Design connects every boundary port to the
`u_core` processor instance. The processor's internal module hierarchy is
stored in SV sections referencing Components in the same Spec; those SV
instances do not create visual instances in Circuit Designer.

All ports use literal wire ranges. There are no module parameters, type
parameters, external includes, or external instruction-memory files. The
datapath is 32 bits, register indices are 5 bits, and instruction/data memories
each contain 256 words. The pipeline-register ports are fixed vectors of
65, 191, 150 and 181 bits. Internal packed records remain local to the
processor/control SV sections. Instruction memory embeds the 91-word directed
test program and initializes the remaining words to NOP.

Behavior matches the default configuration of [base_rtl](base_rtl/README.md):
ADD, MUL, ADDI, LW, SW, BEQ, BNE, JAL and LUI; IF → ID → EX → MEM → WB;
and MEM-stage redirection that flushes all three younger instructions.
There is no forwarding or interlock. Register dependencies require three
intervening instructions; three NOPs suffice. This is a teaching instruction
subset, not full RV32I/RV32M compliance. Reset and memory-access limitations
are documented in the Spec and the baseline README.

## Verify

From the repository root, using the requested Python environment:

```bash
~/workpsace/env-python/bin/python samples/riscV/verify_fixed_spec.py
```

Requires Verilator 5+, Make and a C++ compiler, plus the repository Python
dependencies. The check loads the saved `.spec`, verifies that all interfaces
have fixed widths, regenerates RTL and compares it byte-for-byte with the API
export, lints the top module, and runs the existing self-checking processor
program twice. It then compares the complete system wrapper against the
baseline for 600 cycles, checking every output, all 32 registers, all 256 data
words, the initial instruction image and three resets. Each invocation prints
a fresh `/tmp/spec2gds-riscv-fixed-verify-*` evidence directory with build logs,
simulation logs and `summary.json`.

This is directed simulation equivalence, not a formal proof. After modifying
the Spec, regenerate its API export before running this check. A changed
instruction image also requires corresponding updates to the baseline program
and its expected results.

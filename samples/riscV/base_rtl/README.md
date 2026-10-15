# Five-stage RISC-V pipeline

A modular SystemVerilog teaching processor following the architecture in
`screenshots/risc5/` and the [CS61C five-stage pipeline notes](https://notes.cs61c.org/content/pipeline/five-stage-pipeline/).
Instructions pass through IF, ID, EX, MEM, and WB, with data and control captured
at every stage boundary. Branch comparison occurs in EX; PC redirection occurs
in MEM. The architectural datapath is fixed at 32 bits.

## Layout

```text
base_rtl/
├── rtl/
│   ├── riscv_defs.svh       shared constants, enums, control and pipeline records
│   ├── common/
│   │   ├── adder.sv        two's-complement addition, wrapping at WIDTH bits
│   │   ├── multiplier.sv   signed multiplication, returning the low WIDTH bits
│   │   ├── mux2.sv         reusable 2:1 mux
│   │   ├── flopr.sv        register with asynchronous reset
│   │   └── pipe_reg.sv     typed pipeline register with reset and flush
│   ├── core/
│   │   ├── pc.sv
│   │   ├── imem.sv
│   │   ├── regfile.sv
│   │   ├── imm_gen.sv
│   │   ├── alu.sv
│   │   ├── branch_comp.sv
│   │   ├── dmem.sv
│   │   └── control.sv
│   ├── pipe/
│   │   ├── if_id_reg.sv
│   │   ├── id_ex_reg.sv
│   │   ├── ex_mem_reg.sv
│   │   └── mem_wb_reg.sv
│   └── riscv5_top.sv       datapath and control wiring
├── tb/
│   ├── tb_riscv5_top.sv    retirement reference model and end-state checks
│   ├── tb_units.sv         arithmetic, decode, immediate, reset and memory checks
│   └── programs/core_test.hex  annotated machine-code program
└── sim/run.sh             lint, build, simulation and optional waveform
```

All module ports use `i_` and `o_` prefixes. Every RTL module includes
`riscv_defs.svh`; there are no SystemVerilog packages or imports. Compile the
sources together with `+incdir+rtl`. The four boundary modules each instantiate
one `pipe_reg` with the corresponding packed payload type.

## Instruction subset and control

Supported instructions are `add`, `mul`, `addi`, `lw`, `sw`, `beq`, `bne`, `jal`,
and `lui`. `mul` uses the RV32M encoding and returns the low 32 product bits.
This is a subset of RV32I plus `mul`, not a full RV32I/RV32M implementation.
The ALU contains only an adder and multiplier; a dedicated comparator handles
branch equality. LUI explicitly selects zero for the first ALU operand, since
the instruction's apparent `rs1` field belongs to its immediate.

| Instruction | Immediate | ALU A | ALU B | Operation | Memory | Write-back | Redirect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `add` | unused | rs1 | rs2 | ADD | none | ALU | none |
| `mul` | unused | rs1 | rs2 | MUL | none | ALU | none |
| `addi` | I | rs1 | immediate | ADD | none | ALU | none |
| `lw` | I | rs1 | immediate | ADD | read | memory | none |
| `sw` | S | rs1 | immediate | ADD | write rs2 | none | none |
| `beq`, `bne` | B | PC | immediate | ADD | none | none | if comparison passes |
| `jal` | J | PC | immediate | ADD | none | PC + 4 | unconditional |
| `lui` | U | zero | immediate | ADD | none | ALU | none |

Decode produces `ctrl_t` in ID. Each stage consumes its relevant fields and
passes the remaining control alongside the instruction. Valid bits gate all
register writes, memory accesses and redirects. Unsupported encodings become
inert bubbles; there is no exception or trap interface.

## Pipeline and hazards

| Stage | Work | Boundary payload |
| --- | --- | --- |
| IF | Read IMEM, compute PC + 4, select next PC | IF/ID: valid, PC, instruction |
| ID | Decode, read registers, form immediate | ID/EX: operands, immediate, register indices, control, PC, instruction, valid |
| EX | Select operands, ADD/MUL, compare branch operands | EX/MEM: result, store data, comparison, destination, control, PC, instruction, valid |
| MEM | Read/write DMEM, resolve redirect, compute link | MEM/WB: ALU/memory/link results, destination, control, PC, instruction, valid |
| WB | Select result and write register file | Architectural register state |

There is **no data forwarding, interlock, or stall**. Put at least three
intervening instructions between a register producer and its consumer. Three
NOPs (`addi x0, x0, 0`, encoding `00000013`) always satisfy this constraint.
It applies to ALU operands, branch operands, store data, and address bases.
Register writes occur on rising clock edges; reads are combinational with no
same-edge WB-to-ID bypass. Register x0 always reads zero and ignores writes.

A taken branch or jump in MEM selects its saved EX result as the next PC.
It flushes **IF/ID, ID/EX, and EX/MEM**, squashing the three younger instructions
in IF, ID, and EX. MEM/WB still captures the redirecting instruction, preserving
JAL's link write. No delay-slot instructions or branch-padding NOPs are required.
A not-taken branch leaves the pipeline running normally.

This corrects the screenshot's claim of two flushed stages: with redirection
in MEM, the younger instruction in EX must also be squashed. The taken-control
transfer penalty is three cycles.

## Interface, memories and parameters

`riscv5_top` takes `i_clk` and active-low asynchronous `i_rst_n`. Reset clears
the register file, data memory and pipeline, and restores `RESET_PC`. Instruction
memory retains its initial image. Deassert reset away from a rising edge.

`o_pc` exposes the fetch address. `o_retire_valid`, `o_retire_pc`,
`o_retire_inst`, `o_retire_we`, `o_retire_rd`, and `o_retire_data` describe WB
immediately before the rising edge on which it commits. Data and destination
are meaningful for a register write only when `o_retire_we` is high.
`o_redirect` identifies a MEM-stage redirect. Stores update memory in MEM, one
cycle before their retirement trace appears.

The separate instruction and data memories have combinational reads; data
writes occur on rising edges. Addresses are byte addresses, and accesses are
aligned 32-bit words. Unaligned or out-of-range instruction fetches return NOP;
invalid data reads return zero and invalid stores are ignored. Addresses do not
wrap onto smaller memories. No caches, bus handshakes, byte enables, variable
latency, interrupts, or misalignment traps are provided.

| Module | Parameters and defaults |
| --- | --- |
| `riscv5_top` | `IMEM_DEPTH=256`, `DMEM_DEPTH=256`, `IMEM_FILE="tb/programs/core_test.hex"`, `RESET_PC=0` |
| `adder`, `multiplier`, `alu`, `branch_comp`, `mux2`, `imm_gen` | `WIDTH=32` |
| `flopr` | `WIDTH=32`, `RESET_VALUE=0` |
| `pc` | `WIDTH=32`, `RESET_PC=0` |
| `regfile` | `WIDTH=32`, `ADDR_W=5`, `DEPTH=32` |
| `imem` | `DEPTH=256`, `ADDR_W=32`, `WIDTH=32`, `FILE=""` |
| `dmem` | `DEPTH=256`, `ADDR_W=32`, `WIDTH=32` |
| `pipe_reg` | `T=logic [31:0]` |

Depths are positive word counts. Register depth must fit `ADDR_W`. Standalone
memory widths must be power-of-two multiples of 8, at least 16; address width
must exceed the byte-offset width and cover the memory. The processor uses
32-bit memory words and 32 registers. Width parameters make leaf blocks reusable;
they do not turn this core into RV64. `RESET_PC` must be word-aligned.

IMEM initializes unused words to NOP and optionally loads `FILE` using
`$readmemh`; an empty filename leaves all NOPs. File paths are relative to the
simulation working directory. RTL has no simulation delays. IMEM initialization
requires synthesis support for initialized ROM; resettable DMEM and register
arrays generally infer registers rather than FPGA block RAM. Replace the memory
modules when integrating a target-specific memory implementation, preserving
the timing contract.

## Build and verification

Requires Verilator 5+, GNU Make, and a C++ compiler. From the repository root:

```bash
bash samples/riscV/base_rtl/sim/run.sh             # includes a VCD waveform
bash samples/riscV/base_rtl/sim/run.sh --no-trace  # no waveform
```

The runner changes to this sample directory, lints the RTL, and builds/runs both
self-checking benches. It prints a fresh `/tmp/spec2gds-riscv5.*` evidence
directory containing logs, binaries, and, when enabled, `riscv5.vcd`. Warnings
are fatal except for intentionally unconsumed signal fields in pipeline/trace
records. The runner does not need a RISC-V cross compiler or Python packages.

The annotated hex program checks all nine instructions, positive and negative
operands, overflow/truncation, three-NOP dependencies, load/store offsets, x0,
LUI operand isolation, both outcomes of BEQ/BNE, backward branches and jumps,
JAL link reuse, and wrong-path stores/register writes/control transfers.
A sequential reference model checks every retirement; fixed expected register
values and all data-memory words are also checked. The program runs twice after
reset, with an additional initial reset while instructions are in flight.
Leaf checks cover alternate widths, immediate boundaries, illegal encodings,
pipeline flushing, and memory bounds including a non-power-of-two depth.

Expected completion:

```text
PASS reusable blocks, immediate formats, decode rejection, flush, and memory bounds
PASS program run 1: 85 retirements, 3 stores, 9 redirects, 113 cycles
PASS program run 2: 85 retirements, 3 stores, 9 redirects, 113 cycles
ALL TESTS PASSED
```

These are directed sample checks, not ISA compliance or physical timing closure.
The repository profiles are separate checks and do not invoke this sample's
simulation automatically.

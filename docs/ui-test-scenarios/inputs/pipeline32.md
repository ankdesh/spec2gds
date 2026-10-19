# Input pack: Two-stage enabled 32-bit addition datapath

Composite definition reference: `pipeline32`. Containing Component name: **Two-stage enabled 32-bit addition datapath**.
Internal Design name: **Two-stage enabled 32-bit addition datapath implementation**. Instance IDs below are exact;
service-generated IDs for Components and Designs are recorded during creation.

## Complete containing interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `clk` | `in` | leave blank (scalar) | 1 | Rising-edge input clock. |
| `reset` | `in` | leave blank (scalar) | 1 | Synchronous active-high reset; highest priority. |
| `enable` | `in` | leave blank (scalar) | 1 | Advance both register stages. |
| `a` | `in` | `31:0` | 32 | First unsigned operand. |
| `b` | `in` | `31:0` | 32 | Second unsigned operand. |
| `cin` | `in` | leave blank (scalar) | 1 | Carry sampled with a and b. |
| `sum` | `out` | `31:0` | 32 | Registered low result. |
| `cout` | `out` | leave blank (scalar) | 1 | Registered carry. |

## Complete explanation to copy

```text
Purpose
Sample operands, add them combinationally, and publish the result after two enabled capture edges.

Requirements and behavior
R1: u_input captures {cin,b,a}. u_output captures {carry,sum} from the previously captured inputs. R2: Both stages share clk, reset, and enable; disabling stalls the whole pipeline. Reset clears both stages. A sample captured on enabled edge N appears after enabled edge N+1: two register captures, even if disabled edges occur between them.

Structure
u_input: Enabled 65-bit register.
u_add: 32-bit unsigned adder.
u_output: Enabled 33-bit register.

Interface and wiring
Use the physical wire ports and named connection table from this input pack. A row is one signal with one driver and the listed sinks. Slices name the exact hardware bit indices.

Corner cases and integration assumptions
An enabled output immediately after reset can contain the zero-input result until the pipeline fills. There is no valid bit. Cycle markers annotate the two physical register stages; moving a marker must not add registers to generated RTL.

Diagram reading order
Arrange u_input, u_add, u_output left to right. Distinguish data buses from common clock/reset/enable fan-out. Add stage labels Input capture and Result capture without covering nodes.

Verification boundary
The saved interfaces and connections, the Circuit, and generated hierarchy must agree. Generate from the saved containing Component and run make lint on the published project. No functional simulation is claimed.
```

Copy this explanation into the containing Component. For the internal Design,
copy the same text and prepend: `This Design implements the containing Component
Two-stage enabled 32-bit addition datapath; its boundary ports are that Component's interface.`

## Child definitions and instances

| Exact instance ID | Definition input pack | Definition reference |
| --- | --- | --- |
| `u_input` | [Enabled 65-bit register](reg65.md) | reg65 |
| `u_add` | [32-bit unsigned adder](add32.md) | add32 |
| `u_output` | [Enabled 33-bit register](reg33.md) | reg33 |

Create each distinct definition once through Spec Editor. If a linked definition
is composite, create its internal Design and connections recursively. Reuse the
definition for repeated instances. These are setup inputs, not dependencies on
the scored result of another case.

## Endpoint-to-endpoint connections

`top` denotes the containing Component's boundary, not an extra instance. A source
is a parent input or child output; a sink is a child input or parent output.
Use the exact slices; unsliced endpoints use their full width. Every table row
is one logical net, including rows with multiple sinks. No implicit width
conversion, clock, reset, constant, or register can be inferred from narrative.

| Net name | Driver | Sinks | Bits |
| --- | --- | --- | ---: |
| `clock` | `top.clk` | `u_input.clk`, `u_output.clk` | 1 |
| `reset` | `top.reset` | `u_input.reset`, `u_output.reset` | 1 |
| `advance` | `top.enable` | `u_input.enable`, `u_output.enable` | 1 |
| `sample_a` | `top.a` | `u_input.din[31:0]` | 32 |
| `sample_b` | `top.b` | `u_input.din[63:32]` | 32 |
| `sample_cin` | `top.cin` | `u_input.din[64]` | 1 |
| `operand_a` | `u_input.dout[31:0]` | `u_add.a` | 32 |
| `operand_b` | `u_input.dout[63:32]` | `u_add.b` | 32 |
| `operand_cin` | `u_input.dout[64]` | `u_add.cin` | 1 |
| `result_sum` | `u_add.sum` | `u_output.din[31:0]` | 32 |
| `result_carry` | `u_add.cout` | `u_output.din[32]` | 1 |
| `published_sum` | `u_output.dout[31:0]` | `top.sum` | 32 |
| `published_carry` | `u_output.dout[32]` | `top.cout` | 1 |

## Expected logical overview

This is the reference architecture at this level, not a screenshot or a required
pixel layout. Clock and reset fan-out are omitted from this overview only; the
complete table above remains the connection authority. A child composite has
its own linked overview and full connection table.

```mermaid
flowchart LR
    incoming["Containing inputs"]
    outgoing["Containing outputs"]
    u_input["u_input<br/>Enabled 65-bit register"]
    u_add["u_add<br/>32-bit unsigned adder"]
    u_output["u_output<br/>Enabled 33-bit register"]
    incoming -->|"advance, sample_a, sample_b, sample_cin"| u_input
    incoming -->|"advance"| u_output
    u_input -->|"operand_a, operand_b, operand_cin"| u_add
    u_add -->|"result_sum, result_carry"| u_output
    u_output -->|"published_sum, published_carry"| outgoing
```

## Authoring and expected structure

1. Create the containing Component, its explanation, and every boundary wire port.
2. Create its internal Design and bind that Design as the Component implementation.
   This is a required designer capability. If there is no UI path, record a
   capability gap here; do not create the link through an API or archive edit.
3. Add the named child instances from the definition table. Open the writable
   internal Circuit and enter editing state.
4. Create the connection rows through browser controls. For fan-out, extend the
   same logical net. For a sliced bus, map source and destination bit offsets
   independently. Missing controls or unsupported mapping are findings.
5. Arrange the Circuit as described below, Save to Spec, and reopen both views.
6. Keep the containing Component and Design SystemVerilog Sections intentionally
   absent: their implementation is the explicit hierarchy and wiring. The linked
   behavioral leaf Components each require their supplied SystemVerilog body.
7. Generate from the containing Component. Expect structural module instances
   and direct wiring, plus each reachable leaf body; no placeholder tie-offs.

At this level expect **3 instances** and **13 named nets**.
The port table has **8 boundary ports**. Count repeated definitions
once; inspect nested levels separately. There must be no unconnected required
endpoint, extra driver, omitted slice, unexplained conversion, or unexpected leaf.

## Layout and exports

Arrange u_input, u_add, u_output left to right. Distinguish data buses from common clock/reset/enable fan-out. Add stage labels Input capture and Result capture without covering nodes.

Use readable Component names and exact instance and port identities. Keep labels
inside their cards, keep terminals reachable, and preserve connection meaning
while routing. SVG/PNG must show the saved layout, current overlay visibility,
and readable labels. Portable circuit output must preserve this level's graph.

Return to the [catalogue](../README.md).

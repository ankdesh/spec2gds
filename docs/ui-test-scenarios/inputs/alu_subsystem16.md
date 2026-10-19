# Input pack: Hierarchical 16-bit ALU with zero flag

Composite definition reference: `alu_subsystem16`. Containing Component name: **Hierarchical 16-bit ALU with zero flag**.
Internal Design name: **Hierarchical 16-bit ALU with zero flag implementation**. Instance IDs below are exact;
service-generated IDs for Components and Designs are recorded during creation.

## Complete containing interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `a` | `in` | `15:0` | 16 | First operand. |
| `b` | `in` | `15:0` | 16 | Second operand. |
| `op` | `in` | `1:0` | 2 | 00 add, 01 subtract, 10 AND, 11 XOR. |
| `result` | `out` | `15:0` | 16 | Selected result. |
| `zero` | `out` | leave blank (scalar) | 1 | One if the selected result is zero. |

## Complete explanation to copy

```text
Purpose
Expose a reusable ALU core and a zero flag through a second hierarchy level.

Requirements and behavior
R1: The child ALU core supplies the result with its documented four-opcode mapping. R2: zero tests the selected result, not the operands or an unselected operator. The complete subsystem is combinational.

Structure
u_execute: Hierarchical four-operation 16-bit ALU core.
u_zero: 16-bit zero detector.

Interface and wiring
Use the physical wire ports and named connection table from this input pack. A row is one signal with one driver and the listed sinks. Slices name the exact hardware bit indices.

Corner cases and integration assumptions
Equal inputs with XOR select produce result=0 and zero=1. Nested design navigation must return to this containing context without changing connectivity.

Diagram reading order
Show u_execute as a child-design boundary and u_zero beside its output. Inside u_execute retain the four operator rows and selector.

Verification boundary
The saved interfaces and connections, the Circuit, and generated hierarchy must agree. Generate from the saved containing Component and run make lint on the published project. No functional simulation is claimed.
```

Copy this explanation into the containing Component. For the internal Design,
copy the same text and prepend: `This Design implements the containing Component
Hierarchical 16-bit ALU with zero flag; its boundary ports are that Component's interface.`

## Child definitions and instances

| Exact instance ID | Definition input pack | Definition reference |
| --- | --- | --- |
| `u_execute` | [Hierarchical four-operation 16-bit ALU core](alu_core16.md) | alu_core16 |
| `u_zero` | [16-bit zero detector](zero16.md) | zero16 |

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
| `operand_a` | `top.a` | `u_execute.a` | 16 |
| `operand_b` | `top.b` | `u_execute.b` | 16 |
| `operation` | `top.op` | `u_execute.op` | 2 |
| `chosen_result` | `u_execute.y` | `top.result`, `u_zero.value` | 16 |
| `zero_flag` | `u_zero.zero` | `top.zero` | 1 |

## Expected logical overview

This is the reference architecture at this level, not a screenshot or a required
pixel layout. Clock and reset fan-out are omitted from this overview only; the
complete table above remains the connection authority. A child composite has
its own linked overview and full connection table.

```mermaid
flowchart LR
    incoming["Containing inputs"]
    outgoing["Containing outputs"]
    u_execute["u_execute<br/>Hierarchical four-operation 16-bit ALU core"]
    u_zero["u_zero<br/>16-bit zero detector"]
    incoming -->|"operand_a, operand_b, operation"| u_execute
    u_execute -->|"chosen_result"| outgoing
    u_execute -->|"chosen_result"| u_zero
    u_zero -->|"zero_flag"| outgoing
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

At this level expect **2 instances** and **5 named nets**.
The port table has **5 boundary ports**. Count repeated definitions
once; inspect nested levels separately. There must be no unconnected required
endpoint, extra driver, omitted slice, unexplained conversion, or unexpected leaf.

## Layout and exports

Show u_execute as a child-design boundary and u_zero beside its output. Inside u_execute retain the four operator rows and selector.

Use readable Component names and exact instance and port identities. Keep labels
inside their cards, keep terminals reachable, and preserve connection meaning
while routing. SVG/PNG must show the saved layout, current overlay visibility,
and readable labels. Portable circuit output must preserve this level's graph.

Return to the [catalogue](../README.md).

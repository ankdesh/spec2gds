# Input pack: Hierarchical four-operation 16-bit ALU core

Composite definition reference: `alu_core16`. Containing Component name: **Hierarchical four-operation 16-bit ALU core**.
Internal Design name: **Hierarchical four-operation 16-bit ALU core implementation**. Instance IDs below are exact;
service-generated IDs for Components and Designs are recorded during creation.

## Complete containing interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `a` | `in` | `15:0` | 16 | First unsigned operand. |
| `b` | `in` | `15:0` | 16 | Second unsigned operand. |
| `op` | `in` | `1:0` | 2 | 00 add, 01 subtract, 10 AND, 11 XOR. |
| `y` | `out` | `15:0` | 16 | Selected modulo-16-bit result. |

## Complete explanation to copy

```text
Purpose
Select one of four arithmetic and bitwise operations without flattening the reusable operator hierarchy.

Requirements and behavior
R1: op 00 selects a+b, 01 a-b, 10 a AND b, 11 a XOR b. Arithmetic wraps to 16 bits. R2: This core is combinational; every operator is a separate child instance and the selector chooses its result.

Structure
u_add: 16-bit modulo adder.
u_sub: 16-bit modulo subtractor.
u_and: 16-bit bitwise AND.
u_xor: 16-bit bitwise XOR.
u_select: 4-input 16-bit selector.

Interface and wiring
Use the physical wire ports and named connection table from this input pack. A row is one signal with one driver and the listed sinks. Slices name the exact hardware bit indices.

Corner cases and integration assumptions
All four binary opcodes are legal. The core has no carry, signed-overflow, or registered latency.

Diagram reading order
Place the four operators in aligned rows and the selector to their right. Label all opcode branches. Preserve readable child design boundaries.

Verification boundary
The saved interfaces and connections, the Circuit, and generated hierarchy must agree. Generate from the saved containing Component and run make lint on the published project. No functional simulation is claimed.
```

Copy this explanation into the containing Component. For the internal Design,
copy the same text and prepend: `This Design implements the containing Component
Hierarchical four-operation 16-bit ALU core; its boundary ports are that Component's interface.`

## Child definitions and instances

| Exact instance ID | Definition input pack | Definition reference |
| --- | --- | --- |
| `u_add` | [16-bit modulo adder](add16.md) | add16 |
| `u_sub` | [16-bit modulo subtractor](sub16.md) | sub16 |
| `u_and` | [16-bit bitwise AND](and16.md) | and16 |
| `u_xor` | [16-bit bitwise XOR](xor16.md) | xor16 |
| `u_select` | [4-input 16-bit selector](mux16x4.md) | mux16x4 |

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
| `operand_a` | `top.a` | `u_add.a`, `u_sub.a`, `u_and.a`, `u_xor.a` | 16 |
| `operand_b` | `top.b` | `u_add.b`, `u_sub.b`, `u_and.b`, `u_xor.b` | 16 |
| `add_result` | `u_add.y` | `u_select.d0` | 16 |
| `sub_result` | `u_sub.y` | `u_select.d1` | 16 |
| `and_result` | `u_and.y` | `u_select.d2` | 16 |
| `xor_result` | `u_xor.y` | `u_select.d3` | 16 |
| `operation` | `top.op` | `u_select.sel` | 2 |
| `result` | `u_select.y` | `top.y` | 16 |

## Expected logical overview

This is the reference architecture at this level, not a screenshot or a required
pixel layout. Clock and reset fan-out are omitted from this overview only; the
complete table above remains the connection authority. A child composite has
its own linked overview and full connection table.

```mermaid
flowchart LR
    incoming["Containing inputs"]
    outgoing["Containing outputs"]
    u_add["u_add<br/>16-bit modulo adder"]
    u_sub["u_sub<br/>16-bit modulo subtractor"]
    u_and["u_and<br/>16-bit bitwise AND"]
    u_xor["u_xor<br/>16-bit bitwise XOR"]
    u_select["u_select<br/>4-input 16-bit selector"]
    incoming -->|"operand_a, operand_b"| u_add
    incoming -->|"operand_a, operand_b"| u_sub
    incoming -->|"operand_a, operand_b"| u_and
    incoming -->|"operand_a, operand_b"| u_xor
    u_add -->|"add_result"| u_select
    u_sub -->|"sub_result"| u_select
    u_and -->|"and_result"| u_select
    u_xor -->|"xor_result"| u_select
    incoming -->|"operation"| u_select
    u_select -->|"result"| outgoing
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

At this level expect **5 instances** and **8 named nets**.
The port table has **4 boundary ports**. Count repeated definitions
once; inspect nested levels separately. There must be no unconnected required
endpoint, extra driver, omitted slice, unexplained conversion, or unexpected leaf.

## Layout and exports

Place the four operators in aligned rows and the selector to their right. Label all opcode branches. Preserve readable child design boundaries.

Use readable Component names and exact instance and port identities. Keep labels
inside their cards, keep terminals reachable, and preserve connection meaning
while routing. SVG/PNG must show the saved layout, current overlay visibility,
and readable labels. Portable circuit output must preserve this level's graph.

Return to the [catalogue](../README.md).

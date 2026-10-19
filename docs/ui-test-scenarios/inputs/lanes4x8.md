# Input pack: Four-lane eight-bit register bank

Composite definition reference: `lanes4x8`. Containing Component name: **Four-lane eight-bit register bank**.
Internal Design name: **Four-lane eight-bit register bank implementation**. Instance IDs below are exact;
service-generated IDs for Components and Designs are recorded during creation.

## Complete containing interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `clk` | `in` | leave blank (scalar) | 1 | Rising-edge input clock. |
| `reset` | `in` | leave blank (scalar) | 1 | Synchronous active-high reset; highest priority. |
| `enable` | `in` | `3:0` | 4 | Bit i advances lane i. |
| `din` | `in` | `31:0` | 32 | Lane i occupies bits 8*i+7:8*i. |
| `dout` | `out` | `31:0` | 32 | Registered lane words in the same order. |

## Complete explanation to copy

```text
Purpose
Capture four independent bytes using one reusable register definition.

Requirements and behavior
R1: Lane i captures din[8*i+7:8*i] on an edge with enable[i]=1. Disabled lanes hold. R2: All four instances share clk and synchronous reset. Reset clears every lane regardless of enables.

Structure
u_lane0: Enabled 8-bit register.
u_lane1: Enabled 8-bit register.
u_lane2: Enabled 8-bit register.
u_lane3: Enabled 8-bit register.

Interface and wiring
Use the physical wire ports and named connection table from this input pack. A row is one signal with one driver and the listed sinks. Slices name the exact hardware bit indices.

Corner cases and integration assumptions
Lane 0 is the low byte. Independent enables must not be replaced by one global enable. There are four instances and one shared leaf definition, not four copied definitions.

Diagram reading order
Use four aligned rows ordered lane 0 through lane 3. Keep common clock/reset fan-out identifiable and show every input/output slice.

Verification boundary
The saved interfaces and connections, the Circuit, and generated hierarchy must agree. Generate from the saved containing Component and run make lint on the published project. No functional simulation is claimed.
```

Copy this explanation into the containing Component. For the internal Design,
copy the same text and prepend: `This Design implements the containing Component
Four-lane eight-bit register bank; its boundary ports are that Component's interface.`

## Child definitions and instances

| Exact instance ID | Definition input pack | Definition reference |
| --- | --- | --- |
| `u_lane0` | [Enabled 8-bit register](reg8.md) | reg8 |
| `u_lane1` | [Enabled 8-bit register](reg8.md) | reg8 |
| `u_lane2` | [Enabled 8-bit register](reg8.md) | reg8 |
| `u_lane3` | [Enabled 8-bit register](reg8.md) | reg8 |

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
| `clock` | `top.clk` | `u_lane0.clk`, `u_lane1.clk`, `u_lane2.clk`, `u_lane3.clk` | 1 |
| `reset` | `top.reset` | `u_lane0.reset`, `u_lane1.reset`, `u_lane2.reset`, `u_lane3.reset` | 1 |
| `enable_0` | `top.enable[0]` | `u_lane0.enable` | 1 |
| `input_0` | `top.din[7:0]` | `u_lane0.din` | 8 |
| `output_0` | `u_lane0.dout` | `top.dout[7:0]` | 8 |
| `enable_1` | `top.enable[1]` | `u_lane1.enable` | 1 |
| `input_1` | `top.din[15:8]` | `u_lane1.din` | 8 |
| `output_1` | `u_lane1.dout` | `top.dout[15:8]` | 8 |
| `enable_2` | `top.enable[2]` | `u_lane2.enable` | 1 |
| `input_2` | `top.din[23:16]` | `u_lane2.din` | 8 |
| `output_2` | `u_lane2.dout` | `top.dout[23:16]` | 8 |
| `enable_3` | `top.enable[3]` | `u_lane3.enable` | 1 |
| `input_3` | `top.din[31:24]` | `u_lane3.din` | 8 |
| `output_3` | `u_lane3.dout` | `top.dout[31:24]` | 8 |

## Expected logical overview

This is the reference architecture at this level, not a screenshot or a required
pixel layout. Clock and reset fan-out are omitted from this overview only; the
complete table above remains the connection authority. A child composite has
its own linked overview and full connection table.

```mermaid
flowchart LR
    incoming["Containing inputs"]
    outgoing["Containing outputs"]
    u_lane0["u_lane0<br/>Enabled 8-bit register"]
    u_lane1["u_lane1<br/>Enabled 8-bit register"]
    u_lane2["u_lane2<br/>Enabled 8-bit register"]
    u_lane3["u_lane3<br/>Enabled 8-bit register"]
    incoming -->|"enable_0, input_0"| u_lane0
    u_lane0 -->|"output_0"| outgoing
    incoming -->|"enable_1, input_1"| u_lane1
    u_lane1 -->|"output_1"| outgoing
    incoming -->|"enable_2, input_2"| u_lane2
    u_lane2 -->|"output_2"| outgoing
    incoming -->|"enable_3, input_3"| u_lane3
    u_lane3 -->|"output_3"| outgoing
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

At this level expect **4 instances** and **14 named nets**.
The port table has **5 boundary ports**. Count repeated definitions
once; inspect nested levels separately. There must be no unconnected required
endpoint, extra driver, omitted slice, unexplained conversion, or unexpected leaf.

## Layout and exports

Use four aligned rows ordered lane 0 through lane 3. Keep common clock/reset fan-out identifiable and show every input/output slice.

Use readable Component names and exact instance and port identities. Keep labels
inside their cards, keep terminals reachable, and preserve connection meaning
while routing. SVG/PNG must show the saved layout, current overlay visibility,
and readable labels. Portable circuit output must preserve this level's graph.

Return to the [catalogue](../README.md).

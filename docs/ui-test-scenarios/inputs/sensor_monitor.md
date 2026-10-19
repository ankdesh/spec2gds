# Input pack: Four-channel unsigned threshold monitor

Composite definition reference: `sensor_monitor`. Containing Component name: **Four-channel unsigned threshold monitor**.
Internal Design name: **Four-channel unsigned threshold monitor implementation**. Instance IDs below are exact;
service-generated IDs for Components and Designs are recorded during creation.

## Complete containing interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `reading0` | `in` | `7:0` | 8 | Unsigned channel 0 reading. |
| `reading1` | `in` | `7:0` | 8 | Unsigned channel 1 reading. |
| `reading2` | `in` | `7:0` | 8 | Unsigned channel 2 reading. |
| `reading3` | `in` | `7:0` | 8 | Unsigned channel 3 reading. |
| `threshold` | `in` | `7:0` | 8 | Shared strict-greater-than threshold. |
| `alarm` | `out` | `3:0` | 4 | Bit i reports channel i above threshold. |
| `any_alarm` | `out` | leave blank (scalar) | 1 | At least one channel alarm. |
| `status` | `out` | `31:0` | 32 | Channel i in bits 8*i+7:8*i. |

## Complete explanation to copy

```text
Purpose
Provide per-channel and aggregate alarm information plus a packed status word for four sensors.

Requirements and behavior
R1: alarm[i] is reading[i] > threshold, using unsigned comparison. Equality is not an alarm. R2: any_alarm is the OR of alarm bits. status={reading3,reading2,reading1,reading0}. All logic is combinational.

Structure
u_compare0: Unsigned eight-bit threshold comparator.
u_compare1: Unsigned eight-bit threshold comparator.
u_compare2: Unsigned eight-bit threshold comparator.
u_compare3: Unsigned eight-bit threshold comparator.
u_pack: Four-byte status packer.
u_summary: Four-alarm summary.

Interface and wiring
Use the physical wire ports and named connection table from this input pack. A row is one signal with one driver and the listed sinks. Slices name the exact hardware bit indices.

Corner cases and integration assumptions
The threshold has one driver and four sinks. Each reading has two sinks. A fan-out must remain one logical signal rather than creating competing drivers. No clocks or resets are needed.

Diagram reading order
Align four comparator rows. Put threshold fan-out on a common trunk, the summary to the right, and the status packer below. Keep channel numbers and byte order visible.

Verification boundary
The saved interfaces and connections, the Circuit, and generated hierarchy must agree. Generate from the saved containing Component and run make lint on the published project. No functional simulation is claimed.
```

Copy this explanation into the containing Component. For the internal Design,
copy the same text and prepend: `This Design implements the containing Component
Four-channel unsigned threshold monitor; its boundary ports are that Component's interface.`

## Child definitions and instances

| Exact instance ID | Definition input pack | Definition reference |
| --- | --- | --- |
| `u_compare0` | [Unsigned eight-bit threshold comparator](compare8.md) | compare8 |
| `u_compare1` | [Unsigned eight-bit threshold comparator](compare8.md) | compare8 |
| `u_compare2` | [Unsigned eight-bit threshold comparator](compare8.md) | compare8 |
| `u_compare3` | [Unsigned eight-bit threshold comparator](compare8.md) | compare8 |
| `u_pack` | [Four-byte status packer](pack4x8.md) | pack4x8 |
| `u_summary` | [Four-alarm summary](or4.md) | or4 |

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
| `common_threshold` | `top.threshold` | `u_compare0.threshold`, `u_compare1.threshold`, `u_compare2.threshold`, `u_compare3.threshold` | 8 |
| `reading_0` | `top.reading0` | `u_compare0.reading`, `u_pack.d0` | 8 |
| `alarm_0` | `u_compare0.alarm` | `top.alarm[0]`, `u_summary.alarm[0]` | 1 |
| `reading_1` | `top.reading1` | `u_compare1.reading`, `u_pack.d1` | 8 |
| `alarm_1` | `u_compare1.alarm` | `top.alarm[1]`, `u_summary.alarm[1]` | 1 |
| `reading_2` | `top.reading2` | `u_compare2.reading`, `u_pack.d2` | 8 |
| `alarm_2` | `u_compare2.alarm` | `top.alarm[2]`, `u_summary.alarm[2]` | 1 |
| `reading_3` | `top.reading3` | `u_compare3.reading`, `u_pack.d3` | 8 |
| `alarm_3` | `u_compare3.alarm` | `top.alarm[3]`, `u_summary.alarm[3]` | 1 |
| `packed_status` | `u_pack.packed_data` | `top.status` | 32 |
| `summary_alarm` | `u_summary.any_alarm` | `top.any_alarm` | 1 |

## Expected logical overview

This is the reference architecture at this level, not a screenshot or a required
pixel layout. Clock and reset fan-out are omitted from this overview only; the
complete table above remains the connection authority. A child composite has
its own linked overview and full connection table.

```mermaid
flowchart LR
    incoming["Containing inputs"]
    outgoing["Containing outputs"]
    u_compare0["u_compare0<br/>Unsigned eight-bit threshold comparator"]
    u_compare1["u_compare1<br/>Unsigned eight-bit threshold comparator"]
    u_compare2["u_compare2<br/>Unsigned eight-bit threshold comparator"]
    u_compare3["u_compare3<br/>Unsigned eight-bit threshold comparator"]
    u_pack["u_pack<br/>Four-byte status packer"]
    u_summary["u_summary<br/>Four-alarm summary"]
    incoming -->|"common_threshold, reading_0"| u_compare0
    incoming -->|"common_threshold, reading_1"| u_compare1
    incoming -->|"common_threshold, reading_2"| u_compare2
    incoming -->|"common_threshold, reading_3"| u_compare3
    incoming -->|"reading_0, reading_1, reading_2, reading_3"| u_pack
    u_compare0 -->|"alarm_0"| outgoing
    u_compare0 -->|"alarm_0"| u_summary
    u_compare1 -->|"alarm_1"| outgoing
    u_compare1 -->|"alarm_1"| u_summary
    u_compare2 -->|"alarm_2"| outgoing
    u_compare2 -->|"alarm_2"| u_summary
    u_compare3 -->|"alarm_3"| outgoing
    u_compare3 -->|"alarm_3"| u_summary
    u_pack -->|"packed_status"| outgoing
    u_summary -->|"summary_alarm"| outgoing
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

At this level expect **6 instances** and **11 named nets**.
The port table has **8 boundary ports**. Count repeated definitions
once; inspect nested levels separately. There must be no unconnected required
endpoint, extra driver, omitted slice, unexplained conversion, or unexpected leaf.

## Layout and exports

Align four comparator rows. Put threshold fan-out on a common trunk, the summary to the right, and the status packer below. Keep channel numbers and byte order visible.

Use readable Component names and exact instance and port identities. Keep labels
inside their cards, keep terminals reachable, and preserve connection meaning
while routing. SVG/PNG must show the saved layout, current overlay visibility,
and readable labels. Portable circuit output must preserve this level's graph.

Return to the [catalogue](../README.md).

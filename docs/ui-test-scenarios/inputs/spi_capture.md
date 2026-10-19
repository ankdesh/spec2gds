# Input pack: SPI byte capture with four-entry result buffer

Composite definition reference: `spi_capture`. Containing Component name: **SPI byte capture with four-entry result buffer**.
Internal Design name: **SPI byte capture with four-entry result buffer implementation**. Instance IDs below are exact;
service-generated IDs for Components and Designs are recorded during creation.

## Complete containing interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `clk` | `in` | leave blank (scalar) | 1 | Rising-edge input clock. |
| `reset` | `in` | leave blank (scalar) | 1 | Synchronous active-high reset; highest priority. |
| `request` | `in` | leave blank (scalar) | 1 | Pulse to request a capture; denied requests are not queued. |
| `tx_data` | `in` | `7:0` | 8 | Byte sent during capture. |
| `miso` | `in` | leave blank (scalar) | 1 | SPI serial input. |
| `rd_en` | `in` | leave blank (scalar) | 1 | Read a buffered result. |
| `mosi` | `out` | leave blank (scalar) | 1 | SPI serial output. |
| `sclk` | `out` | leave blank (scalar) | 1 | Mode 0 clock. |
| `cs_n` | `out` | leave blank (scalar) | 1 | SPI active-low select. |
| `busy` | `out` | leave blank (scalar) | 1 | SPI engine active. |
| `rejected` | `out` | leave blank (scalar) | 1 | Request denied due to busy/full/handoff. |
| `rd_data` | `out` | `7:0` | 8 | Last accepted buffered read. |
| `full` | `out` | leave blank (scalar) | 1 | Result FIFO full. |
| `empty` | `out` | leave blank (scalar) | 1 | Result FIFO empty. |
| `count` | `out` | `2:0` | 3 | Buffered result count 0..4. |

## Complete explanation to copy

```text
Purpose
Capture SPI bytes into a four-entry FIFO without accepting a transfer that has no reserved result space.

Requirements and behavior
R1: Admit request only when SPI is idle, FIFO is not full, and no completion handoff is pending. R2: Completed rx_data is written to the FIFO on the edge observing done. No other writer exists. R3: Busy/full/handoff requests assert rejected and are not queued. FIFO reads are registered; raw FIFO boundary rules still apply.

Structure
u_spi: Eight-bit SPI Mode 0 master.
u_admit: SPI capture admission control.
u_fifo: Four-entry eight-bit synchronous FIFO.

Interface and wiring
Use the physical wire ports and named connection table from this input pack. A row is one signal with one driver and the listed sinks. Slices name the exact hardware bit indices.

Corner cases and integration assumptions
The done guard prevents overbooking the last free entry during the write handoff. A caller retries rejected requests. The in-flight transfer and four buffered words are distinct; no extra transfer starts while full.

Diagram reading order
Place admission control above the SPI engine and FIFO to the right. Distinguish SPI pins from internal byte buses. Label full and done feedback so the admission condition is readable.

Verification boundary
The saved interfaces and connections, the Circuit, and generated hierarchy must agree. Generate from the saved containing Component and run make lint on the published project. No functional simulation is claimed.
```

Copy this explanation into the containing Component. For the internal Design,
copy the same text and prepend: `This Design implements the containing Component
SPI byte capture with four-entry result buffer; its boundary ports are that Component's interface.`

## Child definitions and instances

| Exact instance ID | Definition input pack | Definition reference |
| --- | --- | --- |
| `u_spi` | [Eight-bit SPI Mode 0 master](spi8.md) | spi8 |
| `u_admit` | [SPI capture admission control](capture_control.md) | capture_control |
| `u_fifo` | [Four-entry eight-bit synchronous FIFO](fifo8x4.md) | fifo8x4 |

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
| `clock` | `top.clk` | `u_spi.clk`, `u_fifo.clk` | 1 |
| `reset` | `top.reset` | `u_spi.reset`, `u_fifo.reset` | 1 |
| `capture_request` | `top.request` | `u_admit.request` | 1 |
| `transmit_byte` | `top.tx_data` | `u_spi.tx_data` | 8 |
| `serial_in` | `top.miso` | `u_spi.miso` | 1 |
| `serial_out` | `u_spi.mosi` | `top.mosi` | 1 |
| `serial_clock` | `u_spi.sclk` | `top.sclk` | 1 |
| `serial_select` | `u_spi.cs_n` | `top.cs_n` | 1 |
| `engine_busy` | `u_spi.busy` | `u_admit.busy`, `top.busy` | 1 |
| `engine_done` | `u_spi.done` | `u_admit.done` | 1 |
| `received_byte` | `u_spi.rx_data` | `u_admit.rx_data` | 8 |
| `admitted_start` | `u_admit.start` | `u_spi.start` | 1 |
| `write_result` | `u_admit.wr_en` | `u_fifo.wr_en` | 1 |
| `buffer_byte` | `u_admit.wr_data` | `u_fifo.wr_data` | 8 |
| `request_rejected` | `u_admit.rejected` | `top.rejected` | 1 |
| `buffer_full` | `u_fifo.full` | `u_admit.full`, `top.full` | 1 |
| `read_request` | `top.rd_en` | `u_fifo.rd_en` | 1 |
| `read_result` | `u_fifo.rd_data` | `top.rd_data` | 8 |
| `buffer_empty` | `u_fifo.empty` | `top.empty` | 1 |
| `buffer_count` | `u_fifo.count` | `top.count` | 3 |

## Expected logical overview

This is the reference architecture at this level, not a screenshot or a required
pixel layout. Clock and reset fan-out are omitted from this overview only; the
complete table above remains the connection authority. A child composite has
its own linked overview and full connection table.

```mermaid
flowchart LR
    incoming["Containing inputs"]
    outgoing["Containing outputs"]
    u_spi["u_spi<br/>Eight-bit SPI Mode 0 master"]
    u_admit["u_admit<br/>SPI capture admission control"]
    u_fifo["u_fifo<br/>Four-entry eight-bit synchronous FIFO"]
    incoming -->|"capture_request"| u_admit
    incoming -->|"transmit_byte, serial_in"| u_spi
    u_spi -->|"serial_out, serial_clock, serial_select, engine_busy"| outgoing
    u_spi -->|"engine_busy, engine_done, received_byte"| u_admit
    u_admit -->|"admitted_start"| u_spi
    u_admit -->|"write_result, buffer_byte"| u_fifo
    u_admit -->|"request_rejected"| outgoing
    u_fifo -->|"buffer_full"| u_admit
    u_fifo -->|"buffer_full, read_result, buffer_empty, buffer_count"| outgoing
    incoming -->|"read_request"| u_fifo
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

At this level expect **3 instances** and **20 named nets**.
The port table has **15 boundary ports**. Count repeated definitions
once; inspect nested levels separately. There must be no unconnected required
endpoint, extra driver, omitted slice, unexplained conversion, or unexpected leaf.

## Layout and exports

Place admission control above the SPI engine and FIFO to the right. Distinguish SPI pins from internal byte buses. Label full and done feedback so the admission condition is readable.

Use readable Component names and exact instance and port identities. Keep labels
inside their cards, keep terminals reachable, and preserve connection meaning
while routing. SVG/PNG must show the saved layout, current overlay visibility,
and readable labels. Portable circuit output must preserve this level's graph.

Return to the [catalogue](../README.md).

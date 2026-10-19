# Input pack: Eight-bit UART transmitter

Definition reference: `uart_tx`. Use this readable Component name: **Eight-bit UART transmitter**.
The reference is a catalogue alias, not a required service-generated ID or module filename.

## Authoring instructions

Create this Component through Spec Editor. Copy the explanation below into its
text Section. Add each wire port separately using its exact Port ID. Add the
SystemVerilog body to the SystemVerilog Section. Save each authored draft.
Do not enter module headers or redeclare ports. Do not replace this body with
connections in narrative text. Record the actual stable Component ID after creation.

## Complete explanation to copy

```text
Purpose
Transmit an eight-bit word using UART 8N1 at one serial bit per 16 input-clock cycles.

Requirements and implemented behavior
R1: Accept start only while idle and capture all data bits. Send start=0, data bits 0 through 7, then stop=1; each lasts 16 clk cycles. R2: busy remains high for all ten serial bits. done pulses for one clk when the stop bit completes. R3: Reset aborts transmission, drives tx high, clears busy and done. No parity is transmitted.

Interface
The Ports Section defines every physical wire. Port IDs, directions, ranges, and descriptions are part of this contract. All data is unsigned unless this explanation says otherwise.

Timing and reset
All state uses rising clk edges and synchronous active-high reset. Reset has priority over the other controls. Read the requirements above for enable and transfer priorities.

Corner cases and integration assumptions
A start while busy is ignored, including the edge that finishes a frame. Data changes after acceptance do not change that frame. Holding start high can begin another frame on the next idle edge. A clock of 16 MHz would produce 1 Mbit/s; the pack does not change the environment clock.

Verification boundary
Review this explanation against the Ports and SystemVerilog Sections. Generate RTL from the saved Component and run the published project lint command. Lint is not functional simulation. Reference examples describe intended behavior; they are not executed test results.
```

## Complete interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `clk` | `in` | leave blank (scalar) | 1 | Rising-edge input clock. |
| `reset` | `in` | leave blank (scalar) | 1 | Synchronous active-high reset; highest priority. |
| `start` | `in` | leave blank (scalar) | 1 | Request a frame; accepted only when busy was zero before the edge. |
| `data` | `in` | `7:0` | 8 | Captured payload at accepted start. |
| `tx` | `out` | leave blank (scalar) | 1 | Idle high serial line. |
| `busy` | `out` | leave blank (scalar) | 1 | Frame in progress. |
| `done` | `out` | leave blank (scalar) | 1 | One-clock pulse after the stop bit. |

## Body-only SystemVerilog to copy

```systemverilog
logic [9:0] frame;
logic [3:0] tick, bit_index;
assign tx = busy ? frame[0] : 1'b1;
always_ff @(posedge clk) begin
    if (reset) begin
        frame <= '1;
        tick <= '0;
        bit_index <= '0;
        busy <= 1'b0;
        done <= 1'b0;
    end else begin
        done <= 1'b0;
        if (!busy) begin
            if (start) begin
                frame <= {1'b1, data, 1'b0};
                tick <= '0;
                bit_index <= '0;
                busy <= 1'b1;
            end
        end else if (tick == 4'd15) begin
            tick <= '0;
            if (bit_index == 4'd9) begin
                busy <= 1'b0;
                done <= 1'b1;
                frame <= '1;
            end else begin
                frame <= {1'b1, frame[9:1]};
                bit_index <= bit_index + 4'd1;
            end
        end else tick <= tick + 4'd1;
    end
end
```

## Expected document and Circuit

The saved Component has one complete explanation, exactly 7 wire
ports with the table's directions and widths, and one SystemVerilog Section
containing this body. No placeholder output tie-offs replace the supplied logic.
The leaf Circuit preview shows one Component and its physical terminals, with no
invented internal instances or internal nets. That leaf preview is read-only.
The generated module wraps these ports and this body. Its technical module name
can differ from `uart_tx`; use the generated manifest and file list to identify it.

## Manual review checkpoints

- Check the explanation, interfaces, and body together; identify contradictions.
- Check scalar ports remain scalar and vector bounds survive save and reopen.
- Inspect every terminal label and width in the leaf preview in both themes.
- Generate from the saved revision, retain the project, and run its `make lint`.
- Record reference-input lint separately from actual UI-generated project lint.
- Keep functional simulation marked **unverified**.

Return to the [catalogue](../README.md).

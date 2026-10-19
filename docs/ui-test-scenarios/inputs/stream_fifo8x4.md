# Input pack: Four-entry ready/valid byte FIFO

Definition reference: `stream_fifo8x4`. Use this readable Component name: **Four-entry ready/valid byte FIFO**.
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
Queue bytes between two ready/valid interfaces.

Requirements and implemented behavior
R1: A transfer occurs on an edge with valid AND ready. in_ready is count<4; out_valid is count>0. R2: The head is combinational and remains stable while stalled. Reset clears memory, count, and pointers. R3: A full FIFO does not accept a write on the same edge as a read; space is advertised on the following cycle.

Interface
The Ports Section defines every physical wire. Port IDs, directions, ranges, and descriptions are part of this contract. All data is unsigned unless this explanation says otherwise.

Timing and reset
All state uses rising clk edges and synchronous active-high reset. Reset has priority over the other controls. Read the requirements above for enable and transfer priorities.

Corner cases and integration assumptions
An empty FIFO does not bypass a newly arriving byte. Simultaneous accepted push/pop keeps count unchanged. A producer must hold data and valid until accepted.

Verification boundary
Review this explanation against the Ports and SystemVerilog Sections. Generate RTL from the saved Component and run the published project lint command. Lint is not functional simulation. Reference examples describe intended behavior; they are not executed test results.
```

## Complete interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `clk` | `in` | leave blank (scalar) | 1 | Rising-edge input clock. |
| `reset` | `in` | leave blank (scalar) | 1 | Synchronous active-high reset; highest priority. |
| `in_data` | `in` | `7:0` | 8 | Incoming byte. |
| `in_valid` | `in` | leave blank (scalar) | 1 | Incoming byte is valid. |
| `in_ready` | `out` | leave blank (scalar) | 1 | Space exists before the edge. |
| `out_data` | `out` | `7:0` | 8 | Current head, zero when empty. |
| `out_valid` | `out` | leave blank (scalar) | 1 | At least one queued byte. |
| `out_ready` | `in` | leave blank (scalar) | 1 | Consumer can accept the head. |

## Body-only SystemVerilog to copy

```systemverilog
logic [7:0] memory [0:3];
logic [1:0] wr_ptr, rd_ptr;
logic [2:0] count;
logic push, pop;
assign in_ready = (count < 3'd4);
assign out_valid = (count != 3'd0);
assign out_data = out_valid ? memory[rd_ptr] : 8'd0;
assign push = in_valid && in_ready;
assign pop = out_valid && out_ready;
always_ff @(posedge clk) begin
    if (reset) begin
        wr_ptr <= '0; rd_ptr <= '0; count <= '0;
        for (int i = 0; i < 4; i++) memory[i] <= '0;
    end else begin
        if (push) begin memory[wr_ptr] <= in_data; wr_ptr <= wr_ptr + 2'd1; end
        if (pop) rd_ptr <= rd_ptr + 2'd1;
        case ({push, pop})
            2'b10: count <= count + 3'd1;
            2'b01: count <= count - 3'd1;
            default: count <= count;
        endcase
    end
end
```

## Expected document and Circuit

The saved Component has one complete explanation, exactly 8 wire
ports with the table's directions and widths, and one SystemVerilog Section
containing this body. No placeholder output tie-offs replace the supplied logic.
The leaf Circuit preview shows one Component and its physical terminals, with no
invented internal instances or internal nets. That leaf preview is read-only.
The generated module wraps these ports and this body. Its technical module name
can differ from `stream_fifo8x4`; use the generated manifest and file list to identify it.

## Manual review checkpoints

- Check the explanation, interfaces, and body together; identify contradictions.
- Check scalar ports remain scalar and vector bounds survive save and reopen.
- Inspect every terminal label and width in the leaf preview in both themes.
- Generate from the saved revision, retain the project, and run its `make lint`.
- Record reference-input lint separately from actual UI-generated project lint.
- Keep functional simulation marked **unverified**.

Return to the [catalogue](../README.md).

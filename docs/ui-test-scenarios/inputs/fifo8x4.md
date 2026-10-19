# Input pack: Four-entry eight-bit synchronous FIFO

Definition reference: `fifo8x4`. Use this readable Component name: **Four-entry eight-bit synchronous FIFO**.
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
Store four eight-bit words and return accepted reads in enqueue order.

Requirements and implemented behavior
R1: rd_accept = rd_en AND NOT empty. wr_accept = wr_en AND (NOT full OR rd_accept). Acceptance uses the state before the edge. R2: An accepted read updates rd_data with the old head; an accepted write stores wr_data at the tail. R3: Count changes by writes minus reads. Reset clears count, pointers, rd_data, and memory. Reads and writes are synchronous to clk.

Interface
The Ports Section defines every physical wire. Port IDs, directions, ranges, and descriptions are part of this contract. All data is unsigned unless this explanation says otherwise.

Timing and reset
All state uses rising clk edges and synchronous active-high reset. Reset has priority over the other controls. Read the requirements above for enable and transfer priorities.

Corner cases and integration assumptions
Empty with both requests: accept only the write; rd_data holds. Full with both requests: accept both; return the old head, retain occupancy four. Full with only write: reject it. Empty with only read: reject it. A rejected operation does not move its pointer.

Verification boundary
Review this explanation against the Ports and SystemVerilog Sections. Generate RTL from the saved Component and run the published project lint command. Lint is not functional simulation. Reference examples describe intended behavior; they are not executed test results.
```

## Complete interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `clk` | `in` | leave blank (scalar) | 1 | Rising-edge input clock. |
| `reset` | `in` | leave blank (scalar) | 1 | Synchronous active-high reset; highest priority. |
| `wr_en` | `in` | leave blank (scalar) | 1 | Request an enqueue. |
| `wr_data` | `in` | `7:0` | 8 | Word to enqueue when accepted. |
| `rd_en` | `in` | leave blank (scalar) | 1 | Request a dequeue. |
| `rd_data` | `out` | `7:0` | 8 | Last accepted read word; registered, holds otherwise. |
| `full` | `out` | leave blank (scalar) | 1 | Four stored words. |
| `empty` | `out` | leave blank (scalar) | 1 | No stored words. |
| `count` | `out` | `2:0` | 3 | Occupancy from zero through four. |

## Body-only SystemVerilog to copy

```systemverilog
logic [7:0] memory [0:3];
logic [1:0] wr_ptr, rd_ptr;
logic rd_accept, wr_accept;
assign full = (count == 3'd4);
assign empty = (count == 3'd0);
assign rd_accept = rd_en && !empty;
assign wr_accept = wr_en && (!full || rd_accept);
always_ff @(posedge clk) begin
    if (reset) begin
        wr_ptr <= '0;
        rd_ptr <= '0;
        count <= '0;
        rd_data <= '0;
        for (int i = 0; i < 4; i++) memory[i] <= '0;
    end else begin
        if (wr_accept) begin
            memory[wr_ptr] <= wr_data;
            wr_ptr <= wr_ptr + 2'd1;
        end
        if (rd_accept) begin
            rd_data <= memory[rd_ptr];
            rd_ptr <= rd_ptr + 2'd1;
        end
        case ({wr_accept, rd_accept})
            2'b10: count <= count + 3'd1;
            2'b01: count <= count - 3'd1;
            default: count <= count;
        endcase
    end
end
```

## Expected document and Circuit

The saved Component has one complete explanation, exactly 9 wire
ports with the table's directions and widths, and one SystemVerilog Section
containing this body. No placeholder output tie-offs replace the supplied logic.
The leaf Circuit preview shows one Component and its physical terminals, with no
invented internal instances or internal nets. That leaf preview is read-only.
The generated module wraps these ports and this body. Its technical module name
can differ from `fifo8x4`; use the generated manifest and file list to identify it.

## Manual review checkpoints

- Check the explanation, interfaces, and body together; identify contradictions.
- Check scalar ports remain scalar and vector bounds survive save and reopen.
- Inspect every terminal label and width in the leaf preview in both themes.
- Generate from the saved revision, retain the project, and run its `make lint`.
- Record reference-input lint separately from actual UI-generated project lint.
- Keep functional simulation marked **unverified**.

Return to the [catalogue](../README.md).

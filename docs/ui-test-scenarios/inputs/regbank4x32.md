# Input pack: Four-word 32-bit byte-write register bank

Definition reference: `regbank4x32`. Use this readable Component name: **Four-word 32-bit byte-write register bank**.
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
Store four software-style words with independent byte writes and an asynchronous read port.

Requirements and implemented behavior
R1: Reset clears all four words. Otherwise, wr_en captures enabled bytes of wr_data into the selected word. R2: wr_strb[0] selects bits 7:0, through wr_strb[3] selecting bits 31:24. Unselected bytes retain their values. R3: rd_data continuously shows the selected word. On a same-address write it shows the old value before the edge and the updated value after the edge.

Interface
The Ports Section defines every physical wire. Port IDs, directions, ranges, and descriptions are part of this contract. All data is unsigned unless this explanation says otherwise.

Timing and reset
All state uses rising clk edges and synchronous active-high reset. Reset has priority over the other controls. Read the requirements above for enable and transfer priorities.

Corner cases and integration assumptions
Zero strobes make no change. Every two-bit address is legal. Writing word 2 must not alter words 0, 1, or 3. For old AABBCCDD, write data 11223344 with strobes 0101 produces AA22CC44.

Verification boundary
Review this explanation against the Ports and SystemVerilog Sections. Generate RTL from the saved Component and run the published project lint command. Lint is not functional simulation. Reference examples describe intended behavior; they are not executed test results.
```

## Complete interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `clk` | `in` | leave blank (scalar) | 1 | Rising-edge input clock. |
| `reset` | `in` | leave blank (scalar) | 1 | Synchronous active-high reset; highest priority. |
| `wr_en` | `in` | leave blank (scalar) | 1 | Commit the selected byte writes on the rising edge. |
| `wr_addr` | `in` | `1:0` | 2 | Write word index 0..3. |
| `wr_data` | `in` | `31:0` | 32 | Write word. |
| `wr_strb` | `in` | `3:0` | 4 | Bit i enables byte [8*i+7:8*i]. |
| `rd_addr` | `in` | `1:0` | 2 | Asynchronous read word index. |
| `rd_data` | `out` | `31:0` | 32 | Current selected word. |

## Body-only SystemVerilog to copy

```systemverilog
logic [31:0] words [0:3];
assign rd_data = words[rd_addr];
always_ff @(posedge clk) begin
    if (reset) begin
        for (int i = 0; i < 4; i++) words[i] <= '0;
    end else if (wr_en) begin
        for (int b = 0; b < 4; b++)
            if (wr_strb[b]) words[wr_addr][8*b +: 8] <= wr_data[8*b +: 8];
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
can differ from `regbank4x32`; use the generated manifest and file list to identify it.

## Manual review checkpoints

- Check the explanation, interfaces, and body together; identify contradictions.
- Check scalar ports remain scalar and vector bounds survive save and reopen.
- Inspect every terminal label and width in the leaf preview in both themes.
- Generate from the saved revision, retain the project, and run its `make lint`.
- Record reference-input lint separately from actual UI-generated project lint.
- Keep functional simulation marked **unverified**.

Return to the [catalogue](../README.md).

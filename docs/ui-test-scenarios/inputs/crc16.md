# Input pack: CRC-16 byte accumulator

Definition reference: `crc16`. Use this readable Component name: **CRC-16 byte accumulator**.
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
Accumulate a CRC-16/CCITT-FALSE over accepted bytes.

Requirements and implemented behavior
R1: Polynomial is 0x1021 (implicit x^16 term), initial value 0xFFFF, input reflection false, output reflection false, and final XOR 0x0000. R2: Process each accepted byte most-significant bit first. R3: Reset or clear restores 0xFFFF; otherwise valid updates the CRC and idle holds it. No byte is accepted while clear=1.

Interface
The Ports Section defines every physical wire. Port IDs, directions, ranges, and descriptions are part of this contract. All data is unsigned unless this explanation says otherwise.

Timing and reset
All state uses rising clk edges and synchronous active-high reset. Reset has priority over the other controls. Read the requirements above for enable and transfer priorities.

Corner cases and integration assumptions
The empty stream leaves FFFF. ASCII bytes for 123456789 produce 29B1. These are reference examples, not evidence of executed simulation. CRC values identify accidental changes; this block does not provide authentication.

Verification boundary
Review this explanation against the Ports and SystemVerilog Sections. Generate RTL from the saved Component and run the published project lint command. Lint is not functional simulation. Reference examples describe intended behavior; they are not executed test results.
```

## Complete interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `clk` | `in` | leave blank (scalar) | 1 | Rising-edge input clock. |
| `reset` | `in` | leave blank (scalar) | 1 | Synchronous active-high reset; highest priority. |
| `clear` | `in` | leave blank (scalar) | 1 | Re-seed the CRC; takes priority over valid. |
| `valid` | `in` | leave blank (scalar) | 1 | Accept this byte on the edge. |
| `data` | `in` | `7:0` | 8 | Byte processed bit 7 first. |
| `crc` | `out` | `15:0` | 16 | Current accumulator; no final XOR. |

## Body-only SystemVerilog to copy

```systemverilog
function automatic logic [15:0] next_crc(input logic [15:0] current, input logic [7:0] byte_data);
    logic [15:0] work;
    begin
        work = current;
        for (int i = 7; i >= 0; i--) begin
            if (work[15] ^ byte_data[i]) work = {work[14:0], 1'b0} ^ 16'h1021;
            else work = {work[14:0], 1'b0};
        end
        next_crc = work;
    end
endfunction
always_ff @(posedge clk) begin
    if (reset || clear) crc <= 16'hFFFF;
    else if (valid) crc <= next_crc(crc, data);
end
```

## Expected document and Circuit

The saved Component has one complete explanation, exactly 6 wire
ports with the table's directions and widths, and one SystemVerilog Section
containing this body. No placeholder output tie-offs replace the supplied logic.
The leaf Circuit preview shows one Component and its physical terminals, with no
invented internal instances or internal nets. That leaf preview is read-only.
The generated module wraps these ports and this body. Its technical module name
can differ from `crc16`; use the generated manifest and file list to identify it.

## Manual review checkpoints

- Check the explanation, interfaces, and body together; identify contradictions.
- Check scalar ports remain scalar and vector bounds survive save and reopen.
- Inspect every terminal label and width in the leaf preview in both themes.
- Generate from the saved revision, retain the project, and run its `make lint`.
- Record reference-input lint separately from actual UI-generated project lint.
- Keep functional simulation marked **unverified**.

Return to the [catalogue](../README.md).

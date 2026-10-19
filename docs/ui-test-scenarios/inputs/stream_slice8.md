# Input pack: One-entry ready/valid byte register

Definition reference: `stream_slice8`. Use this readable Component name: **One-entry ready/valid byte register**.
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
Provide one byte of elastic output storage.

Requirements and implemented behavior
R1: in_ready = NOT out_valid OR out_ready. When in_ready, capture in_valid and capture data only if in_valid. R2: Occupied and stalled means hold data and valid. Reset clears data and valid. An accepted replacement can occur on the same edge as a drain.

Interface
The Ports Section defines every physical wire. Port IDs, directions, ranges, and descriptions are part of this contract. All data is unsigned unless this explanation says otherwise.

Timing and reset
All state uses rising clk edges and synchronous active-high reset. Reset has priority over the other controls. Read the requirements above for enable and transfer priorities.

Corner cases and integration assumptions
With no replacement after a drain, valid becomes zero and the old data bits can remain; data is meaningful only when valid=1.

Verification boundary
Review this explanation against the Ports and SystemVerilog Sections. Generate RTL from the saved Component and run the published project lint command. Lint is not functional simulation. Reference examples describe intended behavior; they are not executed test results.
```

## Complete interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `clk` | `in` | leave blank (scalar) | 1 | Rising-edge input clock. |
| `reset` | `in` | leave blank (scalar) | 1 | Synchronous active-high reset; highest priority. |
| `in_data` | `in` | `7:0` | 8 | Byte to capture. |
| `in_valid` | `in` | leave blank (scalar) | 1 | Valid input byte. |
| `in_ready` | `out` | leave blank (scalar) | 1 | Empty or draining on this edge. |
| `out_data` | `out` | `7:0` | 8 | Stored byte. |
| `out_valid` | `out` | leave blank (scalar) | 1 | Stored byte is valid. |
| `out_ready` | `in` | leave blank (scalar) | 1 | Consumer accepts the stored byte. |

## Body-only SystemVerilog to copy

```systemverilog
assign in_ready = !out_valid || out_ready;
always_ff @(posedge clk) begin
    if (reset) begin out_data <= '0; out_valid <= 1'b0; end
    else if (in_ready) begin
        out_valid <= in_valid;
        if (in_valid) out_data <= in_data;
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
can differ from `stream_slice8`; use the generated manifest and file list to identify it.

## Manual review checkpoints

- Check the explanation, interfaces, and body together; identify contradictions.
- Check scalar ports remain scalar and vector bounds survive save and reopen.
- Inspect every terminal label and width in the leaf preview in both themes.
- Generate from the saved revision, retain the project, and run its `make lint`.
- Record reference-input lint separately from actual UI-generated project lint.
- Keep functional simulation marked **unverified**.

Return to the [catalogue](../README.md).

# Input pack: 4-input 16-bit selector

Definition reference: `mux16x4`. Use this readable Component name: **4-input 16-bit selector**.
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
Select one of 4 words without stored state.

Requirements and implemented behavior
R1: y equals dN when sel=N. Selection is combinational, with no added latency, clock, or reset.

Interface
The Ports Section defines every physical wire. Port IDs, directions, ranges, and descriptions are part of this contract. All data is unsigned unless this explanation says otherwise.

Timing and reset
This is a combinational Component. It has no clock, reset, or state.

Corner cases and integration assumptions
All binary selector values are covered. The default branch provides a defined zero result for a non-binary selector in four-state tools.

Verification boundary
Review this explanation against the Ports and SystemVerilog Sections. Generate RTL from the saved Component and run the published project lint command. Lint is not functional simulation. Reference examples describe intended behavior; they are not executed test results.
```

## Complete interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `d0` | `in` | `15:0` | 16 | Input selected when sel=0. |
| `d1` | `in` | `15:0` | 16 | Input selected when sel=1. |
| `d2` | `in` | `15:0` | 16 | Input selected when sel=2. |
| `d3` | `in` | `15:0` | 16 | Input selected when sel=3. |
| `sel` | `in` | `1:0` | 2 | Unsigned input selector. |
| `y` | `out` | `15:0` | 16 | Selected input word. |

## Body-only SystemVerilog to copy

```systemverilog
always_comb begin
    case (sel)
        2'd0: y = d0;
        2'd1: y = d1;
        2'd2: y = d2;
        2'd3: y = d3;
        default: y = '0;
    endcase
end
```

## Expected document and Circuit

The saved Component has one complete explanation, exactly 6 wire
ports with the table's directions and widths, and one SystemVerilog Section
containing this body. No placeholder output tie-offs replace the supplied logic.
The leaf Circuit preview shows one Component and its physical terminals, with no
invented internal instances or internal nets. That leaf preview is read-only.
The generated module wraps these ports and this body. Its technical module name
can differ from `mux16x4`; use the generated manifest and file list to identify it.

## Manual review checkpoints

- Check the explanation, interfaces, and body together; identify contradictions.
- Check scalar ports remain scalar and vector bounds survive save and reopen.
- Inspect every terminal label and width in the leaf preview in both themes.
- Generate from the saved revision, retain the project, and run its `make lint`.
- Record reference-input lint separately from actual UI-generated project lint.
- Keep functional simulation marked **unverified**.

Return to the [catalogue](../README.md).

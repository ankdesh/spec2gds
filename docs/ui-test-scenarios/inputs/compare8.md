# Input pack: Unsigned eight-bit threshold comparator

Definition reference: `compare8`. Use this readable Component name: **Unsigned eight-bit threshold comparator**.
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
Compare one sensor reading against a shared threshold.

Requirements and implemented behavior
R1: alarm = reading > threshold, with unsigned eight-bit operands and no clock.

Interface
The Ports Section defines every physical wire. Port IDs, directions, ranges, and descriptions are part of this contract. All data is unsigned unless this explanation says otherwise.

Timing and reset
This is a combinational Component. It has no clock, reset, or state.

Corner cases and integration assumptions
Equality does not raise alarm. Reading 255, threshold 254 raises alarm. Threshold 255 never raises alarm.

Verification boundary
Review this explanation against the Ports and SystemVerilog Sections. Generate RTL from the saved Component and run the published project lint command. Lint is not functional simulation. Reference examples describe intended behavior; they are not executed test results.
```

## Complete interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `reading` | `in` | `7:0` | 8 | Unsigned sensor value. |
| `threshold` | `in` | `7:0` | 8 | Shared unsigned threshold. |
| `alarm` | `out` | leave blank (scalar) | 1 | One when reading is strictly greater than threshold. |

## Body-only SystemVerilog to copy

```systemverilog
assign alarm = (reading > threshold);
```

## Expected document and Circuit

The saved Component has one complete explanation, exactly 3 wire
ports with the table's directions and widths, and one SystemVerilog Section
containing this body. No placeholder output tie-offs replace the supplied logic.
The leaf Circuit preview shows one Component and its physical terminals, with no
invented internal instances or internal nets. That leaf preview is read-only.
The generated module wraps these ports and this body. Its technical module name
can differ from `compare8`; use the generated manifest and file list to identify it.

## Manual review checkpoints

- Check the explanation, interfaces, and body together; identify contradictions.
- Check scalar ports remain scalar and vector bounds survive save and reopen.
- Inspect every terminal label and width in the leaf preview in both themes.
- Generate from the saved revision, retain the project, and run its `make lint`.
- Record reference-input lint separately from actual UI-generated project lint.
- Keep functional simulation marked **unverified**.

Return to the [catalogue](../README.md).

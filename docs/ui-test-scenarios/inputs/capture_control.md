# Input pack: SPI capture admission control

Definition reference: `capture_control`. Use this readable Component name: **SPI capture admission control**.
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
Admit SPI requests only when a result slot is available and the previous result is not being handed off.

Requirements and implemented behavior
R1: start = request AND NOT(busy OR full OR done). rejected = request AND (busy OR full OR done). R2: wr_en = done AND NOT full; wr_data = rx_data. All outputs are combinational. The one-cycle done guard prevents a second transfer from reserving the last slot before the pending FIFO write.

Interface
The Ports Section defines every physical wire. Port IDs, directions, ranges, and descriptions are part of this contract. All data is unsigned unless this explanation says otherwise.

Timing and reset
This is a combinational Component. It has no clock, reset, or state.

Corner cases and integration assumptions
Requests are pulses and are not queued. Rejected requests must be retried by the external user. Only the SPI engine writes the result FIFO; no competing writer is permitted.

Verification boundary
Review this explanation against the Ports and SystemVerilog Sections. Generate RTL from the saved Component and run the published project lint command. Lint is not functional simulation. Reference examples describe intended behavior; they are not executed test results.
```

## Complete interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `request` | `in` | leave blank (scalar) | 1 | One-clock capture request. |
| `busy` | `in` | leave blank (scalar) | 1 | SPI engine is active. |
| `full` | `in` | leave blank (scalar) | 1 | Result FIFO cannot accept another byte. |
| `done` | `in` | leave blank (scalar) | 1 | SPI completion pulse; a FIFO handoff is pending. |
| `rx_data` | `in` | `7:0` | 8 | Completed SPI byte. |
| `start` | `out` | leave blank (scalar) | 1 | Admitted SPI start. |
| `wr_en` | `out` | leave blank (scalar) | 1 | Write a completed byte when space exists. |
| `wr_data` | `out` | `7:0` | 8 | Completed byte routed to FIFO. |
| `rejected` | `out` | leave blank (scalar) | 1 | Request denied due to busy, full, or handoff. |

## Body-only SystemVerilog to copy

```systemverilog
assign start = request && !(busy || full || done);
assign rejected = request && (busy || full || done);
assign wr_en = done && !full;
assign wr_data = rx_data;
```

## Expected document and Circuit

The saved Component has one complete explanation, exactly 9 wire
ports with the table's directions and widths, and one SystemVerilog Section
containing this body. No placeholder output tie-offs replace the supplied logic.
The leaf Circuit preview shows one Component and its physical terminals, with no
invented internal instances or internal nets. That leaf preview is read-only.
The generated module wraps these ports and this body. Its technical module name
can differ from `capture_control`; use the generated manifest and file list to identify it.

## Manual review checkpoints

- Check the explanation, interfaces, and body together; identify contradictions.
- Check scalar ports remain scalar and vector bounds survive save and reopen.
- Inspect every terminal label and width in the leaf preview in both themes.
- Generate from the saved revision, retain the project, and run its `make lint`.
- Record reference-input lint separately from actual UI-generated project lint.
- Keep functional simulation marked **unverified**.

Return to the [catalogue](../README.md).

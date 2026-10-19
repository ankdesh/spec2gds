# Input pack: Programmable 16-bit periodic timer

Definition reference: `timer16`. Use this readable Component name: **Programmable 16-bit periodic timer**.
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
Issue a periodic interrupt after a configured number of enabled clock edges.

Requirements and implemented behavior
R1: Priority is reset, then load, then enabled counting. Reset clears the stored period, count, and irq. Load captures period_in into the period register and count and suppresses irq. R2: Each later enabled edge decrements count when count>1. When count=1, pulse irq and reload the stored period. R3: period=0 disables expiry. irq defaults to zero on every edge, including disabled edges; count holds while disabled.

Interface
The Ports Section defines every physical wire. Port IDs, directions, ranges, and descriptions are part of this contract. All data is unsigned unless this explanation says otherwise.

Timing and reset
All state uses rising clk edges and synchronous active-high reset. Reset has priority over the other controls. Read the requirements above for enable and transfer priorities.

Corner cases and integration assumptions
Period 1 pulses on every enabled edge after load. Period 3 first expires on the third enabled edge after load. A new load replaces an unfinished interval. Load works even when enable=0. Changing period_in without load has no effect.

Verification boundary
Review this explanation against the Ports and SystemVerilog Sections. Generate RTL from the saved Component and run the published project lint command. Lint is not functional simulation. Reference examples describe intended behavior; they are not executed test results.
```

## Complete interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `clk` | `in` | leave blank (scalar) | 1 | Rising-edge input clock. |
| `reset` | `in` | leave blank (scalar) | 1 | Synchronous active-high reset; highest priority. |
| `load` | `in` | leave blank (scalar) | 1 | Load period_in, restart the interval, and clear irq. |
| `enable` | `in` | leave blank (scalar) | 1 | Advance the timer when one. |
| `period_in` | `in` | `15:0` | 16 | Period to capture on load; zero disables expiry. |
| `count` | `out` | `15:0` | 16 | Remaining enabled edges in the current interval. |
| `irq` | `out` | leave blank (scalar) | 1 | One input-clock-cycle pulse on expiry. |

## Body-only SystemVerilog to copy

```systemverilog
logic [15:0] period;
always_ff @(posedge clk) begin
    if (reset) begin
        period <= '0;
        count <= '0;
        irq <= 1'b0;
    end else begin
        irq <= 1'b0;
        if (load) begin
            period <= period_in;
            count <= period_in;
        end else if (enable && (period != 16'd0)) begin
            if (count == 16'd1) begin
                count <= period;
                irq <= 1'b1;
            end else if (count != 16'd0) begin
                count <= count - 16'd1;
            end
        end
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
can differ from `timer16`; use the generated manifest and file list to identify it.

## Manual review checkpoints

- Check the explanation, interfaces, and body together; identify contradictions.
- Check scalar ports remain scalar and vector bounds survive save and reopen.
- Inspect every terminal label and width in the leaf preview in both themes.
- Generate from the saved revision, retain the project, and run its `make lint`.
- Record reference-input lint separately from actual UI-generated project lint.
- Keep functional simulation marked **unverified**.

Return to the [catalogue](../README.md).

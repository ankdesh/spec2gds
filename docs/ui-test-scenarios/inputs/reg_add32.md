# Input pack: Enabled registered 32-bit adder

Definition reference: `reg_add32`. Use this readable Component name: **Enabled registered 32-bit adder**.
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
Produce a registered unsigned addition result with a clear reset and enable policy.

Requirements and implemented behavior
R1: On a rising clock edge with reset=1, sum and cout become zero, regardless of enable. R2: Otherwise, when enable=1, capture the explicitly 33-bit a+b+cin result. R3: When enable=0, retain both outputs. Latency is one enabled capture edge; this block contains one register stage.

Interface
The Ports Section defines every physical wire. Port IDs, directions, ranges, and descriptions are part of this contract. All data is unsigned unless this explanation says otherwise.

Timing and reset
All state uses rising clk edges and synchronous active-high reset. Reset has priority over the other controls. Read the requirements above for enable and transfer priorities.

Corner cases and integration assumptions
Input changes between edges do not update outputs. Reset is synchronous, not asynchronous. Reset and enable together clear the result. Carry follows unsigned arithmetic and must be registered with sum.

Verification boundary
Review this explanation against the Ports and SystemVerilog Sections. Generate RTL from the saved Component and run the published project lint command. Lint is not functional simulation. Reference examples describe intended behavior; they are not executed test results.
```

## Complete interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `clk` | `in` | leave blank (scalar) | 1 | Rising-edge input clock. |
| `reset` | `in` | leave blank (scalar) | 1 | Synchronous active-high reset; highest priority. |
| `enable` | `in` | leave blank (scalar) | 1 | Advance the output registers when one. |
| `a` | `in` | `31:0` | 32 | Unsigned operand sampled on an enabled edge. |
| `b` | `in` | `31:0` | 32 | Second sampled unsigned operand. |
| `cin` | `in` | leave blank (scalar) | 1 | Sampled carry input. |
| `sum` | `out` | `31:0` | 32 | Registered low result bits. |
| `cout` | `out` | leave blank (scalar) | 1 | Registered carry bit. |

## Body-only SystemVerilog to copy

```systemverilog
logic [32:0] total;
assign total = {1'b0, a} + {1'b0, b} + {32'b0, cin};
always_ff @(posedge clk) begin
    if (reset) begin
        sum <= '0;
        cout <= 1'b0;
    end else if (enable) begin
        sum <= total[31:0];
        cout <= total[32];
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
can differ from `reg_add32`; use the generated manifest and file list to identify it.

## Manual review checkpoints

- Check the explanation, interfaces, and body together; identify contradictions.
- Check scalar ports remain scalar and vector bounds survive save and reopen.
- Inspect every terminal label and width in the leaf preview in both themes.
- Generate from the saved revision, retain the project, and run its `make lint`.
- Record reference-input lint separately from actual UI-generated project lint.
- Keep functional simulation marked **unverified**.

Return to the [catalogue](../README.md).

# Input pack: Four-request round-robin arbiter

Definition reference: `rr4`. Use this readable Component name: **Four-request round-robin arbiter**.
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
Choose one of four requesting clients with rotating priority after each accepted grant.

Requirements and implemented behavior
R1: The priority pointer resets to client 0. Search pointer, pointer+1, pointer+2, pointer+3 modulo four. R2: grant and index are combinational; valid reports a request. With no requests, all outputs are zero. R3: Advance the pointer to index+1 only on an edge with accept AND valid. Otherwise hold priority.

Interface
The Ports Section defines every physical wire. Port IDs, directions, ranges, and descriptions are part of this contract. All data is unsigned unless this explanation says otherwise.

Timing and reset
All state uses rising clk edges and synchronous active-high reset. Reset has priority over the other controls. Read the requirements above for enable and transfer priorities.

Corner cases and integration assumptions
When all requests stay high and each grant is accepted, indices are 0,1,2,3,0. Without accept the pointer holds, but a change in request may change the combinational grant. This arbiter alone does not lock a stalled ready/valid transfer. Fairness assumes continued requests and accepted grants.

Verification boundary
Review this explanation against the Ports and SystemVerilog Sections. Generate RTL from the saved Component and run the published project lint command. Lint is not functional simulation. Reference examples describe intended behavior; they are not executed test results.
```

## Complete interface

| Port ID | Direction | Range to enter | Bits | Description |
| --- | --- | --- | ---: | --- |
| `clk` | `in` | leave blank (scalar) | 1 | Rising-edge input clock. |
| `reset` | `in` | leave blank (scalar) | 1 | Synchronous active-high reset; highest priority. |
| `request` | `in` | `3:0` | 4 | One request bit per client. |
| `accept` | `in` | leave blank (scalar) | 1 | Accept the current valid grant. |
| `grant` | `out` | `3:0` | 4 | One-hot grant or zero when idle. |
| `index` | `out` | `1:0` | 2 | Granted client index; zero when idle. |
| `valid` | `out` | leave blank (scalar) | 1 | At least one request is asserted. |

## Body-only SystemVerilog to copy

```systemverilog
logic [1:0] pointer;
always_comb begin
    grant = '0;
    index = '0;
    valid = 1'b0;
    for (int k = 0; k < 4; k++) begin
        logic [1:0] slot;
        slot = pointer + 2'(k);
        if (!valid && request[slot]) begin
            grant[slot] = 1'b1;
            index = slot;
            valid = 1'b1;
        end
    end
end
always_ff @(posedge clk) begin
    if (reset) pointer <= '0;
    else if (accept && valid) pointer <= index + 2'd1;
end
```

## Expected document and Circuit

The saved Component has one complete explanation, exactly 7 wire
ports with the table's directions and widths, and one SystemVerilog Section
containing this body. No placeholder output tie-offs replace the supplied logic.
The leaf Circuit preview shows one Component and its physical terminals, with no
invented internal instances or internal nets. That leaf preview is read-only.
The generated module wraps these ports and this body. Its technical module name
can differ from `rr4`; use the generated manifest and file list to identify it.

## Manual review checkpoints

- Check the explanation, interfaces, and body together; identify contradictions.
- Check scalar ports remain scalar and vector bounds survive save and reopen.
- Inspect every terminal label and width in the leaf preview in both themes.
- Generate from the saved revision, retain the project, and run its `make lint`.
- Record reference-input lint separately from actual UI-generated project lint.
- Keep functional simulation marked **unverified**.

Return to the [catalogue](../README.md).

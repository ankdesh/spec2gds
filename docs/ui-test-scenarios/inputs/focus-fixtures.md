# Canonical focused-check inputs

These inputs support the 40 focused cases intended for later Playwright
implementation. They are not scored dependencies on the complete journeys.
Prepare a fresh source per case; never share a mutable binding between cases.
Future Playwright may seed prerequisites through existing public service fixtures.
It must perform the action being checked through the browser and inspect the
real service/saved result where relevant. Do not mock a successful product write.

## F-A: arithmetic Spec

Title: **Focus authoring A**. Path: `CASE-DIR/focus_a.spec`.
Create one Component from the complete [add32 input](add32.md), including its
explanation, five ports, and exact body. There are no Designs or instances.
Record document ID, Component ID, and saved source revision when exposed.

## F-B: separate counter Spec

Title: **Focus authoring B**. Path: `CASE-DIR/focus_b.spec`.
Create one Component from the complete [counter8 input](counter8.md). There are
no Designs. Its explanation, ports, and body must be distinguishable from F-A.

## F-CD: source-bound lane Circuit

Use the complete [lanes4x8 input](lanes4x8.md): containing Component, internal
Design relation, one reg8 definition, four instances, fourteen named nets, and
the exact containing interface. No placeholder leaf bodies are allowed.
For future deterministic layout setup, use grid 20; place lane nodes in readable
rows with clear gaps, and retain the actual geometries as the baseline.
Use ordinary direct connections, with no route locks or cycle markers unless
the individual case requests them. This fixture's creation is setup, not the
browser behavior under assessment.

## F-CD-OPEN: one missing connection

Clone F-CD into the case's isolated source and remove only the net `input_0`
from setup. All other thirteen nets stay as documented. The intentional open
sink is `u_lane0.din`; its required driver is `top.din[7:0]`. Do not pre-create
the connection using setup code in a connection-authoring case.

## Standalone Status buffer fixture

One local definition named **Status buffer**, definition reference `status_buffer`,
has terminals `input` (input, scalar) and `output` (output, scalar). Its first
instance is `status_buffer`; the two-instance version also has `status_buffer_2`.
They share one definition and initially have no nets. Use non-overlapping grid
placements and record them. These interface-only local placeholders make no
functional RTL claim. Obtain portable files through the UI during execution.

## Wire range fixture descriptions

| Port ID | Direction | Range | Description |
| --- | --- | --- | --- |
| flag | in | scalar, leave blank | Scalar control flag. |
| data | in | 31:0 | Thirty-two-bit unsigned input. |
| result | out | 31:0 | Thirty-two-bit observation output. |
| indexed | in | 4:1 | Four-bit input retaining nonzero bounds. |
| ascending | out | 0:3 | Four-bit output retaining ascending bounds. |

This fixture intentionally has no SV Section. Its range semantics are the
observable result; do not claim an implemented hardware function.

## Parameterized pass-through input

Name: **Parameterized pass-through**. Explanation to copy:

```text
Purpose
Pass an unsigned word to the output without storage.

Requirements
The stored parameter N has declaration type int unsigned and initial default 13.
It must be a positive integer. Ports a and y each retain the source range N-1:0.
The output continuously equals the input. There is no clock or reset.

Revision
For the focused check, change N to 5 through the UI and keep the symbolic source
ranges. The resolved width must change from 13 to 5. No data conversion is added.

Verification boundary
Generate the saved parameter declaration, port expressions, and body together.
Run the published project lint. Functional simulation remains unverified.
```

| Declaration | Initial value | Final value |
| --- | --- | --- |
| parameter N, type int unsigned | 13 | 5 |

| Port ID | Direction | Source range | Description |
| --- | --- | --- | --- |
| a | in | N-1:0 | Unsigned input word. |
| y | out | N-1:0 | Same word without storage. |

Body-only SystemVerilog:

```systemverilog
assign y = a;
```

Missing UI access to typed parameter declarations is an acceptance finding.
Do not substitute a fixed numeric width or use a backend write for the action.

## Long explanation to copy

Use the complete following text for a readable explanation, not as executable
hardware semantics. Structured headings, list, and table are a desired authoring
expectation. If only raw text is supported, assess whether the resulting content
is clear and retain the limitation rather than inventing a rich-text control.

```text
32-bit arithmetic unit — release review

Purpose
This Component adds two unsigned operands and an incoming carry. A reviewer
must be able to find the arithmetic, interface, timing, and integration rules
without reading the SystemVerilog body first.

Requirements
- R1: Use an explicitly 33-bit total for a + b + cin.
- R2: sum contains total bits 31:0; cout contains bit 32.
- R3: The implementation is combinational, with no clock, reset, or enable.
- R4: The saved interface and SystemVerilog body must implement the same rule.

Interface and examples
| a | b | cin | sum | cout |
| 00000000 | 00000000 | 1 | 00000001 | 0 |
| FFFFFFFF | 00000001 | 0 | 00000000 | 1 |
| FFFFFFFF | FFFFFFFF | 1 | FFFFFFFF | 1 |
All hexadecimal values are unsigned. cout is carry, not signed overflow.

Integration
Do not infer a clock or a registered stage from a diagram layout or cycle marker.
A containing Design can reuse this Component twice for a wider carry chain.
The lower carry must feed the upper cin and the operand slices must retain order.
The readable Component name can change while the stable identity remains fixed.

Saved-state review
Read all five port descriptions, inspect the full SystemVerilog body, and reopen
the saved file after editing. A failed save must preserve the last accepted source.
A stale writer must not replace a later reviewed change. These rules protect the
designer's saved content and keep Circuit and Spec representations consistent.

Verification boundary
RTL generation uses stored interfaces, explicit wiring, and the saved body.
It does not infer implemented behavior from this explanation. Lint checks the
published project; it does not establish functional simulation coverage.

End of arithmetic requirements
```

## Deliberately malformed files and snippets

Create these temporary negative inputs only in the run directory:

- `malformed.spec`: UTF-8 text `this is not a Spec archive`.
- `malformed.circuit.json`: UTF-8 text `{"invalid":true}`.
- Invalid port range: `31::0`; duplicate Port ID: `a` in F-A.
- Invalid replacement SV body: `assign sum = ;`.

Keep failed-input evidence and original saved source separate. Supplying a
negative fixture does not authorize replacing a valid source or suppressing
the expected validation failure.

Return to the [catalogue](../README.md).

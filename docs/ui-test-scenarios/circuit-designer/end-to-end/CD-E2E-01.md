# CD-E2E-01: Build a reusable hierarchical 64-bit adder

## Case contract

Authoring policy: new wire ports start at `in` and `0:0`. Clear Range when the input pack requires a scalar; preserve every supplied expression. Save source before selecting **Verify Component** or **Verify Design**. Require a current **Lint passed** result before UI RTL generation. Component verification and the generated project's `make lint` are separate checks; simulation remains unverified.

- Application emphasis: **Circuit Designer**; cross-application checks are part of the goal.
- Executor: **human or computer-use executor; do not implement this journey with Playwright**.
- Priority: release acceptance, mandatory integrity/interface/generation checks.
- Estimated effort: 90–150 minutes; planning estimate, record actual time.
- Starting state: fresh case directory and Spec; no dependence on another scored case.
- Prerequisites: [common execution guide](../../README.md#execution-guide), local services, Chromium, Verilator 5.x, GNU Make, writable temporary storage.
- Complete input: [Reusable hierarchical 64-bit adder](../../inputs/add64.md). Follow all linked child packs for composite inputs.

- Expected output: a saved `add64.spec`, complete readable content, the required Circuit view, and a UI-generated RTL project with a retained lint log.
- Verification limit: source/interface consistency and generation/lint; functional simulation remains unverified.

## Specific review checkpoint

Two instances reuse one add32 definition. Low and high operand/result slices are exact and carry_middle has one driver and one sink.

## Numbered execution

| Step | Designer action | Expected visible result | Evidence to retain |
| ---: | --- | --- | --- |
| 1 | Prepare a fresh case directory under temp/TEMP_spec2gds_acceptance/RUN-ID/CD-E2E-01 and start the documented local services. Use Chromium at 1440×900. | A clean environment and empty evidence directory are ready. Activity outputs are configured beneath the same temporary run root. | Environment/version record; no reused scored output. |
| 2 | Open Spec Editor. Use File → New Spec with title Reusable hierarchical 64-bit adder 0.1 and server-local path CASE-DIR/add64.spec. | A new empty Spec opens with the requested title/path and a recorded stable document identity. | New Spec view and actual path/identity. |
| 3 | Author every distinct reachable leaf definition from the linked input packs through Spec Editor, including its complete explanation, exact wire ports, and body. Reuse existing definitions created for this case. | Each leaf has the supplied interface and executable body, with no copied definitions for repeated instances. | Per-definition name/ID/interface/body inventory. |
| 4 | Create the containing Component with the full boundary port table and explanation. Create its internal Design, bind it as this Component implementation, and copy the supplied Design explanation. | The containing interface belongs to the intended Composite Component and its Design is the editable internal topology. If the UI cannot create this relation, record a mandatory capability failure and stop dependent steps. | Containing interface, Design relationship, or missing-capability recording. |
| 5 | Launch the containing internal Design in Circuit Designer through the Spec UI; inspect its source context and select Edit → Begin editing. | The correct writable source-bound Circuit opens and enters private draft state. Leaf preview is not used as an editable substitute. | Active Spec/Component/Design context and editing state. |
| 6 | Place u_low using the 32-bit unsigned adder definition, or retain that exact existing instance during the expansion case. | One u_low instance references the intended add32 definition. Source identity remains traceable. | Instance u_low and definition reference. |
| 7 | Place u_high using the 32-bit unsigned adder definition, or retain that exact existing instance during the expansion case. | One u_high instance references the intended add32 definition. Source identity remains traceable. | Instance u_high and definition reference. |
| 8 | Create or update net a_low: top.a[31:0] → u_low.a. | Exactly this 32-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net a_low endpoint and width inspection. |
| 9 | Create or update net a_high: top.a[63:32] → u_high.a. | Exactly this 32-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net a_high endpoint and width inspection. |
| 10 | Create or update net b_low: top.b[31:0] → u_low.b. | Exactly this 32-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net b_low endpoint and width inspection. |
| 11 | Create or update net b_high: top.b[63:32] → u_high.b. | Exactly this 32-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net b_high endpoint and width inspection. |
| 12 | Create or update net carry_in: top.cin → u_low.cin. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net carry_in endpoint and width inspection. |
| 13 | Create or update net carry_middle: u_low.cout → u_high.cin. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net carry_middle endpoint and width inspection. |
| 14 | Create or update net sum_low: u_low.sum → top.sum[31:0]. | Exactly this 32-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net sum_low endpoint and width inspection. |
| 15 | Create or update net sum_high: u_high.sum → top.sum[63:32]. | Exactly this 32-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net sum_high endpoint and width inspection. |
| 16 | Create or update net carry_out: u_high.cout → top.cout. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net carry_out endpoint and width inspection. |
| 17 | Arrange the diagram according to the input-pack layout paragraph. Check each visible label, port, route, and containing boundary. | Put u_low before u_high in reading order. Label carry_middle and show low/high slices near their endpoints. External operands enter from the left and result leaves to the right; no text covers terminals. | Whole-diagram image plus crowded-label details. |
| 18 | Route carry_middle so it can be followed from the low adder to the high adder. Inspect each half-bus slice and use the Component catalog to confirm definition reuse. | There are two instances, one reusable leaf definition, five containing ports, and nine named nets at this level. | Case-specific interaction recording and inspected graph. |
| 19 | Review the entire graph against the connection table and check the containing explanation against: Two instances reuse one add32 definition. Low and high operand/result slices are exact and carry_middle has one driver and one sink. | There are two instances, one reusable leaf definition, five containing ports, and nine named nets at this level. | Final per-level ports/instances/nets checklist and explanation. |
| 20 | Use Save to Spec. Return to Spec Editor and refresh the saved source view without replacing the authoring path with backend writes. | The saved containing interface, internal Design, instances, connections, and readable topology agree across both applications. | Saved-state result and both application views. |
| 21 | Switch to each application theme. Inspect at 1440×900 and 1024×768; also inspect Spec Editor at 560×760. Navigate to every required Section or diagram area. | All necessary names, values, controls, and messages remain reachable and readable; scrollable areas do not hide required actions. | Theme/window captures; note each overlap or clipped label. |
| 22 | Update the Spec readable title from 0.1 to 1.0 after reviewing the finished content. Save any remaining drafts and record the saved target/revision. | The final title and revision are explicit; renaming does not redirect the Spec or discard unrelated content. | Final title, path, target, and revision record. |
| 23 | In Spec Editor select the saved target Component, run Verify Component and require Lint passed for the saved revision, then Options → Generate RTL. Wait for the terminal job result and obtain the full published project through the UI. | The Activity identifies the intended saved target and publishes all required files. If complete project access is missing, record that gap; do not regenerate through a CLI. | Activity status, saved target/revision, artifacts, project manifest and file list. |
| 24 | Inspect generated ports and source. For a composite, inspect structural child instances and leaf bodies. Run make lint from that actual published project using the common guide command. | The generated interface and implementation match the saved source; make lint exits zero without unexpected diagnostics. Simulation remains unverified. | Generated-source review and exact lint command/log/exit status. |
| 25 | Close the document view, reopen the saved .spec through File → Open Spec, and reopen the target Circuit. Compare every applicable Section, interface, hierarchy, and identity. | The same final Spec and Circuit return; no saved explanation, port, logic, connection, or unrelated content is lost. | Reopened views and before/after inventory. |
| 26 | Download a portable Circuit and SVG/PNG from the saved view. Open the portable copy separately, inspect the exported images, and compare labels, routes, and overlay state. | The portable graph and images agree with the saved Circuit. Exporting does not replace the active Spec or alter topology. | Portable file, SVG, PNG, and matching canvas image. |
| 27 | Score every criterion using the scoring guide, record mandatory failures and product gaps, and leave unperformed external checks incomplete. | A complete evidence-backed result or an explicit incomplete result is recorded; a high numeric score never removes a mandatory failure. | Completed per-case record in the temporary run directory. |

## Expected final Spec, Circuit, and artifacts

The final title is **Reusable hierarchical 64-bit adder 1.0**. It contains containing Component/Design explanations, the boundary Ports Section, all child interfaces, and all leaf SystemVerilog Sections; structural parent bodies are intentionally absent.
At the target level: 5 ports, 2 instances, 9 named nets. Reachable definitions: add32, add64.
The actual readable Component name can have the explicitly requested revision;
record its stable ID before and after. All intended inputs come from the pack;
do not invent missing clock, reset, interface conversion, or behavior.

There are two instances, one reusable leaf definition, five containing ports, and nine named nets at this level.

Retain the final saved `.spec`, source/identity comparison, both-theme views,
Activity target/revision and complete project, generated source review, and the
actual generated-project lint result. For composites also retain portable,
SVG, and PNG exports. All run outputs belong under the temporary case directory.

## Weighted criteria

| Criterion ID | Observable criterion | Weight | Mandatory | Rating kind | Required evidence |
| --- | --- | ---: | --- | --- | --- |
| CD-E2E-01-C01 | Every instance, definition reuse, hierarchy level, and named net in add64's connection table is present; no required endpoint is open. The explanation and timing claims agree with this structure and its leaf behavior. | 30 | yes | 0 or 4 | Per-level instance/net inventory, connection table, and behavior-description comparison. |
| CD-E2E-01-C02 | All 5 boundary ports, slices, driver/sink directions, and clock/reset/enable mappings exactly match the input pack. | 15 | yes | 0 or 4 | Boundary/endpoint inspections with full ranges and driver counts. |
| CD-E2E-01-C03 | The containing Component and Design explanations describe purpose, operation, timing, assumptions, and this case-specific integration policy. | 10 | no | 0–4 | Saved Component and Design text. |
| CD-E2E-01-C04 | The diagram follows the pack reading order; names, widths, hierarchy, routes, and overlays remain legible in both themes. | 10 | no | 0–4 | Full diagram and zoomed difficult areas in both themes. |
| CD-E2E-01-C05 | All required authoring and revision actions can be completed through the UI without backend writes, archive edits, or replacement with flat parent logic. | 5 | yes | 0 or 4 | Action recording and explicit record of any missing capability. |
| CD-E2E-01-C06 | Save to Spec and reopen preserve the complete graph, layouts, hierarchy, recorded identities, and unrelated source members. | 15 | yes | 0 or 4 | Spec Editor/Circuit reopened comparisons and identity record. |
| CD-E2E-01-C07 | Generation from the saved containing Component retains structural hierarchy and leaf bodies, and its published project make lint exits zero without unexpected diagnostics. | 10 | yes | 0 or 4 | Saved target/revision, generated instances/file list, and lint log. |
| CD-E2E-01-C08 | Portable Circuit, SVG, and PNG exports preserve graph meaning and agree with the saved visible layout, labels, and overlay state. | 5 | yes | 0 or 4 | Reopened portable file, SVG, PNG, and matching canvas view. |

Use [scoring rules](../../SCORING.md). Objective checks use 0 or 4; qualitative
checks use the documented 0–4 anchors and evidence. Weights total 100.

### Partial-credit anchors for this case

- Explanation (C03): rating 2 if the purpose is clear but the case-specific
  integration rule is not: Two instances reuse one add32 definition. Low and high operand/result slices are exact and carry_middle has one driver and one sink. Rating 3 if all meaning is present with
  one minor cross-reference/wording issue; rating 4 if the requirements, timing,
  assumptions, and hierarchy are easy to understand together.
- Diagram (C04): the concrete target is: Put u_low before u_high in reading order. Label carry_middle and show low/high slices near their endpoints. External operands enter from the left and result leaves to the right; no text covers terminals. Rating 2 if the graph is
  correct but substantial tracing/zooming is needed to follow that organization;
  rating 3 for a minor local spacing/wrapping issue; rating 4 when every required
  signal group and hierarchy boundary is clear in both themes. Incorrect
  connectivity receives zero on its mandatory criterion, not partial diagram
  correctness credit.


## Result fields

Copy the [run template](../../RUN-TEMPLATE.md) into the run directory and fill it
for `CD-E2E-01`. Record run ID, code revision, browser/version, theme, window size,
actual Spec path, source revision if exposed, ratings for every criterion,
mandatory failures, capability gaps, evidence links, and verification limits.
Default result: **unrun**. Do not prefill a passing score from this casebook.
Functional simulation: **unverified**.

Return to the [catalogue](../../README.md).

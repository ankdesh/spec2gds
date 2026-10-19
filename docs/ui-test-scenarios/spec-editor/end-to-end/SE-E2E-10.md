# SE-E2E-10: Evolve and release a hierarchical adder Spec

## Case contract

- Application emphasis: **Spec Editor**; cross-application checks are part of the goal.
- Executor: **human or computer-use executor; do not implement this journey with Playwright**.
- Priority: release acceptance, mandatory integrity/interface/generation checks.
- Estimated effort: 90–150 minutes; planning estimate, record actual time.
- Starting state: fresh case directory and Spec; no dependence on another scored case.
- Prerequisites: [common execution guide](../../README.md#execution-guide), local services, Chromium, Verilator 5.x, GNU Make, writable temporary storage.
- Complete input: [Reusable hierarchical 64-bit adder](../../inputs/add64.md). Follow all linked child packs for composite inputs.
- Additional preservation input: [Enabled eight-bit counter](../../inputs/counter8.md). Keep this unrelated Component intact.
- Expected output: a saved `add64.spec`, complete readable content, the required Circuit view, and a UI-generated RTL project with a retained lint log.
- Verification limit: source/interface consistency and generation/lint; functional simulation remains unverified.

## Specific review checkpoint

The existing add32 Component keeps its interface, body, and stable identity. A new containing add64 Component uses two instances of that same definition and an explicit carry chain.

## Numbered execution

| Step | Designer action | Expected visible result | Evidence to retain |
| ---: | --- | --- | --- |
| 1 | Prepare a fresh case directory under /tmp/spec2gds-acceptance/RUN-ID/SE-E2E-10 and start the documented local services. Use Chromium at 1440×900. | A clean environment and empty evidence directory are ready. Activity outputs are configured beneath the same temporary run root. | Environment/version record; no reused scored output. |
| 2 | Open Spec Editor. Use File → New Spec with title Reusable hierarchical 64-bit adder 0.1 and server-local path CASE-DIR/add64.spec. | A new empty Spec opens with the requested title/path and a recorded stable document identity. | New Spec view and actual path/identity. |
| 3 | Create the original add32 Component from its input pack and an unrelated counter8 Component from its input pack. Save the first version and record both IDs, complete explanations, interfaces, and bodies before extending this same Spec. | The initial saved Spec has the two original Components. Their identities and source content provide the preservation baseline for the extension. | Initial-version identity and full content record. |
| 4 | Author every distinct reachable leaf definition from the linked input packs through Spec Editor, including its complete explanation, exact wire ports, and body. Reuse existing definitions created for this case. | Each leaf has the supplied interface and executable body, with no copied definitions for repeated instances. | Per-definition name/ID/interface/body inventory. |
| 5 | Create the containing Component with the full boundary port table and explanation. Create its internal Design, bind it as this Component implementation, and copy the supplied Design explanation. | The containing interface belongs to the intended Composite Component and its Design is the editable internal topology. If the UI cannot create this relation, record a mandatory capability failure and stop dependent steps. | Containing interface, Design relationship, or missing-capability recording. |
| 6 | Launch the containing internal Design in Circuit Designer through the Spec UI; inspect its source context and select Edit → Begin editing. | The correct writable source-bound Circuit opens and enters private draft state. Leaf preview is not used as an editable substitute. | Active Spec/Component/Design context and editing state. |
| 7 | Place u_low using the 32-bit unsigned adder definition, or retain that exact existing instance during the expansion case. | One u_low instance references the intended add32 definition. Source identity remains traceable. | Instance u_low and definition reference. |
| 8 | Place u_high using the 32-bit unsigned adder definition, or retain that exact existing instance during the expansion case. | One u_high instance references the intended add32 definition. Source identity remains traceable. | Instance u_high and definition reference. |
| 9 | Create or update net a_low: top.a[31:0] → u_low.a. | Exactly this 32-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net a_low endpoint and width inspection. |
| 10 | Create or update net a_high: top.a[63:32] → u_high.a. | Exactly this 32-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net a_high endpoint and width inspection. |
| 11 | Create or update net b_low: top.b[31:0] → u_low.b. | Exactly this 32-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net b_low endpoint and width inspection. |
| 12 | Create or update net b_high: top.b[63:32] → u_high.b. | Exactly this 32-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net b_high endpoint and width inspection. |
| 13 | Create or update net carry_in: top.cin → u_low.cin. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net carry_in endpoint and width inspection. |
| 14 | Create or update net carry_middle: u_low.cout → u_high.cin. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net carry_middle endpoint and width inspection. |
| 15 | Create or update net sum_low: u_low.sum → top.sum[31:0]. | Exactly this 32-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net sum_low endpoint and width inspection. |
| 16 | Create or update net sum_high: u_high.sum → top.sum[63:32]. | Exactly this 32-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net sum_high endpoint and width inspection. |
| 17 | Create or update net carry_out: u_high.cout → top.cout. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net carry_out endpoint and width inspection. |
| 18 | Arrange the diagram according to the input-pack layout paragraph. Check each visible label, port, route, and containing boundary. | Put u_low before u_high in reading order. Label carry_middle and show low/high slices near their endpoints. External operands enter from the left and result leaves to the right; no text covers terminals. | Whole-diagram image plus crowded-label details. |
| 19 | Review the entire graph against the connection table and check the containing explanation against: The existing add32 Component keeps its interface, body, and stable identity. A new containing add64 Component uses two instances of that same definition and an explicit carry chain. | The same Spec contains the preserved add32 and counter plus the containing add64 and its internal Design. Only add64 and its two reachable adder instances appear in its generated hierarchy. | Final per-level ports/instances/nets checklist and explanation. |
| 20 | Use Save to Spec. Return to Spec Editor and refresh the saved source view without replacing the authoring path with backend writes. | The saved containing interface, internal Design, instances, connections, and readable topology agree across both applications. | Saved-state result and both application views. |
| 21 | Switch to each application theme. Inspect at 1440×900 and 1024×768; also inspect Spec Editor at 560×760. Navigate to every required Section or diagram area. | All necessary names, values, controls, and messages remain reachable and readable; scrollable areas do not hide required actions. | Theme/window captures; note each overlap or clipped label. |
| 22 | Update the Spec readable title from 0.1 to 1.0 after reviewing the finished content. Save any remaining drafts and record the saved target/revision. | The final title and revision are explicit; renaming does not redirect the Spec or discard unrelated content. | Final title, path, target, and revision record. |
| 23 | In Spec Editor select the saved target Component, then Options → Generate RTL. Wait for the terminal job result and obtain the full published project through the UI. | The Activity identifies the intended saved target and publishes all required files. If complete project access is missing, record that gap; do not regenerate through a CLI. | Activity status, saved target/revision, artifacts, project manifest and file list. |
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

The same Spec contains the preserved add32 and counter plus the containing add64 and its internal Design. Only add64 and its two reachable adder instances appear in its generated hierarchy.

Retain the final saved `.spec`, source/identity comparison, both-theme views,
Activity target/revision and complete project, generated source review, and the
actual generated-project lint result. For composites also retain portable,
SVG, and PNG exports. All run outputs belong under the temporary case directory.

## Weighted criteria

| Criterion ID | Observable criterion | Weight | Mandatory | Rating kind | Required evidence |
| --- | --- | ---: | --- | --- | --- |
| SE-E2E-10-C01 | Explanation teaches the purpose, timing, assumptions, and corner cases of Reusable hierarchical 64-bit adder; it includes the case-specific review example. | 20 | no | 0–4 | Full explanation view and saved text. |
| SE-E2E-10-C02 | Exactly the required ports exist: a (in, 64 bit), b (in, 64 bit), cin (in, 1 bit), sum (out, 64 bit), cout (out, 1 bit). Descriptions and stored ranges agree with the input pack. | 15 | yes | 0 or 4 | Entire Ports Section before and after reopen. |
| SE-E2E-10-C03 | The existing add32 Component keeps its interface, body, and stable identity. A new containing add64 Component uses two instances of that same definition and an explicit carry chain. The explanation, interface, and saved body/wiring all agree with that reference contract; materially false or contradictory behavior claims fail this check. No functional simulation claim is made. | 15 | yes | 0 or 4 | Explanation/interface/body comparison and the specific review checkpoint. |
| SE-E2E-10-C04 | All applicable text, Ports, and SystemVerilog Sections are complete and readable. Structural parents intentionally use an internal Design instead of a body. | 10 | no | 0–4 | Section list and views containing complete content. |
| SE-E2E-10-C05 | Circuit representation shows the expected terminals, widths, hierarchy, and reading order without hidden or overlapping essential labels. | 10 | no | 0–4 | Circuit views in both themes; leaf is correctly read-only. |
| SE-E2E-10-C06 | UI-launched RTL generation uses the final saved target and publishes the complete project with the expected body or structural hierarchy. | 10 | yes | 0 or 4 | Activity result, target/revision, project file list, and generated source. |
| SE-E2E-10-C07 | The actual UI-generated project make lint exits zero with no unexpected diagnostics. Temporary reference-wrapper lint is not substituted. | 10 | yes | 0 or 4 | Exact generated-project command, exit status, and full lint log. |
| SE-E2E-10-C08 | Reopening preserves title, recorded identities, all interfaces, explanation edits, logic, and unrelated content. Only planned revisions differ. | 10 | yes | 0 or 4 | Saved/reopened comparison and identity records. |

Use [scoring rules](../../SCORING.md). Objective checks use 0 or 4; qualitative
checks use the documented 0–4 anchors and evidence. Weights total 100.

### Partial-credit anchors for this case

- Explanation (C01): rating 2 if the purpose is described but this case's rule is
  hard to find or incomplete: The existing add32 Component keeps its interface, body, and stable identity. A new containing add64 Component uses two instances of that same definition and an explicit carry chain. Rating 3 if the complete meaning is
  present with one minor grouping or wording issue; rating 4 if a new reader can
  find the purpose, exact rule, assumptions, and examples without reading code.
- Sections (C04): rating 2 if the expected Sections exist but substantial text or
  code is hard to reach/read; rating 3 for a minor local wrapping/navigation
  issue; rating 4 for complete readable Sections in the stated order. A missing
  required implementation still fails its separate mandatory criterion.
- Circuit view (C05): rating 2 if these port labels require repeated zooming or
  decoding to follow: a, b, cin, sum, cout. Rating 3 if the complete representation is clear
  except for a minor local label issue; rating 4 if all relevant labels, widths,
  and hierarchy can be read and traced in the required views.


## Result fields

Copy the [run template](../../RUN-TEMPLATE.md) into the run directory and fill it
for `SE-E2E-10`. Record run ID, code revision, browser/version, theme, window size,
actual Spec path, source revision if exposed, ratings for every criterion,
mandatory failures, capability gaps, evidence links, and verification limits.
Default result: **unrun**. Do not prefill a passing score from this casebook.
Functional simulation: **unverified**.

Return to the [catalogue](../../README.md).

# CD-E2E-08: Build an SPI capture buffer

## Case contract

Authoring policy: new wire ports start at `in` and `0:0`. Clear Range when the input pack requires a scalar; preserve every supplied expression. Save source before selecting **Verify Component** or **Verify Design**. Require a current **Lint passed** result before UI RTL generation. Component verification and the generated project's `make lint` are separate checks; simulation remains unverified.

- Application emphasis: **Circuit Designer**; cross-application checks are part of the goal.
- Executor: **human or computer-use executor; do not implement this journey with Playwright**.
- Priority: release acceptance, mandatory integrity/interface/generation checks.
- Estimated effort: 90–150 minutes; planning estimate, record actual time.
- Starting state: fresh case directory and Spec; no dependence on another scored case.
- Prerequisites: [common execution guide](../../README.md#execution-guide), local services, Chromium, Verilator 5.x, GNU Make, writable temporary storage.
- Complete input: [SPI byte capture with four-entry result buffer](../../inputs/spi_capture.md). Follow all linked child packs for composite inputs.

- Expected output: a saved `spi_capture.spec`, complete readable content, the required Circuit view, and a UI-generated RTL project with a retained lint log.
- Verification limit: source/interface consistency and generation/lint; functional simulation remains unverified.

## Specific review checkpoint

Admission uses busy, full, and done. The done handoff guard prevents reservation of a slot before the preceding result write is visible.

## Numbered execution

| Step | Designer action | Expected visible result | Evidence to retain |
| ---: | --- | --- | --- |
| 1 | Prepare a fresh case directory under /tmp/spec2gds-acceptance/RUN-ID/CD-E2E-08 and start the documented local services. Use Chromium at 1440×900. | A clean environment and empty evidence directory are ready. Activity outputs are configured beneath the same temporary run root. | Environment/version record; no reused scored output. |
| 2 | Open Spec Editor. Use File → New Spec with title SPI byte capture with four-entry result buffer 0.1 and server-local path CASE-DIR/spi_capture.spec. | A new empty Spec opens with the requested title/path and a recorded stable document identity. | New Spec view and actual path/identity. |
| 3 | Author every distinct reachable leaf definition from the linked input packs through Spec Editor, including its complete explanation, exact wire ports, and body. Reuse existing definitions created for this case. | Each leaf has the supplied interface and executable body, with no copied definitions for repeated instances. | Per-definition name/ID/interface/body inventory. |
| 4 | Create the containing Component with the full boundary port table and explanation. Create its internal Design, bind it as this Component implementation, and copy the supplied Design explanation. | The containing interface belongs to the intended Composite Component and its Design is the editable internal topology. If the UI cannot create this relation, record a mandatory capability failure and stop dependent steps. | Containing interface, Design relationship, or missing-capability recording. |
| 5 | Launch the containing internal Design in Circuit Designer through the Spec UI; inspect its source context and select Edit → Begin editing. | The correct writable source-bound Circuit opens and enters private draft state. Leaf preview is not used as an editable substitute. | Active Spec/Component/Design context and editing state. |
| 6 | Place u_spi using the Eight-bit SPI Mode 0 master definition, or retain that exact existing instance during the expansion case. | One u_spi instance references the intended spi8 definition. Source identity remains traceable. | Instance u_spi and definition reference. |
| 7 | Place u_admit using the SPI capture admission control definition, or retain that exact existing instance during the expansion case. | One u_admit instance references the intended capture_control definition. Source identity remains traceable. | Instance u_admit and definition reference. |
| 8 | Place u_fifo using the Four-entry eight-bit synchronous FIFO definition, or retain that exact existing instance during the expansion case. | One u_fifo instance references the intended fifo8x4 definition. Source identity remains traceable. | Instance u_fifo and definition reference. |
| 9 | Create or update net clock: top.clk → u_spi.clk, u_fifo.clk. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net clock endpoint and width inspection. |
| 10 | Create or update net reset: top.reset → u_spi.reset, u_fifo.reset. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net reset endpoint and width inspection. |
| 11 | Create or update net capture_request: top.request → u_admit.request. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net capture_request endpoint and width inspection. |
| 12 | Create or update net transmit_byte: top.tx_data → u_spi.tx_data. | Exactly this 8-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net transmit_byte endpoint and width inspection. |
| 13 | Create or update net serial_in: top.miso → u_spi.miso. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net serial_in endpoint and width inspection. |
| 14 | Create or update net serial_out: u_spi.mosi → top.mosi. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net serial_out endpoint and width inspection. |
| 15 | Create or update net serial_clock: u_spi.sclk → top.sclk. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net serial_clock endpoint and width inspection. |
| 16 | Create or update net serial_select: u_spi.cs_n → top.cs_n. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net serial_select endpoint and width inspection. |
| 17 | Create or update net engine_busy: u_spi.busy → u_admit.busy, top.busy. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net engine_busy endpoint and width inspection. |
| 18 | Create or update net engine_done: u_spi.done → u_admit.done. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net engine_done endpoint and width inspection. |
| 19 | Create or update net received_byte: u_spi.rx_data → u_admit.rx_data. | Exactly this 8-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net received_byte endpoint and width inspection. |
| 20 | Create or update net admitted_start: u_admit.start → u_spi.start. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net admitted_start endpoint and width inspection. |
| 21 | Create or update net write_result: u_admit.wr_en → u_fifo.wr_en. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net write_result endpoint and width inspection. |
| 22 | Create or update net buffer_byte: u_admit.wr_data → u_fifo.wr_data. | Exactly this 8-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net buffer_byte endpoint and width inspection. |
| 23 | Create or update net request_rejected: u_admit.rejected → top.rejected. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net request_rejected endpoint and width inspection. |
| 24 | Create or update net buffer_full: u_fifo.full → u_admit.full, top.full. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net buffer_full endpoint and width inspection. |
| 25 | Create or update net read_request: top.rd_en → u_fifo.rd_en. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net read_request endpoint and width inspection. |
| 26 | Create or update net read_result: u_fifo.rd_data → top.rd_data. | Exactly this 8-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net read_result endpoint and width inspection. |
| 27 | Create or update net buffer_empty: u_fifo.empty → top.empty. | Exactly this 1-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net buffer_empty endpoint and width inspection. |
| 28 | Create or update net buffer_count: u_fifo.count → top.count. | Exactly this 3-bit logical signal has one driver and the listed sinks, with the specified source/destination slices. A required unavailable slice/fan-out control is a capability failure. | Net buffer_count endpoint and width inspection. |
| 29 | Arrange the diagram according to the input-pack layout paragraph. Check each visible label, port, route, and containing boundary. | Place admission control above the SPI engine and FIFO to the right. Distinguish SPI pins from internal byte buses. Label full and done feedback so the admission condition is readable. | Whole-diagram image plus crowded-label details. |
| 30 | Trace full and done feedback into u_admit. Confirm there is one FIFO writer and one read path. Add the rejected-request retry requirement to the containing explanation. | The graph has three instances, twenty nets, and fifteen boundary ports. Buffered words and the in-flight SPI transfer remain distinct; rejection is observable. | Case-specific interaction recording and inspected graph. |
| 31 | Review the entire graph against the connection table and check the containing explanation against: Admission uses busy, full, and done. The done handoff guard prevents reservation of a slot before the preceding result write is visible. | The graph has three instances, twenty nets, and fifteen boundary ports. Buffered words and the in-flight SPI transfer remain distinct; rejection is observable. | Final per-level ports/instances/nets checklist and explanation. |
| 32 | Use Save to Spec. Return to Spec Editor and refresh the saved source view without replacing the authoring path with backend writes. | The saved containing interface, internal Design, instances, connections, and readable topology agree across both applications. | Saved-state result and both application views. |
| 33 | Switch to each application theme. Inspect at 1440×900 and 1024×768; also inspect Spec Editor at 560×760. Navigate to every required Section or diagram area. | All necessary names, values, controls, and messages remain reachable and readable; scrollable areas do not hide required actions. | Theme/window captures; note each overlap or clipped label. |
| 34 | Update the Spec readable title from 0.1 to 1.0 after reviewing the finished content. Save any remaining drafts and record the saved target/revision. | The final title and revision are explicit; renaming does not redirect the Spec or discard unrelated content. | Final title, path, target, and revision record. |
| 35 | In Spec Editor select the saved target Component, run Verify Component and require Lint passed for the saved revision, then Options → Generate RTL. Wait for the terminal job result and obtain the full published project through the UI. | The Activity identifies the intended saved target and publishes all required files. If complete project access is missing, record that gap; do not regenerate through a CLI. | Activity status, saved target/revision, artifacts, project manifest and file list. |
| 36 | Inspect generated ports and source. For a composite, inspect structural child instances and leaf bodies. Run make lint from that actual published project using the common guide command. | The generated interface and implementation match the saved source; make lint exits zero without unexpected diagnostics. Simulation remains unverified. | Generated-source review and exact lint command/log/exit status. |
| 37 | Close the document view, reopen the saved .spec through File → Open Spec, and reopen the target Circuit. Compare every applicable Section, interface, hierarchy, and identity. | The same final Spec and Circuit return; no saved explanation, port, logic, connection, or unrelated content is lost. | Reopened views and before/after inventory. |
| 38 | Download a portable Circuit and SVG/PNG from the saved view. Open the portable copy separately, inspect the exported images, and compare labels, routes, and overlay state. | The portable graph and images agree with the saved Circuit. Exporting does not replace the active Spec or alter topology. | Portable file, SVG, PNG, and matching canvas image. |
| 39 | Score every criterion using the scoring guide, record mandatory failures and product gaps, and leave unperformed external checks incomplete. | A complete evidence-backed result or an explicit incomplete result is recorded; a high numeric score never removes a mandatory failure. | Completed per-case record in the temporary run directory. |

## Expected final Spec, Circuit, and artifacts

The final title is **SPI byte capture with four-entry result buffer 1.0**. It contains containing Component/Design explanations, the boundary Ports Section, all child interfaces, and all leaf SystemVerilog Sections; structural parent bodies are intentionally absent.
At the target level: 15 ports, 3 instances, 20 named nets. Reachable definitions: capture_control, fifo8x4, spi8, spi_capture.
The actual readable Component name can have the explicitly requested revision;
record its stable ID before and after. All intended inputs come from the pack;
do not invent missing clock, reset, interface conversion, or behavior.

The graph has three instances, twenty nets, and fifteen boundary ports. Buffered words and the in-flight SPI transfer remain distinct; rejection is observable.

Retain the final saved `.spec`, source/identity comparison, both-theme views,
Activity target/revision and complete project, generated source review, and the
actual generated-project lint result. For composites also retain portable,
SVG, and PNG exports. All run outputs belong under the temporary case directory.

## Weighted criteria

| Criterion ID | Observable criterion | Weight | Mandatory | Rating kind | Required evidence |
| --- | --- | ---: | --- | --- | --- |
| CD-E2E-08-C01 | Every instance, definition reuse, hierarchy level, and named net in spi_capture's connection table is present; no required endpoint is open. The explanation and timing claims agree with this structure and its leaf behavior. | 30 | yes | 0 or 4 | Per-level instance/net inventory, connection table, and behavior-description comparison. |
| CD-E2E-08-C02 | All 15 boundary ports, slices, driver/sink directions, and clock/reset/enable mappings exactly match the input pack. | 15 | yes | 0 or 4 | Boundary/endpoint inspections with full ranges and driver counts. |
| CD-E2E-08-C03 | The containing Component and Design explanations describe purpose, operation, timing, assumptions, and this case-specific integration policy. | 10 | no | 0–4 | Saved Component and Design text. |
| CD-E2E-08-C04 | The diagram follows the pack reading order; names, widths, hierarchy, routes, and overlays remain legible in both themes. | 10 | no | 0–4 | Full diagram and zoomed difficult areas in both themes. |
| CD-E2E-08-C05 | All required authoring and revision actions can be completed through the UI without backend writes, archive edits, or replacement with flat parent logic. | 5 | yes | 0 or 4 | Action recording and explicit record of any missing capability. |
| CD-E2E-08-C06 | Save to Spec and reopen preserve the complete graph, layouts, hierarchy, recorded identities, and unrelated source members. | 15 | yes | 0 or 4 | Spec Editor/Circuit reopened comparisons and identity record. |
| CD-E2E-08-C07 | Generation from the saved containing Component retains structural hierarchy and leaf bodies, and its published project make lint exits zero without unexpected diagnostics. | 10 | yes | 0 or 4 | Saved target/revision, generated instances/file list, and lint log. |
| CD-E2E-08-C08 | Portable Circuit, SVG, and PNG exports preserve graph meaning and agree with the saved visible layout, labels, and overlay state. | 5 | yes | 0 or 4 | Reopened portable file, SVG, PNG, and matching canvas view. |

Use [scoring rules](../../SCORING.md). Objective checks use 0 or 4; qualitative
checks use the documented 0–4 anchors and evidence. Weights total 100.

### Partial-credit anchors for this case

- Explanation (C03): rating 2 if the purpose is clear but the case-specific
  integration rule is not: Admission uses busy, full, and done. The done handoff guard prevents reservation of a slot before the preceding result write is visible. Rating 3 if all meaning is present with
  one minor cross-reference/wording issue; rating 4 if the requirements, timing,
  assumptions, and hierarchy are easy to understand together.
- Diagram (C04): the concrete target is: Place admission control above the SPI engine and FIFO to the right. Distinguish SPI pins from internal byte buses. Label full and done feedback so the admission condition is readable. Rating 2 if the graph is
  correct but substantial tracing/zooming is needed to follow that organization;
  rating 3 for a minor local spacing/wrapping issue; rating 4 when every required
  signal group and hierarchy boundary is clear in both themes. Incorrect
  connectivity receives zero on its mandatory criterion, not partial diagram
  correctness credit.


## Result fields

Copy the [run template](../../RUN-TEMPLATE.md) into the run directory and fill it
for `CD-E2E-08`. Record run ID, code revision, browser/version, theme, window size,
actual Spec path, source revision if exposed, ratings for every criterion,
mandatory failures, capability gaps, evidence links, and verification limits.
Default result: **unrun**. Do not prefill a passing score from this casebook.
Functional simulation: **unverified**.

Return to the [catalogue](../../README.md).

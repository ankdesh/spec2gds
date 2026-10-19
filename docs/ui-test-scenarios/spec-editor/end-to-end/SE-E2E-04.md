# SE-E2E-04: Create a four-entry synchronous byte FIFO

## Case contract

Authoring policy: new wire ports start at `in` and `0:0`. Clear Range when the input pack requires a scalar; preserve every supplied expression. Save source before selecting **Verify Component** or **Verify Design**. Require a current **Lint passed** result before UI RTL generation. Component verification and the generated project's `make lint` are separate checks; simulation remains unverified.

- Application emphasis: **Spec Editor**; cross-application checks are part of the goal.
- Executor: **human or computer-use executor; do not implement this journey with Playwright**.
- Priority: release acceptance, mandatory integrity/interface/generation checks.
- Estimated effort: 40–90 minutes; planning estimate, record actual time.
- Starting state: fresh case directory and Spec; no dependence on another scored case.
- Prerequisites: [common execution guide](../../README.md#execution-guide), local services, Chromium, Verilator 5.x, GNU Make, writable temporary storage.
- Complete input: [Four-entry eight-bit synchronous FIFO](../../inputs/fifo8x4.md). Follow all linked child packs for composite inputs.

- Expected output: a saved `fifo8x4.spec`, complete readable content, the required Circuit view, and a UI-generated RTL project with a retained lint log.
- Verification limit: source/interface consistency and generation/lint; functional simulation remains unverified.

## Specific review checkpoint

Full plus read/write accepts both and returns the old head. Empty plus read/write accepts only the write. Registered rd_data holds when no read is accepted.

## Numbered execution

| Step | Designer action | Expected visible result | Evidence to retain |
| ---: | --- | --- | --- |
| 1 | Prepare a fresh case directory under /tmp/spec2gds-acceptance/RUN-ID/SE-E2E-04 and start the documented local services. Use Chromium at 1440×900. | A clean environment and empty evidence directory are ready. Activity outputs are configured beneath the same temporary run root. | Environment/version record; no reused scored output. |
| 2 | Open Spec Editor. Use File → New Spec with title Four-entry eight-bit synchronous FIFO 0.1 and server-local path CASE-DIR/fifo8x4.spec. | A new empty Spec opens with the requested title/path and a recorded stable document identity. | New Spec view and actual path/identity. |
| 3 | Create the Component named Four-entry eight-bit synchronous FIFO using Components → Options → Add component…; record its stable ID. | Exactly one new Component appears under the active Spec; its readable name is distinguishable from its technical ID. | Component header and ID record. |
| 4 | Use the Component Options → Edit text… action and copy the entire explanation from the input pack. | Purpose, requirements, interface, timing/reset, corner cases, and verification boundary are visible and readable. | Complete explanation, including lower paragraphs. |
| 5 | Use Options → Add wire port… to add clk, direction in, a blank scalar range, and its exact description from the input table. Save to Spec. | The clk row has 1 bit(s), direction in, and the supplied description; earlier rows remain unchanged. | Port row clk after save. |
| 6 | Use Options → Add wire port… to add reset, direction in, a blank scalar range, and its exact description from the input table. Save to Spec. | The reset row has 1 bit(s), direction in, and the supplied description; earlier rows remain unchanged. | Port row reset after save. |
| 7 | Use Options → Add wire port… to add wr_en, direction in, a blank scalar range, and its exact description from the input table. Save to Spec. | The wr_en row has 1 bit(s), direction in, and the supplied description; earlier rows remain unchanged. | Port row wr_en after save. |
| 8 | Use Options → Add wire port… to add wr_data, direction in, range 7:0, and its exact description from the input table. Save to Spec. | The wr_data row has 8 bit(s), direction in, and the supplied description; earlier rows remain unchanged. | Port row wr_data after save. |
| 9 | Use Options → Add wire port… to add rd_en, direction in, a blank scalar range, and its exact description from the input table. Save to Spec. | The rd_en row has 1 bit(s), direction in, and the supplied description; earlier rows remain unchanged. | Port row rd_en after save. |
| 10 | Use Options → Add wire port… to add rd_data, direction out, range 7:0, and its exact description from the input table. Save to Spec. | The rd_data row has 8 bit(s), direction out, and the supplied description; earlier rows remain unchanged. | Port row rd_data after save. |
| 11 | Use Options → Add wire port… to add full, direction out, a blank scalar range, and its exact description from the input table. Save to Spec. | The full row has 1 bit(s), direction out, and the supplied description; earlier rows remain unchanged. | Port row full after save. |
| 12 | Use Options → Add wire port… to add empty, direction out, a blank scalar range, and its exact description from the input table. Save to Spec. | The empty row has 1 bit(s), direction out, and the supplied description; earlier rows remain unchanged. | Port row empty after save. |
| 13 | Use Options → Add wire port… to add count, direction out, range 2:0, and its exact description from the input table. Save to Spec. | The count row has 3 bit(s), direction out, and the supplied description; earlier rows remain unchanged. | Port row count after save. |
| 14 | Use Options → Add SystemVerilog section… and paste the exact body-only code. Use Add section to save as unverified. | One complete SystemVerilog Section is saved; no module wrapper, duplicate ports, or placeholder body is introduced. | Complete saved body and validation result. |
| 15 | Read the explanation, port table, and body together against this case review checkpoint: Full plus read/write accepts both and returns the old head. Empty plus read/write accepts only the write. Registered rd_data holds when no read is accepted. | The written contract and the saved implementation agree. This is a source review, not executed functional verification. | Annotated comparison or explicit disagreement finding. |
| 16 | Add a human-readable operation table to the explanation using the four boundary rows in the input pack: full write-only reject; full read/write both accept; empty read-only reject; empty read/write write-only accept. | The explanation preserves all four rows, count limits 0..4, and the difference between requests and accepted operations. No array or pointer declaration is lost. | Before/after revision views and preserved identity/interface record. |
| 17 | Select Component Options → Preview interface and inspect the embedded read-only preview in Spec Editor. Inspect every terminal name, direction, and width. | One read-only leaf Component with exactly 9 physical ports is visible; no internal topology is invented. | Circuit overview and readable terminal details. |
| 18 | Switch to each application theme. Inspect at 1440×900 and 1024×768; also inspect Spec Editor at 560×760. Navigate to every required Section or diagram area. | All necessary names, values, controls, and messages remain reachable and readable; scrollable areas do not hide required actions. | Theme/window captures; note each overlap or clipped label. |
| 19 | Update the Spec readable title from 0.1 to 1.0 after reviewing the finished content. Save any remaining drafts and record the saved target/revision. | The final title and revision are explicit; renaming does not redirect the Spec or discard unrelated content. | Final title, path, target, and revision record. |
| 20 | In Spec Editor select the saved target Component, run Verify Component and require Lint passed for the saved revision, then Options → Generate RTL. Wait for the terminal job result and obtain the full published project through the UI. | The Activity identifies the intended saved target and publishes all required files. If complete project access is missing, record that gap; do not regenerate through a CLI. | Activity status, saved target/revision, artifacts, project manifest and file list. |
| 21 | Inspect generated ports and source. For a composite, inspect structural child instances and leaf bodies. Run make lint from that actual published project using the common guide command. | The generated interface and implementation match the saved source; make lint exits zero without unexpected diagnostics. Simulation remains unverified. | Generated-source review and exact lint command/log/exit status. |
| 22 | Close the document view, reopen the saved .spec through File → Open Spec, and reopen the target Circuit. Compare every applicable Section, interface, hierarchy, and identity. | The same final Spec and Circuit return; no saved explanation, port, logic, connection, or unrelated content is lost. | Reopened views and before/after inventory. |
| 23 | Retain the published RTL project and use the leaf preview download when available. Check exported port labels against the saved interface. | The retained artifacts identify the final saved target and do not silently use an earlier draft. | Published project and available preview export; record missing expected access. |
| 24 | Score every criterion using the scoring guide, record mandatory failures and product gaps, and leave unperformed external checks incomplete. | A complete evidence-backed result or an explicit incomplete result is recorded; a high numeric score never removes a mandatory failure. | Completed per-case record in the temporary run directory. |

## Expected final Spec, Circuit, and artifacts

The final title is **Four-entry eight-bit synchronous FIFO 1.0**. It contains one text Section, one Ports Section, and one complete body-only SystemVerilog Section.
Exactly one behavioral target Component with 9 ports; a leaf preview has no invented internal nets.
The actual readable Component name can have the explicitly requested revision;
record its stable ID before and after. All intended inputs come from the pack;
do not invent missing clock, reset, interface conversion, or behavior.

The explanation preserves all four rows, count limits 0..4, and the difference between requests and accepted operations. No array or pointer declaration is lost.

Retain the final saved `.spec`, source/identity comparison, both-theme views,
Activity target/revision and complete project, generated source review, and the
actual generated-project lint result. For composites also retain portable,
SVG, and PNG exports. All run outputs belong under the temporary case directory.

## Weighted criteria

| Criterion ID | Observable criterion | Weight | Mandatory | Rating kind | Required evidence |
| --- | --- | ---: | --- | --- | --- |
| SE-E2E-04-C01 | Explanation teaches the purpose, timing, assumptions, and corner cases of Four-entry eight-bit synchronous FIFO; it includes the case-specific review example. | 20 | no | 0–4 | Full explanation view and saved text. |
| SE-E2E-04-C02 | Exactly the required ports exist: clk (in, 1 bit), reset (in, 1 bit), wr_en (in, 1 bit), wr_data (in, 8 bit), rd_en (in, 1 bit), rd_data (out, 8 bit), full (out, 1 bit), empty (out, 1 bit), count (out, 3 bit). Descriptions and stored ranges agree with the input pack. | 15 | yes | 0 or 4 | Entire Ports Section before and after reopen. |
| SE-E2E-04-C03 | Full plus read/write accepts both and returns the old head. Empty plus read/write accepts only the write. Registered rd_data holds when no read is accepted. The explanation, interface, and saved body/wiring all agree with that reference contract; materially false or contradictory behavior claims fail this check. No functional simulation claim is made. | 15 | yes | 0 or 4 | Explanation/interface/body comparison and the specific review checkpoint. |
| SE-E2E-04-C04 | All applicable text, Ports, and SystemVerilog Sections are complete and readable. Structural parents intentionally use an internal Design instead of a body. | 10 | no | 0–4 | Section list and views containing complete content. |
| SE-E2E-04-C05 | Circuit representation shows the expected terminals, widths, hierarchy, and reading order without hidden or overlapping essential labels. | 10 | no | 0–4 | Circuit views in both themes; leaf is correctly read-only. |
| SE-E2E-04-C06 | UI-launched RTL generation uses the final saved target and publishes the complete project with the expected body or structural hierarchy. | 10 | yes | 0 or 4 | Activity result, target/revision, project file list, and generated source. |
| SE-E2E-04-C07 | The actual UI-generated project make lint exits zero with no unexpected diagnostics. Temporary reference-wrapper lint is not substituted. | 10 | yes | 0 or 4 | Exact generated-project command, exit status, and full lint log. |
| SE-E2E-04-C08 | Reopening preserves title, recorded identities, all interfaces, explanation edits, logic, and unrelated content. Only planned revisions differ. | 10 | yes | 0 or 4 | Saved/reopened comparison and identity records. |

Use [scoring rules](../../SCORING.md). Objective checks use 0 or 4; qualitative
checks use the documented 0–4 anchors and evidence. Weights total 100.

### Partial-credit anchors for this case

- Explanation (C01): rating 2 if the purpose is described but this case's rule is
  hard to find or incomplete: Full plus read/write accepts both and returns the old head. Empty plus read/write accepts only the write. Registered rd_data holds when no read is accepted. Rating 3 if the complete meaning is
  present with one minor grouping or wording issue; rating 4 if a new reader can
  find the purpose, exact rule, assumptions, and examples without reading code.
- Sections (C04): rating 2 if the expected Sections exist but substantial text or
  code is hard to reach/read; rating 3 for a minor local wrapping/navigation
  issue; rating 4 for complete readable Sections in the stated order. A missing
  required implementation still fails its separate mandatory criterion.
- Circuit view (C05): rating 2 if these port labels require repeated zooming or
  decoding to follow: clk, reset, wr_en, wr_data, rd_en, rd_data, full, empty, count. Rating 3 if the complete representation is clear
  except for a minor local label issue; rating 4 if all relevant labels, widths,
  and hierarchy can be read and traced in the required views.


## Result fields

Copy the [run template](../../RUN-TEMPLATE.md) into the run directory and fill it
for `SE-E2E-04`. Record run ID, code revision, browser/version, theme, window size,
actual Spec path, source revision if exposed, ratings for every criterion,
mandatory failures, capability gaps, evidence links, and verification limits.
Default result: **unrun**. Do not prefill a passing score from this casebook.
Functional simulation: **unverified**.

Return to the [catalogue](../../README.md).

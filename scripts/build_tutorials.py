"""Build the checked-in HTML tutorials from lesson text and the canonical example.

Run with --check to detect stale pages without changing files.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs/tutorials"
EXAMPLE = json.loads((DEST / "example.json").read_text())


def code(text):
    return f'<pre><code>{html.escape(text.strip())}</code></pre>'


def table(head, rows):
    return '<div class="table-scroll"><table><thead><tr>' + ''.join(f'<th scope="col">{html.escape(str(x))}</th>' for x in head) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{html.escape(str(x))}</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def ports(key):
    return table(["Port ID", "Direction", "Range", "Description"],
                 [[name, direction, bounds or "Leave blank (scalar)", text]
                  for name, direction, bounds, text in EXAMPLE["components"][key]["ports"]])


def photo(name, caption):
    return f'<figure data-capture="{name}"><a href="assets/{name}.jpg"><img src="assets/{name}.jpg" alt="{html.escape(caption)}" loading="lazy" decoding="async"></a><figcaption>{html.escape(caption)} Select the image to view its full size.</figcaption></figure>'


def note(title, body):
    return f'<aside class="note"><strong>{title}</strong><p>{body}</p></aside>'


def action(title, instruction, result):
    return dict(title=title, instruction=instruction, result=result)


def content(text):
    """Keep example values in the canonical example rather than copied lesson text."""
    values = {
        "adder-description": code(adder["description"]),
        "adder-sv": code(adder["systemverilog"]),
        "register-sv": code(register["systemverilog"]),
        "wrapper-description": code(wrapper["description"]),
        "register-prompt": code(register_prompt(EXAMPLE)),
        "nets": nets, "make-lint": code("make lint"),
        "verification-table": table(["Intent", "Given", "When", "Then"], [[x[1], x[2], x[3], x[4]] for x in EXAMPLE["verification"]]),
        **{f"ports:{key}": ports(key) for key in EXAMPLE["components"]},
    }
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    if "{{" in text:
        raise ValueError(f"Unknown lesson content token: {text}")
    return text


def lesson(slug, title, minutes, goal, start, needs, actions, check, practice, failure, pictures, reference, track="Core"):
    return dict(slug=slug, title=title, minutes=minutes, goal=goal, start=start,
                needs=needs, actions=actions, check=check, practice=practice,
                failure=failure, pictures=pictures, reference=reference, track=track)


adder = EXAMPLE["components"]["add16"]
register = EXAMPLE["components"]["reg16"]
wrapper = EXAMPLE["components"]["registered_adder"]
nets = table(["Net name", "Driver", "Sink", "Bits"], EXAMPLE["design"]["nets"])
from scripts.prepare_tutorials import register_prompt

CORE = [
    lesson("01-first-spec", "Create your first Spec", 5,
           "Create a Spec and reopen the same saved file.", "01", "Spec Editor and a writable folder within Spec root. No model key or compiler is required.", [
        action('Find the document controls', 'Open Spec Editor at the supplied URL. Locate File, Contents, Diagnostics, Activity, and AI Assistant. On a narrow screen, open Menu for the application menus.', 'The editor is visible. Opening a menu does not create a Spec.'),
        action('Open New Spec', 'Select <strong>File → New Spec</strong>.', 'A creation dialog asks for a Spec name and destination.'),
        action('Name the Spec', 'Enter <strong>My registered adder</strong> as the Spec name. Inspect the suggested filename.', 'The readable name and suggested .spec filename are shown separately.'),
        action('Choose a fresh destination', 'Use <strong>Change location</strong> to select your tutorial run folder within Spec root, then select <strong>Use this folder</strong>. For an exact filename, expand <strong>More options</strong> and enter a fresh <code>my-adder.spec</code> path.', 'The destination is inside your run folder and does not replace a prepared start.'),
        action('Create the file', 'Select <strong>Create Spec</strong>. Wait for the document cover.', 'The cover shows My registered adder. The Components and Designs groups are empty.'),
        action('Check where it was saved', 'Hover over the active document name to inspect its path. Record that exact path. A Spec is the logical document; its .spec file is the saved archive.', 'You can identify the saved file on the service host, which may differ from your browser computer.'),
        action('Use Contents', 'Select Overview, Components, and Designs in Contents. On a small screen, open Contents first.', 'The document moves to the selected heading; no hardware is added.'),
        action('Reopen the saved file', 'Close this editor tab, open Spec Editor again, and select <strong>File → Open Spec</strong>. Browse to the recorded folder or use More options for the exact path.', 'The file picker lists the .spec file you created.'),
        action('Confirm the saved identity', 'Select the file and <strong>Open Spec</strong>. Compare its name, path, and empty groups. Use each draft’s Save to Spec control for later changes; File has no separate Save command.', 'The same empty Spec returns from disk.'),
    ], 'The reopened Spec has the same name and path. Its Components and Designs groups are empty.',
           'Use <strong>Edit name</strong> on the cover to change the readable name. Save and reopen it. The path stays the same.',
           'If New Spec reports an existing destination, choose a fresh filename. Use Open Spec to inspect an existing file. Do not delete or replace it.',
           [("spec-new", "New Spec sets the filename and save location from one readable name."), ("spec-cover", "The saved document cover and Contents panel.")], "spec-editor.md"),
    lesson("02-component-ports", "Define a Component and its ports", 7,
           "Save a complete interface for a 16-bit adder.", "02", "Spec Editor. Continue with your empty Spec or open the prepared start.", [
        action('Create the definition', 'Open <code>02-start.spec</code> or your empty Spec. In Components select <strong>Options → Add component…</strong>. Enter <strong>16-bit modulo adder</strong>, then select <strong>Create component</strong>.', 'One reusable Component definition appears. It is not yet an instance in a Design.'),
        action('Save its explanation', 'On that Component select <strong>Options → Edit text…</strong>. Enter the explanation below and select <strong>Save to Spec</strong>. {{adder-description}}', 'The saved explanation describes unsigned addition and modulo wraparound.'),
        action('Open a port draft', 'In the Ports heading, open <strong>Options → Add port</strong>. Component Options also offers Add wire port.', 'An inline draft shows Port ID, Direction, Range, and Description.'),
        action('Enter the first input', 'Enter Port ID <code>a</code>, Direction <code>in</code>, Range <code>15-0</code>, and the first description in the table. {{ports:add16}}', 'All draft fields remain editable. The Range is intentionally invalid.'),
        action('Check format validation', 'Select <strong>Save and add another</strong>. Read the Range error.', 'Range receives focus, the draft remains, and no port is saved. A range needs explicit left:right bounds.'),
        action('Correct and save input a', 'Replace the Range with <code>15:0</code>. Select <strong>Save and add another</strong>.', 'Input a appears in the saved table. A fresh draft is ready for the next port.'),
        action('Save input b', 'Enter <code>b</code>, Direction <code>in</code>, Range <code>15:0</code>, and its description. Select <strong>Save and add another</strong>.', 'The table contains inputs a and b. The new draft is empty.'),
        action('Save output y', 'Enter <code>y</code>, Direction <code>out</code>, Range <code>15:0</code>, and its description. Select <strong>Save to Spec</strong>.', 'The draft closes. Exactly three 16-bit wire ports are saved.'),
        action('Edit a saved row', 'In port a’s Options select <strong>Edit</strong>. Improve its description without changing its ID, direction, or range, then Save to Spec.', 'Only the intended description changes.'),
        action('Try Duplicate safely', 'In port a’s Options select <strong>Duplicate</strong>. Inspect the suggested unused ID and copied fields, then select <strong>Cancel</strong>.', 'No fourth port is saved. Duplicate uses the same validation rules as Add and Edit.'),
        action('Understand scalar ranges', 'A blank Range is a scalar. <code>0:0</code> is an indexed one-bit vector. <code>15:15</code> keeps explicit identical bounds. Optional outer brackets such as <code>[15:0]</code> are removed on save; standalone <code>15</code> or <code>WIDTH-1</code> is rejected.', 'You can choose a scalar or indexed vector deliberately. Format checks do not resolve parameter expressions.'),
        action('Reopen and compare', 'Use File → Open Spec to reopen the same path. Compare all three saved rows and the explanation.', 'The interface persists. No clock, reset, or SystemVerilog was added yet.'),
    ], 'There is one Component, exactly three 16-bit wire ports, and a saved explanation. No clock or reset was added.',
           'Edit the description of port <code>a</code> to “First unsigned 16-bit operand.” Save it without changing its range.',
           'If a port range is rejected, use explicit <code>15:0</code> bounds; optional outer brackets are accepted. A range of <code>0:0</code> is an indexed one-bit vector; a blank range is scalar.',
           [("spec-ports", "The saved adder has inputs a and b and output y."), ("spec-port-draft", "An inline wire-port draft keeps its own Save to Spec control.")], "spec-editor.md"),
    lesson("03-hardware-behavior", "Add hardware behavior", 6,
           "Save adder logic and run an explicit lint check.", "03", "Spec Editor and Verilator 5.x on the service host. Use the saved three-port adder.", [
        action('Find the leaf Component', 'Open <code>03-start.spec</code>. Locate the 16-bit modulo adder and inspect its three ports.', 'The interface is complete but the Component has no saved SystemVerilog body.'),
        action('Add a behavior Section', 'Select <strong>Options → Add SystemVerilog section…</strong> on the adder.', 'An editor opens for a module body, not a complete module declaration.'),
        action('Save the assignment', 'Paste the body below, then select <strong>Add section</strong>. Do not include module, endmodule, or port declarations. {{adder-sv}}', 'The saved SystemVerilog section shows assign y = a + b;.'),
        action('Run an explicit check', 'Select the Component’s <strong>Options → Verify Component</strong>. Do not open the panel yet.', 'A short notification reports the result. Verification does not open the panel or insert a report into the document.'),
        action('Inspect Diagnostics', 'Select the notification’s <strong>View details</strong>, or use the <strong>Diagnostics</strong> toolbar button if it has expired. Find the adder’s verification report.', 'With Verilator available and this source unchanged, the result is Lint passed. Unavailable tools are reported instead of a pass.'),
        action('Inspect the checked source', 'Expand <strong>Technical details</strong> for the report. Compare the saved target, revision, tool, and resolved interface.', 'The report identifies the source it checked. A successful report does not add an attention count.'),
        action('Return to the document', 'Close the side panel or press Escape. Inspect <strong>Interface preview (read-only)</strong> on the adder; use Options → Preview interface if needed.', 'The complete leaf diagram has three terminals. Small diagrams are not enlarged; the document remains visible.'),
        action('Inspect at full size', 'Open the preview’s Options menu and select <strong>Expand</strong>. Inspect the diagram, then close the expanded view.', 'The preview shows the interface, not an inferred implementation of the assignment.'),
        action('Download the diagram', 'In the preview’s Options menu, select <strong>Download SVG</strong>. Save it under your tutorial run directory and open it.', 'The downloaded SVG keeps the original diagram dimensions and geometry.'),
        action('Confirm persistence and limits', 'Reopen the same Spec. Compare the saved body and run Verify again if the result is missing or stale.', 'The source persists. Lint checks consistency; functional simulation is still unverified.'),
    ], 'The saved SystemVerilog section contains the assignment. The explicit check reports Lint passed for the current saved source. The preview has exactly three terminals.',
           'Open Edit on the SystemVerilog section, add a source comment, and save. Check whether the verification becomes out of date, then run Verify Component again.',
           'If the compiler is missing, the result is Not verified. Ask the environment maintainer to install Verilator. If lint fails, inspect its diagnostic and fix the saved SystemVerilog. A saved body can still contain a compiler error.',
           [("spec-sv", "The saved SystemVerilog section contains a module body."), ("spec-verified", "Diagnostics identifies the checked target; Technical details contains the saved revision and resolved interface.")], "rtl-generation.md"),
    lesson("04-assistant-register", "Create a Component with AI Assistant", 8,
           "Review an architecture and inspect the register that the Assistant saves.", "04", "Spec Editor, AI Assistant, and configured model credentials. The prepared start already contains the completed adder.", [
        action('Check the intended document', 'Open <code>04-start.spec</code>. Record its path and confirm that the adder is present.', 'This Spec will receive the register. It already contains the completed adder.'),
        action('Launch a bound conversation', 'Select <strong>AI Assistant ↗</strong> in Spec Editor. Inspect the document context in the Assistant.', 'A separate conversation is bound to this exact Spec. Selecting another Spec later does not retarget it.'),
        action('Read and send the request', 'Read the complete request below, copy it, and submit it in the Assistant. {{register-prompt}}', 'The request names five ports, reset behavior, enable behavior, and the required module body.'),
        action('Wait for architecture review', 'Follow the flow progress until the architecture review appears.', 'A proposed architecture is ready for a designer decision. No saved register is implied yet.'),
        action('Check the interface', 'Compare the proposed ports with the table below. Reject extra clocks, resets, or status ports. {{ports:reg16}}', 'The proposed interface has exactly clk, reset, enable, din, and dout with the listed directions and ranges.'),
        action('Check the behavior', 'Confirm rising-edge clocking, synchronous active-high reset, reset priority, capture when enabled, and hold when disabled.', 'The architecture agrees with the requested hardware.'),
        action('Make the architecture decision', 'Use <strong>Approve architecture</strong> only when the proposal agrees. Otherwise use Revise with specific feedback, or Cancel.', 'Approval authorizes this architecture; it does not itself save authored content.'),
        action('Inspect execution and receipt', 'Wait for the confirmed service result. In automatic mode valid content saves after authoring. If a content proposal is pending, follow the restricted-review guide.', 'The result identifies a saved change, a pending decision, or a failure. Do not treat pending content as saved.'),
        action('Compare saved content', 'Return to Spec Editor and inspect Enabled 16-bit register: explanation, ports, and SystemVerilog. {{register-sv}}', 'The saved register agrees with the requested reset, capture, and hold behavior. The adder is retained.'),
        action('Verify and reopen', 'Run Verify Component if Verilator is available, inspect Diagnostics, then reopen the same Spec.', 'The register persists independently of the Assistant’s prose. Lint and functional verification remain distinct.'),
    ], 'The same Spec contains the unchanged adder and the enabled register. The saved register implements reset, capture, and hold exactly as requested.',
           'Ask the bound Assistant to explain why reset has priority over enable. Compare its explanation with the saved body.',
           'If no model key is configured, stop this exercise and open <code>05-start.spec</code> to continue. The checkpoint supplies the register. If an operation is rejected, inspect the diagnostic and saved source before submitting a fresh request.',
           [("assistant-architecture", "Review the enabled-register architecture before approving it."), ("spec-register", "Check the saved register interface and implementation in Spec Editor.")], "ai-assistant.md"),
    lesson("05-compose-design", "Compose a Design from Components", 8,
           "Create a containing Design with two reusable Component instances.", "05", "Spec Editor. The prepared start supplies the adder, register, and containing Component interface. It has no internal Design yet.", [
        action('Inspect the prepared interface', 'Open <code>05-start.spec</code>. It supplies both leaf Components and the containing Registered 16-bit adder interface. If continuing your own Spec, create that containing Component first using this table and explanation. {{ports:registered_adder}} {{wrapper-description}}', 'The containing Component has six boundary ports and no SystemVerilog body or Internal Design.'),
        action('Create the Design', 'In Designs select <strong>Options → Add design…</strong>. Enter <strong>Registered adder implementation</strong>, then select <strong>Create design</strong>.', 'A Design appears without instances or connections.'),
        action('Inspect entry selection', 'Expand the Design’s <strong>Hardware settings</strong> and keep <strong>Entry Design</strong> selected.', 'This Design is available as an entry point. Its identity differs from the containing Component.'),
        action('Assign the implementation', 'In the containing Component expand <strong>Hardware settings</strong>. Set <strong>Internal Design</strong> to Registered adder implementation.', 'The Component now uses that Design as its implementation. Do not also add a SystemVerilog body.'),
        action('Add the adder instance', 'On the Design select <strong>Options → Add component instance…</strong>. Set Instance ID to <code>u_add</code> and choose the existing 16-bit modulo adder. Select <strong>Add instance</strong>.', 'One instance refers to the existing adder definition.'),
        action('Add the register instance', 'Repeat for Instance ID <code>u_reg</code>, using Enabled 16-bit register.', 'Exactly two instances reuse the existing leaf definitions.'),
        action('Read the instance table', 'Compare both instance IDs and Component references. Inspect the Design circuit preview.', 'The preview has two blocks and the containing boundary, without signal connections.'),
        action('Open the Design projection', 'Use the Design’s <strong>Options → Open in Circuit Designer</strong>. Inspect the binding notice.', 'An editable source-bound Circuit opens. A leaf Component preview would be read-only.'),
        action('Confirm the saved setup', 'Return to Spec Editor and reopen the same Spec.', 'The Internal Design assignment and both instances persist. The next exercise starts from this unconnected topology.'),
    ], 'The containing Component has six boundary ports and one internal Design. That Design has exactly u_add and u_reg, with no connections yet.',
           'Locate the adder definition and its u_add instance. Explain why an edit to the definition affects every instance that uses it.',
           'If you opened a read-only leaf preview, return to Spec Editor and open the Design. If boundary ports cannot be edited after composition, use Circuit Designer’s boundary controls or return to the supplied start; do not edit archive files.',
           [("spec-composition", "Hardware settings assign the containing Component’s internal Design."), ("spec-instances", "The Design lists two instances that reuse existing Component definitions.")], "spec-circuit-integration-architecture.md"),
    lesson("06-connect-save", "Connect and save a circuit", 8,
           "Save seven explicit wire connections back to the Spec.", "06", "Spec Editor, Circuit service, and Circuit Designer. The start has two instances, six boundary ports, and no nets.", [
        action('Open the source-bound Design', 'Open <code>06-start.spec</code>, then its Design’s Options → Open in Circuit Designer. Inspect the source binding.', 'The Circuit has u_add, u_reg, and six boundary ports, with no nets.'),
        action('Begin a private draft', 'Select <strong>Edit → Begin editing</strong>.', 'Save to Spec is available for the private draft. A visible draft is not saved source.'),
        action('Arrange the blocks', 'Move u_add to the left of u_reg. Drag empty canvas to pan; use <strong>View → Fit circuit</strong> to see all terminals.', 'All terminals are readable. Moving a block changes placement, not its hardware interface.'),
        action('Read the connection map', 'Use the following map. <code>top</code> means the containing boundary, not a third instance. {{nets}}', 'Every row has a driver, sink, name, and bit width.'),
        action('Create the first input connection', 'Select <strong>Connect → New connection</strong>. Enter the first Net label, select the driver as Endpoint A and sink as Endpoint B, and set both LSB fields to zero and Width (0=full) to zero. Select <strong>Create net</strong>.', 'The first named input net joins the intended boundary port and adder port.'),
        action('Complete the data path', 'Repeat the dialog for the other operand, the adder-to-register data net, and the output net, using the exact table names.', 'Both adder inputs are connected; u_add.y drives u_reg.din; u_reg.dout reaches the boundary.'),
        action('Connect the control signals', 'Create the clock, reset, and enable connections from the remaining rows.', 'There are seven nets. The scalar controls and 16-bit data paths have compatible widths.'),
        action('Inspect and route', 'Select each net to check endpoints. Drag route segments to improve readability. Direct terminal dragging can also connect ports; the dialog makes the required net names explicit.', 'Each net has one driver and one sink. Routing edits have not changed endpoints.'),
        action('Save the draft', 'Select <strong>Save to Spec</strong> and wait for the saved-source confirmation.', 'The Circuit service confirms that the source Spec accepted this draft.'),
        action('Check both applications', 'Return to Spec Editor, reopen the same Spec, and inspect the Design connection table and regenerated preview.', 'The saved source and Circuit agree on two instances, six boundary ports, and seven nets.'),
    ], 'The Spec and Circuit agree: two instances, six boundary ports, and seven named nets. Each net has one driver and one sink. u_add.y feeds u_reg.din.',
           'Begin another edit, move u_reg, then use <strong>File → Cancel changes</strong>. Confirm that the saved layout and connections return.',
           'If Save fails, retain the draft and read the diagnostic. Check source freshness and signal widths. If another tab holds editing access, close or finish that edit before retrying. Do not assume that a visible draft is saved.',
           [("circuit-edit", "An editable source-bound circuit has a private draft and Save to Spec control."), ("circuit-connected", "The completed datapath has seven direct wire connections.")], "circuit-designer.md"),
    lesson("07-generate-rtl", "Generate an RTL project", 7,
           "Obtain and lint RTL generated from the saved hierarchical Design.", "07", "Spec Editor, Verilator 5.x, GNU Make, and access to the Activity output directory. No model key is required.", [
        action('Inspect saved generation inputs', 'Open <code>07-start.spec</code>. Confirm the containing Design, two leaf bodies, and seven nets. Finish or cancel any source edits you intend to include.', 'Generation will use saved source, not unsaved draft text.'),
        action('Optionally verify first', 'Select the Design’s Options → Verify Design and inspect Diagnostics. Close the panel after inspection.', 'The report identifies the saved hierarchical target. A separate Verify is optional because generation checks it again.'),
        action('Launch generation', 'Select the Design’s <strong>Options → Generate RTL</strong>.', 'The service verifies the saved target before starting the job. A failed or unavailable check prevents generation.'),
        action('Open Activity manually', 'Use the <strong>Activity</strong> toolbar button, or the job notification’s <strong>View details</strong>.', 'The Activity tab opens beside the Spec. Starting the job did not open it automatically.'),
        action('Inspect the job result', 'Find the generation job for this target and wait for its terminal status. Read its report and any error.', 'A successful result identifies the actual published output; a job launch alone is not completion.'),
        action('Record provenance', 'Inspect Technical details for the saved target, source revision, output path, and file list.', 'You can tie the published project to this saved Spec revision.'),
        action('Obtain the project', 'Use the available artifact download links and the reported complete project directory on the service host. Keep downloaded files under your tutorial run directory.', 'You have the complete project, not just a result notification or an unrelated sample.'),
        action('Inspect the RTL', 'Open the generation manifest and module files. Find the containing structural module, adder assignment, and register body.', 'The hierarchy has two leaf implementations and the expected seven nets. Filenames come from the manifest.'),
        action('Lint that project', 'On the machine holding the actual published project, change to its reported directory and run: {{make-lint}} Record the exit status and retain the log.', 'Exit zero establishes lint for that generated project. If files or tools are missing, record this check as incomplete.'),
        action('Keep verification claims precise', 'Reopen the Spec and compare its target with the report.', 'The source remains saved. Successful generation and lint do not establish functional simulation.'),
    ], 'The actual published project contains the expected hierarchy and seven nets. Its make lint command exits zero. Functional simulation remains unverified.',
           'Use <strong>Options → Export target details (JSON)</strong> on the containing Component. Inspect the recorded revision and all reachable Sections. This diagnostic Activity does not verify RTL.',
           'If verification fails or the required tool is unavailable, read the diagnostic and correct the saved source or environment. No generation job starts until verification passes. If no complete project or output path is available, record the gap and stop the lint exercise. A successful job alone does not prove that you obtained its files.',
           [("spec-design-verified", "Verify Design checks the saved hierarchical source before generation."), ("spec-activity", "Activity results identify the saved target, report, and published artifacts.")], "rtl-generation.md"),
    lesson("08-export-reopen", "Export and reopen your work", 6,
           "Check portable Circuit and image exports against the saved circuit.", "08", "Spec Editor, Circuit Designer, and a browser download directory inside the tutorial TEMP_ folder.", [
        action('Open the saved Circuit', 'Open <code>08-start.spec</code> and launch its Design in Circuit Designer. Finish or cancel any private draft.', 'The source-bound Circuit shows the completed seven-net graph.'),
        action('Download portable JSON', 'Select <strong>File → Download → Download Circuit JSON</strong>. Save it under your run directory.', 'A .circuit.json file is downloaded; the source Spec is not replaced.'),
        action('Export SVG', 'Select <strong>File → Download → Export SVG</strong>. Save and open the image.', 'The SVG has the expected labels and routes.'),
        action('Export PNG', 'Use the same submenu for <strong>Export PNG</strong>. Save and open it.', 'The raster image matches the saved view and its visible timing-overlay setting.'),
        action('Open a separate root tab', 'Open Circuit Designer at its root URL in a new tab. Select <strong>File → Open circuit</strong> and choose the downloaded JSON.', 'An independent Circuit copy opens, separate from the Spec projection.'),
        action('Inspect its binding', 'Read the binding notice and File save controls before editing.', 'This independent copy saves by browser download; it does not write back to the original Spec.'),
        action('Compare the graph', 'Compare instance names, ports, seven nets, and routes with the source-bound tab.', 'The portable graph matches. Image exports are views, not editable hardware source.'),
        action('Confirm the original source', 'Reopen the original Spec in Spec Editor and compare its connections.', 'Export and independent opening have not changed the original Spec.'),
    ], 'The portable copy has the same graph. SVG and PNG have readable labels and the expected layout. The original Spec retains its connections.',
           'Move a block in the independent copy and save it. Confirm that its downloaded JSON changes while the original Spec does not.',
           'If export is blocked by a draft, save or cancel that draft first. If your browser saves outside the repository, set its download location before repeating the export.',
           [("circuit-download", "File → Download offers portable JSON and image exports."), ("circuit-connected", "Compare the saved canvas with each exported view.")], "circuit-designer.md"),
    lesson("09-independent-change", "Make a change independently", 7,
           "Recover from a rejected draft and confirm a durable change without a click-by-click solution.", "09", "Spec Editor and the completed registered-adder checkpoint. Circuit Designer is needed for the final comparison.", [
        action('Choose the correct target', 'Open <code>09-start.spec</code>. Improve the adder input a description to <strong>First unsigned 16-bit operand.</strong> Find the correct saved row and edit control yourself.', 'The draft belongs to the adder input, not a register port or Design boundary.'),
        action('Test a rejected draft', 'Before saving, enter invalid Range <code>15-0</code> and attempt to save. Read the error and inspect the saved row.', 'The invalid Range receives focus. Every draft field remains available; the saved Range is still 15:0.'),
        action('Save only the intended change', 'Correct the Range to <code>15:0</code> and save, or cancel and create a fresh correct edit.', 'The description changes while ID, direction, and width stay the same.'),
        action('Reopen independently', 'Close the view and reopen the same Spec from its exact path. Compare both leaf bodies, both instances, and all seven nets.', 'The description persists and the hardware structure is unchanged.'),
        action('Compare the Circuit', 'Open the Design in Circuit Designer. Compare the source graph and record the final path and revision.', 'The saved Circuit still agrees with the Spec.'),
        action('Explain the result', 'Write down which change was saved and which invalid draft was rejected. Explain draft, architecture approval, accepted content, and successful lint in your own words.', 'Your explanation distinguishes authoring, approval, saving, and verification.'),
    ], 'The new description persists. All original IDs, widths, implementations, and seven connections remain intact. The invalid range never became saved source.',
           'Explain to another designer the difference between a private draft, an accepted Spec change, an architecture approval, and a successful lint check.',
           'If a different document opens, compare the exact path rather than only its readable name. If you see a stale-source warning, review the current saved source before resubmitting the draft.',
           [("spec-invalid", "An invalid port range leaves the rejected draft available for correction."), ("spec-ports", "Compare the saved interface after reopening the same Spec.")], "spec-editor.md"),
]

EXTRAS = [
    lesson("circuit-hierarchy", "Navigate hierarchy and reuse", 7,
           "Follow a Design into a child implementation and identify reused definitions.", "complete", "Spec Editor and Circuit Designer. Use a separate completed checkpoint copy.", [
        action('Inspect the containing definition', 'Open your separate <code>circuit-hierarchy-start.spec</code>. Find Registered 16-bit adder and its Internal Design assignment.', 'The containing definition refers to Registered adder implementation. The adder and register are leaf definitions.'),
        action('Create the parent Design', 'In Designs use Options → Add design. Name it <strong>Reuse practice</strong> and create it as a separate entry Design.', 'The practice parent is separate from the completed internal Design.'),
        action('Add the first containing instance', 'On Reuse practice use Options → Add component instance. Set Instance ID to <code>u_left</code> and select the existing Registered 16-bit adder definition. Add the instance.', 'u_left refers to the containing definition, not directly to either leaf.'),
        action('Add the second instance', 'Repeat for <code>u_right</code> using the same containing definition.', 'Two instances reuse one definition; neither creates a new copy of that definition.'),
        action('Open the parent Circuit', 'Open Reuse practice in Circuit Designer. Inspect both blocks. Finish or cancel any draft before entering a child Design.', 'The parent displays u_left and u_right.'),
        action('Enter the implementation', 'Select u_left, then <strong>Components → Open selected child design</strong>.', 'The child contains u_add, u_reg, and the original seven internal nets.'),
        action('Return and inspect reuse', 'Return through the parent navigation controls. Inspect u_right’s referenced definition.', 'Both parent instances use the same internal Design.'),
        action('Confirm persistence and limits', 'Reopen the Spec and compare the two parent instances and the completed child. Leave this unconnected practice parent out of RTL generation.', 'Reuse practice persists, while the completed child retains its original connections.'),
    ], 'You can locate parent instances, one shared containing definition, its internal Design, and both leaf definitions.',
           'Change only one parent instance name. Confirm the other instance and shared definition keep their identities.',
           'If Open selected child design is disabled, select a composite instance. A leaf Component has no internal Design to enter.',
           [("spec-composition", "A containing Component points to its internal Design."), ("circuit-hierarchy", "Two parent instances can reuse one containing Component definition.")], "circuit-designer.md", "Circuit Designer"),
    lesson("circuit-timing", "Inspect stages and clock domains", 7,
           "Add a timing annotation and inspect its path analysis.", "complete", "Circuit Designer. Use a fresh completed checkpoint, separate from your final core result.", [
        action('Open an isolated draft', 'Open <code>circuit-timing-start.spec</code> and its internal Design in Circuit Designer. Select Edit → Begin editing.', 'The timing exercise cannot change your completed core file.'),
        action('Leave space for a marker', 'Arrange u_add before u_reg. Keep empty space between the blocks and inspect the path u_add.y → u_reg.din.', 'The intended boundary does not divide a block or boundary terminal.'),
        action('Add a cycle edge', 'Select <strong>Timing → Add cycle edge</strong> and place it in that empty space.', 'The marker crosses the intended data path.'),
        action('Inspect the reported path', 'Open <strong>Timing → Timing analysis</strong>. Compare the annotated cycle count and any feedback warning.', 'Each crossed cycle edge adds one annotated cycle on a same-domain path.'),
        action('Inspect the clock', 'Close Timing analysis. Select u_reg and open <strong>Timing → Clock settings</strong>. Inspect its default clk domain.', 'The annotation is visible separately from actual RTL clock wiring.'),
        action('Try another domain', 'Expand Multiple clock domains. Enter <code>practice</code> in New domain and select Add. Set Selected object domain to practice and Apply. Reopen Timing analysis.', 'A crossing can produce a CDC warning; it is not a completed CDC verification.'),
        action('Restore the intended annotation', 'Restore u_reg to clk and remove the practice domain if it does not describe the hardware. Save the intended cycle edge with Save to Spec.', 'Only the intended annotation is saved. No register or SystemVerilog behavior was inserted.'),
        action('Compare the saved view', 'Reopen the Design and compare its timing overlay with the Spec preview.', 'The marker persists and agrees with the intended stage boundary.'),
    ], 'The marker and reported latency agree with the intended stage boundary. You can identify a clock-domain warning without treating it as a completed CDC verification.',
           'Toggle the timing overlay in View. Compare the canvas with an SVG export using that same visibility setting.',
           'If a marker placement is rejected, move it into empty space. If Selected object domain is absent, close the dialog, clear the selection, select one block, and reopen it. If the control remains unavailable, record that limit and leave domain assignment incomplete. Correct annotations that disagree with RTL; they do not change the implementation.',
           [("circuit-timing", "Timing analysis reports paths and annotated cycle counts."), ("circuit-clocks", "Clock settings describe the domains used for timing annotations.")], "circuit-designer.md", "Circuit Designer"),
    lesson("circuit-independent", "Work with an independent circuit", 6,
           "Save a portable circuit and set a personal shortcut.", "complete", "Circuit Designer and a downloaded portable Circuit from core tutorial 8.", [
        action('Start from a fresh saved Design', 'Open <code>circuit-independent-start.spec</code> and its Design in Circuit Designer. Finish or cancel any private draft.', 'This exercise has its own completed source-bound Circuit.'),
        action('Download a portable copy', 'Select File → Download → Download Circuit JSON. Save the file under your tutorial run directory.', 'You have a .circuit.json file independent of the Spec archive.'),
        action('Open an independent tab', 'Open Circuit Designer at its root URL in another tab. Use File → Open circuit to choose that JSON. Read the binding notice.', 'This tab saves by browser download instead of Save to Spec.'),
        action('Try undo and redo', 'Select Edit → Begin editing. Move an instance, undo the move, then redo it.', 'Only placement changes; the seven connections remain intact.'),
        action('Save the portable file', 'Select File → Save and retain the new download under the run directory.', 'The browser downloads the edited Circuit; the service does not replace an arbitrary local file.'),
        action('Inspect a shortcut', 'Open Edit → Preferences → Actions and shortcuts. Find Fit circuit and record its current binding before changing it.', 'You can restore the original preference later.'),
        action('Resolve and save preferences', 'Set a preferred unused binding, resolve any reported conflict, and save. Reopen Preferences to compare it.', 'The browser retains the preference. Another browser is unaffected.'),
        action('Reopen and restore', 'Open the newly downloaded Circuit and confirm its placement. Compare the original Spec, then restore the recorded shortcut.', 'The independent file changed, the original Spec did not, and your previous shortcut is restored.'),
    ], 'The newly downloaded file retains your layout, and the source Spec retains its original data.',
           'Record the original shortcut before editing and restore that value after the exercise. Use Reset defaults only with a fresh practice preference file; it does not restore previous custom settings.',
           'If you see Save to Spec, you are still in the source-bound tab. Open the portable JSON in a separate root tab before doing this exercise.',
           [("circuit-download", "Download the portable Circuit before opening an independent copy."), ("circuit-preferences", "Actions and shortcuts reports binding conflicts.")], "circuit-designer.md", "Circuit Designer"),
    lesson("assistant-restricted", "Review restricted Spec proposals", 7,
           "Decide on a pending Spec proposal and inspect its saved outcome.", "complete", "An isolated environment started with --require-designer-approval, AI Assistant, and model credentials. Do not restart a shared environment for this exercise.", [
        action('Check the review policy', 'Open <code>assistant-restricted-start.spec</code> in an isolated environment started with --require-designer-approval. Open Activity and inspect Review policy.', 'The environment requires designer content decisions. Do not restart a shared environment to change policy.'),
        action('Launch the exact document', 'Close Activity and launch AI Assistant from this Spec. Compare the conversation binding with the Spec path.', 'The new conversation is bound to this practice file.'),
        action('Request a text-only change', 'Ask: “Change only the adder explanation to add that arithmetic wraps modulo 65536. Keep the interface, RTL, and connections unchanged.”', 'Only an explanation edit is requested; no structural architecture review is required.'),
        action('Wait for pending content', 'Follow the confirmed service result. If asked which text, identify the existing adder explanation.', 'A pending proposal has not changed saved source.'),
        action('Open submission history', 'Return to Spec Editor and open the Activity toolbar tab. Locate AI Assistant submission history and the exact pending proposal.', 'The proposal target and summary agree with your request.'),
        action('Inspect the stored diff', 'In that submission’s Options select <strong>Details and diff</strong>. Compare the before and after explanation.', 'The diff contains only the requested text change and retains the hardware.'),
        action('Make the content decision', 'Use the submission’s Options → Approve to save, or Reject to retain the previous source. Use the controls for that exact proposal.', 'The submission records the content decision, separate from architecture approval.'),
        action('Reopen and compare', 'Reopen the same Spec and compare its explanation, ports, bodies, instances, and nets.', 'The saved outcome agrees with the decision. If valid content saved automatically, this restricted exercise is incomplete.'),
    ], 'You can identify pending, approved, or rejected content and verify the corresponding saved source.',
           'Prepare a second text-only proposal and reject it. Confirm its text does not appear after reopening.',
           'If valid content saves immediately, your environment uses automatic mode. Use an isolated restricted environment from the setup guide. Do not pretend that an automatic save was a pending review.',
           [("assistant-history", "Activity contains the pending adder explanation proposal."), ("assistant-review", "Inspect the exact adder explanation diff before approval.")], "ai-assistant.md", "AI Assistant"),
    lesson("assistant-circuit", "Review a Circuit proposal", 7,
           "Accept a Circuit proposal into a private draft, then choose whether to save it.", "complete", "Circuit Designer, AI Assistant, and model credentials. Open a source-bound Design with no existing private draft.", [
        action('Open the practice Circuit', 'Open <code>assistant-circuit-start.spec</code> and its internal Design in Circuit Designer. Finish or cancel any private draft.', 'The source-bound Circuit has the completed seven-net topology.'),
        action('Launch a Circuit conversation', 'Select <strong>Tools → AI Assistant</strong> and inspect its context.', 'The conversation is bound to this Circuit, not a different Spec or independent copy.'),
        action('Request only placement', 'Ask: “Move u_reg to the right of u_add for clearer reading. Keep every port, instance reference, wire endpoint, and net name unchanged.”', 'The request permits a layout change, not a hardware change.'),
        action('Inspect the service result', 'Wait for any review request and confirmed proposal handoff.', 'A text description alone is not a Circuit service proposal.'),
        action('Open proposal review', 'Return to Circuit Designer and select <strong>Components → Review proposals</strong>. Inspect the exact proposed placement change.', 'The intended proposal is available for a designer decision.'),
        action('Accept into a private draft', 'Accept the proposal after checking its target. Finish or cancel a competing draft first.', 'Acceptance stages a private draft; it does not save the source Spec.'),
        action('Compare the staged graph', 'Inspect both instance references, port widths, and all seven named nets.', 'Only placement changed.'),
        action('Save or cancel and reopen', 'Select Save to Spec to persist, or File → Cancel changes to discard. Reopen the Design.', 'The saved placement agrees with the final decision, not merely the proposal acceptance.'),
    ], 'The saved result matches your final save or cancel decision. A proposal handoff or acceptance alone is never reported as a saved Spec change.',
           'Repeat with another small placement request and cancel its accepted draft.',
           'If no proposal appears, inspect the Assistant’s last confirmed service result. Do not treat a text description of the layout as a service proposal or saved change.',
           [("circuit-proposals", "Components lists the proposal review control; it is disabled when no proposal is pending."), ("circuit-edit", "An accepted source-bound proposal still requires Save to Spec.")], "ai-assistant.md", "AI Assistant"),
    lesson("verification-plan", "Capture intent and review P1", 8,
           "Review a snapshot-bound Test Plan and freeze its first plan checkpoint.", "verification-plan", "Verification Planner runs separately from the combined launcher. Prepare its lesson plans as described in Setup. The current browser has no requirement-creation form, so the start supplies captured requirements; you will audit their source and author the missing intent. No model is required.", [
        action('Inspect the snapshot handoff', 'Open Verification Planner and select + New Plan. Upload <code>registered-adder.snapshot</code> and inspect its scopes, then Cancel.', 'The snapshot is immutable; later Spec edits do not change it.'),
        action('Select the prepared plan', 'Use <code>verification/starts.json</code> to select Tutorial plan with your run name and exact ID.', 'This start contains three captured requirements and two ready intents, with no P1.'),
        action('Audit the source', 'Open <strong>Source &amp; Requirements</strong>. Inspect reset, capture, and hold source locators and their audit dispositions.', 'Each requirement points to exact snapshot source. This small example is not complete hardware coverage.'),
        action('Inspect the existing intents', 'Return to the plan view and inspect reset and capture.', 'Both already have explicit Given, When, Then, and observable outcomes.'),
        action('Create the hold intent', 'Select + Intent. Enter <strong>Disabled output holds</strong> and choose Register behavior as its Section. Link the captured hold requirement.', 'The new draft has the intended Section and requirement link.'),
        action('State its behavior', 'Use the hold row below for Given, When, and Then. {{verification-table}}', 'The intent distinguishes preconditions, the clock event, and the expected held output.'),
        action('State the observation', 'Set the observable outcome name to <code>y</code> and describe its expected held value. Remove any unrelated default observation. Select Save &amp; Mark Ready.', 'Exactly three intents are ready, including hold.'),
        action('Inspect review blockers', 'Select Review Plan. Read the checklist, blockers, and warnings. Resolve source or intent issues rather than bypassing them.', 'The selected candidate is ready to review only when blockers are clear.'),
        action('Freeze and inspect P1', 'Enter your reviewer label and comment, acknowledge applicable warnings, and confirm the review.', 'P1 freezes the reviewed source and intents. Later draft edits cannot change it.'),
        action('Confirm the plan result', 'Reload the selected plan and inspect its checkpoint identity.', 'The reviewed P1 persists. No hardware tests were executed.'),
    ], 'The selected plan refers to the intended source snapshot and has one reviewed P1 checkpoint. No hardware tests were executed.',
           'Create a draft intent for modulo wraparound (65535 + 1). Identify the missing fields needed before it could be ready.',
           'If review is blocked, inspect unresolved audits, requirements, or intent fields. Do not bypass the checklist. If port 6016 is unavailable, start the separate service using Setup.',
           [("verification-source", "A Test Plan is created from an imported source snapshot."), ("verification-plan", "Review the plan checklist before freezing P1.")], "verification-planner.md", "Verification Planner"),
    lesson("verification-coverage", "Map coverage and import evidence", 8,
           "Freeze coverage policy and inspect clearly marked synthetic evidence.", "verification-coverage", "Verification Planner and the prepared Tutorial coverage plan. It includes reviewed P1 and checking policies for reset and capture, but no hold objective or C1.", [
        action('Select the coverage start', 'Select Tutorial coverage with your run name. Open <strong>2 · Coverage &amp; Evidence</strong>.', 'The start has reviewed P1 and checking policies for reset and capture, but no hold objective or C1.'),
        action('Inspect the existing policies', 'Compare each intent with its checking objective.', 'A scenario hit alone cannot establish correctness of an intent.'),
        action('Add the hold objective', 'Select + Objective. Enter Disabled output holds, choose correctness, and link the Disabled output holds intent.', 'The objective belongs to the intended behavior.'),
        action('Set acceptance and save', 'Enter the expected observation “y remains 16 when enable=0”. Select Pass Verdict Required and Save Objective. Inspect its evidence policy.', 'The hold intent now has an explicit checking objective and policy.'),
        action('Review coverage', 'Select Review Coverage (C1), choose the prepared P1, and read the checklist and blockers.', 'The review candidate is tied to the intended upstream checkpoint.'),
        action('Freeze C1', 'Confirm the clear review and inspect C1.', 'The checkpoint freezes objectives and policies against P1.'),
        action('Switch to the evidence exercise', 'Select the separate Tutorial evidence plan with your run name and its prepared campaign.', 'This plan already supplies C1, an evaluation profile, and a campaign that match the teaching result file.'),
        action('Stage the result import', 'Select Import Results, paste <code>verification/synthetic-results.json</code>, choose the matching profile, and select Stage &amp; Validate Preview.', 'The preview identifies explicitly synthetic observations; nothing has been committed yet.'),
        action('Commit the validated import', 'Review its identities and preview, then select Commit Import.', 'The imported run retains its producer, checkpoint, profile, and synthetic provenance.'),
        action('Inspect outcomes and gaps', 'Inspect Coverage Matrix, Gaps, Evidence Runs, and Trace.', 'A later pass does not erase an earlier failure. The teaching data is not hardware simulation evidence.'),
    ], 'You have created C1 on one teaching plan and imported a synthetic run into a separate prepared evidence plan. Provenance remains visible.',
           'Inspect one checking objective and identify its minimum evaluation requirement. Explain why zero observations cannot establish full coverage.',
           'If import reports a checkpoint or profile mismatch, use the Tutorial evidence plan and its matching result file together. Do not change result identities to conceal a mismatch.',
           [("verification-coverage", "Coverage objectives and evidence policy are separate from scenario activity."), ("verification-evidence", "Stage and validate a synthetic result import before committing it.")], "verification-planner.md", "Verification Planner"),
    lesson("verification-implementation", "Review recipes and generate references", 8,
           "Freeze I1 and inspect reference artifacts without claiming an executed test.", "verification-implementation", "Verification Planner and the prepared Tutorial implementation plan. It includes P1, C1, target bindings, and one ready recipe; no I1 is present.", [
        action('Open the implementation start', 'Select Tutorial implementation with your run name and open <strong>3 · Implementation</strong>.', 'This start has P1, C1, bindings, and a ready recipe, but no I1.'),
        action('Inspect physical bindings', 'Open Target Bindings. Compare all six signal names, widths, drive/sample permissions, rising clock, and synchronous reset.', 'The recipe can address only its explicitly mapped signals.'),
        action('Inspect recipe intent', 'Open Recipes and the prepared recipe.', 'The recipe references reset, capture, and hold objectives.'),
        action('Read the Test IR', 'Inspect the sequence that resets, captures 7 + 9, and changes inputs with enable low. Compare explicit checks for zero, sixteen, and held sixteen.', 'Expected values are stated reference values, not inferred from observed output.'),
        action('Inspect the backend', 'Open Backend Plugins and inspect <code>spec2gds.reference.bundle</code> version 1.0.0.', 'This backend publishes reference files and a synthetic result template, not executable hardware tests.'),
        action('Review and freeze I1', 'Select Review Implementation (I1), choose C1, resolve blockers, and confirm with your reviewer label.', 'I1 freezes the reviewed implementation inputs.'),
        action('Run preflight', 'Open Generate Artifacts, select I1 and the reference backend, and select Preview Capabilities &amp; Preflight.', 'The preview reports capability limits and any blocking source issue before generation.'),
        action('Generate references', 'Run generation only after a clear preflight. Inspect Generated Artifacts.', 'The result publishes Test IR, bindings, recipe, producer manifest, validation report, and a synthetic result template.'),
        action('Download and verify provenance', 'Download the recipe and compare its checkpoint and source identities with I1.', 'The reference artifact identifies its source. Simulation occurs outside Verification Planner and requires a separate result import.'),
    ], 'I1 identifies the reviewed implementation inputs. Reference generation succeeds and its artifacts identify their source. No executable hardware test or simulation pass is claimed.',
           'Find the output sample binding and the check that maps its observation to a correctness objective.',
           'If generation is blocked, inspect missing mappings, permissions, upstream C1, and recipe readiness. Resolve those source issues before repeating preflight.',
           [("verification-bindings", "Target bindings map observations to concrete ports and permissions."), ("verification-implementation", "Implementation review and reference generation retain separate results.")], "verification-planner.md", "Verification Planner"),
    lesson("systemc-cycle", "Generate cycle-accurate SystemC", 7,
           "Publish a native SystemC model from explicit wire topology and leaf bodies.", "complete", "Spec Editor, CIRCT with circt-verilog and the spec2gds-systemc-emit tool, and SystemC. Ask the environment maintainer to prepare this optional toolchain first.", [
        action('Inspect the separate saved input', 'Open <code>systemc-cycle-start.spec</code> and its completed Design.', 'The source contains explicit wire topology and two leaf implementations.'),
        action('Check the supported profile', 'Inspect six unsigned physical ports, full-width direct connections, one driver per signal, and nonempty leaf SystemVerilog bodies.', 'This is a native cycle-accurate input, not the separate TLM topology.'),
        action('Check tool availability', 'Inspect Activity availability in Options. The environment needs CIRCT, circt-verilog, the native spec2gds-systemc-emit tool, and SystemC.', 'A missing tool makes this exercise incomplete; it is not a successful generation.'),
        action('Launch the Activity', 'If available, select Options → Generate cycle-accurate SystemC. Open Activity manually.', 'The job uses saved structure and SystemVerilog, not narrative guesses.'),
        action('Inspect the actual result', 'Wait for its terminal result. Inspect source revision, tool versions, Section records, output path, and file list.', 'The published model is tied to this saved Design.'),
        action('Read the generated project', 'Open the generated project instructions and locate the native Component and structural model classes.', 'The output preserves the intended hierarchy.'),
        action('Build that output', 'Build the actual published project using its README and configured SystemC toolchain. Retain output and the build log under the tutorial run directory.', 'Compilation has its own exit result. Do not substitute an RTL output directory.'),
        action('Compare the implementation', 'Locate synchronous reset, enable, and hold in the generated register model. Compare with saved SystemVerilog.', 'Generation and compilation are separate from functional simulation; do not claim an unexecuted test.'),
    ], 'The published native model identifies the same saved Design and its two leaf implementations, or reports a specific missing tool or unsupported construct.',
           'Find where the generated register implements synchronous reset and enable. Compare it with the saved body.',
           'If CIRCT, the emitter, or SystemC is missing, record this guide as incomplete. Unsupported constructs require a supported source implementation, not an inferred replacement.',
           [("spec-instances", "The source Design supplies explicit hierarchy and wire topology."), ("systemc-options", "Compatible SystemC Activities appear with target-specific availability.")], "systemc-activities.md", "SystemC Activities"),
    lesson("systemc-at", "Generate an approximately-timed skeleton", 7,
           "Publish a TLM skeleton from a separate one-to-one interface example.", "tlm", "Spec Editor and tlm-start.spec from the preparation command. SystemC and CMake are needed only for the optional build. The wire-based adder is not a compatible TLM input.", [
        action('Open the TLM start', 'Open <code>tlm-start.spec</code>. Inspect TLM practice with one initiator and one target.', 'This is a separate interface-based example; the wire-only adder is incompatible.'),
        action('Inspect the connection limit', 'Inspect the explicit socket connection. The wire preview omits that unsupported item.', 'The preview is not a complete view of the TLM interface connection.'),
        action('Check Activity availability', 'Inspect Options on the TLM practice Design.', 'The selected input is compatible with the AT skeleton Activity.'),
        action('Generate the skeleton', 'Select Options → Generate SystemC AT skeleton and open Activity manually.', 'The job reads the saved TLM topology.'),
        action('Inspect the published result', 'Read the report, source revision, output directory, and file list.', 'The report refers to the selected TLM Design.'),
        action('Inspect its socket binding', 'Open CMakeLists.txt, Component and Design headers, main program, and generation manifest. Find the initiator-to-target socket binding.', 'The project retains one initiator, one target, and one explicit binding.'),
        action('Optionally build the project', 'Read the generated README and configure/build with CMake and SystemC when available. Keep all output below your tutorial run directory.', 'A missing build tool leaves compilation incomplete even when generation succeeds.'),
        action('Separate defaults from requirements', 'Inspect the scaffold’s default timing and response behavior and the duration in main.cpp.', 'This is a structural performance-model starting point, not an inferred performance specification or an implementation of the registered adder.'),
    ], 'The generated project preserves one initiator, one target, and their explicit binding. The report identifies the selected TLM Design and source revision.',
           'Identify the generated top class and the simulation duration in main.cpp. Separate those scaffold defaults from source requirements.',
           'If the Activity rejects ad-hoc wires or fan-out, confirm that you opened tlm-start.spec. Do not run this guide on the registered-adder checkpoint.',
           [("tlm-source", "The separate TLM example has two instances; its interface connection is omitted from the wire preview."), ("tlm-activity", "The AT skeleton Activity publishes its own report and source revision.")], "systemc-activities.md", "SystemC Activities"),
]


EXTRAS += [
    lesson("diagnostics", "Diagnose and correct a failed check", 12,
           "Use Diagnostics to correct saved source and distinguish current and stale results.", "diagnostics",
           "Spec Editor and Verilator 5.x. Use the separate diagnostics start; do not break your completed core Spec.", [
        action("Inspect the starting source", "Open <code>diagnostics-start.spec</code>. Locate the adder’s SystemVerilog section.", "The three-port adder contains the valid assignment. No core exercise file is changed."),
        action("Save a known error", "In the SystemVerilog heading, select <strong>Options → Edit</strong>. Replace its body with <code>assign y = ;</code> and select <strong>Save to Spec</strong>.", "The invalid compiler input is saved. Format-valid authoring does not automatically run a compiler."),
        action("Verify without opening the panel", "Select the Component’s <strong>Options → Verify Component</strong>. Leave Diagnostics closed.", "A Lint failed notification appears. The document has no verification report or status badge."),
        action("Open the finding", "Select <strong>View details</strong>, or use the Diagnostics toolbar button after the notification expires. Find the adder’s report.", "The actionable message and checked target appear first. Opening the tab does not clear findings."),
        action("Go to saved source", "Inspect the diagnostic’s file location and select <strong>Go to source</strong>.", "The relevant target or Section opens. A line is highlighted only if its saved revision still matches and no private draft covers it."),
        action("Correct the body", "Edit the SystemVerilog section back to the body below and Save to Spec. {{adder-sv}}", "The assignment is saved. The earlier failed report is now stale and is not proof about this revision."),
        action("Run a fresh check", "Select Verify Component again, then inspect Diagnostics.", "With the required compiler available, the fresh result is Lint passed for this saved revision."),
        action("Inspect details and return", "Expand Technical details to inspect the tool and saved revision. Close the panel with Close or Escape and reopen the Spec.", "The corrected source persists. A generated RTL file location would navigate to the checked target without pretending its line is a source Section line."),
    ], "The known source error was saved, detected, corrected, and checked again. Current and stale reports are not confused.",
           "Open a private text draft, then open and resize Diagnostics and switch to Activity. Confirm the draft and document position remain. Cancel that draft.",
           "If Verilator is unavailable, record Not verified and leave the compiler exercise incomplete. If Go to source does not highlight a line, compare the saved revision and draft state; do not force a line match.",
           [("spec-failed", "Diagnostics groups the failed check under the saved adder target."), ("spec-source", "Go to source returns to the relevant saved SystemVerilog section."), ("spec-stale", "An earlier result becomes stale after a source change.")], "spec-editor.md", "Spec Editor"),
    lesson("activity", "Track an Activity and retrieve its outputs", 12,
           "Inspect a real job, download its output, and keep job completion separate from source changes.", "activity",
           "Spec Editor and the prepared Activity start. The target-details Activity needs no model or compiler; RTL generation additionally needs Verilator and Make.", [
        action("Inspect the saved target", "Open <code>activity-start.spec</code>. Locate the containing Registered 16-bit adder.", "The completed source has two leaf implementations and seven nets."),
        action("Launch a diagnostic export", "On the containing Component select <strong>Options → Export target details (JSON)</strong>.", "A real job starts against saved source. Its launch does not open the side panel."),
        action("Open Activity", "Select the Activity toolbar button or the job notification’s View details.", "The Activity tab shows the job target and its current state beside the document."),
        action("Inspect progress and cancellation", "Inspect queued/running state when present. A running job offers Cancel. If this short export has already finished, leave it completed; cancellation is optional practice on a separate running job.", "Completed and cancelled are distinct outcomes. Do not report a completed export as a cancelled job."),
        action("Read the terminal result", "Wait for success or failure. Expand the result’s details and compare target and source revision.", "The report identifies the source actually used. An export does not run RTL verification or change source."),
        action("Download the published JSON", "Select <strong>Download JSON</strong> on Target Section details. Save it below the tutorial run directory.", "The downloaded file belongs to this document and job."),
        action("Inspect content and provenance", "Open the JSON. Compare its target and source_revision_hash with the job. Inspect the reachable Section records.", "The export includes saved target content and source identity, not a simulated hardware result."),
        action("Inspect review areas", "Find change reviews and AI Assistant submission history in Activity. A pending proposal must be reviewed before it can be counted as saved content; follow the restricted-review guide for a live exercise.", "Job completion, pending review, accepted changes, and submission history have separate meanings."),
        action("Reopen and compare", "Close the panel, reopen the same Spec, and reopen Activity. Compare the source and retained job result.", "The diagnostic export did not modify hardware. Downloads and reviews retain document and revision checks."),
    ], "A real target-details job completed, its JSON was downloaded, and its target/revision agree with the saved source.",
           "Launch Generate RTL on a separate completed copy, inspect its progress and available outputs, and cancel only while a cancellation control is available. Record the actual outcome.",
           "If a download fails, compare document binding and job identity before retrying. If no running job remains, cancellation practice is incomplete; do not fabricate progress or reuse a different document’s output.",
           [("spec-activity", "Activity keeps published results beside the Spec document."), ("spec-download", "The target-details job provides a document-bound Download JSON link.")], "spec-editor.md", "Spec Editor"),
    lesson("catalog-reuse", "Reuse a Catalog Component", 12,
           "Import an exact release, resolve a local naming conflict, and distinguish published evidence from current verification.", "catalog-reuse",
           "Spec Editor and a running Spec Catalog service with the published barrel_shift release. Use the empty Catalog practice start. No model is needed.", [
        action("Open the Component library", "Open <code>catalog-reuse-start.spec</code>. In Components select <strong>Options → Import from catalog…</strong>.", "The Component library dialog opens without changing the Spec."),
        action("Search and inspect filters", "Search for <code>barrel_shift</code>. Expand Filters to inspect category, implementation, and recorded verification options; clear filters that hide the release.", "The matching published Component appears in the results."),
        action("Inspect an exact release", "Select barrel_shift and inspect its version, interface, parameter defaults, usage, and published evidence. On a narrow screen use Back to results when needed.", "The chosen release is explicit. Published evidence describes that release, not your current Spec."),
        action("Review the first import", "Select <strong>Review import</strong>. Read the proposed local changes, then select <strong>Import into Spec</strong>.", "An editable local Component definition is saved with its published defaults."),
        action("Inspect the local definition", "Close the dialog if needed. Inspect the imported ports, Parameters, and SystemVerilog in the document.", "The definition is self-contained. Import does not automatically create a Design instance."),
        action("Try a second import", "Open the library again, select the same release, and choose <strong>Import as a renamed copy</strong>. Select Review import.", "The review requests a local name instead of overwriting the existing definition."),
        action("Resolve and import the copy", "Set the requested local name to <strong>Local barrel shifter</strong>, review again, and select Import into Spec.", "Both definitions are retained, with separate local identities."),
        action("Inspect origin and evidence", "Open Diagnostics manually. Inspect Catalog origin and published evidence for the imported definitions.", "Origin and published evidence remain separate from verification of the current saved Spec."),
        action("Verify and reopen", "If Verilator is available, run Verify Component on the local definition and inspect its current report. Reopen the same Spec and compare both definitions and their origin records.", "Both imports persist. Any current verification identifies this local saved revision; unavailable tools do not become a pass."),
    ], "Two editable local definitions persist without overwriting the first. Their Catalog origin is retained and published evidence is not mistaken for current verification.",
           "Add an imported definition as an instance in a separate practice Design. Explain the difference between a release, a local definition, and an instance.",
           "If no release appears, clear filters and ask the environment maintainer to check the Catalog service and inventory. Do not upload into a shared Catalog to complete this exercise. On a conflict, review the renamed-copy controls; do not delete an existing definition.",
           [("catalog-library", "Inspect a release’s interface, defaults, usage, and evidence before import."), ("catalog-review", "Review a renamed local copy before saving the import."), ("catalog-origin", "Diagnostics separates Catalog origin from verification of the local Spec.")], "spec-editor.md", "Spec Editor"),
]

# Explicit screenshot placement follows the action it illustrates, not a fixed
# image count or a fixed position in every lesson.
PICTURE_ACTIONS = {
    "01-first-spec": [4, 7], "02-component-ports": [8, 3],
    "03-hardware-behavior": [3, 6], "04-assistant-register": [6, 9],
    "05-compose-design": [4, 7], "06-connect-save": [2, 10],
    "07-generate-rtl": [2, 6], "08-export-reopen": [2, 7],
    "09-independent-change": [2, 4], "diagnostics": [4, 5, 6],
    "activity": [3, 6], "catalog-reuse": [3, 7, 8],
    "circuit-hierarchy": [1, 5], "circuit-timing": [4, 5],
    "circuit-independent": [2, 7], "assistant-restricted": [5, 6],
    "assistant-circuit": [5, 6], "verification-plan": [1, 9],
    "verification-coverage": [4, 8], "verification-implementation": [2, 6],
    "systemc-cycle": [1, 3], "systemc-at": [2, 5],
}

for item in CORE + EXTRAS:
    if item["start"] == "complete":
        item["start"] = item["slug"]
    item["pictures"] = [dict(after=after, name=name, caption=caption) for after, (name, caption)
                        in zip(PICTURE_ACTIONS[item["slug"]], item["pictures"], strict=True)]

CORE[1]["pictures"] += [dict(after=5, name="spec-range-error", caption="An invalid 15-0 Range keeps the full draft and focuses the error.")]
CORE[0]["pictures"] += [dict(after=8, name="spec-open", caption="Open Spec browses saved files on the service host.")]
CORE[8]["pictures"][1]["name"] = "spec-port-description"
next(item for item in EXTRAS if item["slug"] == "assistant-circuit")["pictures"][1].update(name="circuit-edit-connected", caption="A source-bound private draft still requires Save to Spec.")
CORE[2]["pictures"] += [dict(after=7, name="spec-preview", caption="The complete Component interface fits a compact preview without enlargement."), dict(after=8, name="spec-preview-expanded", caption="Expand provides a larger inspection view without changing saved geometry.")]


def sidebar(current):
    links = '<a class="overview-link" href="index.html">Course overview</a>'
    links += '<span class="nav-label">CORE PATH · 9 GUIDES</span>'
    for index, item in enumerate(CORE, 1):
        active = ' aria-current="page"' if current == item["slug"] else ''
        links += f'<a href="{item["slug"]}.html"{active}><span class="nav-number">{index:02}</span><span>{item["title"]}</span></a>'
    links += '<span class="nav-label">KEEP EXPLORING</span><a href="index.html#extensions">Optional feature guides</a><a href="setup.html">Environment and checkpoints</a><a href="example.html">Example reference</a>'
    return '<nav class="course-nav" aria-label="Tutorial navigation">' + links + '</nav>'


def shell(title, body, current="", description="Hands-on tutorials for Spec Editor, Circuit Designer, AI Assistant, and Verification Planner."):
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · spec2hw tutorials</title><meta name="description" content="{html.escape(description)}">
<link rel="stylesheet" href="assets/tutorials.css"><script src="assets/tutorials.js" defer></script></head>
<body><a class="skip-link" href="#main">Skip to content</a>
<header class="site-header"><a class="brand" href="index.html"><span class="brand-mark" aria-hidden="true">s²</span>spec2hw <span class="brand-divider">/</span> <span class="brand-section">Learn</span></a><a href="setup.html" class="header-link">Environment setup <span aria-hidden="true">↗</span></a><button class="nav-toggle" aria-expanded="false" aria-controls="sidebar">Lessons</button></header>
<div class="page-grid"><aside id="sidebar" class="sidebar">{sidebar(current)}<p class="sidebar-note">Learn one action.<br>Check the saved result.</p></aside>
<main id="main" tabindex="-1">{body}<footer class="page-footer"><span>spec2hw · Designer tutorials</span><a href="../TERMINOLOGY.md">Terms</a><a href="validation.html">Validation status</a></footer></main></div></body></html>'''


def lesson_page(item, index):
    core = item["track"] == "Core"
    label = f'CORE {index + 1:02} / 09' if core else item["track"].upper()
    start = f'{item["start"]}-start.spec' if item["start"] not in ["verification-plan", "verification-coverage", "verification-implementation", "tlm"] else ('tlm-start.spec' if item["start"] == "tlm" else 'verification/starts.json')
    before = f'<p>{item["needs"]}</p><div class="checkpoint"><span class="eyebrow">START HERE</span><p><code>temp/TEMP_tutorials/my-run/{start}</code></p><a href="setup.html#checkpoints">Prepare or reset a lesson →</a></div>'
    if item["slug"] == "01-first-spec":
        before += '<p>The prepared start is an empty reference. For this lesson, create a separate fresh <code>my-adder.spec</code> file.</p>'
    if item["slug"] == "05-compose-design":
        before += '<p>This lesson adds a supplied containing interface to the earlier results. Continue from your own Spec with the listed setup, or use this prepared checkpoint.</p>'
    body = f'<div class="breadcrumbs"><a href="index.html">Tutorials</a><span>/</span>{item["track"]}</div><article><header class="lesson-heading"><p class="eyebrow">{label} <span>· GUIDED PRACTICE</span></p><h1>{item["title"]}</h1><p class="lead">{item["goal"]}</p></header>'
    body += '<nav class="article-nav" aria-label="On this page"><a href="#before">Before you start</a><a href="#actions">Actions</a><a href="#check">Check your result</a><a href="#practice">Try it</a><a href="#recovery">If it fails</a></nav>'
    before += '<p>Read each action, do it, then compare the expected result before continuing. Use a fresh prepared start to retry. Reading time and automated execution time are not measured learner practice time.</p>'
    body += f'<section id="before"><h2>Before you start</h2>{before}</section><section id="actions"><h2>Actions</h2><ol class="actions">'
    for i, entry in enumerate(item["actions"], 1):
        body += f'<li id="action-{i}"><h3>{html.escape(entry["title"])}</h3><div>{content(entry["instruction"])}</div><p class="expected"><strong>Expected result:</strong> {entry["result"]}</p>'
        for picture in item["pictures"]:
            if picture["after"] == i:
                body += photo(picture["name"], picture["caption"])
        body += '</li>'
    body += '</ol></section>'
    body += f'<section id="check" class="result"><span class="eyebrow">SAVED-STATE CHECK</span><h2>Check your result</h2><p>{item["check"]}</p></section><section id="practice"><h2>Try it yourself</h2><p>{item["practice"]}</p></section><section id="recovery"><h2>If it fails</h2><p>{item["failure"]}</p></section>'
    following = CORE[index + 1] if core and index + 1 < len(CORE) else None
    next_link = f'<a class="next-guide" href="{following["slug"]}.html"><span class="eyebrow">NEXT GUIDE</span><strong>{following["title"]} <span aria-hidden="true">→</span></strong></a>' if following else '<a class="next-guide" href="index.html#extensions"><span class="eyebrow">CONTINUE</span><strong>Explore another feature →</strong></a>'
    body += f'<section id="continue"><h2>Continue</h2>{next_link}<p class="reference-link">Reference: <a href="../{item["reference"]}">{item["reference"].removesuffix(".md").replace("-", " ")}</a> · <a href="example.html">Complete example</a></p></section></article>'
    return shell(item["title"], body, item["slug"], item["goal"])


def index_page():
    body = f'''<section class="course-hero"><p class="eyebrow">THE DESIGNER’S STARTING POINT</p><h1>From your first Spec<br>to a saved circuit.</h1><p class="lead">Build a small registered adder. Try the important controls and check each saved result.</p><div class="hero-meta"><span>9 core guides</span><span>{len(EXTRAS)} optional exercises</span><span>Read · Do · Check</span></div><a class="button" href="01-first-spec.html">Start with your first Spec <span aria-hidden="true">→</span></a><a class="hero-secondary" href="setup.html#checkpoints">Jump in with a prepared checkpoint</a></section>
<div class="course-intro"><p>For designers who know basic digital hardware and are new to spec2hw. Start with the running environment supplied to you. No model key is needed for manual authoring; the Assistant lesson has a prepared fallback.</p><p>Use one example throughout: a 16-bit modulo adder, followed by an enabled register. Every guide has a fresh starting point and a visible result check.</p></div>
<section id="core"><div class="section-heading"><div><p class="eyebrow">LEARN THE BASICS</p><h2>Your core path</h2></div><span>Read · Do · Check</span></div><ol class="lesson-list">'''
    for i, item in enumerate(CORE, 1):
        body += f'<li><a href="{item["slug"]}.html"><span class="lesson-number">{i:02}</span><span><strong>{item["title"]}</strong><span class="lesson-summary">{item["goal"]}</span></span><span class="lesson-time">{len(item["actions"])} actions <span aria-hidden="true">↗</span></span></a></li>'
    body += '</ol></section>' + note('Review edition', 'The guides are ready for learner review. A new designer must still check the first three guides, the full core path, and the independent challenge. Times are estimates. Optional tracks remain review material until the core path passes that review. See the <a href="validation.html">validation and review checklist</a>.')
    body += '<section id="extensions"><p class="eyebrow">CHOOSE WHAT YOU NEED NEXT</p><h2>Explore more features</h2><p>Try a focused operation with its own prepared start. Follow each guide’s prerequisites. Optional compiler exercises remain incomplete when their tools are unavailable.</p><div class="extension-grid">'
    for track in dict.fromkeys(x["track"] for x in EXTRAS):
        body += f'<div class="extension-group"><h3>{track}</h3><ul>'
        for item in EXTRAS:
            if item["track"] == track:
                body += f'<li><a href="{item["slug"]}.html">{item["title"]}<span>{len(item["actions"])} actions →</span></a></li>'
        body += '</ul></div>'
    body += '</div></section>' + note('What a result means', 'A draft is not a saved Spec. Architecture approval is not a saved result. Lint is not functional simulation. Each guide tells you which result to check.')
    body += '<section class="resource-row"><a href="setup.html"><strong>Need an environment?</strong><span>Setup, prerequisites, and reset instructions →</span></a><a href="example.html"><strong>Keep the example nearby</strong><span>Ports, behavior, connection map, and prompt →</span></a></section>'
    return shell("Get started", body)


def setup_page():
    body = '''<article><header class="lesson-heading"><p class="eyebrow">BEFORE YOUR FIRST GUIDE</p><h1>Environment and checkpoints</h1><p class="lead">Use a ready environment, or prepare a local one without changing the shared service configuration.</p></header>
<section><h2>Use a ready environment</h2><p>Ask its maintainer for the Spec Editor, Circuit Designer, and AI Assistant URLs, plus a writable absolute server-local tutorial directory. Default ports are 6010, 6012, and 6013. Verification Planner runs separately on 6016. Use the actual host and ports printed by your environment; <code>0.0.0.0</code> is not a browser address.</p><p>Keep browser downloads, scratch files, Activity outputs, and validation evidence under the repository’s ignored <code>temp/TEMP_tutorials/</code> directory. Browser-local paths and server-local paths can refer to different machines.</p></section>
<section id="checkpoints"><h2>Prepare a fresh set of starts</h2><p>On the service host, run this from the repository root after Python setup:</p>''' + code('uv run python scripts/prepare_tutorials.py --output temp/TEMP_tutorials/my-run') + '''<p>The command uses the production Spec HTTP API in a private in-process service. Each optional Spec Editor, Circuit Designer, and Assistant exercise also has its own named start, including diagnostics-start.spec, activity-start.spec, and catalog-reuse-start.spec. It does not need a model or alter a running editor. It creates a separate start for each core lesson, the complete source, a snapshot, a TLM example, and prepared Verification Planner records. It prints absolute paths in <code>starts.json</code>.</p><p>Use <strong>File → Open Spec</strong> to open the start named in a guide. These are real editable files. To reset after editing one, prepare a new directory such as <code>temp/TEMP_tutorials/retry-02</code>. The command refuses an existing output directory. Do not overwrite a start or someone else’s work.</p><p>Continue with your own Spec where the previous result matches the next lesson. Guide 5 supplies an additional containing interface; its start includes that setup. Each start is complete for its named lesson. The preparation does not claim lint or simulation success.</p></section>
<section><h2>Install and start locally</h2><p>This section is for the environment maintainer. The combined launcher targets Linux or WSL. Install Python 3.12+, uv, Node.js 24.2+, and lsof. RTL checks also need Verilator 5.x and GNU Make. Package setup requires GitHub Packages read access through <code>NODE_AUTH_TOKEN</code>; keep credentials out of files and tutorial screenshots.</p>''' + code('scripts/setup-all.sh\nuv run python scripts/prepare_tutorials.py --output temp/TEMP_tutorials/my-run') + '''<p>Point this process at the run-local registry so Activity outputs and preferences stay below TEMP_. Keep the tracked registry unchanged:</p>''' + code('export SPEC_EDITOR_STATE_ROOT="$PWD/temp/TEMP_tutorials/my-run/spec-state"\nexport ASSISTANT_STATE="$PWD/temp/TEMP_tutorials/my-run/assistant-state"\nexport SPEC2GDS_SCRATCH_ROOT="$PWD/temp/TEMP_tutorials/my-run/scratch"\nexport SPEC_DOCUMENT_ROOT="$PWD/temp/TEMP_tutorials/my-run/documents"\nscripts/serve-all.sh start --service-config "$PWD/temp/TEMP_tutorials/my-run/services.json"') + '''<p>Use the printed browser URLs. If model credentials are not already configured, set <code>OPENAI_API_KEY</code> in the launching environment before starting. The first three manual guides work without it. Never paste a credential into a guide, prompt, screenshot, or log.</p><p>To use restricted Spec content review in an isolated environment, add <code>--require-designer-approval</code> when starting. Do not restart a shared environment for a tutorial. The combined launcher has one shared process record per checkout. Start it only when that checkout has no running shared stack. Do not use it for a second recording environment. Stop only the stack that you started:</p>''' + code('scripts/serve-all.sh stop') + '''</section>
<section><h2>Start Verification Planner separately</h2>''' + code('uv run verification-planner --service-config temp/TEMP_tutorials/my-run/services.json --storage-dir temp/TEMP_tutorials/my-run/verification/planner-data') + '''<p>Open its printed URL. Select the prepared plans by name in the plan selector. The first guide also shows snapshot upload in New Plan. Later Spec edits do not change the imported snapshot.</p><p>The <code>verification/</code> directory contains a private prepared service data directory, a starts.json file with each plan name and ID, and a clearly marked synthetic result file. To add starts to an already running Verification Planner, give its URL to the preparation command with <code>--planner-url http://127.0.0.1:6016</code>. This adds new tutorial plans and does not modify existing ones. No simulator is run during preparation. Use these prepared plans directly: do not substitute a portable .vplan import without checking its source and review prerequisites.</p></section>
<section><h2>Optional SystemC prerequisites</h2><p>Cycle-accurate generation needs CIRCT, <code>circt-verilog</code>, the native <code>spec2gds-systemc-emit</code> tool, and SystemC. The AT skeleton uses a separate TLM topology; building it needs CMake and SystemC. Follow the current <a href="../systemc-activities.md">SystemC reference</a> before starting those guides. Keep build output under TEMP_. A missing optional toolchain leaves that guide incomplete.</p></section>
<section><h2>Read the HTML guides</h2><p>Open <code>docs/tutorials/index.html</code> directly, or serve the repository locally:</p>''' + code('uv run python -m http.server 6080 --bind 127.0.0.1') + '''<p>Then open <a href="http://127.0.0.1:6080/docs/tutorials/index.html">the local tutorial index</a>. The pages use local CSS and JavaScript, with no package build or external fonts. Reading and navigation also work without JavaScript.</p></section><section><h2>Continue</h2><a class="button" href="01-first-spec.html">Create your first Spec →</a><p><a href="../development.md">Development reference</a> · <a href="../ai-assistant-operations.md">Assistant setup reference</a> · <a href="validation.html">Validation and review checklist</a></p></section></article>'''
    return shell("Environment and checkpoints", body)


def example_page():
    body = '<article><header class="lesson-heading"><p class="eyebrow">ONE EXAMPLE · EXPLICIT BEHAVIOR</p><h1>Registered 16-bit adder</h1><p class="lead">A combinational adder feeds one enabled register. Every interface and connection is explicit.</p></header>'
    for key in EXAMPLE["components"]:
        data = EXAMPLE["components"][key]
        body += f'<section><h2>{data["name"]}</h2><p>{data["description"]}</p>{ports(key)}'
        if data.get("systemverilog"):
            body += code(data["systemverilog"])
        else:
            body += '<p>The containing Component has no SystemVerilog section. Its internal Design instantiates <code>u_add</code> and <code>u_reg</code>.</p>'
        body += '</section>'
    body += '<section><h2>Seven connections</h2><p><code>top</code> denotes the containing interface, not an instance. All endpoints use their full width.</p>' + nets + '</section>'
    body += '<section><h2>Reference observations</h2>' + table(["Case", "Given", "When", "Expected"], [[x[1], x[2], x[3], x[4]] for x in EXAMPLE["verification"]]) + '<p>These are reference expectations, not executed simulation results. The tutorial Test Plan intentionally covers only these three cases. Modulo wraparound, timing constraints, and other test objectives need separate review.</p></section>'
    body += '<section><h2>Assistant request</h2>' + code(register_prompt(EXAMPLE)) + '</section><section><h2>Canonical source</h2><p><a href="example.json">example.json</a> is the single maintained source for ports, behavior, connections, and these reference cases. The preparation and HTML build commands read it. Service-generated Component IDs can differ when you author manually; locate Components by their saved references.</p></section></article>'
    return shell("Example reference", body)


def validation_page():
    body = '''<article><header class="lesson-heading"><p class="eyebrow">EVIDENCE, NOT ASSUMPTIONS</p><h1>Validation and learner review</h1><p class="lead">A guide is complete only when its actions and saved-state check have been exercised.</p></header>
<section><h2>Review gates</h2><p>The core guides and optional tracks are available for review. A new designer must still complete guides 1–3 and confirm that the format is clear, then complete the full core path and the independent challenge. Until that review is recorded, reading-time estimates and learner independence are unverified. Do not label an automated browser run as a human review.</p></section>
<section><h2>Run the checks</h2>''' + code('uv run python scripts/build_tutorials.py --check\nuv run python -m pytest tests/test_tutorials.py -q\nscripts/test-all.sh fast --output temp/TEMP_tutorials/evidence/fast\nscripts/test-all.sh integration --scope spec,circuit,assistant,verification,activities,shared --output temp/TEMP_tutorials/evidence/integration') + '''<p>The fast profile includes exactly three live model checks. Missing credentials or tools make it incomplete. Keep the report’s executed commands, exit results, and coverage limits. Run broad regression if implementation changes cross-application contracts, persistence, shared runtime, or the Activity SDK. This tutorial change does not change those contracts.</p></section>
<section><h2>Guide acceptance record</h2><p>For each guide, record its title, code revision, start path, browser, service URLs, prerequisites, elapsed practice time, actions completed, final source revision, expected versus actual result, and evidence paths. Capture the important states next to their actions; do not use a fixed image quota. Store the run under an ignored repository TEMP_ directory.</p><ul><li>Reopen the Spec after a successful save.</li><li>Compare Spec and Circuit after Save to Spec.</li><li>Check invalid drafts, unavailable tools, stale lint, and missing model credentials.</li><li>For Assistant exercises, use live model access and inspect saved results; do not require identical prose.</li><li>For RTL, retain the actual published project and its lint log.</li><li>For Verification Planner, retain snapshot and checkpoint identities and synthetic evidence provenance.</li><li>Record SystemC generation, compilation, and simulation separately.</li></ul></section>
<section id="captures"><h2>Screenshot maintenance</h2><p>The page images are focused captures of the actual applications. The <a href="assets/captures.json">capture manifest</a> maps each image to its lesson action, source revision, viewport, theme, and hash. The maintained <a href="../tutorial-maintenance.md">tutorial maintenance guide</a> gives the exact capture and publish commands. They illustrate controls and source data; they are not proof of a learner’s run or live model success. Keep capture originals and reports below TEMP_. Publish only selected documentation images in the tutorial assets directory, with no credentials or private design data.</p></section>
<section><h2>Human review form</h2><ul><li>Can the designer find each control without undocumented help?</li><li>How long did the hands-on exercise take, excluding installation and tool queue time? Record practice time before publishing an estimate.</li><li>Can the designer restart from its prepared checkpoint?</li><li>Can the designer explain what was saved and what remains unverified?</li><li>Can the designer complete guide 9 without a supplied click sequence?</li></ul><p>Record findings in the evidence directory. Correct instructions and repeat the affected guide before marking the course ready.</p></section></article>'''
    return shell("Validation and learner review", body)


def pages():
    result = {"index.html": index_page(), "setup.html": setup_page(), "example.html": example_page(), "validation.html": validation_page()}
    for i, item in enumerate(CORE):
        result[f'{item["slug"]}.html'] = lesson_page(item, i)
    for item in EXTRAS:
        result[f'{item["slug"]}.html'] = lesson_page(item, 0)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for name, content in pages().items():
        path = DEST / name
        content += "\n"
        if args.check:
            if not path.exists() or path.read_text() != content:
                stale.append(name)
        else:
            path.write_text(content)
    if stale:
        parser.exit(1, "Rebuild tutorials: " + ", ".join(stale) + "\n")
    print(f'{len(pages())} tutorial pages {"checked" if args.check else "written"}.')


if __name__ == "__main__":
    main()

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
    return f'<figure><a href="assets/{name}.jpg"><img src="assets/{name}.jpg" alt="{html.escape(caption)}" loading="lazy"></a><figcaption>{html.escape(caption)} Select the image to view its full size.</figcaption></figure>'


def note(title, body):
    return f'<aside class="note"><strong>{title}</strong><p>{body}</p></aside>'


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
           "Create a Spec and reopen the same saved file.", "01", "Spec Editor and a writable server-local directory. No model key or compiler is required.", [
        'Open the Spec Editor URL supplied with your environment. Use <strong>Contents</strong> to move between Sections. On a small screen, open <strong>Menu</strong> for the application menus.',
        'Select <strong>File → New Spec</strong>. Enter <strong>My registered adder</strong> as the Spec name. Enter a new absolute server-local path below your tutorial run directory, ending in <code>my-adder.spec</code>. Select <strong>Create</strong>. Do not select an existing start file as the new destination.',
        'Inspect the document cover, Components group, and Designs group. Hover over the active document name to inspect the path. A Spec is the logical document; its <code>.spec</code> file is the saved archive.',
        'Close this browser tab. Open Spec Editor again. Select <strong>File → Open Spec</strong>, enter the same absolute path, and select <strong>Open</strong>. This command opens a file on the service host, not a file on your browser computer.',
        'Confirm the name and path. Accepted source changes save automatically. Use the save control inside an open draft; the File menu has no separate Save command.',
    ], 'The reopened Spec has the same name and path. Its Components and Designs groups are empty.',
           'Use <strong>Edit name</strong> on the cover to change the readable name. Save and reopen it. The path stays the same.',
           'If New Spec reports an existing destination, choose a fresh filename. Use Open Spec to inspect an existing file. Do not delete or replace it.',
           [("spec-new", "New Spec asks for a readable name and a server-local path."), ("spec-cover", "The saved document cover and Contents panel.")], "spec-editor.md"),
    lesson("02-component-ports", "Define a Component and its ports", 7,
           "Save a complete interface for a 16-bit adder.", "02", "Spec Editor. Continue with your empty Spec or open the prepared start.", [
        'In Components, select <strong>Add Component</strong>. Enter <strong>16-bit modulo adder</strong> as the Component name. Select <strong>Create component</strong>. A Component is a reusable definition; an instance is one use of that definition.',
        'Open the new Component’s <strong>Options → Edit text…</strong>. Paste this explanation and select <strong>Save to Spec</strong>.' + code(adder["description"]),
        'Select <strong>Add port</strong> in its Ports Section, or <strong>Options → Add wire port…</strong>. Enter each row below. Set Direction and Range explicitly. Use <strong>Save and add another</strong> for the first two ports and <strong>Save to Spec</strong> for the last port.' + ports("add16"),
        'Read the saved Ports table. A Port ID such as <code>a</code> is an exact hardware identifier. The Component name is readable text. Keep the service-created Component ID; do not assume that the display name is its ID.',
        'Select <strong>File → Open Spec</strong> with the same path. Confirm that the explanation and all three ports return. Leave the missing-RTL status for the next lesson.',
    ], 'There is one Component, exactly three 16-bit wire ports, and a saved explanation. No clock or reset was added.',
           'Edit the description of port <code>a</code> to “First unsigned 16-bit operand.” Save it without changing its range.',
           'If a port range is rejected, use <code>15:0</code>, without square brackets. A range of <code>0:0</code> is an indexed one-bit vector; a blank range is scalar.',
           [("spec-ports", "The saved adder has inputs a and b and output y."), ("spec-port-draft", "An inline wire-port draft keeps its own Save to Spec control.")], "spec-editor.md"),
    lesson("03-hardware-behavior", "Add hardware behavior", 6,
           "Save adder logic and run an explicit lint check.", "03", "Spec Editor and Verilator 5.x on the service host. Use the saved three-port adder.", [
        'In the adder Component, select <strong>Options → Add SystemVerilog section…</strong>. Paste this module body, then select <strong>Add section</strong>.' + code(adder["systemverilog"]),
        'Keep <code>module</code>, <code>endmodule</code>, port declarations, and module headers out of this Section. The Activity builds those from the saved interface. An explanation alone does not implement behavior.',
        'Select <strong>Verify Component</strong>. Wait for <strong>Lint passed</strong>. Expand <strong>Verification details</strong> to inspect the checked target, source revision, and resolved widths.',
        'Select <strong>Options → Preview interface</strong>. Inspect the embedded <strong>Interface preview (read-only)</strong>. It shows one leaf Component with three terminals. It does not invent an internal circuit from the assignment.',
        'Reopen the Spec. The SystemVerilog text persists. Verification results can require a new check after a reload or source change. Lint checks source and interface consistency; functional simulation remains unverified.',
    ], 'The saved SystemVerilog section contains the assignment. The explicit check reports Lint passed for the current saved source. The preview has exactly three terminals.',
           'Open Edit on the SystemVerilog section, add a source comment, and save. Check whether the verification becomes out of date, then run Verify Component again.',
           'If the compiler is missing, the result is Not verified. Ask the environment maintainer to install Verilator. If lint fails, inspect its diagnostic and fix the saved SystemVerilog. A saved body can still contain a compiler error.',
           [("spec-sv", "The saved SystemVerilog section contains a module body."), ("spec-verified", "Verification details identify the source revision and resolved interface.")], "rtl-generation.md"),
    lesson("04-assistant-register", "Create a Component with AI Assistant", 8,
           "Review an architecture and inspect the register that the Assistant saves.", "04", "Spec Editor, AI Assistant, and configured model credentials. The prepared start already contains the completed adder.", [
        'Open the intended Spec. Select <strong>AI Assistant ↗</strong> in the application bar. This creates a conversation bound to this exact document. Opening another Spec later does not retarget this conversation.',
        'Copy the following request. It gives the complete interface and behavior. Read it before sending it.' + code(register_prompt(EXAMPLE)),
        'Inspect the architecture review card. Require exactly five ports, one 16-bit register stage, rising-edge clocking, synchronous active-high reset, and reset priority. Approve the architecture only when it agrees. If it does not agree, request a revision or cancel it.',
        'Wait for the service result. Architecture approval authorizes the structure; it does not prove that content was saved. In the default mode, valid Spec content saves automatically. If content is pending, follow the restricted-approval guide.',
        'Return to Spec Editor. Inspect <strong>Enabled 16-bit register</strong>: explanation, ports, and body. Run <strong>Verify Component</strong> when Verilator is available. Confirm that the adder was retained.' + ports("reg16") + code(register["systemverilog"]),
    ], 'The same Spec contains the unchanged adder and the enabled register. The saved register implements reset, capture, and hold exactly as requested.',
           'Ask the bound Assistant to explain why reset has priority over enable. Compare its explanation with the saved body.',
           'If no model key is configured, stop this exercise and open <code>05-start.spec</code> to continue. The checkpoint supplies the register. If an operation is rejected, inspect the diagnostic and saved source before submitting a fresh request.',
           [("assistant-architecture", "Review the complete register architecture before approving it."), ("spec-register", "Check the saved register interface and implementation in Spec Editor.")], "ai-assistant.md"),
    lesson("05-compose-design", "Compose a Design from Components", 8,
           "Create a containing Design with two reusable Component instances.", "05", "Spec Editor. The prepared start supplies the adder, register, and containing Component interface. It has no internal Design yet.", [
        'Open <code>05-start.spec</code>. If continuing your own Spec, first create a Component named <strong>Registered 16-bit adder</strong>, add the following six boundary ports while it is still a leaf, and paste the supplied explanation. The checkpoint avoids this repeated port entry.' + ports("registered_adder") + code(wrapper["description"]),
        'In Designs, select <strong>Add Design</strong>. Enter <strong>Registered adder implementation</strong>. Select <strong>Create design</strong>. In that Design’s Hardware settings, keep <strong>Entry Design</strong> selected.',
        'In the containing Component, expand <strong>Hardware settings</strong>. Set <strong>Internal Design</strong> to Registered adder implementation. Do not add a SystemVerilog section to the containing Component; its implementation will be the Design.',
        'In the Design, select <strong>Options → Add component instance…</strong>. Set <strong>Instance ID</strong> to <code>u_add</code> and <strong>Component</strong> to the existing 16-bit modulo adder definition. Select <strong>Add instance</strong>. Repeat with <code>u_reg</code> and Enabled 16-bit register.',
        'Inspect the instance table and circuit preview. Both instances refer to existing definitions. Open <strong>Options → Open in Circuit Designer</strong> on the Design. It must be an editable source-bound circuit, not a leaf preview.',
    ], 'The containing Component has six boundary ports and one internal Design. That Design has exactly u_add and u_reg, with no connections yet.',
           'Locate the adder definition and its u_add instance. Explain why an edit to the definition affects every instance that uses it.',
           'If you opened a read-only leaf preview, return to Spec Editor and open the Design. If boundary ports cannot be edited after composition, use Circuit Designer’s boundary controls or return to the supplied start; do not edit archive files.',
           [("spec-composition", "Hardware settings assign the containing Component’s internal Design."), ("spec-instances", "The Design lists two instances that reuse existing Component definitions.")], "spec-circuit-integration-architecture.md"),
    lesson("06-connect-save", "Connect and save a circuit", 8,
           "Save seven explicit wire connections back to the Spec.", "06", "Spec Editor, Circuit service, and Circuit Designer. The start has two instances, six boundary ports, and no nets.", [
        'Open the Design from Spec Editor using <strong>Options → Open in Circuit Designer</strong>. Check the source binding. Select <strong>Edit → Begin editing</strong>. Changes now belong to a private draft.',
        'Move u_add to the left of u_reg. Drag empty canvas to pan; use View controls to fit the circuit. Inspect the terminals. <code>top</code> in this table means the containing boundary, not a third instance.',
        'For each row, select <strong>Connect → New connection</strong>. Enter its <strong>Net label</strong>, select the driver as <strong>Endpoint A</strong> and sink as <strong>Endpoint B</strong>, set both LSB fields to zero and <strong>Width (0=full)</strong> to zero, then select <strong>Create net</strong>. Use these seven connections. Direct terminal dragging also connects ports, but this dialog lets you set each required name.' + nets,
        'Drag route segments to improve readability. Check every endpoint and width before saving. Routing changes the drawing; the connection endpoints define the signal.',
        'Select <strong>Save to Spec</strong>. Wait for the saved-source confirmation. Return to Spec Editor and inspect the Design connection table and regenerated preview. Close and reopen the Spec to confirm persistence.',
    ], 'The Spec and Circuit agree: two instances, six boundary ports, and seven named nets. Each net has one driver and one sink. u_add.y feeds u_reg.din.',
           'Begin another edit, move u_reg, then use <strong>File → Cancel changes</strong>. Confirm that the saved layout and connections return.',
           'If Save fails, retain the draft and read the diagnostic. Check source freshness and signal widths. If another tab holds editing access, close or finish that edit before retrying. Do not assume that a visible draft is saved.',
           [("circuit-edit", "An editable source-bound circuit has a private draft and Save to Spec control."), ("circuit-connected", "The completed datapath has seven direct wire connections.")], "circuit-designer.md"),
    lesson("07-generate-rtl", "Generate an RTL project", 7,
           "Obtain and lint RTL generated from the saved hierarchical Design.", "07", "Spec Editor, Verilator 5.x, GNU Make, and access to the Activity output directory. No model key is required.", [
        'Open the saved Design in Spec Editor. Select <strong>Verify Design</strong>. Require <strong>Lint passed</strong> for the current source before continuing. If you edited the source, verify again.',
        'Select the Design’s <strong>Options → Generate RTL</strong>. This starts the job directly and opens the Activity view. Check the target name and wait for the terminal job result.',
        'Read the generation report. Record the saved target, source revision, output path, file list, and any diagnostics. Obtain the complete project from the reported output directory on the service host. Use available artifact download links for individual published artifacts.',
        'Inspect the manifest and RTL files. Expect one containing structural module and two leaf implementations. Find the adder assignment and register body. Module filenames come from the manifest; they need not equal display names.',
        'In a terminal on the machine with that published project, change to its reported directory and run:' + code('make lint') + 'Record the exit status. Keep the complete project and lint log under the tutorial TEMP_ directory. Do not run against a different sample project.',
    ], 'The actual published project contains the expected hierarchy and seven nets. Its make lint command exits zero. Functional simulation remains unverified.',
           'Use <strong>Options → Export target details (JSON)</strong> on the containing Component. Inspect the recorded revision and all reachable Sections. This diagnostic Activity does not verify RTL.',
           'If Generate RTL is disabled, rerun Verify Design against the current saved revision. If no complete project or output path is available, record the gap and stop the lint exercise. A successful job alone does not prove that you obtained its files.',
           [("spec-design-verified", "Verify Design checks the saved hierarchical source before generation."), ("spec-activity", "Activity results identify the saved target, report, and published artifacts.")], "rtl-generation.md"),
    lesson("08-export-reopen", "Export and reopen your work", 6,
           "Check portable Circuit and image exports against the saved circuit.", "08", "Spec Editor, Circuit Designer, and a browser download directory inside the tutorial TEMP_ folder.", [
        'Open the saved Design in Circuit Designer. Finish or cancel any draft. Inspect the seven connections and readable labels.',
        'Select <strong>File → Download → Download Circuit JSON</strong>. Save the portable file below your tutorial run directory. Its extension is <code>.circuit.json</code>.',
        'Use the same Download submenu to select <strong>Export SVG</strong>, then <strong>Export PNG</strong>. Save both exports. Open them and compare port labels, routes, and the visible timing overlay with the saved canvas.',
        'Open a separate Circuit Designer tab at its root URL. Select <strong>File → Open circuit</strong> and choose the downloaded JSON. This is an independent copy; inspect its source-binding notice before editing.',
        'Compare the portable copy with the source-bound Circuit. Reopen the original Spec in Spec Editor and confirm the saved source is unchanged. Images are views; they are not editable hardware source.',
    ], 'The portable copy has the same graph. SVG and PNG have readable labels and the expected layout. The original Spec retains its connections.',
           'Move a block in the independent copy and save it. Confirm that its downloaded JSON changes while the original Spec does not.',
           'If export is blocked by a draft, save or cancel that draft first. If your browser saves outside the repository, set its download location before repeating the export.',
           [("circuit-download", "File → Download offers portable JSON and image exports."), ("circuit-connected", "Compare the saved canvas with each exported view.")], "circuit-designer.md"),
    lesson("09-independent-change", "Make a change independently", 7,
           "Recover from a rejected draft and confirm a durable change without a click-by-click solution.", "09", "Spec Editor and the completed registered-adder checkpoint. Circuit Designer is needed for the final comparison.", [
        'Challenge: improve the adder input <code>a</code> description to <strong>First unsigned 16-bit operand.</strong> Keep its ID, direction, and width. Find the correct Component and edit control yourself.',
        'Before saving, enter the invalid range <code>15::0</code>. Attempt to save. Read the error. Confirm the draft remains available and that the saved range is still <code>15:0</code>.',
        'Correct the range to <code>15:0</code> and save the intended description, or cancel the rejected draft and create a fresh correct edit. Do not change the hardware behavior.',
        'Close the view and reopen the same Spec from its path. Inspect the saved description, adder body, register body, two instances, and seven nets.',
        'Open the Design in Circuit Designer. Check that the source graph still agrees. Record the final source path and revision. Write down which change you saved and which invalid draft was rejected.',
    ], 'The new description persists. All original IDs, widths, implementations, and seven connections remain intact. The invalid range never became saved source.',
           'Explain to another designer the difference between a private draft, an accepted Spec change, an architecture approval, and a successful lint check.',
           'If a different document opens, compare the exact path rather than only its readable name. If you see a stale-source warning, review the current saved source before resubmitting the draft.',
           [("spec-invalid", "An invalid port range leaves the rejected draft available for correction."), ("spec-ports", "Compare the saved interface after reopening the same Spec.")], "spec-editor.md"),
]

EXTRAS = [
    lesson("circuit-hierarchy", "Navigate hierarchy and reuse", 7,
           "Follow a Design into a child implementation and identify reused definitions.", "complete", "Spec Editor and Circuit Designer. Use a separate completed checkpoint copy.", [
        'Open the containing Registered 16-bit adder and inspect its Internal Design assignment. Its implementation is a Design; the adder and register are leaf Components.',
        'In Spec Editor, create a new entry Design named <strong>Reuse practice</strong>. Add two instances of Registered 16-bit adder, named <code>u_left</code> and <code>u_right</code>. Use the same existing definition for both.',
        'Open Reuse practice in Circuit Designer. Select u_left, then <strong>Components → Open selected child design</strong>. Inspect u_add and u_reg. Finish or cancel drafts before entering or leaving a child Design.',
        'Return to the parent through its navigation controls. Inspect u_right’s definition reference. Both instances reuse one containing definition; the referenced internal Design is shared.',
        'Return to Spec Editor and reopen the Spec. Confirm two parent instances and the original seven internal connections. Leave the unconnected practice parent out of RTL generation.',
    ], 'You can locate parent instances, one shared containing definition, its internal Design, and both leaf definitions.',
           'Change only one parent instance name. Confirm the other instance and shared definition keep their identities.',
           'If Open selected child design is disabled, select a composite instance. A leaf Component has no internal Design to enter.',
           [("spec-composition", "A containing Component points to its internal Design."), ("circuit-hierarchy", "Two parent instances can reuse one containing Component definition.")], "circuit-designer.md", "Circuit Designer"),
    lesson("circuit-timing", "Inspect stages and clock domains", 7,
           "Add a timing annotation and inspect its path analysis.", "complete", "Circuit Designer. Use a fresh completed checkpoint, separate from your final core result.", [
        'Open the internal Design. Select <strong>Edit → Begin editing</strong>. Arrange u_add before u_reg with enough empty space between them.',
        'Select <strong>Timing → Add cycle edge</strong> and place the marker between the two blocks. It must not divide a block or boundary terminal. Inspect the path from u_add.y to u_reg.din.',
        'Open <strong>Timing → Timing analysis</strong>. Inspect the cycle count and any feedback warnings. Each crossed cycle edge adds one annotated cycle to a same-domain path.',
        'Select u_reg, then open <strong>Timing → Clock settings</strong>. Inspect the default clk domain. Expand <strong>Multiple clock domains</strong>, enter a <strong>New domain</strong> named practice, and select <strong>Add</strong>. Set <strong>Selected object domain</strong> to practice, then select <strong>Apply</strong>. Reopen Timing analysis and inspect any clock-domain crossing warning. Keep the actual RTL clock wiring in view.',
        'If the practice domain does not describe the hardware, restore the selected block to clk and remove the practice domain before saving. Save the intended marker with <strong>Save to Spec</strong> and inspect it in the Spec preview. This annotates timing; it does not insert a register or change the saved SystemVerilog body.',
    ], 'The marker and reported latency agree with the intended stage boundary. You can identify a clock-domain warning without treating it as a completed CDC verification.',
           'Toggle the timing overlay in View. Compare the canvas with an SVG export using that same visibility setting.',
           'If a marker placement is rejected, move it into empty space. If Selected object domain is absent, close the dialog, clear the selection, select one block, and reopen it. If the control remains unavailable, record that limit and leave domain assignment incomplete. Correct annotations that disagree with RTL; they do not change the implementation.',
           [("circuit-timing", "Timing analysis reports paths and annotated cycle counts."), ("circuit-clocks", "Clock settings describe the domains used for timing annotations.")], "circuit-designer.md", "Circuit Designer"),
    lesson("circuit-independent", "Work with an independent circuit", 6,
           "Save a portable circuit and set a personal shortcut.", "complete", "Circuit Designer and a downloaded portable Circuit from core tutorial 8.", [
        'Open a separate Circuit Designer root tab. Use <strong>File → Open circuit</strong> to load the portable Circuit. Inspect the binding notice: this copy saves to a browser download.',
        'Select <strong>Edit → Begin editing</strong>. Move an instance, undo the move, then redo it. Check the graph is unchanged.',
        'Select <strong>File → Save</strong>. Retain the downloaded <code>.circuit.json</code> under your tutorial TEMP_ directory. The Circuit service does not directly replace a file on your computer.',
        'Open <strong>Edit → Preferences → Actions and shortcuts</strong>. Find Fit circuit and inspect or change its binding. Resolve any reported conflict. Save the preference, then reopen the page to check it.',
        'Open the newly downloaded circuit file. Confirm the saved placement. Return to the original Spec and confirm it was not changed by editing the independent copy.',
    ], 'The newly downloaded file retains your layout, and the source Spec retains its original data.',
           'Record the original shortcut before editing and restore that value after the exercise. Use Reset defaults only with a fresh practice preference file; it does not restore previous custom settings.',
           'If you see Save to Spec, you are still in the source-bound tab. Open the portable JSON in a separate root tab before doing this exercise.',
           [("circuit-download", "Download the portable Circuit before opening an independent copy."), ("circuit-preferences", "Actions and shortcuts reports binding conflicts.")], "circuit-designer.md", "Circuit Designer"),
    lesson("assistant-restricted", "Review restricted Spec proposals", 7,
           "Decide on a pending Spec proposal and inspect its saved outcome.", "complete", "An isolated environment started with --require-designer-approval, AI Assistant, and model credentials. Do not restart a shared environment for this exercise.", [
        'Open the exact completed Spec and launch its document-bound AI Assistant. Ask: “Change only the adder explanation to add that arithmetic wraps modulo 65536. Keep the interface, RTL, and connections unchanged.”',
        'If the Assistant asks which text to edit, select the Component’s existing explanation. Wait for a pending content proposal. A text-only change does not require a structural architecture review. Inspect the proposal target and summary; pending content is not saved content.',
        'In Spec Editor, open the Activity view and <strong>AI Assistant submission history</strong>. Select <strong>Details and diff</strong> for that exact proposal. Compare the explanation before and after.',
        'Select <strong>Approve</strong> to save the stored proposal, or <strong>Reject</strong> to leave the source unchanged. The submission-history controls are Approve and Reject. Use the controls for that exact stored proposal.',
        'Inspect the saved-state result in history and reopen the Spec. If approved, the explanation persists and the hardware remains unchanged. Architecture approval in the Assistant is a separate decision from this content save.',
    ], 'You can identify pending, approved, or rejected content and verify the corresponding saved source.',
           'Prepare a second text-only proposal and reject it. Confirm its text does not appear after reopening.',
           'If valid content saves immediately, your environment uses automatic mode. Use an isolated restricted environment from the setup guide. Do not pretend that an automatic save was a pending review.',
           [("assistant-history", "Submission history identifies the proposal and its stored result."), ("assistant-review", "Review the exact diff before approving restricted content.")], "ai-assistant.md", "AI Assistant"),
    lesson("assistant-circuit", "Review a Circuit proposal", 7,
           "Accept a Circuit proposal into a private draft, then choose whether to save it.", "complete", "Circuit Designer, AI Assistant, and model credentials. Open a source-bound Design with no existing private draft.", [
        'Open the Design in Circuit Designer. Select <strong>Tools → AI Assistant</strong>. Check that this conversation is bound to this circuit.',
        'Ask: “Move u_reg to the right of u_add for clearer reading. Keep every port, instance reference, wire endpoint, and net name unchanged.” Inspect any review request and the proposed layout change.',
        'Return to Circuit Designer and open <strong>Components → Review proposals</strong>. Inspect the intended change and accept the exact proposal. If another draft is open, finish or cancel it first.',
        'Inspect the staged private draft. Acceptance does not save the source Spec. Confirm that only placement changed and all seven nets remain present.',
        'Select <strong>Save to Spec</strong> to persist the draft, or <strong>File → Cancel changes</strong> to discard it. Reopen the Design and compare the saved outcome.',
    ], 'The saved result matches your final save or cancel decision. A proposal handoff or acceptance alone is never reported as a saved Spec change.',
           'Repeat with another small placement request and cancel its accepted draft.',
           'If no proposal appears, inspect the Assistant’s last confirmed service result. Do not treat a text description of the layout as a service proposal or saved change.',
           [("circuit-proposals", "Components lists the proposal review control; it is disabled when no proposal is pending."), ("circuit-edit", "An accepted source-bound proposal still requires Save to Spec.")], "ai-assistant.md", "AI Assistant"),
    lesson("verification-plan", "Capture intent and review P1", 8,
           "Review a snapshot-bound Test Plan and freeze its first plan checkpoint.", "verification-plan", "Verification Planner runs separately from the combined launcher. Prepare its lesson plans as described in Setup. The current browser has no requirement-creation form, so the start supplies captured requirements; you will audit their source and author the missing intent. No model is required.", [
        'Open Verification Planner at the supplied URL (default port 6016). To inspect the handoff first, select <strong>+ New Plan</strong>, upload <code>registered-adder.snapshot</code>, and inspect its scopes. This snapshot is immutable; later Spec edits do not update it. Cancel this exploratory dialog.',
        'Select the plan named <strong>Tutorial plan</strong> with your run name in the plan selector. Find its exact name and ID in <code>verification/starts.json</code>. This prepared start includes the imported snapshot, source audit, three captured requirements, and two ready intents, with no P1 checkpoint.',
        'Open <strong>Source &amp; Requirements</strong>. Inspect each source audit disposition and the exact source locator for reset, capture, and hold requirements. The prepared plan is a small teaching example, not a completeness claim for all hardware behavior.',
        'Inspect the two ready intents, then select <strong>+ Intent</strong> to add <strong>Disabled output holds</strong>. Select Register behavior as its Section, link the captured hold requirement, and copy its Given, When, Then, and output observation from the table below. Select <strong>Save &amp; Mark Ready</strong>. There must now be three ready intents.' + table(["Intent", "Given", "When", "Then"], [[x[1], x[2], x[3], x[4]] for x in EXAMPLE["verification"]]),
        'Select <strong>Review Plan</strong>. Read the checklist and the blocker list. Enter your reviewer label and comment. Confirm the review only after the checklist is clear. Inspect the resulting P1 checkpoint. Draft edits made later do not change that frozen checkpoint.',
    ], 'The selected plan refers to the intended source snapshot and has one reviewed P1 checkpoint. No hardware tests were executed.',
           'Create a draft intent for modulo wraparound (65535 + 1). Identify the missing fields needed before it could be ready.',
           'If review is blocked, inspect unresolved audits, requirements, or intent fields. Do not bypass the checklist. If port 6016 is unavailable, start the separate service using Setup.',
           [("verification-source", "A Test Plan is created from an imported source snapshot."), ("verification-plan", "Review the plan checklist before freezing P1.")], "verification-planner.md", "Verification Planner"),
    lesson("verification-coverage", "Map coverage and import evidence", 8,
           "Freeze coverage policy and inspect clearly marked synthetic evidence.", "verification-coverage", "Verification Planner and the prepared Tutorial coverage plan. It includes reviewed P1 and checking policies for reset and capture, but no hold objective or C1.", [
        'Select <strong>Tutorial coverage</strong> with your run name in the plan selector, then open <strong>2 · Coverage &amp; Evidence</strong>. Inspect the correctness objective for each reset, capture, and hold intent.',
        'Select <strong>+ Objective</strong>. Enter Disabled output holds, choose the correctness family, and link the Disabled output holds intent. Enter the expected observation “y remains 16 when enable=0”, set <strong>Acceptance Metric</strong> to <strong>Pass Verdict Required</strong>, and select <strong>Save Objective</strong>. Review the resulting evidence policy. Each intent needs a checking objective; a scenario hit alone is insufficient.',
        'Select <strong>Review Coverage (C1)</strong>, choose the prepared P1 checkpoint, inspect the checklist, and confirm. This freezes the objectives and policies against that P1.',
        'For the evidence exercise, select <strong>Tutorial evidence</strong> with your run name. This separate prepared plan supplies C1, an evaluation profile, and a campaign. Select its campaign, then <strong>Import Results</strong>. Paste <code>verification/synthetic-results.json</code>, select the matching profile, and use <strong>Stage &amp; Validate Preview</strong>. Review the preview, then commit the import.',
        'Inspect Coverage Matrix, Gaps, Evidence Runs, and Trace. The producer is explicitly synthetic. Its observations teach result import; they do not prove hardware simulation. A later passing run does not erase an earlier failure; a documented disposition is required.',
    ], 'You have created C1 on one teaching plan and imported a synthetic run into a separate prepared evidence plan. Provenance remains visible.',
           'Inspect one checking objective and identify its minimum evaluation requirement. Explain why zero observations cannot establish full coverage.',
           'If import reports a checkpoint or profile mismatch, use the Tutorial evidence plan and its matching result file together. Do not change result identities to conceal a mismatch.',
           [("verification-coverage", "Coverage objectives and evidence policy are separate from scenario activity."), ("verification-evidence", "Stage and validate a synthetic result import before committing it.")], "verification-planner.md", "Verification Planner"),
    lesson("verification-implementation", "Review recipes and generate references", 8,
           "Freeze I1 and inspect reference artifacts without claiming an executed test.", "verification-implementation", "Verification Planner and the prepared Tutorial implementation plan. It includes P1, C1, target bindings, and one ready recipe; no I1 is present.", [
        'Select <strong>Tutorial implementation</strong> with your run name in the plan selector. Open <strong>3 · Implementation</strong>, then <strong>Target Bindings</strong>. Inspect the six signal names, widths, input-drive and output-sample permissions, rising clock, and synchronous reset.',
        'Open <strong>Recipes</strong>. Inspect the ready recipe and its Test IR. It drives reset, captures 7 + 9, then changes inputs with enable low. Inspect the explicit checks for zero, sixteen, and held sixteen. Expected values are independently stated reference values.',
        'Inspect <strong>Backend Plugins</strong>. The selected backend is <code>spec2gds.reference.bundle</code> version 1.0.0. It publishes reference files and a synthetic result template.',
        'Select <strong>Review Implementation (I1)</strong>. Choose C1, read blockers and the checklist, then confirm with your reviewer label. Open <strong>Generate Artifacts</strong>, select I1 and the reference backend, and use <strong>Preview Capabilities &amp; Preflight</strong> before running.',
        'Inspect <strong>Generated Artifacts</strong>. Open the Test IR, target bindings, recipe, producer manifest, validation report, and synthetic result template. Hardware simulation occurs outside Verification Planner and its results must be imported separately.',
    ], 'I1 identifies the reviewed implementation inputs. Reference generation succeeds and its artifacts identify their source. No executable hardware test or simulation pass is claimed.',
           'Find the output sample binding and the check that maps its observation to a correctness objective.',
           'If generation is blocked, inspect missing mappings, permissions, upstream C1, and recipe readiness. Resolve those source issues before repeating preflight.',
           [("verification-bindings", "Target bindings map observations to concrete ports and permissions."), ("verification-implementation", "Implementation review and reference generation retain separate results.")], "verification-planner.md", "Verification Planner"),
    lesson("systemc-cycle", "Generate cycle-accurate SystemC", 7,
           "Publish a native SystemC model from explicit wire topology and leaf bodies.", "complete", "Spec Editor, CIRCT with circt-verilog and the spec2gds-systemc-emit tool, and SystemC. Ask the environment maintainer to prepare this optional toolchain first.", [
        'Open the completed registered-adder Design. Confirm six unsigned physical ports, full-width direct connections, one driver per signal, and a nonempty SystemVerilog section on each leaf.',
        'Inspect availability diagnostics in Options. Select <strong>Options → Generate cycle-accurate SystemC</strong> to start the job directly. This Activity reads saved structure and SystemVerilog, not narrative guesses.',
        'Wait for the job result. Inspect tool versions, source revision, source Section records, output path, and the published file list. The model uses native SystemC classes after compilation.',
        'Read the generated project README. If the SystemC development toolchain is available, follow its exact configure/build instructions from the reported output directory. Do not substitute an RTL project directory.',
        'Compare the generated adder and register structure with the source. Keep generation, compilation, and simulation outcomes separate. Generation alone does not demonstrate functional simulation.',
    ], 'The published native model identifies the same saved Design and its two leaf implementations, or reports a specific missing tool or unsupported construct.',
           'Find where the generated register implements synchronous reset and enable. Compare it with the saved body.',
           'If CIRCT, the emitter, or SystemC is missing, record this guide as incomplete. Unsupported constructs require a supported source implementation, not an inferred replacement.',
           [("spec-instances", "The source Design supplies explicit hierarchy and wire topology."), ("systemc-options", "Compatible SystemC Activities appear with target-specific availability.")], "systemc-activities.md", "SystemC Activities"),
    lesson("systemc-at", "Generate an approximately-timed skeleton", 7,
           "Publish a TLM skeleton from a separate one-to-one interface example.", "tlm", "Spec Editor and tlm-start.spec from the preparation command. SystemC and CMake are needed only for the optional build. The wire-based adder is not a compatible TLM input.", [
        'Open <code>tlm-start.spec</code>. Inspect TLM practice: one initiator instance and one target instance. The prepared source joins their sockets with one interface connection. The wire-only preview omits that connection and reports an unsupported item. Check the actual socket binding and connection count in the generated project below. The adder’s ad-hoc wire topology is not a compatible input.',
        'Review the TLM practice Design and Activity availability, then select <strong>Options → Generate SystemC AT skeleton</strong> to start the job directly.',
        'Inspect the completed report and output path. Open CMakeLists.txt, the generated Component and Design headers, main program, and generation manifest.',
        'Find the initiator-to-target socket binding. Read the generated README before configuring and building the project with your SystemC installation. Retain outputs below the tutorial TEMP_ directory.',
        'Inspect the scaffold’s default timing and response behavior. It is a structural starting point for a performance model; it does not implement the registered adder’s functional behavior or infer a performance specification.',
    ], 'The generated project preserves one initiator, one target, and their explicit binding. The report identifies the selected TLM Design and source revision.',
           'Identify the generated top class and the simulation duration in main.cpp. Separate those scaffold defaults from source requirements.',
           'If the Activity rejects ad-hoc wires or fan-out, confirm that you opened tlm-start.spec. Do not run this guide on the registered-adder checkpoint.',
           [("tlm-source", "The separate TLM example has two instances; its interface connection is omitted from the wire preview."), ("tlm-activity", "The AT skeleton Activity publishes its own report and source revision.")], "systemc-activities.md", "SystemC Activities"),
]


def sidebar(current):
    links = '<a class="overview-link" href="index.html">Course overview</a>'
    links += '<span class="nav-label">CORE PATH · 9 GUIDES</span>'
    for index, item in enumerate(CORE, 1):
        active = ' aria-current="page"' if current == item["slug"] else ''
        links += f'<a href="{item["slug"]}.html"{active}><span class="nav-number">{index:02}</span><span>{item["title"]}</span></a>'
    links += '<span class="nav-label">KEEP EXPLORING</span><a href="index.html#extensions">Optional feature guides</a><a href="setup.html">Environment and checkpoints</a><a href="example.html">Example reference</a>'
    return '<nav class="course-nav" aria-label="Tutorial navigation">' + links + '</nav>'


def shell(title, body, current="", description="Short, practical tutorials for Spec Editor, Circuit Designer, AI Assistant, and Verification Planner."):
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · spec2gds tutorials</title><meta name="description" content="{html.escape(description)}">
<link rel="stylesheet" href="assets/tutorials.css"><script src="assets/tutorials.js" defer></script></head>
<body><a class="skip-link" href="#main">Skip to content</a>
<header class="site-header"><a class="brand" href="index.html"><span class="brand-mark" aria-hidden="true">s²</span>spec2gds <span class="brand-divider">/</span> <span class="brand-section">Learn</span></a><a href="setup.html" class="header-link">Environment setup <span aria-hidden="true">↗</span></a><button class="nav-toggle" aria-expanded="false" aria-controls="sidebar">Lessons</button></header>
<div class="page-grid"><aside id="sidebar" class="sidebar">{sidebar(current)}<p class="sidebar-note">Learn one action.<br>Check the saved result.</p></aside>
<main id="main" tabindex="-1">{body}<footer class="page-footer"><span>spec2gds · Designer tutorials</span><a href="../TERMINOLOGY.md">Terms</a><a href="validation.html">Validation status</a></footer></main></div></body></html>'''


def lesson_page(item, index):
    core = item["track"] == "Core"
    label = f'CORE {index + 1:02} / 09' if core else item["track"].upper()
    start = f'{item["start"]}-start.spec' if item["start"] not in ["verification-plan", "verification-coverage", "verification-implementation", "tlm"] else ('tlm-start.spec' if item["start"] == "tlm" else 'verification/starts.json')
    before = f'<p>{item["needs"]}</p><div class="checkpoint"><span class="eyebrow">START HERE</span><p><code>TEMP_tutorials/my-run/{start}</code></p><a href="setup.html#checkpoints">Prepare or reset a lesson →</a></div>'
    if item["slug"] == "01-first-spec":
        before += '<p>The prepared start is an empty reference. For this lesson, create a separate fresh <code>my-adder.spec</code> file.</p>'
    if item["slug"] == "05-compose-design":
        before += '<p>This lesson adds a supplied containing interface to the earlier results. Continue from your own Spec with the listed setup, or use this prepared checkpoint.</p>'
    body = f'<div class="breadcrumbs"><a href="index.html">Tutorials</a><span>/</span>{item["track"]}</div><article><header class="lesson-heading"><p class="eyebrow">{label} <span>· {item["minutes"]} MINUTES</span></p><h1>{item["title"]}</h1><p class="lead">{item["goal"]}</p></header>'
    body += '<nav class="article-nav" aria-label="On this page"><a href="#before">Before you start</a><a href="#actions">Actions</a><a href="#check">Check your result</a><a href="#practice">Try it</a></nav>'
    body += f'<section id="before"><h2>Before you start</h2>{before}</section><section id="actions"><h2>Actions</h2><ol class="actions">'
    for i, action in enumerate(item["actions"]):
        body += f'<li><div>{action}</div></li>'
        if i == 1:
            body += '</ol>' + photo(*item["pictures"][0]) + f'<ol class="actions" start="{i + 2}">'
    body += '</ol>' + photo(*item["pictures"][1]) + '</section>'
    body += f'<section id="check" class="result"><span class="eyebrow">SAVED-STATE CHECK</span><h2>Check your result</h2><p>{item["check"]}</p></section><section id="practice"><h2>Try it yourself</h2><p>{item["practice"]}</p></section><section id="recovery"><h2>If it fails</h2><p>{item["failure"]}</p></section>'
    following = CORE[index + 1] if core and index + 1 < len(CORE) else None
    next_link = f'<a class="next-guide" href="{following["slug"]}.html"><span class="eyebrow">NEXT GUIDE</span><strong>{following["title"]} <span aria-hidden="true">→</span></strong></a>' if following else '<a class="next-guide" href="index.html#extensions"><span class="eyebrow">CONTINUE</span><strong>Explore another feature →</strong></a>'
    body += f'<section id="continue"><h2>Continue</h2>{next_link}<p class="reference-link">Reference: <a href="../{item["reference"]}">{item["reference"].removesuffix(".md").replace("-", " ")}</a> · <a href="example.html">Complete example</a></p></section></article>'
    return shell(item["title"], body, item["slug"], item["goal"])


def index_page():
    duration = sum(x["minutes"] for x in CORE)
    body = f'''<section class="course-hero"><p class="eyebrow">THE DESIGNER’S STARTING POINT</p><h1>From your first Spec<br>to a saved circuit.</h1><p class="lead">Build a small registered adder. Learn the controls, make a change, and check what was saved.</p><div class="hero-meta"><span>9 core guides</span><span>5–8 minutes each</span><span>About {duration} minutes total</span></div><a class="button" href="01-first-spec.html">Start with your first Spec <span aria-hidden="true">→</span></a><a class="hero-secondary" href="setup.html#checkpoints">Jump in with a prepared checkpoint</a></section>
<div class="course-intro"><p>For designers who know basic digital hardware and are new to spec2gds. Start with the running environment supplied to you. No model key is needed for manual authoring; the Assistant lesson has a prepared fallback.</p><p>Use one example throughout: a 16-bit modulo adder, followed by an enabled register. Every guide has a fresh starting point and a visible result check.</p></div>
<section id="core"><div class="section-heading"><div><p class="eyebrow">LEARN THE BASICS</p><h2>Your core path</h2></div><span>Read · Do · Check</span></div><ol class="lesson-list">'''
    for i, item in enumerate(CORE, 1):
        body += f'<li><a href="{item["slug"]}.html"><span class="lesson-number">{i:02}</span><span><strong>{item["title"]}</strong><span class="lesson-summary">{item["goal"]}</span></span><span class="lesson-time">{item["minutes"]} min <span aria-hidden="true">↗</span></span></a></li>'
    body += '</ol></section>' + note('Review edition', 'The guides are ready for learner review. A new designer must still check the first three guides, the full core path, and the independent challenge. Times are estimates. Optional tracks remain review material until the core path passes that review. See the <a href="validation.html">validation and review checklist</a>.')
    body += '<section id="extensions"><p class="eyebrow">CHOOSE WHAT YOU NEED NEXT</p><h2>Explore more features</h2><p>These guides use separate prepared copies. Start any track after the core path. Each guide takes 5–8 minutes.</p><div class="extension-grid">'
    for track in dict.fromkeys(x["track"] for x in EXTRAS):
        body += f'<div class="extension-group"><h3>{track}</h3><ul>'
        for item in EXTRAS:
            if item["track"] == track:
                body += f'<li><a href="{item["slug"]}.html">{item["title"]}<span>{item["minutes"]} min →</span></a></li>'
        body += '</ul></div>'
    body += '</div></section>' + note('What a result means', 'A draft is not a saved Spec. Architecture approval is not a saved result. Lint is not functional simulation. Each guide tells you which result to check.')
    body += '<section class="resource-row"><a href="setup.html"><strong>Need an environment?</strong><span>Setup, prerequisites, and reset instructions →</span></a><a href="example.html"><strong>Keep the example nearby</strong><span>Ports, behavior, connection map, and prompt →</span></a></section>'
    return shell("Get started", body)


def setup_page():
    body = '''<article><header class="lesson-heading"><p class="eyebrow">BEFORE YOUR FIRST GUIDE</p><h1>Environment and checkpoints</h1><p class="lead">Use a ready environment, or prepare a local one without changing the shared service configuration.</p></header>
<section><h2>Use a ready environment</h2><p>Ask its maintainer for the Spec Editor, Circuit Designer, and AI Assistant URLs, plus a writable absolute server-local tutorial directory. Default ports are 6010, 6012, and 6013. Verification Planner runs separately on 6016. Use the actual host and ports printed by your environment; <code>0.0.0.0</code> is not a browser address.</p><p>Keep browser downloads, scratch files, Activity outputs, and validation evidence under the repository’s ignored <code>TEMP_tutorials/</code> directory. Browser-local paths and server-local paths can refer to different machines.</p></section>
<section id="checkpoints"><h2>Prepare a fresh set of starts</h2><p>On the service host, run this from the repository root after Python setup:</p>''' + code('uv run python scripts/prepare_tutorials.py --output TEMP_tutorials/my-run') + '''<p>The command uses the production Spec HTTP API in a private in-process service. It does not need a model or alter a running editor. It creates a separate start for each core lesson, the complete source, a snapshot, a TLM example, and prepared Verification Planner records. It prints absolute paths in <code>starts.json</code>.</p><p>Use <strong>File → Open Spec</strong> to open the start named in a guide. These are real editable files. To reset after editing one, prepare a new directory such as <code>TEMP_tutorials/retry-02</code>. The command refuses an existing output directory. Do not overwrite a start or someone else’s work.</p><p>Continue with your own Spec where the previous result matches the next lesson. Guide 5 supplies an additional containing interface; its start includes that setup. Each start is complete for its named lesson. The preparation does not claim lint or simulation success.</p></section>
<section><h2>Install and start locally</h2><p>This section is for the environment maintainer. The combined launcher targets Linux or WSL. Install Python 3.12+, uv, Node.js 24.2+, and lsof. RTL checks also need Verilator 5.x and GNU Make. Package setup can need GitHub Packages read access through <code>NODE_AUTH_TOKEN</code>; keep credentials out of files and tutorial screenshots.</p>''' + code('scripts/setup-all.sh\nuv run python scripts/prepare_tutorials.py --output TEMP_tutorials/my-run') + '''<p>Point this process at the run-local registry so Activity outputs and preferences stay below TEMP_. Keep the tracked registry unchanged:</p>''' + code('export SPEC_EDITOR_STATE_ROOT="$PWD/TEMP_tutorials/my-run/spec-state"\nexport ASSISTANT_STATE="$PWD/TEMP_tutorials/my-run/assistant-state"\nexport SPEC2GDS_SCRATCH_ROOT="$PWD/TEMP_tutorials/my-run/scratch"\nexport SPEC_DOCUMENT_ROOT="$PWD/TEMP_tutorials/my-run/documents"\nscripts/serve-all.sh start --service-config "$PWD/TEMP_tutorials/my-run/services.json"') + '''<p>Use the printed browser URLs. If model credentials are not already configured, set <code>OPENAI_API_KEY</code> in the launching environment before starting. The first three manual guides work without it. Never paste a credential into a guide, prompt, screenshot, or log.</p><p>To use restricted Spec content review in an isolated environment, add <code>--require-designer-approval</code> when starting. Do not restart a shared environment for a tutorial. Stop only the stack that you started:</p>''' + code('scripts/serve-all.sh stop') + '''</section>
<section><h2>Start Verification Planner separately</h2>''' + code('uv run verification-planner --service-config TEMP_tutorials/my-run/services.json --storage-dir TEMP_tutorials/my-run/verification/planner-data') + '''<p>Open its printed URL. Select the prepared plans by name in the plan selector. The first guide also shows snapshot upload in New Plan. Later Spec edits do not change the imported snapshot.</p><p>The <code>verification/</code> directory contains a private prepared service data directory, a starts.json file with each plan name and ID, and a clearly marked synthetic result file. To add starts to an already running Verification Planner, give its URL to the preparation command with <code>--planner-url http://127.0.0.1:6016</code>. This adds new tutorial plans and does not modify existing ones. No simulator is run during preparation. Use these prepared plans directly: portable .vplan import currently does not restore all review prerequisites.</p></section>
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
<section><h2>Run the checks</h2>''' + code('uv run python scripts/build_tutorials.py --check\nuv run python -m pytest tests/test_tutorials.py -q\nscripts/test-all.sh fast --output TEMP_tutorials/evidence/fast\nscripts/test-all.sh integration --scope spec,circuit,assistant,verification,activities --output TEMP_tutorials/evidence/integration') + '''<p>The fast profile includes exactly three live model checks. Missing credentials or tools make it incomplete. Keep the report’s executed commands, exit results, and coverage limits. Run broad regression if implementation changes cross-application contracts, persistence, shared runtime, or the Activity SDK. This tutorial change does not change those contracts.</p></section>
<section><h2>Guide acceptance record</h2><p>For each guide, record its title, code revision, start path, browser, service URLs, prerequisites, elapsed practice time, actions completed, final source revision, expected versus actual result, and evidence paths. Capture at least two focused UI states. Store the run under an ignored repository TEMP_ directory.</p><ul><li>Reopen the Spec after a successful save.</li><li>Compare Spec and Circuit after Save to Spec.</li><li>Check invalid drafts, unavailable tools, stale lint, and missing model credentials.</li><li>For Assistant exercises, use live model access and inspect saved results; do not require identical prose.</li><li>For RTL, retain the actual published project and its lint log.</li><li>For Verification Planner, retain snapshot and checkpoint identities and synthetic evidence provenance.</li><li>Record SystemC generation, compilation, and simulation separately.</li></ul></section>
<section><h2>Screenshot maintenance</h2><p>The page images are focused captures of the actual applications. They illustrate controls and source data; they are not proof of a learner’s run or live model success. Keep capture originals and reports below TEMP_. Publish only selected documentation images in the tutorial assets directory, with no credentials or private design data.</p></section>
<section><h2>Human review form</h2><ul><li>Can the designer find each control without undocumented help?</li><li>Does each guide fit its 5–8 minute estimate, excluding installation and tool queue time?</li><li>Can the designer restart from its prepared checkpoint?</li><li>Can the designer explain what was saved and what remains unverified?</li><li>Can the designer complete guide 9 without a supplied click sequence?</li></ul><p>Record findings in the evidence directory. Correct instructions and repeat the affected guide before marking the course ready.</p></section></article>'''
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

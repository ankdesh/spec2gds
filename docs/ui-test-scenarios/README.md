# Designer acceptance catalogue

This catalogue contains **60 cases**: 10 Spec Editor complete journeys, 10 Circuit
Designer complete journeys, and 20 focused checks per application. It specifies
desired designer outcomes, including capabilities that may be missing today.
No case is an executed acceptance result. It makes no release-readiness claim.

The 20 complete journeys are for a **human or computer-use executor**. Do not
convert them into Playwright scripts. They assess complete readable Specs and
usable Circuits, with manual UI authoring and without AI Assistant authoring.
The 40 focused checks specify **future Playwright coverage**. This delivery adds
Markdown definitions, not executable Playwright tests or new profile selection.

## Start here

1. Read this execution guide and the [scoring guide](SCORING.md).
2. Copy [RUN-TEMPLATE.md](RUN-TEMPLATE.md) into a new temporary run directory.
3. Select cases in a copy of the index below. All 60 are selected by default.
   To prune, mark `[ ]` and record an exclusion reason before execution. Keep IDs
   stable. Retain failed evidence if selection changes after a run.
4. Use each case's complete linked inputs and numbered actions. A missing control
   is a finding, not permission to bypass the UI or invent a menu entry.
5. Report four separate group scores and completion counts. There is no combined
   overall score. Functional simulation remains unverified in this catalogue.

## Execution guide

### Environment and outputs

Use a tested local build and record its code revision, dirty state, service
addresses, serving mode, Chromium version, and prerequisite tools. See the
[development guide](../development.md) for service setup. Use independent test
sources and dedicated service bindings when other designers are working.

Use desktop Chromium at 1440×900 and 1024×768. Inspect Spec Editor compact
navigation at 560×760. Both implemented themes are required: Spec Editor
`obsidian` and `clean`; Circuit Designer `blueprint-slate` and `obsidian`.
These are desktop-window checks, not a claim of mobile or touch coverage.

Set the run root to `/tmp/spec2gds-acceptance/RUN-ID/`. Create a child directory
for each case ID. Save `.spec` files, Circuit files, screenshots, recordings,
downloads, Activity outputs, logs, and completed result Markdown there.
Configure the Activity scratch directory in a temporary copy of the documented
service configuration so output also stays beneath the run root. Do not edit
tracked configuration or write temporary artifacts into source directories.
Ensure the browser download location is inside the run directory.
For a dedicated test-service instance, set `SPEC_DOCUMENT_ROOT` to the run root
and `SPEC_EDITOR_STATE_ROOT` to its `spec-state` child before starting services.
Keep Circuit preferences and service logs in that temporary configuration's
run directory as well. Choose free service/UI ports using the development guide;
record the resulting addresses so the browser cannot use another run's binding.
`RUN-ID` is a unique label chosen for this run; `CASE-DIR` means that run's
child directory named for the current case ID. Substitute actual paths before
entering a file path or running a command.

### Authoring boundary

For complete journeys, create the Spec, Component definitions, ports, bodies,
hierarchy, and connections through normal UI controls. Setup can start services,
configure temporary storage, and supply input text. Read-only inspection of
published artifacts and identities is permitted. Backend writes, archive edits,
fixture injection, CLI generation, and AI Assistant authoring cannot substitute
for a missing authoring action in a complete journey.

For future focused Playwright checks, public real-service fixture setup can
prepare prerequisites. It must not perform the operation being assessed or fake
successful writes. Put the browser action and saved-state assertions in the
maintained existing suite, following the [testing strategy](../testing-strategy.md).

Current verified entry labels include Spec Editor **File → New Spec**, **File →
Open Spec**, **Options → Add component…**, **Options → Add wire port…**, **Options →
Add SystemVerilog section…**, **Save to Spec**, and **Options → Generate RTL**.
Circuit Designer includes **Edit → Begin editing**, **Connect → New connection**,
**Components → Component catalog**, and **File → Download**. Other steps express
the intended operation. Do not invent a control name when the required UI path
does not exist. Capture the attempted entry point and mark a capability gap.

### Readable content and structural inputs

Input packs give complete explanations, interfaces, and body-only SystemVerilog.
Definition references such as `add32` are catalogue aliases. Actual stable
Component/Design IDs and generated module filenames can differ. Record them and
compare them across edits; never assume a display rename creates a new identity.
Port IDs and instance IDs in the packs are exact hardware identifiers.

A leaf requires the supplied text, Ports, and SystemVerilog Sections. A composite
requires its boundary interface, Component and Design explanations, explicit
internal-Design relation, child instances, and named connections. Its structural
parent SV Section is intentionally absent. Each reachable behavioral leaf still
requires its supplied body; placeholder tie-offs are not acceptable substitutes.

Case criteria assess explanation usefulness, not just the presence of text.
Check whether a new hardware reader can identify purpose, operation, interfaces,
clock/reset rules, assumptions, corner cases, and verification limits. Formatting
must preserve those distinctions and keep the full content reachable.

### Generation and lint

Generation uses stored interfaces, parameters, bodies, and explicit wiring. It
does not infer behavior from narrative or create hardware registers from cycle
markers. See the [RTL contract](../rtl-generation.md). Launch generation through
the UI on the saved target and obtain its complete published project. Missing
project access is a capability finding, not a reason to generate another project
with a CLI. Record the target and saved source revision used by the Activity.

Run the published project's command from its own directory. For example, after
obtaining the actual project at this path:

```bash
make -C /tmp/spec2gds-acceptance/run-001/SE-E2E-01/rtl-project lint
```

Retain the exact command, working directory, exit status, tool version, and full
diagnostics in that case directory. Do not add warning suppressions to force a
pass. A missing Verilator 5.x or GNU Make is an external prerequisite block.
An error in the generated project is a product finding.

Reference-input lint uses temporary wrappers only to check the supplied corpus.
It is separate from actual UI generation and cannot satisfy a case's generation
or lint criterion. Lint is not functional simulation. Reference examples, cycle
descriptions, and arithmetic vectors remain intended results until separately
simulated; this catalogue does not request or claim that simulation.

### Capture a failure without hiding it

Keep the failing action, expected result, visible result, active source, and
before/after data. If an essential UI capability is missing, fail that criterion
and score dependent unachieved outcomes zero with the cause recorded. Continue
independent observations where useful. Do not replace the goal with an easier
design, flatten required hierarchy, silently omit a connection, or mark a gap
as an environmental skip.

For an external prerequisite block, leave the affected criteria unverified and
the case score incomplete. For a product failure, retain the first evidence and
any diagnostic reruns. Only the designer can decide whether to exclude a desired
capability from the release scope; a passing current test does not settle that
decision.

## Regression mapping for the 40 focused checks

Each focused case names its scopes and fast suitability. Future Spec Editor
browser checks belong in maintained Spec suites; Circuit Designer checks belong
in maintained Circuit suites. Real-service and cross-application cases belong
in `tests/ui-scenarios`. Source round-trips use `spec,circuit`; RTL Activity
checks also name `activities`. Add lower-layer protection at the lowest effective
layer when implementing a confirmed defect. Avoid duplicate regression copies.

Use affected integration profiles for detailed checks and full regression for
release evidence. Fast candidates must stay short and deterministic; retain its
exactly three existing short live model checks. Do not put the 20 manual journeys
or a model-based quality judge into fast. These mappings are intended additions,
not claims that the current profiles execute these new Markdown cases.

## Selection and exclusion record

Copy the four tables below into a run record. Clear a checkbox to exclude a case
and add its reason, decision date, and reviewer. Record all excluded IDs, even
when an entire group is excluded. An unrun selected case is not a pass.

## Spec Editor complete journeys

| Selected | Case | Goal |
| --- | --- | --- |
| [x] | [SE-E2E-01](spec-editor/end-to-end/SE-E2E-01.md) | Create a complete 32-bit unsigned adder Spec |
| [x] | [SE-E2E-02](spec-editor/end-to-end/SE-E2E-02.md) | Create an enabled registered 32-bit adder |
| [x] | [SE-E2E-03](spec-editor/end-to-end/SE-E2E-03.md) | Create and revise a programmable 16-bit timer |
| [x] | [SE-E2E-04](spec-editor/end-to-end/SE-E2E-04.md) | Create a four-entry synchronous byte FIFO |
| [x] | [SE-E2E-05](spec-editor/end-to-end/SE-E2E-05.md) | Create a byte-enabled four-word register bank |
| [x] | [SE-E2E-06](spec-editor/end-to-end/SE-E2E-06.md) | Create an 8N1 UART transmitter |
| [x] | [SE-E2E-07](spec-editor/end-to-end/SE-E2E-07.md) | Create a streaming CRC-16 accumulator |
| [x] | [SE-E2E-08](spec-editor/end-to-end/SE-E2E-08.md) | Create a four-request round-robin arbiter |
| [x] | [SE-E2E-09](spec-editor/end-to-end/SE-E2E-09.md) | Create an eight-bit SPI Mode 0 master |
| [x] | [SE-E2E-10](spec-editor/end-to-end/SE-E2E-10.md) | Evolve and release a hierarchical adder Spec |
## Circuit Designer complete journeys

| Selected | Case | Goal |
| --- | --- | --- |
| [x] | [CD-E2E-01](circuit-designer/end-to-end/CD-E2E-01.md) | Build a reusable hierarchical 64-bit adder |
| [x] | [CD-E2E-02](circuit-designer/end-to-end/CD-E2E-02.md) | Build a two-stage registered addition datapath |
| [x] | [CD-E2E-03](circuit-designer/end-to-end/CD-E2E-03.md) | Build a selectable registered add/subtract datapath |
| [x] | [CD-E2E-04](circuit-designer/end-to-end/CD-E2E-04.md) | Build a four-lane register bank |
| [x] | [CD-E2E-05](circuit-designer/end-to-end/CD-E2E-05.md) | Build a five-byte ready/valid stream buffer |
| [x] | [CD-E2E-06](circuit-designer/end-to-end/CD-E2E-06.md) | Build a four-channel sensor threshold monitor |
| [x] | [CD-E2E-07](circuit-designer/end-to-end/CD-E2E-07.md) | Build a timer-triggered UART status transmitter |
| [x] | [CD-E2E-08](circuit-designer/end-to-end/CD-E2E-08.md) | Build an SPI capture buffer |
| [x] | [CD-E2E-09](circuit-designer/end-to-end/CD-E2E-09.md) | Build a nested four-operation ALU |
| [x] | [CD-E2E-10](circuit-designer/end-to-end/CD-E2E-10.md) | Expand and release a four-channel counter monitor |
## Spec Editor focused checks

| Selected | Case | Goal |
| --- | --- | --- |
| [x] | [SE-FOCUS-01](spec-editor/focused/SE-FOCUS-01.md) | Create a Spec with title, path, and stable identity |
| [x] | [SE-FOCUS-02](spec-editor/focused/SE-FOCUS-02.md) | Reject a failed Open without replacing the active Spec |
| [x] | [SE-FOCUS-03](spec-editor/focused/SE-FOCUS-03.md) | Rename a Spec while retaining its identity |
| [x] | [SE-FOCUS-04](spec-editor/focused/SE-FOCUS-04.md) | Create and rename a Component |
| [x] | [SE-FOCUS-05](spec-editor/focused/SE-FOCUS-05.md) | Create a Design and place an existing Component instance |
| [x] | [SE-FOCUS-06](spec-editor/focused/SE-FOCUS-06.md) | Add scalar and packed-range wire ports |
| [x] | [SE-FOCUS-07](spec-editor/focused/SE-FOCUS-07.md) | Edit direction, width, and description of a wire port |
| [x] | [SE-FOCUS-08](spec-editor/focused/SE-FOCUS-08.md) | Reject invalid ranges and duplicate port IDs |
| [x] | [SE-FOCUS-09](spec-editor/focused/SE-FOCUS-09.md) | Author parameters and symbolic port ranges |
| [x] | [SE-FOCUS-10](spec-editor/focused/SE-FOCUS-10.md) | Render a substantial readable explanation |
| [x] | [SE-FOCUS-11](spec-editor/focused/SE-FOCUS-11.md) | Add and edit a SystemVerilog Section |
| [x] | [SE-FOCUS-12](spec-editor/focused/SE-FOCUS-12.md) | Save unverified SystemVerilog and report explicit verification errors |
| [x] | [SE-FOCUS-13](spec-editor/focused/SE-FOCUS-13.md) | Cancel and confirm SystemVerilog deletion |
| [x] | [SE-FOCUS-14](spec-editor/focused/SE-FOCUS-14.md) | Cancel a text draft and restore the saved view |
| [x] | [SE-FOCUS-15](spec-editor/focused/SE-FOCUS-15.md) | Preserve a stale draft during a competing save |
| [x] | [SE-FOCUS-16](spec-editor/focused/SE-FOCUS-16.md) | Ignore a delayed response after switching Specs |
| [x] | [SE-FOCUS-17](spec-editor/focused/SE-FOCUS-17.md) | Refresh and reopen all saved content |
| [x] | [SE-FOCUS-18](spec-editor/focused/SE-FOCUS-18.md) | Keep clipboard and keyboard edits local to the active field |
| [x] | [SE-FOCUS-19](spec-editor/focused/SE-FOCUS-19.md) | Publish RTL generation status and correct artifacts |
| [x] | [SE-FOCUS-20](spec-editor/focused/SE-FOCUS-20.md) | Read long content in both themes and compact windows |
## Circuit Designer focused checks

| Selected | Case | Goal |
| --- | --- | --- |
| [x] | [CD-FOCUS-01](circuit-designer/focused/CD-FOCUS-01.md) | Launch the correct bound Design from the correct Spec |
| [x] | [CD-FOCUS-02](circuit-designer/focused/CD-FOCUS-02.md) | Keep a leaf Component preview read-only |
| [x] | [CD-FOCUS-03](circuit-designer/focused/CD-FOCUS-03.md) | Begin editing and cancel without changing source |
| [x] | [CD-FOCUS-04](circuit-designer/focused/CD-FOCUS-04.md) | Create a local definition and its first instance |
| [x] | [CD-FOCUS-05](circuit-designer/focused/CD-FOCUS-05.md) | Reuse a definition and retain distinct instance identities |
| [x] | [CD-FOCUS-06](circuit-designer/focused/CD-FOCUS-06.md) | Connect compatible terminals by dragging |
| [x] | [CD-FOCUS-07](circuit-designer/focused/CD-FOCUS-07.md) | Create a named connection through the dialog |
| [x] | [CD-FOCUS-08](circuit-designer/focused/CD-FOCUS-08.md) | Reject invalid directions and multiple drivers |
| [x] | [CD-FOCUS-09](circuit-designer/focused/CD-FOCUS-09.md) | Preserve numeric bus slices and reject invalid bounds |
| [x] | [CD-FOCUS-10](circuit-designer/focused/CD-FOCUS-10.md) | Select and multi-select without changing topology |
| [x] | [CD-FOCUS-11](circuit-designer/focused/CD-FOCUS-11.md) | Pan, zoom, and fit without moving the circuit |
| [x] | [CD-FOCUS-12](circuit-designer/focused/CD-FOCUS-12.md) | Move and nudge instances with undo and redo |
| [x] | [CD-FOCUS-13](circuit-designer/focused/CD-FOCUS-13.md) | Edit route bends and honor route locks |
| [x] | [CD-FOCUS-14](circuit-designer/focused/CD-FOCUS-14.md) | Arrange a diagram while preserving constraints |
| [x] | [CD-FOCUS-15](circuit-designer/focused/CD-FOCUS-15.md) | Create and edit containing boundary ports |
| [x] | [CD-FOCUS-16](circuit-designer/focused/CD-FOCUS-16.md) | Navigate child Designs and return to the right context |
| [x] | [CD-FOCUS-17](circuit-designer/focused/CD-FOCUS-17.md) | Inspect cycle markers and clock-domain timing |
| [x] | [CD-FOCUS-18](circuit-designer/focused/CD-FOCUS-18.md) | Save to Spec and reject a stale Circuit revision |
| [x] | [CD-FOCUS-19](circuit-designer/focused/CD-FOCUS-19.md) | Round-trip a portable circuit and reject malformed files |
| [x] | [CD-FOCUS-20](circuit-designer/focused/CD-FOCUS-20.md) | Export the visible diagram consistently |

## Canonical input library

Use [focused fixtures and negative inputs](inputs/focus-fixtures.md) for focused
checks. Composite packs include their full boundary interface, explanation,
named instances, exact driver/sink/slice tables, and layout expectations. Follow
linked child packs recursively. No case depends on another case's scored result.

- [32-bit unsigned adder](inputs/add32.md) (`add32`)
- [Enabled registered 32-bit adder](inputs/reg_add32.md) (`reg_add32`)
- [Programmable 16-bit periodic timer](inputs/timer16.md) (`timer16`)
- [Four-entry eight-bit synchronous FIFO](inputs/fifo8x4.md) (`fifo8x4`)
- [Four-word 32-bit byte-write register bank](inputs/regbank4x32.md) (`regbank4x32`)
- [Eight-bit UART transmitter](inputs/uart_tx.md) (`uart_tx`)
- [CRC-16 byte accumulator](inputs/crc16.md) (`crc16`)
- [Four-request round-robin arbiter](inputs/rr4.md) (`rr4`)
- [Eight-bit SPI Mode 0 master](inputs/spi8.md) (`spi8`)
- [Enabled 8-bit register](inputs/reg8.md) (`reg8`)
- [Enabled 16-bit register](inputs/reg16.md) (`reg16`)
- [Enabled 33-bit register](inputs/reg33.md) (`reg33`)
- [Enabled 65-bit register](inputs/reg65.md) (`reg65`)
- [16-bit modulo adder](inputs/add16.md) (`add16`)
- [16-bit modulo subtractor](inputs/sub16.md) (`sub16`)
- [16-bit bitwise AND](inputs/and16.md) (`and16`)
- [16-bit bitwise XOR](inputs/xor16.md) (`xor16`)
- [2-input 16-bit selector](inputs/mux16x2.md) (`mux16x2`)
- [4-input 16-bit selector](inputs/mux16x4.md) (`mux16x4`)
- [2-input 8-bit selector](inputs/mux8x2.md) (`mux8x2`)
- [4-input 8-bit selector](inputs/mux8x4.md) (`mux8x4`)
- [16-bit zero detector](inputs/zero16.md) (`zero16`)
- [Four-entry ready/valid byte FIFO](inputs/stream_fifo8x4.md) (`stream_fifo8x4`)
- [One-entry ready/valid byte register](inputs/stream_slice8.md) (`stream_slice8`)
- [Unsigned eight-bit threshold comparator](inputs/compare8.md) (`compare8`)
- [Four-byte status packer](inputs/pack4x8.md) (`pack4x8`)
- [Four-alarm summary](inputs/or4.md) (`or4`)
- [SPI capture admission control](inputs/capture_control.md) (`capture_control`)
- [Enabled eight-bit counter](inputs/counter8.md) (`counter8`)
- [Timer before pulse-duration revision](inputs/timer16_initial.md) (`timer16_initial`)
- [Reusable hierarchical 64-bit adder](inputs/add64.md) (`add64`)
- [Two-stage enabled 32-bit addition datapath](inputs/pipeline32.md) (`pipeline32`)
- [Registered selectable 16-bit add/subtract datapath](inputs/addsub16.md) (`addsub16`)
- [Four-lane eight-bit register bank](inputs/lanes4x8.md) (`lanes4x8`)
- [Five-byte buffered ready/valid stream](inputs/buffered_stream.md) (`buffered_stream`)
- [Four-channel unsigned threshold monitor](inputs/sensor_monitor.md) (`sensor_monitor`)
- [Timer-triggered UART status transmitter](inputs/status_tx.md) (`status_tx`)
- [SPI byte capture with four-entry result buffer](inputs/spi_capture.md) (`spi_capture`)
- [Hierarchical four-operation 16-bit ALU core](inputs/alu_core16.md) (`alu_core16`)
- [Hierarchical 16-bit ALU with zero flag](inputs/alu_subsystem16.md) (`alu_subsystem16`)
- [2-channel eight-bit counter monitor](inputs/counter_monitor2.md) (`counter_monitor2`)
- [4-channel eight-bit counter monitor](inputs/counter_monitor4.md) (`counter_monitor4`)

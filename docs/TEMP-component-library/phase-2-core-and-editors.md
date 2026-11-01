# Phase 2: build the leaf catalogue through Spec Editor

Status: not started. Required authoring method: Spec Editor UI.
Prerequisite: [Phase 1](phase-1-foundation.md) complete and
[implementation guide](README.md).
Next: [Circuit Designer UI](phase-3-control-and-composition.md).

## 1. Fixed result and scope

Build 17 original leaf Components and two derived CSR endpoint profiles through
Spec Editor. Add any missing authoring, contract, library, and CSR controls
first. Publish/import through those controls. Find and fix defects in forms,
validation, save, verification status, and library use.

This is real UI authoring. Use the rendered controls with Playwright or computer
use. Normal application HTTP calls are expected. Direct API mutation, archive
seeding, browser-state injection, and calling application internals are not
acceptance evidence. Read-only service/Spec inspection verifies the results.
Backend unit fixtures may use APIs when labelled as supporting checks.

## 2. Ordered implementation packages

### 2A. Complete the required UI controls

Extend the existing Spec Editor, document controls, and typed client packages.
Preserve the current save model and naming rules. Implement these controls
before using them to build the catalogue:

| Control | Required behaviour |
| --- | --- |
| Existing File → New/Open and Components Options → Add component | Create/open source, show the bound Spec, preserve errors and in-place drafts |
| Existing wire-port, Parameters, description, and SV editors | Author symbolic ranges and typed defaults; distinguish saved source from verification status |
| Component Options → Library details… | Edit library ID/version, family/tags, structured contract, parameter limits/presets, and limitations through typed forms |
| File → Import library Component… | Search, filter, inspect an exact release, select a supported preset, preview the closure, then import atomically |
| Component Options → Publish to library… | Prepare a detached release, qualify the exact candidate, show compatibility limits, then publish those immutable bytes |
| Component Options → Qualify library Component | Launch `library.qualify` for saved source, show separate outcomes and exact configuration |
| Component Options → CSR description… | Edit the typed CSR source below; validate fields and access policies; preserve invalid input as a draft |
| Component Options → Build CSR | Run `csr.build`, inspect derived artifacts, and accept source proposals through the configured product policy |

Keep existing supported controls where their spelling differs. Use the labels
above for new controls and add stable accessible names. New contracts are typed
annotations, not a second handwritten port schema. Show friendly names normally;
put raw hashes, ID maps, and full tool output in diagnostic details.

Add a clear saved/draft state and field-level errors. Never show qualified
because an SV Section was merely saved or lint passed. Changing source marks
prior evidence stale. The existing ability to save incomplete SV text for later
repair remains; publication rejects incomplete executable content.

### 2B. Repeat the reference case through the UI

From a new Spec created with File → New:

1. Recreate `register_en_arst_n` with the Phase 1 contract using Component,
   parameter, port, description, SV, and library-detail controls.
2. Use width 8, reset zero; save and qualify. Compare the normalized contract,
   ports, selected values, SV behaviour, and simulation results with Phase 1.
   Different opaque IDs are allowed and must be mapped explicitly.
3. Import the published Phase 1 register twice at width 8 and once at width 32.
   Confirm one local definition per unchanged realization. Add repeated
   instances through existing Design controls to exercise shared definitions.
   Build the exact `register_reference` boundary and eight nets from the guide.
4. Change the width-8 local reset value to 165 (`8'hA5`) through the parameter
   editor. The result is a local fork; the published release remains unchanged.
5. Cancel a port and import draft; verify no source change. Save a corrected
   draft, restart the service, reopen through File → Open, and verify saved data.

Do not pre-create this case through an API and count viewing it as authoring.
Fix any missing controls or defects, then repeat the original UI operation.

### 2C. Author the stream and storage leaves

For every leaf use the UI sequence: new Component → parameters → ports →
description → SV Section → library details/contract → Save to Spec → qualification
→ publication. A local draft can need several saves; no release is published
until all required checks complete.

All clocked leaves use `clk_i` and `rst_ni`. The default stream contract is:
`DATA_WIDTH=32`, `s_valid_i`, `s_ready_o`, `s_data_i[DATA_WIDTH-1:0]`,
`m_valid_o`, `m_ready_i`, `m_data_o[DATA_WIDTH-1:0]`. A beat transfers on a
rising edge with valid and ready high. Payload and valid remain stable under
stall. Reset discards buffered data and clears valid; payload when valid is
low is not meaningful. Describe forward/reverse combinational paths per block.

| ID | Mandatory behaviour and interface additions | Required configurations/checks |
| --- | --- | --- |
| `stream_register` | Capacity one; registered valid/data; input ready when empty or downstream ready; no empty bypass; input accepted at edge E is visible during the cycle after E | Width 1/8/32; sustained rate one beat/clock; arbitrary stalls; reset while full |
| `skid_buffer` | Capacity two including output; registered data/valid; ready depends only on stored occupancy, with no combinational downstream-ready path; no empty bypass | Width 1/8/32; full-to-drain recovery, no loss/duplication, steady one beat/clock |
| `fifo_sync` | Single clock; no pass-through; capacity exactly DEPTH; head visible after the accepting edge; `level_o[CW-1:0]`, CW=max(1,clog2(DEPTH+1)); `s_ready_o` can accept a simultaneous pop while full; no flush input | All combinations of DEPTH 1/3/4/16 and width 1/8/32; wrap, simultaneous push/pop, held head, ordering proof |
| `stream_arbiter2` | Two stream inputs `s0_*`, `s1_*` and one `m_*`; round robin starts at input 0; hold selected payload/valid under stall; update priority only on accepted output; each input holds until accepted | Width 8/32; both continuously valid; starvation bound in accepted events; winner withdrawal is invalid |
| `stream_transfer_counter` | Inputs scalar `valid_i`, `ready_i`; `count_o[COUNT_WIDTH-1:0]`; increment modulo 2**COUNT_WIDTH on accepted transfer; hold otherwise; reset zero | COUNT_WIDTH 1/8/32; no count on valid-only or ready-only; wrap |
| `stream_gate` | Standard stream ports plus requested `enable_i`; registered effective enable resets zero; update effective enable only when no output beat is stalled; forward valid/data/ready while effectively enabled; otherwise output valid, upstream ready, and data are zero | Width 8/32; enable/disable during a stall cannot withdraw valid or change payload; disabled upstream data remains held through backpressure |
| `ram_1rw_sync` | `req_i`, `we_i`, `addr_i`, `wdata_i`, byte `be_i`, `rdata_o`, `rvalid_o`, `error_o`; one request/clock; read result after accepting edge; writes have no read response | Width 8/32, DEPTH 1/3/16; byte masks; invalid address ignored with registered error; memory contents not reset |
| `ram_1r1w_sync` | `we_i`, `waddr_i`, `wdata_i`, `be_i`, `re_i`, `raddr_i`, `rdata_o`, `rvalid_o`, `error_o`; one read and write/clock; same-address read returns old data before that write | Width 8/32, DEPTH 1/3/16; masked collision, independent invalid requests, one-cycle read result |

For both RAMs, address width is max(1,clog2(DEPTH)); width is a positive multiple
of eight. Byte-enable bit zero controls the least significant byte. An invalid
request does not change storage or produce read-valid. On 1R1W RAM, the other
legal request can still complete; error is the OR of invalid requests. Reset
clears output-valid/error and output registers, not the array. Unwritten contents
are unspecified. Test defined semantics without forcing random memory to zero.

For `stream_gate`, retain the effective enable while
`m_valid_o && !m_ready_i`. Otherwise sample the requested enable at the rising
edge. A disable request can therefore wait for one offered beat to complete.
An enable request takes effect after a clock edge. This preserves the stream
contract when software changes enable during backpressure.

For the two RAMs, run all listed width/depth combinations. Parameters must have
explicit legal ranges: DATA_WIDTH and DEPTH at least one for ordinary streams,
byte-multiple DATA_WIDTH for RAM/CRC, A_WIDTH/B_WIDTH at least one for multiply,
and `1 <= OUT_WIDTH <= IN_WIDTH` with `0 <= DROP_LSB < IN_WIDTH` for round/saturate.
Derived address/level widths are not independently editable parameters.

### 2D. Author bounded adapters, arithmetic, and integrity leaves

| ID | Fixed initial contract | Required evidence |
| --- | --- | --- |
| `stream_upsizer` | IN_WIDTH=8, OUT_WIDTH=32; integer byte ratio; stream `last` and `keep` on both sides; first accepted byte occupies lowest output byte; flush partial group only on last; no cross-packet combining | 8→32 and 16→32; short/final partial packets; full-rate and random stalls; accepted-byte conservation |
| `stream_downsizer` | IN_WIDTH=32, OUT_WIDTH=8; inverse byte ordering; emit only bytes marked by a contiguous low-order keep mask; last appears only on final emitted beat; nonempty final packet required | 32→8 and 32→16; matching round trip; invalid mask/empty final packet diagnostics |
| `crc32_stream_observer` | Observe `valid_i`, `ready_i`, `data_i[DATA_WIDTH-1:0]`; no backpressure output; `clear_i` and `crc_o[31:0]`; reflected polynomial 0xEDB88320, initial state 0xffffffff, final XOR 0xffffffff; process least significant byte first on each accepted beat | DATA_WIDTH 8/32; Python zlib reference, byte sequence 123456789, stalls, reset; clear wins over transfer |
| `parity_codec` | Combinational `data_i[DATA_WIDTH-1:0]`, `parity_i`, generated even `parity_o`, and `error_o = parity_i XOR parity_o`; no odd-parity mode | Width 1/8/32; all single-bit errors and parity-bit error |
| `secded_32_7` | 32-bit `data_i`, 39-bit `code_o`; independent 39-bit `code_i`, corrected 32-bit `data_o`, `corrected_o`, `uncorrectable_o`; extended Hamming, even parity; Hamming positions 1/2/4/8/16/32 in positions 1..38; position 39 is overall parity | Exact placement table; all 39 single-bit and all two-bit faults; overall-parity fault; double-error data remains extracted uncorrected and flagged |
| `addsub_wrap` | DATA_WIDTH=32; `a_i`, `b_i`, `sub_i`, `y_o`, `carry_o`, `overflow_o`; modulo-width result; subtract computes a + ~b + 1; subtract carry means no borrow; overflow is signed overflow | Width 1/8/32; signed extrema, wrap, carry/no-borrow |
| `mul_pipe` | A_WIDTH=B_WIDTH=16, SIGNED=0; full-width product; `valid_i`, `a_i`, `b_i`, `valid_o`, `y_o`; one registered stage, no ready; accept one valid input/clock; hold data when invalid; reset valid/data zero | Width pairs (1,1), (8,8), (16,16); SIGNED 0/1; signed reference and adjacent valid cycles |
| `fixed_round_sat` | Combinational signed two's-complement `data_i[IN_WIDTH-1:0]` to `data_o[OUT_WIDTH-1:0]`; divide by 2**DROP_LSB, round nearest ties-even, then clamp to signed OUT_WIDTH range; defaults (32,16,8) | DROP_LSB 0 and 8; negative/positive ties; min/max; overflow; independent integer model |
| `apb_demux2` | One 16-bit-address APB4 input and two 12-bit-address outputs; window 0x0000..0x0fff→0, 0x1000..0x1fff→1; all others return PSLVERR with PREADY high in access; preserve selection through waits | Setup/access, back-to-back transfers, waits, invalid regions, no response/selection leakage |

The adapters carry `s_last_i`, `s_keep_i`, `m_last_o`, `m_keep_o`; each keep
width is its data byte count. Every non-final input beat has all keep bits set;
final keep is nonzero and contiguous from bit zero. Invalid masks are contract
violations diagnosed by assertions; do not claim defined data conversion for
them. Use separate normal
stream and packet-stream contract IDs so plain streams do not silently acquire
packet semantics.

For the CRC observer, clear resets the state even if a transfer occurs in that
cycle; that transfer is not included in the new CRC. The stream itself can
still transfer. Phase 3 exposes this clear action explicitly through the CSR.

For APB, use `paddr`, `psel`, `penable`, `pwrite`, `pwdata`, `pstrb`, `pprot`,
`prdata`, `pready`, and `pslverr`. Input-side ports use `s_` plus direction suffix;
output-side ports use `m0_`/`m1_`. PWDATA/PRDATA are 32 bits, PSTRB four bits,
PPROT three bits, all controls scalar. Clocks/resets use the common names.
Output address is the low 12 input bits. Unselected PSEL/PENABLE are zero.

### 2E. Implement the fixed CSR source and Activity

Use one authoritative editable JSON document under
`annotations/library/csr/<component-id>.json`. No SystemRDL/HJSON dependency.
Use schema version 1 with these fields:

- `data_width` fixed 32, `address_width` fixed 12, `byte_order` fixed `little`.
- `clock_port`=`clk_i`, `reset_port`=`rst_ni`, `reset_style`=`async_active_low`.
- `bus_profile`: `apb4` or `axi4_lite`.
- Registers with ID/name, aligned offset, and fields with ID, lsb, width,
  reset value, software access, hardware input/output roles, and precedence.
- Explicit error policy for unsupported/misaligned/unmapped access.

Use explicit typed hardware actions, not narrative interpreted by the Activity:
`read_source: {kind: port, id: ...}` for RO input values;
`value_output: {port: ...}` for stored RW outputs;
`hw_set: {kind: unsigned_ge, lhs_port: level_i, rhs_register: THRESHOLD,
require_rhs_nonzero: true}` for sticky STATUS bit 0; and
`write_effect: {kind: pulse_on_one, port: crc_clear_o}` for COMMAND bit 0.
Field `hw_precedence` is `set_wins` for STATUS. Validate referenced ports,
registers, widths, and parameter expressions. Other action kinds are rejected.
FIFO_DEPTH is a declared Component parameter; LEVEL_WIDTH is derived through
the existing interface resolver, not an independently authored value.

Support RO, RW, WO, W1C, W1S, and read-clear. Define hardware-set versus software
clear precedence per field; the initial interrupt field gives hardware set
priority. Reject overlaps, out-of-range resets, duplicate offsets/IDs, unknown
access modes, unbound hardware roles, and unsupported sizes.

The `csr.build` Activity reads a saved immutable snapshot and returns typed
source proposals plus derived RTL, IP-XACT register metadata, Markdown register
docs, a C header, and executable access-policy checks. Proposals pass through
the existing review/revision policy. No direct write to live source. Structured
JSON is authoritative; derived register metadata and SV are not independently
editable. Editing the JSON invalidates derived output until rebuilt. Inputs,
Activity version, and output digests travel with imports.

Author the following two Components through the CSR UI, then Build CSR and
accept its proposal: `apb_stream_regs` and `axi_lite_stream_regs`. They have the
same register source and hardware-facing roles, with separate bus profiles.
Their fixed map is:

| Offset | Register | Exact behaviour |
| --- | --- | --- |
| 0x00 | CONTROL | RW bit 0 `enable_o`, reset 0; other bits read zero and ignore writes |
| 0x04 | THRESHOLD | RW 32-bit threshold, reset FIFO_DEPTH (default 4); zero disables threshold interrupt; compare unsigned |
| 0x08 | COUNT0 | RO `count0_i[31:0]` |
| 0x0c | COUNT1 | RO `count1_i[31:0]` |
| 0x10 | STATUS | Bit 0 sticky threshold interrupt, W1C; hardware sets while threshold nonzero and occupancy>=threshold; hardware set wins concurrent clear; `irq_o` reflects bit 0 |
| 0x14 | OCCUPANCY | RO zero-extended `level_i[LEVEL_WIDTH-1:0]`, LEVEL_WIDTH=max(1,clog2(FIFO_DEPTH+1)) |
| 0x18 | CRC | RO `crc_i[31:0]` |
| 0x1c | COMMAND | WO bit 0 emits `crc_clear_o` for one cycle after an accepted write of one; read zero; zero write has no effect |

Byte strobes apply to writes. Unmapped or misaligned accesses return an error
and no side effect. Writes to read-only fields are accepted and ignored; reads
of write-only fields return zero. The initial interrupt is status-driven and
can assert even while stream output is disabled. Reset wins over all updates.
Use separate maintained CSR fixtures to cover W1S and read-clear, although the
example map does not require them.

APB4 has one access at a time and supports waits/errors. AXI4-Lite has separate
AW/W capture, independent read and write response channels, no IDs/bursts,
32-bit data, 12-bit byte address, WSTRB, and explicit AXPROT pass/ignore policy.
Allow at most one pending read and one pending write. Serialize shared CSR
execution with alternating read/write priority starting with read when both are
ready; capture address and data in either order. Hold B/R payload under stall.
ARPROT/AWPROT are accepted and ignored in this nonsecure profile. Record the
protocol baseline as Arm IHI 0024D for the APB4 subset and IHI 0022H Part B1
for AXI4-Lite. Test their mandatory channel rules; APB5 features are excluded.
Use the official [APB specification](https://developer.arm.com/documentation/ihi0024/d)
and [AXI specification](https://developer.arm.com/documentation/ihi0022/h).
Record the exact downloaded document identifier/digest in evidence. The
protocol baseline is fixed; do not select a different bus generation.

Sample a CSR read value at its execution edge and latch the response while
stalled. Apply each write side effect once at its execution edge, even if its
response stalls. For APB this is the accepting access edge. For AXI4-Lite,
execution occurs only after the necessary request fields are captured and a
response slot is free. Errors return AXI SLVERR (`2'b10`) or APB PSLVERR;
accepted ignored writes/read-zero operations return OKAY/no error. Evaluate
STATUS hardware-set using pre-edge occupancy and pre-edge threshold; a
simultaneous threshold write affects the next edge's comparison.

### 2F. Qualify and run the Spec Editor defect campaign

For each required release, run the declared simulation, assertions, generic
synthesis, and applicable formal checks from the UI. For FIFO prove occupancy
bounds and accepted-data ordering; for stream arbitration prove mutual exclusion
and progress under stated input/backpressure assumptions. Use independent
models for arithmetic, CRC, and ECC. Declare the tested matrix; do not claim an
unbounded parameter space from samples.

Draft qualification helps authoring. Publication preview first fixes release
VLNV mappings and embeds required test/constraint assets. The publication UI
then qualifies that exact immutable candidate and commits its unchanged bytes.
Evidence for a different draft hash cannot authorize release promotion.

Add real browser scenarios for:

- Parameter/port editing order, dependent symbolic widths, duplicate IDs,
  reversed/one-bit ranges, invalid defaults, keyboard operation, and focus.
- Cancelled text, parameter, contract, CSR, publication, and import drafts.
- Saving incomplete SV, visible failed lint, repair, requalification, and stale
  evidence after edits. Do not remove the useful incomplete-authoring behaviour.
- Wrong-document response, service restart, stale save, and loss of a response
  after a successful publication/import. Use exact receipts to reconcile.
- Same realization reused, new parameter realization, local fork, dependent
  qualification invalidation, and attempted overwrite of a published version.
- CSR edits invalidating output; stale CSR proposals rejected; source, derived
  metadata, docs, and tests agreeing after rebuild.

Fix each in-scope confirmed defect and rerun it through the same UI controls.
Keep read-only archive checks alongside browser traces to prove durable results.

## 3. Acceptance and exit gate

All 17 original leaves and two derived endpoint profiles have valid UI-authored
source, exact local releases, scoped qualification, and reopen evidence. The
reference case matches Phase 1 semantics. Publication/import/cancel/fork controls
operate through the shared service contracts. No mandatory source was seeded
outside the UI path. Phase 3 can resolve every required leaf without inventing
new behaviour or a missing helper.

Run `fast`, `integration --scope spec,activities,verification`, and `regression`.
Include `circuit` when its shared client packages change, and `shared` plus all
consumers for shared contracts. Store new reports in `TEMP_library_<run>/`.
Required missing tools/credentials make the applicable gate incomplete.

## 4. Handoff record

- Implementation revision; delivered UI controls and actual accessible names.
- Nineteen release references/digests, UI authoring traces, and parameter matrix.
- CSR schema/Activity versions and reproducibility results.
- Reference case and reopened source evidence.
- Defect register: failing interaction, cause, fix, browser/unit regression.
- Executed profiles/hardware checks, outcomes, and evidence directory.
- Remaining prerequisites and explicitly deferred backlog.
- Exit gate: not evaluated.

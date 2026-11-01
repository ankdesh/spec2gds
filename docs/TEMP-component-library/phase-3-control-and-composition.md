# Phase 3: build reusable composites through Circuit Designer

Status: not started. Required authoring method: source-bound Circuit Designer UI.
Prerequisite: [Phase 2](phase-2-core-and-editors.md) complete and
[implementation guide](README.md).
Next: [AI Assistant](phase-4-releases-and-evolution.md).

## 1. Fixed result and scope

Create and publish three composite Components by placing released definitions,
connecting physical ports, adding boundaries, and saving through Circuit
Designer. The required releases are `buffered_stream_control`,
`apb_stream_subsystem`, and `axi_lite_stream_subsystem`. Verify nested hierarchy,
source authority, private drafts, parameters, and library publication.

The first composite releases are deliberately concrete: stream width 32,
FIFO depth 4, count width 32, level width 3, CSR data width 32, and CSR byte
address width 12. Their public hardware interfaces have no configurable
parameters. Keep the selected leaf parameter values in provenance. This avoids
claiming unsupported propagation through parameterized topology. Future
parameterized composites need a separate explicit propagation contract.

Reuse the exact qualified Phase 2 releases. New leaf SV behaviour is outside
this phase. If a dependency defect is found, fix it, produce a new release via
its original authoring path, then repeat the Circuit placement/save checks.
Do not hide a replacement leaf inside a composite SV Section.

## 2. Complete the Circuit authoring path first

Work in Circuit source adapters, the Circuit service, and the Spec adapter.
Keep `.spec` loading/persistence out of reusable Circuit core. The Circuit
browser talks to Circuit service; the private Spec source provider talks to
Spec service. Respect leases, bindings, source revisions, and existing
Save to Spec/Cancel Changes behaviour.

Add these missing controls where they do not exist:

| Control | Required result |
| --- | --- |
| File → New Spec design… in the Spec host adapter | Create a new scratch Spec and empty bound Design through the services; return the authoritative binding and projection |
| Components → Create composite Component… | Draft a named Component, its internal Design, and a selected edit target in the same Spec |
| Boundary port editor | Add/edit numeric wire port IDs, display names, direction, and width through the private draft |
| Component catalog → Library | Search exact releases, choose presets, preview terminals/limits, and place a provisional instance |
| Composite details → Library details… | Edit the same typed metadata/behaviour contract used by Spec Editor |
| Composite details → Qualify / Publish to library… | Check saved source, preview the final composite closure, qualify that immutable candidate, and publish its exact bytes |

The host-specific New Spec design command is an addition, not a capability of
standalone Circuit core. A standalone document without a Spec provider must
report library source operations as unavailable; it must not invent a binding.
Leaf previews remain read-only. Editing a composite selects its internal Design.

Creating source from these actual UI controls is part of this phase. Do not
pre-seed the final graph or use an API script to compensate for a missing control.
Read-only snapshots and archive inspection verify each durable result.

### Provisional placement and atomic save

A library placement adds a provisional definition/instance to the private
Circuit draft. The source adapter holds an immutable import plan with exact
release/dependency digests and realization values. Return safe numeric terminals
and an opaque plan reference to the browser, not package bytes or private tokens.

At Save to Spec, validate the plan, new Component/internal Design relationship,
connections, boundary ports, and any source annotations together. Commit import
plus topology through one revision-checked Spec transaction. Re-project the
accepted source and map provisional IDs to accepted IDs. If validation/approval
fails, keep the draft and leave the saved Spec unchanged. Cancel drops every
provisional import and topology edit. A stale source revision requires the
existing conflict/reload path; no silent rebase or force save.

Evaluate terminal widths through `rtl_interface.py` for selected leaf defaults.
Keep symbolic expressions in source and numeric terminals in the Circuit
projection. Include original range orientation and numeric slice mapping.
Changing a local definition must recompute widths, validate every connection,
and invalidate dependent qualification. Never drop a connected pin because its
port role or source representation is unsupported.

## 3. Mandatory reference case and defect checks

Before the full composites, import one Phase 1 width-8 register definition and
one width-32 definition through the catalog. Place u_reg8a and u_reg8b from the
same width-8 definition, and u_reg32 from the width-32 definition. Build the
guide's exact register_reference boundary/eight nets, save, reopen, and compare
normalized source with the prior methods. Cancel one additional placement and
prove no stray definition remains.

Exercise parameter-dependent terminals, one-bit and reversed ranges, numeric
slices, keyboard actions, port selection, routing, undo/redo, and zoom. Preserve
layout as annotations, not logical topology. A cycle-edge marker is a visual
timing annotation; it does not insert registers or establish hardware latency.

Keep failing inputs and repair in-scope defects before continuing. Add browser
checks for control/gesture/draft faults and adapter/transaction checks for shared
logic. Re-execute every reproducer from the same UI path after the fix.

## 4. Composite A: buffered_stream_control

Create a composite with exactly these boundary ports:

| Ports | Direction | Width |
| --- | --- | --- |
| `clk_i`, `rst_ni` | in | 1 each |
| `s0_valid_i`, `s1_valid_i`, `m_ready_i` | in | 1 each |
| `s0_data_i`, `s1_data_i` | in | 32 each |
| `s0_ready_o`, `s1_ready_o`, `m_valid_o` | out | 1 each |
| `m_data_o` | out | 32 |
| `level_o` | out | 3 |
| `count0_o`, `count1_o` | out | 32 each |

Place exactly these five instances:

| ID | Released Component | Exact preset |
| --- | --- | --- |
| `u_arb` | `stream_arbiter2` | DATA_WIDTH=32 |
| `u_skid` | `skid_buffer` | DATA_WIDTH=32 |
| `u_fifo` | `fifo_sync` | DATA_WIDTH=32, DEPTH=4 |
| `u_count0`, `u_count1` | `stream_transfer_counter` | COUNT_WIDTH=32 |

Make these named wire connections. Each row has one source and the listed
sinks. For a stream, the table spells out the reverse ready direction.

| Net | Source | Sinks |
| --- | --- | --- |
| `clock` | boundary clk_i | clk_i of all five instances |
| `reset_n` | boundary rst_ni | rst_ni of all five instances |
| `input0_valid` | boundary s0_valid_i | u_arb.s0_valid_i, u_count0.valid_i |
| `input0_data` | boundary s0_data_i | u_arb.s0_data_i |
| `input0_ready` | u_arb.s0_ready_o | boundary s0_ready_o, u_count0.ready_i |
| `input1_valid` | boundary s1_valid_i | u_arb.s1_valid_i, u_count1.valid_i |
| `input1_data` | boundary s1_data_i | u_arb.s1_data_i |
| `input1_ready` | u_arb.s1_ready_o | boundary s1_ready_o, u_count1.ready_i |
| `arbitrated_valid` | u_arb.m_valid_o | u_skid.s_valid_i |
| `arbitrated_data` | u_arb.m_data_o | u_skid.s_data_i |
| `arbitrated_ready` | u_skid.s_ready_o | u_arb.m_ready_i |
| `buffered_valid` | u_skid.m_valid_o | u_fifo.s_valid_i |
| `buffered_data` | u_skid.m_data_o | u_fifo.s_data_i |
| `buffered_ready` | u_fifo.s_ready_o | u_skid.m_ready_i |
| `output_valid` | u_fifo.m_valid_o | boundary m_valid_o |
| `output_data` | u_fifo.m_data_o | boundary m_data_o |
| `output_ready` | boundary m_ready_i | u_fifo.m_ready_i |
| `fifo_level` | u_fifo.level_o | boundary level_o |
| `accepted0` | u_count0.count_o | boundary count0_o |
| `accepted1` | u_count1.count_o | boundary count1_o |

There are five instances and twenty named nets at this level. Reuse one counter
definition for both counters. No unused mandatory port may be hidden.

Counts measure accepted source beats, not output beats. FIFO level counts only
its four entries; the skid buffer adds up to two more stored beats. Do not claim
that level_o measures all in-flight storage. Under no backpressure, the earliest
input accepted at rising edge n can first transfer at the output at edge n+2;
stalls can extend this transfer latency without a finite maximum.
The assembly has no combinational ready path through the skid buffer.

Save, close, reopen, qualify, and publish version 1.0.0 using the Circuit controls.
Test two active sources, stalls, full buffers, reset with in-flight data,
arbitration order/fairness assumptions, and accepted-transfer counter wrap using
an independent short-width leaf check. Use a scoreboard for complete assembly
ordering and data conservation.

## 5. Composites B/C: APB and AXI4-Lite stream subsystems

Build `apb_stream_subsystem`, then `axi_lite_stream_subsystem`. Both contain
exactly these four instances:

| ID | Component | Preset |
| --- | --- | --- |
| `u_core` | Released buffered_stream_control | Fixed Phase 3 interface |
| `u_gate` | stream_gate | DATA_WIDTH=32 |
| `u_regs` | apb_stream_regs or axi_lite_stream_regs | FIFO_DEPTH=4, address 12, data 32 |
| `u_crc` | crc32_stream_observer | DATA_WIDTH=32 |

The boundary has common `clk_i`/`rst_ni`, both `s0_*`/`s1_*` input stream groups,
one `m_*` output stream group, scalar `irq_o`, and the complete chosen bus group.
Do not expose level/count/CRC as extra external pins; software reads them through
the fixed CSR map. No unused bus or stream pins are allowed.

Use this internal wiring:

1. Fan common clock/reset to all four instances.
2. Connect each source boundary stream to u_core with valid/data forward and
   ready backward, preserving exact IDs from Composite A.
3. Connect u_core.m_valid_o/data_o to u_gate.s_valid_i/data_i; connect
   u_gate.s_ready_o to u_core.m_ready_i.
4. Connect u_regs.enable_o to u_gate.enable_i. Apply the Phase 2 registered
   effective-enable contract; a CSR disable must not withdraw a stalled beat.
5. Connect u_gate.m_valid_o/data_o to boundary m_valid_o/data_o and to
   u_crc.valid_i/data_i. Connect boundary m_ready_i to u_gate.m_ready_i and
   u_crc.ready_i. Thus CRC measures accepted output data only.
6. Connect u_core.count0_o/count1_o/level_o to u_regs.count0_i/count1_i/level_i.
7. Connect u_crc.crc_o to u_regs.crc_i; u_regs.crc_clear_o to u_crc.clear_i;
   u_regs.irq_o to boundary irq_o.
8. Map every bus boundary input to the same-named u_regs input, and every
   u_regs bus output to its same-named boundary output. Keep the flat physical
   port representation; do not add IP-XACT bus interfaces in these releases.

For APB the flat boundary IDs are `paddr_i[11:0]`, `psel_i`, `penable_i`,
`pwrite_i`, `pwdata_i[31:0]`, `pstrb_i[3:0]`, `pprot_i[2:0]`,
`prdata_o[31:0]`, `pready_o`, `pslverr_o`.

For AXI4-Lite use all five channels: `awaddr_i[11:0]`, `awprot_i[2:0]`,
`awvalid_i`, `awready_o`; `wdata_i[31:0]`, `wstrb_i[3:0]`, `wvalid_i`,
`wready_o`; `bresp_o[1:0]`, `bvalid_o`, `bready_i`; `araddr_i[11:0]`,
`arprot_i[2:0]`, `arvalid_i`, `arready_o`; `rdata_o[31:0]`,
`rresp_o[1:0]`, `rvalid_o`, `rready_i`. Clocks/resets remain shared.
These exact leaf port IDs are part of the Phase 2 endpoint release contract.

Runtime behaviour is fixed:

- Reset disables output and clears stored stream data, counts, CRC, and IRQ.
- Disabled output retains data; input can fill the skid/FIFO capacity before
  backpressure reaches sources. It does not discard already accepted beats.
- Enabling starts output after the gate's control sampling edge.
- Disabling during a stalled output waits until that offered beat completes.
- Counts measure accepted ingress; CRC measures accepted egress. A CRC clear
  wins over an egress beat on its pulse cycle as specified in Phase 2.
- Threshold status uses FIFO occupancy only, including when output is disabled.
- CSR reset, simultaneous hardware-set/software-clear, byte strobes, waits,
  unmapped access, and AXI AW/W ordering follow the Phase 2 contracts.

Publish both composites as exact 1.0.0 releases. Their common u_core and leaves
must deduplicate by realization when imported together. Preserve nested internal
Designs rather than flattening or duplicating them.

## 6. Circuit defect campaign and hardware evidence

Exercise all of the following, fixing confirmed in-scope defects:

- Cancel after placement, after boundary creation, and after routing: no source
  additions or orphaned library definitions persist.
- Save with one invalid final connection: no partial import/topology write.
- Revision conflict between two editing surfaces: draft retained, no overwrite.
- Edit-lease expiry, lost response after accepted save, restart, and reload.
- Duplicate instance names; ID/VLNV collisions; same release with different
  parameter realization; unsupported symbolic ranges and bus-mapped pins.
- Nested drill-down/back navigation, stable boundary mapping, layout reload,
  undo/redo before save, numeric slices, and keyboard connection actions.
- Shared-definition fork versus clone-and-retarget-one-instance; warn about all
  affected instances and recompute dependent evidence.
- Read-only leaf preview remains read-only; only supported composite source is
  writable. A standalone circuit cannot save to an unrelated Spec.

For each composite, invoke RTL creation and qualification against saved source,
then simulate the resulting hierarchy. Use independent bus/stream scoreboards
and CSR reference checks. Exercise disable during stall, full storage, reset,
IRQ set/clear races, and output CRC. No library call occurs during a running
Activity; later library/source edits cannot change its snapshot.

Inspect the same saved hierarchy in Spec Editor using read-only UI navigation.
Check every nested instance, port, net, contract, and source mapping. Agreement
between applications, archive, emitted RTL, and simulation is required.

## 7. Exit gate and handoff

Three composites are authored through Circuit Designer and published with exact
source/evidence. Parameter terminal projection and provisional imports work;
all acceptance scenarios use the actual UI. No graph was pre-seeded through
an API. Known mandatory Circuit gaps are fixed and protected.

Run `fast`, `integration --scope spec,circuit,activities,verification`, and
`regression`. Shared contract changes include all consumers. Use new
`TEMP_library_<run>/` evidence paths.

Record:

- Implementation revision and new source-bound controls.
- Three release references/digests and the qualified dependency closure.
- Browser traces, saved topology inventories, and source ID mappings.
- Hardware simulation/assertion/synthesis results and assumptions.
- Defect register with before/after evidence and maintained regressions.
- Executed commands/profile outcomes, evidence directory, and remaining limits.
- Exit gate: not evaluated.

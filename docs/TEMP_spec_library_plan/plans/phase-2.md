# Phase 2: storage, streams, CDC, and reset

Status: implementation instructions. Requires completed Phase 1.

## 1. Inputs, outputs, and ordered implementation

Read [the shared contract](../README.md) and `handoffs/phase-1.md`. Verify the 32
previous releases and their digests before changes. Deliver 32 new entries,
64 total. Preserve all accepted Phase 1 bytes.

1. Run the Phase 1 `check` against releases and service download smoke. Missing or
   failed predecessor evidence is a prerequisite failure; do not recreate the
   predecessor library under new identities.
2. Extend independent reference helpers for queue state, byte-masked memories,
   ready/valid transfer records, and unrelated clocks. Add failing reference
   cases before implementing asynchronous and packet storage.
3. Author storage in the listed order, then stream entries, then CDC/reset.
   Reuse verified behavioral concepts but retain each entry's distinct timing
   contract. A skid buffer is not a renamed FIFO with different undocumented ready.
4. Add service metadata/search tests with the new categories and protocol tags;
   add an incremental index refresh after successful upload. Keep full rebuild as
   recovery authority. Concurrent search must return either pre-commit or
   post-commit state, never a partial version record.
5. Execute the Spec Editor stress scenarios below on temporary copies only.
   Fix confirmed source, validation, and browser defects. Do not implement an
   editor library import or catalogue feature for this secondary check.
6. Run all Phase 2 checks, selected predecessor hardware regressions, service
   checks, and required profiles. Publish exact candidate bytes and complete handoff.

Memory convention: read requests are sampled at edge t. A registered read result
is visible immediately after that edge and can be sampled by downstream logic at
t+1 (one-cycle read latency). Read-valid/error pulse for the resulting interval.
Unless specified, rdata holds its last registered value when no valid read;
initial/unwritten memory data is unspecified. Reset clears control/valid/error
outputs, not RAM arrays. Reference checks must initialize a location before
expecting its data. Do not resolve read/write collisions with simulator ordering.

## 2. Component contracts

Apply the shared rules and every listed preset, plus the extra CDC checks below.
All CDC synchronizers need recognizable two-or-more-flop structures and source
comments stating clock/reset assumptions. Digital simulation cannot model analog
metastability. Do not advertise a CDC sign-off or MTBF result.

### fifo_sync

- Parameters: W=32 [1..256], DEPTH=4 [1..256].
- Ports: CLK; S(W); M(W); O(level_o:C(DEPTH)).
- Behavior: No fall-through. Output is the oldest stored word. s_ready=(level<DEPTH); full pop does not admit a simultaneous push. Empty cannot pop. Otherwise simultaneous push/pop preserves level.
- Required directed checks: Empty/full boundaries, wrap pointers repeatedly, simultaneous operations, stable stalled output, DEPTH=1.
- Presets: default; W=1,DEPTH=1; W=7,DEPTH=3; W=64,DEPTH=256.

### fifo_fallthrough

- Parameters: W=32 [1..256], DEPTH=4 [1..256].
- Ports: CLK; S(W); M(W); O(level_o:C(DEPTH)).
- Behavior: When empty, connect input valid/data to output; s_ready=1. If downstream stalls, store the word. When nonempty use oldest storage; full pop allows simultaneous push. level counts stored words only.
- Required directed checks: Zero-edge bypass, bypass stall capture, full pop+push, wrap, DEPTH=1.
- Presets: default; W=1,DEPTH=1; W=7,DEPTH=3; W=64,DEPTH=256.

### fifo_async

- Parameters: W=32 [1..256], DEPTH=8 [2..256, power of two].
- Ports: I(wclk_i:1,wrst_ni:1,s_valid_i:1,s_data_i:W,rclk_i:1,rrst_ni:1,m_ready_i:1); O(s_ready_o:1,m_valid_o:1,m_data_o:W).
- Behavior: Independent write/read clocks. Gray pointers cross through two destination flops; synchronized pointers determine conservative full/empty. No combinational stream path. Read payload remains stable until consumed. Both resets must assert together; each domain releases synchronously. Unilateral reset during traffic is unsupported and explicitly documented.
- Required directed checks: Ratios 1:1,1:3,3:1 and relatively prime periods; varied phase; full/empty; Gray one-bit local transitions; no data loss; coordinated reset while full. Structural check that only Gray/control values cross synchronizers.
- Presets: default; W=1,DEPTH=2; W=7,DEPTH=4; W=64,DEPTH=256.

### fifo_packet

- Parameters: W=32 [1..256], DEPTH=16 [2..256].
- Ports: CLK; SL(W); ML(W); O(level_o:C(DEPTH),drop_o:1).
- Behavior: Store words; expose only packets whose last word has been accepted. level includes committed and partial words. Full stalls input. If the DEPTH-th word of one packet is accepted without last, discard that entire partial packet, pulse drop, and accept/discard subsequent words through last. Older committed packets remain intact. A packet of exactly DEPTH words with last is legal. No combinational fall-through.
- Required directed checks: No partial visibility, exact maximum packet, oversize recovery with one drop pulse, backpressure with older packets, reset mid-packet, payload and last stability.
- Presets: default; W=1,DEPTH=2; W=7,DEPTH=3; W=64,DEPTH=256.

### lifo_stack

- Parameters: W=32 [1..256], DEPTH=4 [1..256].
- Ports: CLK; I(push_i:1,pop_i:1,data_i:W); O(data_o:W,valid_o:1,level_o:C(DEPTH),overflow_o:1,underflow_o:1).
- Behavior: Top is combinationally visible when nonempty. Pop alone removes top; push alone appends if not full. Both replace top without level change when nonempty; both on empty push and pulse underflow. Rejected full push pulses overflow. Errors pulse for one edge; invalid data unspecified.
- Required directed checks: All simultaneous cases at empty/full/one word, last-in-first-out ordering, error pulses.
- Presets: default; W=1,DEPTH=1; W=7,DEPTH=3; W=64,DEPTH=256.

### ring_buffer

- Parameters: W=32 [1..256], DEPTH=8 [1..256].
- Ports: CLK; I(write_i:1,data_i:W,index_i:L(DEPTH)); O(data_o:W,valid_o:1,count_o:C(DEPTH)).
- Behavior: Retain newest DEPTH words; every write overwrites oldest when full. index 0 is newest, 1 previous. Combinational read is valid only index<count; invalid data is zero.
- Required directed checks: More than three wraps, index order, valid history before full, DEPTH=1.
- Presets: default; W=1,DEPTH=1; W=7,DEPTH=3; W=64,DEPTH=256.

### ram_1rw

- Parameters: W=32 [8..256, multiple of 8], DEPTH=16 [2..1024].
- Ports: CLK; I(en_i:1,we_i:1,addr_i:L(DEPTH),wdata_i:W,be_i:W/8); O(rvalid_o:1,rdata_o:W,addr_error_o:1).
- Behavior: Shared read/write port. Enabled valid write updates selected bytes without read response. Enabled valid read registers word. rvalid/error pulse after request edge. Invalid address causes error and no read/write. Storage is not reset; read only initialized locations.
- Required directed checks: Each byte mask, zero mask, last address, out-of-range for non-power-of-two depth, no read on write, hold while disabled.
- Presets: default; W=8,DEPTH=2; W=24,DEPTH=3; W=256,DEPTH=1024.

### ram_1r1w

- Parameters: W=32 [8..256, multiple of 8], DEPTH=16 [2..1024].
- Ports: CLK; I(we_i:1,waddr_i:L(DEPTH),wdata_i:W,be_i:W/8,re_i:1,raddr_i:L(DEPTH)); O(rvalid_o:1,rdata_o:W,write_error_o:1,read_error_o:1).
- Behavior: Independent same-clock write/read. Masked write. Read registers old pre-edge word on same-address collision. Invalid requests pulse corresponding error and do nothing. No reset of memory.
- Required directed checks: Same-address old-data behavior, different addresses, each byte mask, errors, reset leaves initialized storage unchanged.
- Presets: default; W=8,DEPTH=2; W=24,DEPTH=3; W=256,DEPTH=1024.

### ram_2rw

- Parameters: W=32 [8..256, multiple of 8], DEPTH=16 [2..1024].
- Ports: CLK; for p=a,b: I(p_en_i:1,p_we_i:1,p_addr_i:L(DEPTH),p_wdata_i:W,p_be_i:W/8); O(p_rvalid_o:1,p_rdata_o:W,p_error_o:1); O(collision_o:1).
- Behavior: Two shared ports on the same clock. Same valid address with two writes rejects both, pulses both errors and collision, even with disjoint masks. Read+write returns old data to reader. Other operations follow ram_1rw. No reset of storage.
- Required directed checks: All read/write combinations, conflicting write rejection, byte masks, independent invalid address, initialized storage.
- Presets: default; W=8,DEPTH=2; W=24,DEPTH=3; W=256,DEPTH=1024.

### rom

- Parameters: W=32 [1..64], DEPTH=16 [2..256], INIT=0 [0..2**(W*DEPTH)-1].
- Ports: CLK; I(en_i:1,addr_i:L(DEPTH)); O(valid_o:1,data_o:W,error_o:1).
- Behavior: Packed INIT lane j is word j. Enabled legal read registers data and valid. Invalid read pulses error, valid=0. No external initialization file or network source.
- Required directed checks: Known packed ramp, zero/default image, invalid address, disabled hold.
- Presets: default; W=1,DEPTH=2,INIT=2; W=8,DEPTH=3,INIT=197121; W=64,DEPTH=256,INIT=0.

### register_file_2r1w

- Parameters: W=32 [1..256], DEPTH=16 [2..256], ZERO_REG=1 [0 or 1].
- Ports: CLK; I(we_i:1,waddr_i:L(DEPTH),wdata_i:W,raddr_a_i:L(DEPTH),raddr_b_i:L(DEPTH)); O(rdata_a_o:W,rdata_b_o:W,rvalid_a_o:1,rvalid_b_o:1,write_error_o:1).
- Behavior: Asynchronous two-port reads; synchronous write. Reset clears registers. If ZERO_REG=1, register 0 reads zero and ignores legal writes without error. Invalid reads return zero and valid=0; invalid enabled write pulses error. Read reflects new value after write edge; no separate combinational bypass.
- Required directed checks: Both read ports, zero register with attempted write, same-address read/write edge, invalid addresses, reset all words.
- Presets: default; W=1,DEPTH=2,ZERO_REG=0; W=7,DEPTH=3,ZERO_REG=1; W=64,DEPTH=256,ZERO_REG=0.

### cam_binary

- Parameters: KEY_W=16 [1..64], VALUE_W=32 [1..256], DEPTH=8 [2..64].
- Ports: CLK; I(write_i:1,delete_i:1,index_i:L(DEPTH),key_i:KEY_W,value_i:VALUE_W,search_i:KEY_W); O(hit_o:1,multi_o:1,index_o:L(DEPTH),value_o:VALUE_W,error_o:1).
- Behavior: Indexed entries with valid bits reset zero. delete wins over write. Legal write sets valid. Invalid enabled update pulses error. Combinational search returns lowest matching index/value; no match returns zeros, multi indicates more than one match.
- Required directed checks: Duplicate keys, deletion priority, empty search, invalid updates, match changes after edge.
- Presets: default; KEY_W=1,VALUE_W=1,DEPTH=2; KEY_W=7,VALUE_W=9,DEPTH=3; KEY_W=64,VALUE_W=64,DEPTH=64.

### stream_register

- Parameters: W=32 [1..256].
- Ports: CLK; S(W); M(W).
- Behavior: One elastic output register; s_ready=!full || m_ready. Replace on simultaneous pop/push. No input-valid-to-output-valid fall-through; latency 1, throughput one per edge.
- Required directed checks: Empty capture, replacement, long output stall, stable data, reset occupied.
- Presets: default; W=1; W=7; W=256.

### stream_skid_buffer

- Parameters: W=32 [1..256].
- Ports: CLK; S(W); M(W).
- Behavior: Two storage entries; input ready depends only on registered occupancy (<2). No combinational path from downstream ready to upstream ready. Output valid/data use head storage; latency 1. A full drain creates one input bubble; otherwise sustained one per edge.
- Required directed checks: Abrupt stalls, two accepted words before full, full drain bubble, no ready combinational path.
- Presets: default; W=1; W=7; W=256.

### stream_spill_buffer

- Parameters: W=32 [1..256].
- Ports: CLK; S(W); M(W).
- Behavior: One-word fall-through buffer. Empty connects valid/data; capture if downstream stalls. Full output is stored; s_ready=m_ready, permitting replacement. Latency 0 when empty; one per edge.
- Required directed checks: Empty bypass, capture on stall, full replacement, reset during hold.
- Presets: default; W=1; W=7; W=256.

### stream_half_buffer

- Parameters: W=32 [1..256].
- Ports: CLK; S(W); M(W).
- Behavior: One slot; s_ready=!full, m_valid=full. No simultaneous replacement; after output transfer input accepts no sooner than next edge. Latency 1; maximum one word per two edges.
- Required directed checks: Ready/valid timing, long stall, expected alternating transfer cadence.
- Presets: default; W=1; W=7; W=256.

### stream_mux

- Parameters: W=32 [1..256], N=4 [2..16].
- Ports: CLK; I(s_valid_i:N,s_data_i:N*W,sel_i:L(N),m_ready_i:1); O(s_ready_o:N,m_valid_o:1,m_data_o:W).
- Behavior: Selected lane is combinationally forwarded. When valid is exposed but stalled, latch selection until transfer; changes to sel do not switch the stalled word. Invalid selection exposes no valid and no ready.
- Required directed checks: Selection changes while stalled, invalid selection, one-ready-lane rule, no traffic when chosen lane invalid.
- Presets: default; W=1,N=2; W=7,N=3; W=64,N=16.

### stream_demux

- Parameters: W=32 [1..256], N=4 [2..16].
- Ports: CLK; I(s_valid_i:1,s_data_i:W,sel_i:L(N),m_ready_i:N); O(s_ready_o:1,m_valid_o:N,m_data_o:N*W).
- Behavior: Forward to selected output and latch selection while a valid word is stalled. Data is replicated to all output lanes but valid only on selected lane. Invalid selection stalls input.
- Required directed checks: Selection changes under stall, invalid selection, only selected ready matters, stable valid destination.
- Presets: default; W=1,N=2; W=7,N=3; W=64,N=16.

### stream_fork

- Parameters: W=32 [1..256], N=2 [2..8].
- Ports: CLK; I(s_valid_i:1,s_data_i:W,m_ready_i:N); O(s_ready_o:1,m_valid_o:N,m_data_o:N*W).
- Behavior: Capture one input word when empty. Track a pending bit per sink. Each sink receives it exactly once; completed sinks deassert valid while others stall. Input ready only when no pending sink (no same-edge replacement). Latency 1.
- Required directed checks: One stalled sink, ready permutations, no duplicate at fast sink, reset partial distribution.
- Presets: default; W=1,N=2; W=7,N=3; W=64,N=8.

### stream_join

- Parameters: W=32 [1..256], N=2 [2..8].
- Ports: CLK; I(s_valid_i:N,s_data_i:N*W,m_ready_i:1); O(s_ready_o:N,m_valid_o:1,m_data_o:N*W).
- Behavior: Each lane has one independent slot. s_ready[j]=!full[j]. Output valid only when all slots full; output transfer clears all. No same-edge lane replacement. Preserve lane order in concatenated tuple.
- Required directed checks: Inputs arriving different edges, one missing lane, backpressure complete tuple, no overwrite of occupied lane.
- Presets: default; W=1,N=2; W=7,N=3; W=64,N=8.

### stream_upsizer

- Parameters: IW=8 [1..128], RATIO=4 [2..16], IW*RATIO<=256.
- Ports: CLK; S(IW); M(IW*RATIO).
- Behavior: Pack exactly RATIO words, earliest word in lowest lane. Publish only complete group; no input accepted while output group held, including output-transfer edge. No partial flush.
- Required directed checks: Lane order, incomplete group invisible, backpressure, reset mid-group.
- Presets: default; IW=1,RATIO=2; IW=7,RATIO=3; IW=16,RATIO=16.

### stream_downsizer

- Parameters: OW=8 [1..128], RATIO=4 [2..16], OW*RATIO<=256.
- Ports: CLK; S(OW*RATIO); M(OW).
- Behavior: Capture a wide word; emit exactly RATIO low-first lanes. No input while held, including final output edge. First lane available next edge.
- Required directed checks: Lane order, stalls between lanes, no early next-input acceptance, reset mid-word.
- Presets: default; OW=1,RATIO=2; OW=7,RATIO=3; OW=16,RATIO=16.

### stream_credit_adapter

- Parameters: W=32 [1..256], CREDITS=4 [1..256].
- Ports: CLK; I(s_valid_i:1,s_data_i:W,credit_return_i:1); O(s_ready_o:1,tx_valid_o:1,tx_data_o:W,credits_o:C(CREDITS),error_o:1).
- Behavior: credits resets to CREDITS. s_ready iff credit count>0. Input transfer emits tx_valid/data combinationally that cycle and decrements at edge. A return adds one; simultaneous send/return cancels. Return at full without send pulses error and clamps. At zero a same-edge return does not enable send. Receiver must always accept tx_valid.
- Required directed checks: Exhaust/replenish, return at zero/full, simultaneous events, no transmission without credit.
- Presets: default; W=1,CREDITS=1; W=7,CREDITS=3; W=64,CREDITS=256.

### stream_rate_limiter

- Parameters: W=32 [1..256], INTERVAL=4 [1..256].
- Ports: CLK; S(W); M(W).
- Behavior: Zero-storage forwarding when cooldown=0. After transfer block the next INTERVAL-1 edges; earliest next transfer is INTERVAL edges later. Idle time accumulates no burst credit. Hold payload through downstream stall.
- Required directed checks: INTERVAL=1 full throughput, exact spacing, idle then burst, stalls do not consume tokens.
- Presets: default; W=1,INTERVAL=1; W=7,INTERVAL=3; W=64,INTERVAL=256.

### cdc_level_sync

- Parameters: STAGES=2 [2..4], RESET_VALUE=0 [0 or 1].
- Ports: CLK; I(async_i:1); O(sync_o:1).
- Behavior: Destination-only STAGES-flop synchronizer. All flops reset to RESET_VALUE; no combinational logic between stages. Input must be a single stable level, not a data bus.
- Required directed checks: Sampled level reaches output after STAGES captures; reset value; structural flop chain. No metastability/MTBF claim.
- Presets: default; STAGES=2,RESET_VALUE=1; STAGES=4,RESET_VALUE=0.

### cdc_pulse_toggle

- Parameters: None.
- Ports: I(src_clk_i:1,src_rst_ni:1,pulse_i:1,dst_clk_i:1,dst_rst_ni:1); O(pulse_o:1).
- Behavior: Source pulse toggles a bit; two destination synchronization stages plus registered XOR detector create a one-destination-edge pulse. No source acknowledgment. Legal source pulses are separated by at least four destination periods; closer pulses may merge and are unsupported. Both resets assert together.
- Required directed checks: Legal pulse spacing at several clock ratios, one-edge output, coordinated reset, no phantom pulse after reset.
- Presets: default only.

### cdc_pulse_handshake

- Parameters: None.
- Ports: I(src_clk_i:1,src_rst_ni:1,pulse_i:1,dst_clk_i:1,dst_rst_ni:1); O(ready_o:1,pulse_o:1,overflow_o:1).
- Behavior: Toggle request/ack with two-flop crossings. Accept pulse only when source ready; busy pulse is rejected with one-source-edge overflow. Destination emits once per accepted toggle and acknowledges it. Both resets assert together; ready starts true after reset.
- Required directed checks: Pulses while busy, rapid legal sends, ratios and phases, exact accepted/delivered count, coordinated reset in flight.
- Presets: default only.

### cdc_bus_handshake

- Parameters: W=32 [1..256].
- Ports: I(src_clk_i:1,src_rst_ni:1,s_valid_i:1,s_data_i:W,dst_clk_i:1,dst_rst_ni:1,m_ready_i:1); O(s_ready_o:1,m_valid_o:1,m_data_o:W).
- Behavior: One outstanding word. Source captures and holds bus until destination consumes and synchronized ack returns. Two-flop request/ack crossings; destination captures held data after synchronized request. Output obeys ready/valid. Both resets assert together. Bundled-data timing constraint must be documented; do not synchronize individual data bits.
- Required directed checks: Random clock ratios, held destination, stable source holding register until ack, exact queue correspondence, coordinated reset.
- Presets: default; W=1; W=7; W=256.

### reset_sync

- Parameters: STAGES=2 [2..4].
- Ports: I(clk_i:1,async_rst_ni:1); O(rst_no:1).
- Behavior: Assert output reset asynchronously low. Release high only after STAGES rising edges with input reset high. No additional clock-domain crossing logic.
- Required directed checks: Assertion between edges, early reassertion restarts release, exact release edge.
- Presets: default; STAGES=3; STAGES=4.

### reset_stretcher

- Parameters: CYCLES=4 [1..256].
- Ports: I(clk_i:1,async_rst_ni:1); O(rst_no:1).
- Behavior: Asynchronous input assertion forces output low; after input goes high keep output low for CYCLES rising edges, release immediately after the CYCLES-th edge. Reassert restarts count. Input release must satisfy this circuit clock recovery/removal constraint or use reset_sync first.
- Required directed checks: Short assertion between edges, release counts 1/4, reassert during count.
- Presets: default; CYCLES=1; CYCLES=7; CYCLES=256.

### reset_sequencer

- Parameters: N=3 [2..8], GAP=4 [1..256].
- Ports: CLK; I(enable_i:1); O(resets_no:N,done_o:1).
- Behavior: Reset all outputs low. While enabled, release output 0 after GAP edges, then next output every GAP edges. Deassert enable synchronously resets all low and restarts. done iff all released. Outputs stay high until disable/reset.
- Required directed checks: Exact order/gap, disable mid-release, GAP=1, asynchronous reset.
- Presets: default; N=2,GAP=1; N=4,GAP=3; N=8,GAP=256.

### input_deglitch

- Parameters: STABLE=4 [1..256].
- Ports: CLK; I(async_i:1); O(level_o:1,rise_o:1,fall_o:1).
- Behavior: Two-flop input synchronizer then require STABLE consecutive samples of a new value before changing output. Consecutive count starts with first differing synchronized sample. Equal current-level sample resets count. Outputs/reset zero. Registered rise/fall pulse on accepted change.
- Required directed checks: Subthreshold glitches, exactly threshold duration, alternating glitches, STABLE=1, reset while input high.
- Presets: default; STABLE=1; STABLE=7; STABLE=256.

## 3. Extra functional and structural checks

For every stream entry, maintain an input/output transfer scoreboard. Exercise
ready patterns all-ready, alternating, 100-edge stall, and seeded random. Include
simultaneous push/pop at each occupancy, not only in a steady-state middle case.
Check valid and every payload bit on every stalled edge. For fork/join use a
separate per-lane queue. Define test completion by drained accepted inputs.

For memories, model bytes independently. For two-write collision verify the
entire old word survives, not only the error pulse. Confirm no array reset loop
was inserted to make unwritten reads deterministic. ROM images are packed source
parameters, never an unrecorded local initialization file.

For asynchronous entries use time schedules with write/read edge periods (in
simulation ticks) of (10,10), (10,30), (30,10), (14,22), with offsets 0 and 3.
Simultaneous edges must be handled as independent clock events in the reference.
Each FIFO case includes at least 1,024 accepted words and a bounded drain with
source idle and sink ready. Clock liveness is an assumption. For pulse-toggle,
respect the stated minimum pulse separation and separately document unsupported
near pulses without requiring lossless behavior. For handshake crossings count
only accepted events, test source busy rejection, and bound delivery after both
clocks resume. Coordinated reset cancels all pre-reset in-flight data.

Perform a maintained structural inspection of generated RTL for synchronizer
stage count, reset polarity, Gray pointer crossing, held bundled data, and lack of
combinational logic between sync stages. Record a digital-structure check, not
physical CDC sign-off. Formal assertions may add evidence if a supported tool is
available; absence is `not_run`, not a reason to weaken simulation or structure.

## 4. Spec Editor stress

Use a real browser and real isolated services. Start from a temporary copy of
`fifo_sync` and a temporary `reset_sync` Spec. Opening a local `.spec` with the
existing application is sufficient; no library-service integration is needed.

1. Open fifo_sync. Inspect ports/parameters/SV. Edit W from 32 to 7 using the
   actual parameter control and save. Reopen and verify symbolic ranges and SV
   remain linked to W; produce RTL and run W=7,DEPTH=4 simulation.
2. Edit the SV through its UI Section: add a harmless explanatory comment, save,
   reopen, and compare body bytes. Attempt a module header in the body; require
   validation and preservation of the last saved version.
3. Attempt DEPTH=0. Require a precise invalid-configuration result before a
   qualifying RTL run; do not require a generic editor to know a new library range
   rule unless it supports that rule. A saved invalid draft cannot be published.
4. Make another parameter edit then cancel the draft; reopen and show no durable
   change. Exercise undo/redo where supported and verify no duplicate port rows.
5. Open reset_sync, change STAGES from 2 to 3, save, reload, and check the release
   timing through the Activity output. Repeat save while a second client changes
   the description: a stale save must conflict or reconcile explicitly, never
   overwrite the other saved edit silently.

Retain browser trace, source revisions, and post-reopen assertions. If a control
is absent, mark that stress case unavailable and continue the library matrix via
validated APIs. Do not seed the final UI edit through HTTP and call it UI success.

## 5. Service and predecessor regression

Test search/filter for storage, streams, and cdc_reset; level/latency/reset
metadata rendering; concurrent upload/search; invalid evidence digest; service
restart and full reindex of 64 entries. Download three new files and compare exact
bytes. Copy fifo_async alone to an isolated temporary directory and produce RTL.

Re-run Phase 1 mux W=7,N=3, register_enable W=7, counter_modulo W=5,MODULUS=7, and
Gray conversion W=7 to protect shared range and state behavior. Confirm all 32
predecessor package digests unchanged.

## 6. Commands and completion gate

```bash
uv run spec2gds-library check --phase 1 --output temp/TEMP_p2/prerequisite
uv run spec2gds-library check --phase 2 --candidates temp/TEMP_p2/candidates --output temp/TEMP_p2/check
uv run spec2gds-library verify --phase 2 --candidates temp/TEMP_p2/candidates --output temp/TEMP_p2/verify
uv run pytest tests/spec_library -m 'not extensive'
scripts/test-all.sh fast
scripts/test-all.sh integration --scope spec,circuit,activities
scripts/test-all.sh regression
uv run spec2gds-library publish --phase 2 --candidates temp/TEMP_p2/candidates --evidence temp/TEMP_p2/verify --output temp/TEMP_p2/publish
uv run spec2gds-library check --phase 2 --output temp/TEMP_p2/published-check
```

`circuit` covers the browser application used by Spec Editor where selected by
current suite registration. Inspect the dry-run and add browser scenarios to the
correct existing suite. Regression is required for index persistence and any
shared parameter/range fixes. Do not omit required live checks in fast.

Accept 32 new files only after every mandatory matrix passes. The service must
index 64 accepted versions and survive rebuild. Handoff must record memory
collision policy, CDC clock/reset assumptions, structural evidence limits,
Spec Editor stress results, fixes, and exact preserved predecessor digests.

# Phase 1: logic, state, and standalone hosting

Status: implementation instructions. No completion is claimed.

## 1. Inputs, outputs, and ordered implementation

Read [the shared contract](../README.md) in full. This file supplies the complete
Phase 1 delta. There is no predecessor implementation requirement. Deliver the
32 entries below and the first useful standalone catalogue service. Do not add
Spec Editor or Circuit Designer library integration.

Execute this order:

1. Inspect the source-format APIs and `rtl.generate` tests listed in the guide.
   Record tool/credential availability under `spec_library/TEMP_p1_<run>/`.
   Add ignored `.state/` storage, the new package directories, CLI entry points,
   strict catalogue/evidence schemas, and maintained test scaffolding. Create
   `spec_library/`, copy this plan's `inventory.json` to
   `spec_library/inventory.json`, and add its designer usage README. Keep the
   implementation instructions in `docs/TEMP_spec_library_plan/`.
2. Add optional explicit creation VLNV through the typed operation and HTTP
   operation. Preserve the old work identity when omitted. Prove atomic duplicate
   rejection, normalized-name agreement, unchanged existing callers, and unchanged
   source when a transaction fails. This is a shared source contract change.
3. Create candidate Specs with typed operations. Complete combinational entries
   before state entries. Each entry needs declared parameters, expanded wire
   ports, a narrative contract, an executable SV section, and catalogue asset.
   Persist before RTL execution. Do not call tie-off RTL functional hardware.
4. Implement `check`, `verify`, and `publish` with the exact shared CLI semantics.
   Make the independent reference harness load saved candidates. Establish
   deterministic simulation and evidence records before bulk publication.
5. Implement all hosting routes and the basic static UI in shared section 7.
   Use only package validators during upload; run functional checks offline.
6. Run all entry matrices, real HTTP stress below, service/browser checks, and
   required software profiles. Publish only exact tested candidate bytes.
   Write the handoff and update the 32 inventory statuses after acceptance.

A missing authoring operation is a small source API extension, not permission to
write XML or mutate SpecIR. Use current implementation conventions for parameter
records and SV section payloads. Add tests to freeze those conventions.

## 2. Component contracts

Apply the notation, reset rules, legal-parameter checks, and randomized matrix in
shared sections 5 and 6. `default` means the complete defaults in that entry;
other presets override only the stated defaults and must be recorded as full maps.
Presets explicitly called illegal are negative checks, not simulation targets.

### mux

- Parameters: W=32 [1..256], N=4 [2..16].
- Ports: I(data_i:N*W,sel_i:L(N)); O(data_o:W).
- Behavior: Select lane sel_i. An out-of-range selection returns zero.
- Required directed checks: Every selection; lane patterns with distinct words; invalid selections when N is not a power of two.
- Presets: default; W=1,N=2; W=7,N=3; W=256,N=16.

### demux

- Parameters: W=32 [1..256], N=4 [2..16].
- Ports: I(data_i:W,sel_i:L(N),en_i:1); O(data_o:N*W).
- Behavior: All lanes zero except selected lane when enabled. Invalid selection leaves all zero.
- Required directed checks: Every lane, disabled state, invalid selection, all-zero and all-one data.
- Presets: default; W=1,N=2; W=7,N=3; W=256,N=16.

### priority_mux

- Parameters: W=32 [1..256], N=4 [2..16].
- Ports: I(data_i:N*W,req_i:N); O(data_o:W,valid_o:1,index_o:L(N)).
- Behavior: Lowest requested lane wins. No request gives all outputs zero.
- Required directed checks: Exhaust request masks at N<=8; overlapping requests; no request.
- Presets: default; W=1,N=2; W=7,N=3; W=64,N=16.

### binary_decoder

- Parameters: N=8 [2..256].
- Ports: I(index_i:L(N),en_i:1); O(onehot_o:N).
- Behavior: Set exactly bit index_i when enabled and in range. Otherwise zero.
- Required directed checks: All indices, disabled state, out-of-range index for N=3.
- Presets: default; N=2; N=3; N=256.

### onehot_encoder

- Parameters: N=8 [2..256].
- Ports: I(onehot_i:N); O(index_o:L(N),valid_o:1).
- Behavior: Valid only for exactly one set bit. Invalid inputs give index zero and valid zero.
- Required directed checks: Zero, each single bit, all double bits, all ones.
- Presets: default; N=2; N=3; N=256.

### priority_encoder

- Parameters: N=8 [2..256].
- Ports: I(req_i:N); O(index_o:L(N),valid_o:1,grant_o:N).
- Behavior: Lowest set bit wins. No request gives all zero.
- Required directed checks: All masks for N<=8; each position; overlapping low/high bits.
- Presets: default; N=2; N=3; N=256.

### onehot_checker

- Parameters: N=8 [1..256].
- Ports: I(data_i:N); O(onehot_o:1,onehot0_o:1).
- Behavior: onehot is exactly one bit set; onehot0 permits zero or one.
- Required directed checks: Zero, single bits, every pair, all ones.
- Presets: default; N=1; N=3; N=256.

### leading_zero_count

- Parameters: W=32 [1..256].
- Ports: I(data_i:W); O(count_o:C(W),zero_o:1).
- Behavior: Count consecutive zero bits from the MSB. All-zero input gives W and zero_o=1.
- Required directed checks: Zero, all ones, each single set bit, alternating patterns; exhaustive W=8.
- Presets: default; W=1; W=8; W=257 is illegal; W=256.

### trailing_zero_count

- Parameters: W=32 [1..256].
- Ports: I(data_i:W); O(count_o:C(W),zero_o:1).
- Behavior: Count consecutive zero bits from the LSB. All-zero input gives W and zero_o=1.
- Required directed checks: Zero, all ones, each single set bit, alternating patterns; exhaustive W=8.
- Presets: default; W=1; W=8; W=257 is illegal; W=256.

### population_count

- Parameters: W=32 [1..256].
- Ports: I(data_i:W); O(count_o:C(W)).
- Behavior: Return the number of set bits.
- Required directed checks: Zero, all ones, each single bit, alternating patterns; exhaustive W=8.
- Presets: default; W=1; W=8; W=256.

### bit_reverse

- Parameters: W=32 [1..256].
- Ports: I(data_i:W); O(data_o:W).
- Behavior: Output bit j equals input bit W-1-j.
- Required directed checks: Each single bit; reversing twice restores input.
- Presets: default; W=1; W=7; W=256.

### byte_reverse

- Parameters: BYTES=4 [1..32].
- Ports: I(data_i:8*BYTES); O(data_o:8*BYTES).
- Behavior: Reverse byte order, preserve bit order in each byte.
- Required directed checks: Distinct byte ramp, single byte markers, reverse twice.
- Presets: default; BYTES=1; BYTES=3; BYTES=32.

### barrel_shift

- Parameters: W=32 [1..256].
- Ports: I(data_i:W,amount_i:L(W+1),right_i:1,arith_i:1); O(data_o:W).
- Behavior: right_i=0 shifts left with zero fill. Right shift sign-extends only when arith_i=1. Amount>=W gives zero, or all sign bits for arithmetic right.
- Required directed checks: All amounts including W and larger encodings; signed min/max; both directions and modes.
- Presets: default; W=1; W=7; W=256.

### rotate

- Parameters: W=32 [1..256].
- Ports: I(data_i:W,amount_i:L(W),right_i:1); O(data_o:W).
- Behavior: Rotate by amount modulo W; W=1 is identity.
- Required directed checks: All encoded amounts; rotate left then right; non-power-of-two W.
- Presets: default; W=1; W=7; W=256.

### sign_extend

- Parameters: IW=8 [1..256], OW=32 [IW..256].
- Ports: I(data_i:IW); O(data_o:OW).
- Behavior: Replicate input sign bit above the preserved IW low bits. Equal widths are legal.
- Required directed checks: Zero, signed limits, all ones, equal width, OW<IW rejection.
- Presets: default; IW=1,OW=1; IW=7,OW=13; IW=128,OW=256.

### zero_extend

- Parameters: IW=8 [1..256], OW=32 [IW..256].
- Ports: I(data_i:IW); O(data_o:OW).
- Behavior: Insert zero bits above the preserved IW low bits. Equal widths are legal.
- Required directed checks: Zero, signed limits, all ones, equal width, OW<IW rejection.
- Presets: default; IW=1,OW=1; IW=7,OW=13; IW=128,OW=256.

### bit_mask

- Parameters: W=32 [1..256].
- Ports: I(start_i:L(W),length_i:C(W)); O(mask_o:W).
- Behavior: Set bits j where start_i<=j<start_i+length_i and j<W. Addition uses enough width to avoid wrap. Out-of-range start gives zero.
- Required directed checks: Length 0/W, last-bit start, clipped range, illegal encoded start.
- Presets: default; W=1; W=7; W=256.

### register

- Parameters: W=32 [1..256].
- Ports: CLK; I(d_i:W); O(q_o:W).
- Behavior: Capture d_i every edge; reset q_o=0. This is the basic boundary-reset register.
- Required directed checks: Reset assertion between edges, capture each edge, reset while active.
- Presets: default; W=1; W=7; W=256.

### register_enable

- Parameters: W=32 [1..256].
- Ports: CLK; I(d_i:W,en_i:1); O(q_o:W).
- Behavior: Capture only when enabled; otherwise hold. Reset wins.
- Required directed checks: Enable transitions, long hold, reset while disabled.
- Presets: default; W=1; W=7; W=256.

### register_sync_reset

- Parameters: W=32 [1..256], RESET_VALUE=0 [0..2**W-1].
- Ports: I(clk_i:1,rst_ni:1,d_i:W); O(q_o:W).
- Behavior: Exception to CLK: reset is synchronous active-low. At each edge reset selects RESET_VALUE, otherwise capture d_i.
- Required directed checks: Assert reset between edges: q does not change until next edge; nonzero reset value.
- Presets: default; W=1,RESET_VALUE=1; W=7,RESET_VALUE=85; W=256,RESET_VALUE=0.

### register_async_reset

- Parameters: W=32 [1..256], RESET_VALUE=0 [0..2**W-1].
- Ports: CLK; I(d_i:W); O(q_o:W).
- Behavior: Asynchronous reset selects RESET_VALUE; capture d_i at every non-reset edge.
- Required directed checks: Assert reset between edges: immediate output update; nonzero reset values; synchronous release.
- Presets: default; W=1,RESET_VALUE=1; W=7,RESET_VALUE=85; W=256,RESET_VALUE=0.

### shift_register

- Parameters: W=32 [1..256], STAGES=4 [1..32].
- Ports: CLK; I(en_i:1,d_i:W); O(q_o:W,taps_o:STAGES*W).
- Behavior: Shift one word per enabled edge. Lane 0 is newest, q is oldest. All stages reset zero.
- Required directed checks: Exact enabled-edge latency, disabled hold, every tap.
- Presets: default; W=1,STAGES=1; W=7,STAGES=3; W=64,STAGES=32.

### pipeline_delay

- Parameters: W=32 [1..256], STAGES=2 [1..16].
- Ports: CLK; I(valid_i:1,data_i:W); O(valid_o:1,data_o:W).
- Behavior: Unstalled pipeline; input at edge t transfers at output t+STAGES. Shift data and valid each edge. Reset valid and data zero.
- Required directed checks: Bubbles, continuous input, exact latency, reset clears in-flight valid.
- Presets: default; W=1,STAGES=1; W=7,STAGES=3; W=64,STAGES=16.

### counter_up

- Parameters: W=32 [1..64].
- Ports: CLK; I(en_i:1,clear_i:1); O(count_o:W,wrap_o:1).
- Behavior: clear wins over enable and clears count. Enabled max wraps to zero and emits one-edge wrap; wrap otherwise zero.
- Required directed checks: Clear+enable, max wrap, disabled max, repeated wraps at W=1.
- Presets: default; W=1; W=5; W=64.

### counter_up_down

- Parameters: W=32 [1..64].
- Ports: CLK; I(up_i:1,down_i:1,clear_i:1); O(count_o:W,wrap_o:1).
- Behavior: Clear wins. Exactly one direction changes count modulo 2**W. Both or neither hold. wrap pulses on max->0 or 0->max only.
- Required directed checks: Both directions asserted, both wraps, clear collision.
- Presets: default; W=1; W=5; W=64.

### counter_saturating

- Parameters: W=32 [1..64].
- Ports: CLK; I(up_i:1,down_i:1,clear_i:1); O(count_o:W,at_min_o:1,at_max_o:1).
- Behavior: Clear wins. Exactly one direction changes count, clamped at 0/max. Flags reflect current count.
- Required directed checks: Repeated increments at max, decrements at zero, both directions hold.
- Presets: default; W=1; W=5; W=64.

### counter_modulo

- Parameters: W=8 [1..64], MODULUS=16 [2..2**W].
- Ports: CLK; I(en_i:1,clear_i:1); O(count_o:W,wrap_o:1).
- Behavior: Count 0..MODULUS-1. Clear wins. Enabled terminal wraps and pulses wrap for one edge.
- Required directed checks: Non-power-of-two modulus, disabled terminal, clear at terminal.
- Presets: default; W=1,MODULUS=2; W=5,MODULUS=7; W=64,MODULUS=17.

### edge_detector

- Parameters: None.
- Ports: CLK; I(level_i:1); O(rise_o:1,fall_o:1).
- Behavior: Compare current input with previous sampled level (reset zero). Register one-edge pulses; high first sample gives rise.
- Required directed checks: Sustained high/low, alternating samples, input changes between edges, reset while high.
- Presets: default only.

### pulse_stretcher

- Parameters: CYCLES=4 [1..256].
- Ports: CLK; I(pulse_i:1); O(pulse_o:1).
- Behavior: An input high at edge t sets output high in interval after t and for CYCLES edge intervals total. Retrigger restarts that interval; sustained input keeps high.
- Required directed checks: CYCLES=1, retrigger on final high edge, sustained input, reset.
- Presets: default; CYCLES=1; CYCLES=7; CYCLES=256.

### timer

- Parameters: W=16 [1..64].
- Ports: CLK; I(start_i:1,cancel_i:1,load_i:W); O(busy_o:1,done_o:1).
- Behavior: cancel wins, clears busy without done. start reloads/restarts; load=0 emits done immediately after that edge, busy=0. Otherwise busy=1 and done pulses after exactly load further edges. done defaults zero each edge.
- Required directed checks: Load 0/1/max at W=3, start while busy, cancel on expiry, no repeated done.
- Presets: default; W=1; W=3; W=64.

### binary_to_gray

- Parameters: W=8 [1..64].
- Ports: I(binary_i:W); O(gray_o:W).
- Behavior: gray = binary XOR (binary >> 1).
- Required directed checks: All values at W=8; inverse round trip; adjacent binary codes differ by one Gray bit.
- Presets: default; W=1; W=7; W=64.

### gray_to_binary

- Parameters: W=8 [1..64].
- Ports: I(gray_i:W); O(binary_o:W).
- Behavior: Binary bit j is XOR of Gray bits W-1 down through j.
- Required directed checks: All values at W=8; inverse round trip; adjacent binary codes differ by one Gray bit.
- Presets: default; W=1; W=7; W=64.

## 3. Real HTTP Spec API stress

Use a real isolated Spec service process, not only FastAPI's in-process client.
Use `POST /documents/create`, `/documents/open`, `/transactions`, and the current
snapshot endpoint. Inspect their current schemas; bind requests to the returned
document key and revision. Store sanitized requests/responses and exact source
hashes. All Specs in this scenario are temporary and do not count toward 32.

1. Create `api_reference.spec`. Through HTTP create a mux with W=7,N=3, a
   register_enable with W=7, and a counter_modulo with W=5,MODULUS=7. Supply their
   exact declared ports and body-only SV via published typed operations.
2. Save/reopen, produce RTL through the Activity, and run the same leaf reference
   checks. Compare normalized interface/behavior with the corresponding library
   presets. Different opaque IDs are allowed; lost fields or behavior are not.
3. Capture revision R. Client A edits the mux description at R and succeeds.
   Client B submits a different edit against stale R: require 409 and no partial
   mutation. Refresh and resubmit once with the new revision; both edits survive.
4. Submit one atomic transaction containing a valid description change and an
   invalid port range. Reject the transaction; no part is saved. Submit a body
   containing a module header: reject it without overwriting the previous body.
5. Kill/restart the service after a successful saved write. Reopen the file and
   compare source, identity, parameters, SV, and revision. Do not count an
   accepted operation as durable until the saved package is reopened.

## 4. Hosting and CLI verification

Implement maintained tests for all shared service routes, schema errors, filters,
version ordering, bounded uploads, evidence digest binding, and index recovery.
Run a real service process for download-byte and restart checks. Use another
instance with an independent root to prove no dependency on authoring services.

Required assertions:

- New upload returns 201, identical retry returns 200, changed bytes with the
  same root VLNV returns 409, and the original download digest is unchanged.
- Two racing uploads of the same key cannot overwrite. Same content coalesces;
  different content has one winner and one 409. Distinct IDs can both publish.
- A ZIP traversal, duplicate name, symlink, invalid manifest, unknown profile,
  broken reference, absent catalogue root, and size/ratio violation are rejected
  without durable output. Use small crafted fixtures, not a large decompression.
- A structurally valid body-less upload is shown as implementation absent and
  unreported functional evidence. It cannot pass the library publication gate.
- Evidence for a different package digest is rejected. A correct recorded report
  is displayed as supplied evidence, never as service-executed verification.
- Delete the derived SQLite index only; rebuild it and compare the full result
  set, version metadata, and byte-identical downloads. Preserve source files.
- Simulate interruption after durable package publication and before index
  commit. Restart recovers the version once. Incomplete staged files are ignored.
- CLI publication refuses any missing/failed entry or digest mismatch before
  changing inventory. A crash during a batch can leave immutable files present;
  retry validates and completes them idempotently, with no false delivered status.

Browser checks must use rendered controls to upload a temporary candidate,
search, change a category filter, open details, select a version, and download it.
Assert the downloaded bytes. Test keyboard operation, a 390px viewport, an empty
catalogue, malformed upload, immutable conflict, and stopped service. Escape a
summary/tag containing HTML and verify it remains text.

## 5. Required commands and completion gate

The commands below run after code exists. Use a unique ignored output directory;
pass that run directory to child tools for their temporary files. Record actual
commands, exit codes, and evidence. Candidate CLI commands use `--candidates`
before publication; repeat `check` against canonical paths after publication.

```bash
uv run spec2gds-library check --phase 1 --candidates spec_library/TEMP_p1/candidates --output spec_library/TEMP_p1/check
uv run spec2gds-library verify --phase 1 --candidates spec_library/TEMP_p1/candidates --output spec_library/TEMP_p1/verify
uv run pytest tests/spec_library -m 'not extensive'
scripts/test-all.sh fast
scripts/test-all.sh integration --scope spec,activities,shared
scripts/test-all.sh regression
uv run spec2gds-library publish --phase 1 --candidates spec_library/TEMP_p1/candidates --evidence spec_library/TEMP_p1/verify --output spec_library/TEMP_p1/publish
uv run spec2gds-library check --phase 1 --output spec_library/TEMP_p1/published-check
```

Regression is required because explicit identity creation and durable hosting
change shared contracts/persistence. Register the hardware matrix under maintained
suite selection; it must also be runnable through `verify` without a browser.

Accept only if all 32 IDs have canonical files, usage and evidence; all presets
and mandatory checks pass; hosting and UI checks pass; stale/atomic HTTP cases
pass; required profiles pass; and no implementation is a stub. `check --phase 1`
must pass from a fresh process. The handoff gives the exact service command, one
upload/download example, the 32 digest records, and outstanding stress limits.

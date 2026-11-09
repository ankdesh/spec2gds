# Spec Catalog: common hardware and verification rules

Use these rules with the Component contracts. See the [service guide](../../spec_catalog_service/README.md) for current commands and delivery status.

## 5. Common hardware notation and rules

Each Component subsection is normative. Parameters are elaboration constants.
`X=32 [1..256]` means default 32 and inclusive legal range. Only listed parameters
are public. Reject an illegal preset before RTL execution; also emit an
elaboration-time diagnostic for illegal dimensions and cross-parameter relations
in direct HDL use. Range-check wide values before conversion to an SV type;
HDL type truncation can otherwise hide an over-wide caller value. Packed arrays have
LSB-first lanes: lane `j` is bits `j*W +: W`. Unsigned unless stated signed.
`I(a:W,b:1)` and `O(q:W)` define exact input and output names and bit widths.
Widths use evaluated parameter formulas; a one-bit port is scalar. Define
`L(n)=max(1,ceil(log2(n)))`, `C(n)=L(n+1)`. Never emit a zero-width range.
L/C are documentation notation: translate L(n) to `((n)<=1 ? 1 : $clog2(n))`
and C(n) to L(n+1) in source expressions. A width greater than one uses descending
range `width-1:0`. There is no implicit public L/C parameter or SV function.
Use `int unsigned` for bounded dimensions and counts. Use appropriately sized
packed constants for RESET_VALUE, INIT, COEFFS, WEIGHTS, POLY, XOROUT, SEED, and
TAPS; GAIN is signed COEFF_W bits. Do not truncate wide defaults through a 32-bit
SV `int` or a JavaScript number. INIT follows WIDTH for CRC and W*DEPTH for ROM.
Name presets `default`, then `p1`, `p2`, ... in listed positive-preset order.
Ignore explicitly illegal presets when assigning those names. Expand all
parameter maps before saving source metadata or evidence.

`CLK` expands to `I(clk_i:1,rst_ni:1)`. Unless overridden, state updates on the
rising edge of `clk_i`, reset is asynchronous active-low, and reset clears state
and output-valid flags to zero. Deassert reset synchronously at the environment
boundary. Data without a valid flag must have the specified reset value. Payload
while invalid is unspecified unless the Component says otherwise. Combinational
Components have no clock or reset and must not infer latches.

`S(W)` expands to input stream ports
`I(s_valid_i:1,s_data_i:W), O(s_ready_o:1)`.
`M(W)` expands to output stream ports
`O(m_valid_o:1,m_data_o:W), I(m_ready_i:1)`.
`SL(W)` / `ML(W)` add `s_last_i` / `m_last_o`, one bit, to that stream.
A transfer occurs at an edge with valid and ready both high. A producer holds
valid and all payload fields stable until transfer. No transfer occurs in reset.
Backpressure cannot lose, duplicate, reorder, or change an accepted word.
Latency counts edges from input transfer to the earliest edge at which that
word can transfer at the output. State whether combinational fall-through exists.

`REQ(A;R)` expands to `CLK`, `I(req_valid_i:1,<A>)`, `O(req_ready_o:1)`,
`O(rsp_valid_o:1,<R>)`, and `I(rsp_ready_i:1)`; use the field names in parentheses
in each entry. It is one request stream and one response stream. One outstanding
request unless explicitly pipelined. Hold every response field under stall.
For a non-pipelined unit ready is low while computing or holding a response;
a new request is permitted on the edge after response transfer. Fixed latency
`K` means request at edge `t`, response available for transfer at `t+K`.
Reset cancels incomplete work. A pipelined unit must stall all affected stages
without overwriting responses and can accept/produce one per edge without stalls.

All counters and arithmetic wrap at their output width unless saturation is
specified. Shifts fill zero unless arithmetic right shift is explicitly selected.
Signed arithmetic is two's complement. Test intermediate widths and signed casts.
Use clock enables, not RTL-created clocks, except explicit independent CDC clocks.
No `#delay`, file I/O, DPI, simulation-only functional body, or unbounded loop in
the hardware implementation. Testbench assertions and setup are separate assets.

## 6. Build, verification, and evidence contract

These commands already exist. Their console entry points are defined in
`spec_catalog_service/pyproject.toml`, not the root project's command list.
Extend their existing implementation for later phase matrices.

Run all command examples from the repository root. `check`, `verify`, and
`publish` accept `--catalog-root`, default `spec_catalog_service/catalog`; their `--phase` is
required, integer 1..4. `--output` is required for check/verify/publish and must be inside
an ignored repository `temp/TEMP_*` directory. Service roots are separately configurable.

```bash
uv run --package spec-catalog-service spec2gds-catalog check --phase 1 --output temp/TEMP_p1/check
uv run --package spec-catalog-service spec2gds-catalog verify --phase 1 --output temp/TEMP_p1/verify
uv run --package spec-catalog-service spec2gds-catalog publish --phase 1 --candidates temp/TEMP_p1/candidates --evidence temp/TEMP_p1/verify --output temp/TEMP_p1/publish
uv run --package spec-catalog-service spec2gds-catalog-service --host 127.0.0.1 --port 6017 --catalog-root spec_catalog_service/catalog --state-dir spec_catalog_service/.state
```

`check` is read-only. It validates inventory schema, phase dependency DAG, paths,
strict packages, root identity, required implementation, closed references, source
metadata, and evidence digests. Planned files may be absent only for later phases.
For phases up to and including the selected phase, missing releases fail. Add
`--candidates PATH` to select an unreleased tree for the selected phase only,
with the same relative paths; earlier phases still use canonical releases.
`verify` accepts the same flag, checks those prerequisites, and runs the hardware
matrix for the selected phase only. A candidate tree also contains a full copied
`inventory.json`; only the selected phase's version/path pins may differ from the
canonical inventory. Initial pins are 1.0.0; a replacement must increase semantic
version. Check/verify use those candidate pins and canonical predecessor pins.
Candidate `check` permits missing functional evidence because it precedes
verification; validate any supplied evidence without claiming a pass from absence.
Canonical `check` requires usage, passing mandatory evidence, and delivered
inventory status for all selected releases up to the requested phase. Candidate
trees contain source/usage and inventory; keep verification results in `--output`.
`verify` writes per-entry evidence to
`<output>/components/<id>/<version>/evidence.json`, plus aggregate `report.json`,
and never edits candidates or canonical releases. `publish --evidence PATH`
reads that output tree and copies its exact matching evidence alongside each
canonical source/usage file. `publish` requires passing evidence for exactly
those candidate digests, validates all files
before writing, and marks inventory entries delivered only after all required
releases exist, retaining prior release records and updating selected pins
atomically. Exit 0 is success, 1 is a failed check, 2 is usage or missing
prerequisites. Write a machine-readable `report.json` and a concise text summary.
Never create a missing implementation during `check` or `verify`.

Each entry must have these checks:

1. Strict load, root and implementation validation, save/reopen semantic equality,
   byte-identical repack of unchanged loaded source, and two identical RTL Activity
   outputs for the same source and parameters, excluding job envelope timestamps.
2. Verilator lint and executable simulation of RTL produced by `rtl.generate`.
   Do not simulate a separately hand-written module instead. Use independent
   Python integer/queue/state reference models and sampled input/output records.
3. Every listed preset, directed cases, reset during active work, hold/stall tests
   where applicable, and deterministic randomized tests. Seed is
   `int(sha256((id + ':' + preset).encode()).hexdigest()[:8],16)`. Record it.
   Minimum randomized work: 256 vectors for combinational entries; 2,000 edges
   for stateful entries; 256 completed requests for iterative numeric entries.
   Use explicit watchdogs, not an unbounded wait for completion.
4. For each parameter, reject below/above legal bounds and non-integral values;
   also check cross-parameter constraints. Integer parameters reject booleans,
   except parameters explicitly limited to 0/1, which accept either representation.
   Exhaustively test scalar controls.
   For a bit transform with W<=8, exhaust data inputs when practical. Use a
   reduced-width exhaustive model for encoders, arithmetic, parity, and ECC.
5. Fail unexpected lint warnings. Fix the cause. A narrowly documented third-party
   tool warning waiver needs a test and a recorded reason; never blanket-disable
   width, latch, multi-driver, or unconnected required-output diagnostics.

Each entry's `usage.md` states purpose, expanded interface, parameters and limits,
reset, latency/throughput, examples, error cases, protocol subset, and evidence
limits. Derive its interface table from the saved Spec. Each `evidence.json` has
`schema_version:1`, `package_sha256`, `source_revision_hash`, `root`, `runner_commit`,
`tools` (exact versions), `presets` (full maps), `checks`, `limitations`, and
`created_at` in UTC. Each check has `kind`, `preset`, `status`, `seed`, `summary`,
and `artifact_sha256`. `preset` is a declared preset name or null for package-wide
checks; `seed` and `artifact_sha256` may be null when not applicable. Required
kinds are `package`, `implementation`, `determinism` at package scope, and
`lint`, `simulation`, `parameter_validation` for every preset. Additional kinds
are `stress`, `structure`, `formal`, `synthesis`, and `physical`. Encode evidence as UTF-8 JSON with sorted keys, no whitespace separators, no
trailing newline, and no NaN/Infinity; hash those exact bytes for evidence identity.
All receipt/report times use ISO8601 UTC with `Z`. Status values
are `pass`, `fail`, `not_run`, `not_applicable`; a missing prerequisite is `not_run`.
Use `sha256:<64 lowercase hex>` for all digests. Record lint, simulation, package,
determinism, stress, formal, synthesis, and physical status separately.

Keep large logs/waves/compiled outputs under an ignored `TEMP_*` evidence directory.
Tracked evidence contains portable summaries and digests, never absolute host
paths, credentials, or invented results. A digest without retained raw output is
an audit hint, not a durable log. Reference tests must remain rerunnable.

Formal proof and synthesis are additional evidence, not universal breadth gates.
For CDC, ECC, bus ordering, and composites, the phase requires extra independent
checks but must not label digital simulation as physical proof. No matching tool
means `not_run`; do not silently substitute fixtures or claim qualification.


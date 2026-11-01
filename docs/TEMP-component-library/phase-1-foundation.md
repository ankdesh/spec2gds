# Phase 1: build and verify Components through the Spec API

Status: not started. Required authoring method: real HTTP Spec API.
Read [the implementation guide](README.md) first.
Next: [Spec Editor UI](phase-2-core-and-editors.md).

## 1. Fixed result and scope

Implement the shared library backend and create six seed Components through
HTTP calls to a real Spec service. Publish exact local releases, import them
into a second Spec, reopen them, and verify their hardware behaviour. Reproduce
and fix service defects found through this path.

This phase implements backend support needed by the next phases. It does not
claim UI or Assistant acceptance. Python APIs can implement shared domain code
and unit fixtures, but the six mandatory authoring runs must use HTTP.

## 2. Implementation locations and prerequisites

Use `spec2gds/spec/component_library/` for host-independent library code and
`library/` for maintained source. Extend the existing Spec service routes,
transaction types, registered annotations, and Activity registry. Use the
existing archive and revision classes; do not add a second ZIP or IR format.

Read these sources before editing:

- `spec2gds/spec/spec_format/{archive,models,ir,transactions,v1_api}.py`.
- `spec2gds/spec/spec_format/{sections,rtl_interface,component_verification}.py`.
- `spec2gds/spec/activities/{snapshot,view,host}.py` and `activities/rtl/`.
- `tests/spec/spec_format/`, `tests/spec/activities/`, and the unified test runner.
- `docs/rtl-generation.md` and the current API operation schemas.

Create `scripts/check-library-tools.py` with a read-only preflight. Require
Python 3.12+, Node 24.2+, Verilator 5.x, GNU Make, a C++ compiler, Yosys with the
Slang frontend, SymbiYosys, and Z3. Reuse the repository setup conventions and
pin the tool versions used for the release in the evidence manifest. Fail
clearly for unsupported/missing tools. Keep downloaded build files, compiler
caches, and temporary directories under an ignored repository `TEMP_` root.
Do not change the running designer stack or global configuration for checks.
Use isolated services and a per-run configuration.

## 3. Ordered implementation packages

### 1A. Implement typed source, release, and evidence contracts

Use JSON with `schema_version: 1` for the new library records. Register the
`library` annotation namespace under `annotations/library/`. Use strict typed
models and one schema source for clients and server.

| Record | Required content |
| --- | --- |
| `library.json` | Stable library ID, exact release/VLNV, root Component, family/tags, source path, exact dependencies, licence, presets, constraints and test source paths |
| `contract.json` | Referenced port/parameter IDs; behaviour; clock/reset domains; transfer event; latency; initiation interval; illegal inputs; family-specific semantics |
| `release.json` | Source/package digests; dependency pins; authoring method (`http_api`, `spec_editor_ui`, `circuit_designer_ui`, or `ai_assistant`); capability matrix; tool versions; evidence-manifest digest |
| `imports.json` | Published baseline, source-to-local ID/VLNV map, realization key, dependency/binding pins, current fork state |
| `evidence.json` | Requirements, checks, commands, exact source/configuration, assumptions, tool results, artifact digests, and coverage limits |

Store source-affecting contracts/import pins inside the Spec annotation tree.
Keep execution logs outside source identity. Avoid package/evidence digest
cycles. Ports and parameter declarations remain in IP-XACT; library contracts
reference them and add semantics. Validate dangling references and conflicting
claims. Source-only packages must contain no mutable Activity history.

For original source, inherit an explicit repository licence when one applies.
If none is declared, record `license: NOASSERTION` and
`distribution: local_only`; do not invent an open-source grant. This permits
the local catalogue planned here without making an external distribution
claim. An external release licence is outside these phases. Preserve applicable
existing notices and never claim rights over third-party source.

### 1B. Implement deterministic local storage and provider operations

Follow the guide's directory structure. The canonical maintained hardware
source is the unpacked Spec emitted after authoring. Do not retain an independent
handwritten IR, XML template, or Python recipe with duplicate editable behaviour.
Generic authoring tools and input requirements are maintained; derived packages,
indexes, modules, and logs go to `TEMP_library_<run>/`.

Implement typed `search`, `describe`, `resolve`, and `fetch`. Use exact pins,
stable sorting, a dependency DAG, deterministic topological order, and digest
validation. Detect missing releases, cycles, conflicting identities, unsafe
paths, illegal parameters, and ambiguous bindings. A missing/ambiguous binding
is an error. Do not choose a newest release during import.

Use stable IDs `spec2gds.blocks.<component_id>` and release VLNVs
`spec2gds.local:blocks:<component_id>:1.0.0` for the first releases. Assign
persistent source IDs once and retain them across rebuilds. Publication can
map draft VLNVs to release VLNVs in a detached package; rewrite every typed
reference. Do not rename source by text replacement.

A realization key hashes the release/dependency digests, normalized typed
parameter values, selected binding, and realization schema version. The initial
binding is `generic`. Import different parameter sets as distinct local
Component definitions. Set selected values through typed parameter operations;
keep source expressions and the SV body. Preserve original values in provenance.
Circuit terminal evaluation is verified in Phase 3.

### 1C. Add the HTTP surface and guarded source operations

Existing routes to reuse, as observed during planning:

| Route | Use |
| --- | --- |
| `POST /documents/create` | Create an empty draft Spec at a new path |
| `POST /documents/open` | Open a saved Spec |
| `GET /documents/snapshot` | Read source revision, binding, and saved content |
| `POST /transactions` | Apply a batch guarded by `expected_source_revision_hash` |
| `POST /assistant/resolve-interface` | Resolve declared interface expressions without saving |
| `POST /entities/{kind}/{entity_id}/verify` | Explicit lint check; not functional qualification |
| Existing Activity launch/read routes | Run `rtl.generate` and qualification against immutable snapshots |

Recheck OpenAPI and integration metadata before issuing calls. Bind requests
explicitly with the returned document key (`owner_document_key` on the current
wire API). Never rely on whichever Spec happens to be active. Use the manual
operation names from the current decoder: `create_entity`, `add_component_port`,
`update_parameter`, `set_entity_metadata`, and `upsert_entity_section`.
The Assistant schema uses aliases in some places; do not assume identical names.

Add these **new** library routes; they are requirements, not existing APIs:

| Route | Required operation |
| --- | --- |
| `POST /library/search` | Query and capability filters; returns stable release references and catalogue revision |
| `POST /library/describe` | Exact release reference; returns contract, limits, presets, and scoped evidence |
| `POST /library/resolve` | Exact root, parameter values, target; returns pinned closure and realization plan |
| `POST /library/import/preview` | Bound destination/revision plus resolved release; returns detached diff and opaque plan ID |
| `POST /library/import/commit` | Exact plan ID and expected destination revision; atomically saves source and provenance |
| `POST /library/publish/preview` | Bound source/revision, root, version; validates a detached release candidate |
| `POST /library/publish/qualify` | Exact candidate ID; runs library.qualify against the final immutable candidate snapshot |
| `POST /library/publish/commit` | Exact candidate and qualification evidence; creates an immutable local release |
| `GET /library/artifacts/{digest_hex}` | Fetch immutable bytes with digest and media type |

Add typed operations `upsert_library_contract`, `upsert_csr_source`, and
`set_library_metadata` to the guarded manual transaction vocabulary. Define
matching domain validation and schema-discovery support. Library import and
publication use domain commands, not model-supplied raw archives. Later phases
bind the same commands to controls and flows.

Prepare and commit must agree on the source/destination binding, revision,
release digests, normalized parameters, and selected root. Repeat commits with
the same completed plan return the original result. Reusing a plan for different
content fails. Expired/stale plans do not write. Browsing and failed previews
leave source unchanged. Do not expose private source-binding tokens or paths
through catalogue identity.

Local publication is part of the library operation authorized by these phases.
It writes only the configured repository library root. External publication or
production hosting is outside this plan. Preserve configured proposal approval
for Assistant/Activity writes; do not reinterpret manual authoring as a model
proposal or bypass approval by calling manual routes from an Assistant flow.

### 1D. Author the six seeds through HTTP

For each seed, create a new draft under `TEMP_library_<run>/authoring/`, capture
its binding and revision, and submit a complete typed transaction batch. Use
explicit IDs so operations in a batch can reference the new Component. Add
ports, parameters, description, SV Section, and library contract through the
service. Save construction errors as failed cases before correcting them.

All stateful seeds use `clk_i` and asynchronous active-low `rst_ni`. The
surrounding environment must synchronize reset release per destination domain.
Reset wins over all other controls. Parameter IDs are uppercase and port IDs
are lower snake case.

| ID | Exact interface and semantics | Required presets |
| --- | --- | --- |
| `mux2` | `a_i`, `b_i`, `y_o`: `DATA_WIDTH` bits; scalar `sel_i`; `y_o = sel_i ? b_i : a_i`; combinational | `DATA_WIDTH` 1, 8, 32 |
| `register_en_arst_n` | `d_i`, `q_o`: `DATA_WIDTH` bits; scalar `en_i`; reset to `RESET_VALUE`; rising-edge load only when enabled | Width 1/8/32; zero and nonzero fitting reset values |
| `counter_wrap` | Scalars `en_i`, `clear_i`; `count_o[COUNT_WIDTH-1:0]`, scalar `wrap_o`; clear before enable; increment until `MAX_VALUE`, then zero and one-cycle wrap pulse; wrap low on hold/clear/reset | `(COUNT_WIDTH, MAX_VALUE)` = (1,1), (4,9), (32,4294967295) |
| `rr_arbiter` | `req_i[N-1:0]`, `grant_o[N-1:0]`, scalar `accept_i`; at most one grant, zero if no request; initial priority zero; hold winner while it remains requested and not accepted; on acceptance next priority follows winner modulo N | `N` 1, 3, 4; request must remain asserted until accepted |
| `reset_sync` | `clk_i`, asynchronous `arst_ni`, `rst_no`; asynchronous assertion, release after `STAGES` destination rising edges; no test bypass | `STAGES` 2, 3 |
| `level_sync` | `clk_i`, `rst_ni`, scalar `d_i`, `q_o`; `STAGES` destination flops reset to zero; single-bit level only; no pulse/bus guarantee | `STAGES` 2, 3; source stability assumptions stated |

`COUNT_WIDTH >= 1`, `1 <= MAX_VALUE < 2**COUNT_WIDTH`, and `STAGES >= 2`.
Default seed values are width 32, maximum unsigned count, N=4, and STAGES=2.
The mux/register use `DATA_WIDTH`; the counter uses `COUNT_WIDTH`.
Do not expose parameters that are not listed above.

Size/stage parameters use `int unsigned`. RESET_VALUE uses
`logic [DATA_WIDTH-1:0]` with default `'0`; MAX_VALUE uses
`logic [COUNT_WIDTH-1:0]` with default `'1`. Preserve these declarations through
the shared interface resolver and RTL output. Parameter expressions, rather
than host-language integer truncation, determine their elaborated width.

For the arbiter, a requester withdrawing before acceptance violates its stated
contract; add an assertion. Fairness is bounded by accepted service events
while the request remains asserted, not by wall-clock cycles under infinite
backpressure. Record this assumption in the proof.

Publication preview maps final release VLNVs and embeds declared verification
and constraint assets before fixing the candidate digest. Qualify that exact
candidate through `/library/publish/qualify`, then commit its unchanged bytes.
Never reuse evidence for draft source if packaging changes its identity. The
publication exporter writes reviewed unpacked source to `library/components/`.
Fetch the
release bytes, import into a clean destination through the API, reopen through
`/documents/open`, and compare normalized interface/contract/SV content.

### 1E. Implement independent hardware qualification

Add registered `library.qualify` Activity with explicit inputs: exact root,
parameter matrix, and `generic` target. Use the immutable saved source snapshot.
Keep lint, functional simulation, assertion execution, synthesis, formal proof,
and CDC/RDC review as separate results. Existing Verify Component remains lint.

Use tracked benches and a requirement-to-check map. Run real Verilator
simulations with assertions and Yosys/Slang synthesis. Prove counter bounds and
arbiter mutual exclusion/progress under their assumptions with SymbiYosys/Z3.
Prove reset_sync release sequencing under an explicit digital clock/reset model;
record how asynchronous assertion is represented and do not infer MTBF.
Record a structural review for synchronizer stages, domain/reset use, and required
placement/constraint assumptions. No digital check establishes analogue MTBF.

Qualification is scoped to tested parameters and binding. Missing behaviour,
compile-safe tie-offs, failed checks, stale evidence, and unavailable required
tools prevent promotion. Do not claim ASIC timing closure, SRAM inference,
physical CDC sign-off, or FPGA mapping from generic checks.

### 1F. Run the API defect campaign

Keep failing cases and add regression checks for:

- Wrong document binding, stale revision, invalid width or reset value, unknown
  parameter, and illegal counter maximum.
- A batch with valid early edits and an invalid final edit: no partial write.
- Symbolic bounds, missing constant dependencies, and source range orientation.
- Same release/different bytes, missing/cyclic dependency, corrupt artifact,
  repeated import, ID/VLNV collision, and independent parameter realizations.
- Local edit/fork detection on every supported mutation path and invalidation
  of dependent qualification.
- Service restart and lost commit response: reconcile the exact result without
  duplicate definitions/publications.
- Incomplete draft saved for authoring but blocked from executable publication.

Fix defects as specified in the common guide. Add focused tests beside their
subsystem. Keep failure evidence distinct from successful qualification.

## 4. Required acceptance evidence

Every seed has an HTTP authoring record, valid maintained source, immutable
release, scoped hardware checks, and successful API import/reopen. Two clean
rebuilds of the same source have equal package digests. A relocated library root
and rebuilt index return the same releases and dependency graph.

Import `register_en_arst_n` twice with width 8: one local realization and two
instances where the destination Design uses them. Import width 32: a second
realization. Change one local realization: it becomes a fork and cannot be
reused as the unchanged published release. This reference case is repeated
through the next methods without API mutation shortcuts.

Run `fast`, `integration --scope spec,activities`, and `regression`. Add `shared`
and all consumers if shared contracts change. Use dry-run selection first and
new `TEMP_library_<run>/fast`, `/integration`, and `/regression` evidence paths.
Do not omit the three required live model checks in fast, even though hardware
authoring in this phase uses no model.

## 5. Handoff and exit gate

Do not start Phase 2 until the required source, service contracts, and evidence
are complete. Fill these fields with actual results:

- Implementation revision; actual route/schema versions; tool versions.
- Six release references/digests and tested matrices.
- API authoring/import/reopen evidence paths and equal-input build checks.
- Defect register: failing case, cause, fix, regression check, re-execution.
- Executed commands/profile outcomes and evidence directory.
- Remaining mandatory prerequisites; optional coverage limits.
- Exit gate: not evaluated.

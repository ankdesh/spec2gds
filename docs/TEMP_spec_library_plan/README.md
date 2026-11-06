# Spec Catalog: phased Component implementation contract

Status: Phases 1 and 2 are fully published (64 components); Phase 3 Part 1 is published (12 components); 44 components remain planned.
Location and integration update: 5 November 2026, baseline commit `0585633`.
The runtime inventory records 76 delivered Components and 44 planned entries.
Read the current inventory before work; this status does not replace verification.

## Current baseline for coding agents

The Spec Catalog is now a top-level UV workspace package, at the same subsystem
level as Spec Editor and Circuit Designer. Extend this package for the remaining
phases. Read [the service guide](../../spec_catalog_service/README.md) first.

- Runtime inventory: `spec_catalog_service/catalog/inventory.json`. This is the
  delivery record. The adjacent planning `inventory.json` retains the initial
  120-entry scope; do not copy it over the runtime inventory or reset statuses.
- Published files and handoffs: `spec_catalog_service/catalog/`. Phase 1's
  [historical handoff](../../spec_catalog_service/catalog/handoffs/phase-1.md)
  retains its original commands and paths. Use this guide for current commands,
  and the runtime inventory plus file hashes for current release validation.
- Tools and Component definitions: `spec_catalog_service/src/spec_catalog_service/catalog/`.
  HTTP service, storage, and standalone UI: `spec_catalog_service/src/spec_catalog_service/http/`.
  Maintained tests: `spec_catalog_service/tests/`.
- Install with `uv sync --all-packages`. Keep any required optional extras when
  syncing. Run catalog commands with `uv run --package spec-catalog-service`.
  The public commands are `spec2gds-catalog` and `spec2gds-catalog-service`;
  the root option is `--catalog-root`. The HTTP prefix is `/api/spec-catalog/v1`.
  Old library commands, module paths, flags, and route aliases were removed.
- Shared configuration uses `spec_catalog` in `config/services.json`, with port
  6017. `catalog_root` and `state_dir` resolve relative to that configuration file.
  CLI values override configuration values, which override defaults.
  `scripts/serve-all.sh start` starts the catalog and the other applications;
  `--catalog-port` overrides its listener. Startup reconciles the derived index
  from releases and all durable evidence before reporting ready.
- Spec Editor already supports **Components → Options → Import from catalog…**.
  It previews imports, retains published parameter defaults, offers unchanged
  reuse or a renamed local copy, and records origin metadata. Imported definitions
  remain editable and self-contained. Generate RTL verifies the saved target
  when selected; separate Verify actions remain available. Content actions use
  right-side Options menus. Use these existing controls in browser checks.
- The Spec service reaches the catalog through HTTP. Keep package import and
  local origin records in `spec2gds/spec/spec_format/catalog_import.py`; do not
  import catalog service code into the Spec service or create a dependency cycle.
- Keep this planning folder and its Component anchors unchanged: published
  metadata references them. Preserve the embedded `library_catalogue_v1` asset ID,
  VLNVs, release bytes, digests, and historical handoffs. Directory moves do not
  require a metadata migration. Existing internal `Library*` class names and
  `library_root` constructor arguments are implementation details, not old CLI aliases.
- AI Assistant's instruction catalog and `SPEC2GDS_CATALOG_ROOT` setting are a
  separate feature. Do not redirect them to the Component catalog.

Recheck prerequisite releases and the required profiles for each new phase.
The migration's fast checks passed, and affected test-harness failures passed
focused reruns. The full repeated live RTL evaluation was deferred at the
designer request after six of 33 passing runs. Do not treat that migration as a
complete regression pass or reuse the historical handoff as current test evidence.

## 1. Objective and execution order

Deliver 120 reusable digital hardware Components. A developer must be able to
open one `.spec` file, understand the interface, produce RTL, and run its checks.
Each file is a useful starting point for an IP. Library breadth and functional
correctness are the main result. Tests of the authoring applications are a
secondary result.

Give the coding agent this guide, the runtime inventory, the planning
[inventory.json](inventory.json), and exactly one phase file. Read prerequisite
handoffs under `spec_catalog_service/catalog/handoffs/` before making changes.
Execute phases in order. A phase is complete only when its delivery gates pass.
Do not implement all phases in one change unless the designer requests it.

| Phase | New / cumulative Components | Required phase instructions | Secondary stress path |
| --- | --- | --- | --- |
| 1 | 32 / 32 | [Logic, state, and hosting](plans/phase-1.md) | Spec HTTP API |
| 2 | 32 / 64 | [Storage, streams, and CDC](plans/phase-2.md) | Spec Editor |
| 3 | 32 / 96 | [Arithmetic, integrity, and control](plans/phase-3.md) | Circuit Designer |
| 4 | 24 / 120 | [Protocols, peripherals, and IP starters](plans/phase-4.md) | AI Assistant |

Designer use after each release: start the catalog, inspect a published Component
and its exact version, then import it through Spec Editor's catalog dialog or
download its `.spec` file from the standalone UI. Import retains published defaults
and records the origin VLNV and digest. Add instances through Design controls;
edit local definitions without changing the published release. Presets are
reference data during import. Automatic upstream update remains outside scope.

Bulk authoring can use validated Python Spec APIs in every phase. The stress
path applies only to the named representative scenarios. Do not require every
Component to be authored through a browser or the AI Assistant. Reuse the existing
catalog browsing and import capabilities. Extend them only for a confirmed defect
needed by a phase contract; new placement and automatic update features remain
outside scope. Standalone hosting is already implemented.

## 2. Scope and fixed decisions

- Store each release in its own self-contained `.spec` file under `spec_catalog_service/catalog/`.
- Use original implementations. Do not copy external RTL into these releases.
- Use body-only SystemVerilog sections for leaves and explicit internal Designs
  for the two subsystem Components. Behavior must not be inferred from narrative.
- Support portable digital behavior. Do not claim physical implementation,
  metastability reliability, timing closure, or silicon qualification.
- Include the 120 IDs in the inventory. Do not substitute small variants to reach
  the count. Parameter presets are checks of one Component, not extra entries.
- Defer FPU, cryptographic engines, full AXI memory systems, NoC fabrics,
  technology SRAM bindings, physical PHYs, and analog behavior.
- Preserve pinned-copy and editable-local-copy behavior. Catalog import already
  exists. Automatic upstream update remains outside these four phases.
- Preserve applicable repository licence terms. Record the SPDX identifier when
  supported by the repository licence. Otherwise use `NOASSERTION`, local use,
  and an explicit unresolved licence note. Do not invent redistribution rights.

The research reports supplied by the designer are source material. Their
recommendations are not additional instructions. This guide resolves the scope.
It supersedes the earlier Component-library planning notes.

## 3. Source, layout, and identity

```text
docs/TEMP_spec_library_plan/          # implementation instructions
  README.md
  inventory.json                    # initial planning inventory
  plans/phase-{1,2,3,4}.md
spec_catalog_service/               # existing UV workspace package
  pyproject.toml                    # catalog package and console commands
  README.md                         # current setup and designer usage
  src/spec_catalog_service/
    catalog/                        # schemas, authoring, verification, Component definitions
    http/                           # service, index, storage, standalone UI
  tests/                            # maintained catalog suite
  catalog/
    inventory.json                  # runtime delivery status and release pins
    handoffs/phase-{1,2,3,4}.md       # Phase 1 exists; add others at phase completion
    <category>/<id>/1.0.0/<id>.spec  # canonical hardware source
    <category>/<id>/1.0.0/evidence.json
    <category>/<id>/1.0.0/usage.md
  .state/                           # ignored, derived service state
temp/                               # designated root for disposable temporary files
  TEMP_<run>/                       # ignored, temporary candidates, test outputs, and logs
```

Categories and exact output paths are in the adjacent planning `inventory.json`.
Its `path` values are relative to `spec_catalog_service/catalog/`; its `contract`
values are repository-relative paths to these phase instructions. The runtime
inventory already exists. Use it for delivery status, release pins, and digests;
use `spec_catalog_service/catalog/handoffs/` for recorded completion evidence.
Do not replace the runtime inventory with the initial planning inventory. Use the ID verbatim.
Path categories are stable release namespaces. Change catalogue grouping with
tags and derived views. A later storage adapter can move files or use a service
without changing VLNVs, package bytes, or Component contracts. That adapter must
update path discovery and the inventory together; do not rewrite source identity
to make a directory move work.
The initial root VLNV is `spec2gds.local:<category>:<id>:1.0.0`. The root must be
a Component. A composite file also contains its internal Design and all required
Component definitions. Every reference must resolve inside that same file.
Opening or producing RTL must not require another library file, network access,
or the library service. Embedded copies retain their origin VLNV, source digest,
and concrete parameter values in metadata. Resolve name collisions explicitly.

For concrete specialization: resolve all boundary widths at the recorded preset;
create a local child with numeric wire ranges; replace public parameter
declarations with equivalent typed localparams at the start of its SV section;
retain the functional body; and remap all references to the local child identity.
Do this through typed creation/port/section operations. No per-instance parameter
override or new Circuit parameter feature is required. Before embedding, compare
its behavior with the original release at that preset. Repeated identical child
copies share one local definition. Specialize a nested Design recursively.

Each file has exactly one catalogue asset. When embedding child definitions,
do not copy their primary catalogue assets; record origins in the root's
dependencies instead. Rebind all copied local refs and Section parent refs to
the destination document. Internal glue has no external-origin dependency row.
Use a source asset with stable asset ID `library_catalogue_v1`, media type
`application/json`, and extension `json`. Add it with `AddAsset`; use the asset
path assigned by the package API. Its version-1 object has these required keys:

| Key | Meaning |
| --- | --- |
| `schema_version` | integer 1 |
| `root` | exact package-local `EntityRef` of the primary Component |
| `id`, `category`, `version` | inventory ID, category, and selected version (initially `1.0.0`) |
| `summary`, `tags` | short description and sorted unique strings |
| `licence` | SPDX expression or `NOASSERTION` |
| `implementation` | `body_sv` or `composite` |
| `contracts` | relative phase document path and Component anchor |
| `presets` | named complete parameter maps, including all defaults; values are canonical base-10 integer strings to preserve values wider than JavaScript integers |
| `timing` | object with string fields `latency`, `throughput`, `reset`; describe the phase contract without browser expression evaluation |
| `limitations` | array of explicit behavioral, protocol, or qualification limits |
| `dependencies` | list of `{vlnv, package_sha256, parameters, local_ref}`; empty for leaves |

Reject unknown schema versions and extra keys. The root identity, version, and
category must agree with IP-XACT and the inventory for planned entries. Metadata
is descriptive. It must not duplicate editable port definitions, SV bodies, or
topology. Store those only in the canonical `.spec` source.
`contracts` is one string equal to the inventory contract path plus anchor.
`presets` is an object mapping preset names to parameter-name/value objects;
an unparameterized Component has `{"default":{}}`. Descriptions are strings,
and tags/limitations/dependencies are arrays, including when empty.

The service accepts the same metadata profile for original Components outside
the 120-entry inventory. Restrict category to the ten categories in the inventory
and IDs to `[a-z][a-z0-9_]{0,63}`. Require vendor `spec2gds.local`, library equal
to category, name equal to ID, and version `MAJOR.MINOR.PATCH` with no leading
zeros. These restrictions define the local first service, not the general Spec
format. No implicit root selection is permitted for a library upload.

Before release, candidates live only in ignored repository `temp/TEMP_*` directories. Publication
copies exact validated bytes atomically to the final path. A released VLNV is
immutable: identical bytes are idempotent; different bytes conflict. Fix a
released Component with a new semantic version. Before initial phase acceptance,
the candidate may be edited freely. Never edit or delete accepted bytes in place.
The inventory `version` and `path` select the currently recommended verified
release; `releases` retains the immutable history. Advance that pin only after
the replacement passes its full matrix. Predecessor checks use the selected pin,
and separately confirm that historical accepted bytes did not change. Do not
rename IDs when directories move. Counts in this plan mean distinct Component
IDs and selected releases; retained version history may add more `.spec` files.

`inventory.json` schema version 1 contains `entries`. Each entry has `id`,
`phase`, `category`, `version`, `path`, `contract`, `dependencies`, `status`, and
`releases`. `status` starts `planned`; set it to `delivered` only at phase
acceptance. Each release record then has `version`, `path`, `package_sha256`,
`evidence_path`, and `evidence_sha256`. Do not use index contents as source truth.

## 4. Authoring boundary and implementation locations

Read [terminology](../TERMINOLOGY.md), [testing rules](../testing-strategy.md),
and root `AGENTS.md` first. At phase start inspect `git status`, predecessor
handoffs, available tools, and changed shared contracts. Preserve unrelated work.

Use `SpecPackage`, `SpecRevision`, and `SpecEditTransaction`. Create hardware,
ports, parameters, sections, assets, and topology through typed operations. Use
`strict` validation for published candidates. Authoring validation can support
an incomplete draft, but cannot qualify a release. Save, reopen, and validate the
actual bytes before testing. Do not mutate the derived SpecIR or hand-write ZIP,
manifest, or IP-XACT files as the authoring path. `InstanceIR` and `ConnectionIR`
are permitted values passed to typed operations.

Existing references:

- `spec2gds/spec/spec_format/{archive,transactions,models,ir,rtl_interface}.py`.
- `spec2gds/spec/spec_format/v1_api.py` and existing HTTP routes for real API use.
- `spec2gds/spec/activities/rtl/codegen.py` and the registered `rtl.generate` Activity.
- `scripts/test_profiles.py`, `scripts/test_capabilities.py`, and `tests/ui-scenarios`.

Maintained code locations are fixed:

| Location | Responsibility |
| --- | --- |
| `spec_catalog_service/src/spec_catalog_service/catalog/` | catalogue schemas, authoring helpers, verification orchestration, CLI |
| `spec_catalog_service/src/spec_catalog_service/http/` | standalone FastAPI service, index, static HTML/CSS/JS catalogue |
| `spec_catalog_service/tests/` | schema, package, API, storage, and hardware reference checks |
| `tests/ui-scenarios/` | maintained browser scenarios for the named stress paths |

Do not keep a second editable set of unpacked RTL/XML/IR or hardware recipes that
must be kept in sync with a released `.spec`. Temporary scripts can create the
first candidates. Maintained authoring helpers may operate on Specs. Maintained
reference models, test harnesses, and expected vectors are verification sources,
not a second hardware source. Repair a saved Component through typed edits.

The existing `CreateHardware` operation and HTTP schema accept an optional
`vlnv`. Omission preserves the local-work identity. Reuse this operation for
catalog authoring. Validate the supplied identity, match its name
to the normalized hardware ID, and reject duplicate identities atomically. Do not
change identities by rewriting saved XML. Test existing callers and HTTP clients.

Use flat wire ports. The current RTL Activity does not accept IP-XACT bus
interfaces or structured/transactional ports for these implementations. Do not
silently emit tie-offs for a missing body. Each leaf requires an SV section;
each composite requires a complete internal Design.

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

## 7. Standalone hosting contract

Maintain `spec2gds-catalog-service` as a separate FastAPI/uvicorn process. It can
run with the installed UV workspace and catalog root without other application
processes. It is also registered as `spec_catalog` in the shared service directory
and started by `scripts/serve-all.sh`. Default configuration binds `0.0.0.0:6017`;
use `--host 127.0.0.1` for a loopback-only standalone run. The static catalog UI is
same-origin at `/`; no wildcard CORS. This is a trusted local service. Public
hosting, multi-user auth, tenancy, and remote object storage remain outside scope.
Existing Spec Editor integration uses the Spec service's HTTP catalog client.

All API routes use `/api/spec-catalog/v1`. `key` is the lower-case SHA-256 hex
of the UTF-8 root VLNV **without its version field**, therefore stable across
versions: `sha256(f"{vendor}:{library}:{name}".encode("utf-8")).hexdigest()`.
There is no trailing colon or `sha256:` prefix in `key`.
Return `key`, full VLNV, ID, category, and version in every version row.
Use exact version routes; do not create a mutable `latest` download alias.

| Method and suffix | Required behavior |
| --- | --- |
| `GET /health` | schema version, ready/degraded status, root readability, index generation |
| `GET /capabilities` | metadata/evidence schema versions, upload limits, supported categories, loopback/local profile |
| `GET /components` | query `q`, `category`, `implementation`, `functional_status`, `limit` (1..100, default 25), `offset` (>=0); return total and items |
| `GET /components/{key}` | identity and immutable versions, sorted numeric semantic version descending |
| `GET /components/{key}/versions/{version}` | metadata, package digest/size, separate validation and evidence summaries |
| `GET /components/{key}/versions/{version}/download` | exact original bytes, attachment filename, digest ETag; support `If-None-Match` -> 304 |
| `POST /uploads` | multipart `file`; structurally validate and publish bytes; 201 new, 200 identical retry, 409 different bytes for same VLNV |
| `POST /components/{key}/versions/{version}/evidence` | JSON evidence matching stored digest; 201 new digest, 200 same evidence digest; append, never replace another record |
| `GET /components/{key}/versions/{version}/evidence` | evidence records and server receipt time; never imply the service ran the checks |

Use these response shapes; do not make the first UI depend on undocumented fields:

- A version row has `key`, `vlnv`, `id`, `category`, `version`, `summary`, `tags`,
  `implementation`, `implementation_kind`, `source_revision_hash`,
  `package_sha256`, `package_size_bytes`, `validation`,
  `functional_status`, `evidence_count`, and relative `download_url`.
  `validation` is `{package:"valid", implementation:"present"|"absent", diagnostics:[]}`.
  `implementation` records presence; `implementation_kind` is `body_sv` or
  `composite`. The implementation filter accepts these kinds. The version-details
  route adds `metadata`, the exact parsed catalogue asset, and `usage_markdown`.
- The list route returns `{total, limit, offset, items:[version_row]}`. The identity
  detail route returns `{key, vendor, library, id, category, versions:[version_row]}`.
- Upload returns `{created, version:version_row}`; evidence submission returns
  `{created, evidence_sha256, received_at}`; evidence read returns
  `{items:[{evidence_sha256, received_at, report}]}` sorted by receipt time then digest.
  An identical evidence retry returns its original server receipt time.
- Health returns `{schema_version:1,status,root_readable,index_generation}`;
  status is `ready` or `degraded`, generation is a nonnegative integer incremented
  on each successful index commit. Return HTTP200 ready and503 degraded. Capabilities
  returns `{schema_version:1,metadata_versions:[1],evidence_versions:[1],limits,
  categories,profile:"trusted_local"}`. `limits` has `max_compressed_bytes`,
  `max_uncompressed_bytes`, `max_member_bytes`, `max_members`,
  `max_compression_ratio`, and `max_evidence_bytes`, with the values below.

These are schema descriptions, not literal JSON examples. Keys are required;
strict models reject unknown request fields. Return ETag as a quoted standard
digest string, for example `"sha256:..."`. Download bytes never change with index
generation, evidence receipts, or UI state.

`q` performs case-insensitive substring matching over ID, summary, and tags;
filters combine with AND. Default order is category then ID; no fuzzy ranking.
The list selects each identity's highest version. Functional status applies to
that version: `unreported`, `reported_pass`, `reported_fail`, or `reported_incomplete`.
Any reported failure in mandatory functional checks wins; otherwise all required offline package/implementation/
determinism checks and each preset's lint/simulation/parameter_validation checks
must pass for reported_pass. Use the union of reports bound to the package digest;
missing required records means reported_incomplete. A later conflicting submission
cannot silently erase a failure. Evidence is supplied evidence, even when it comes
from the repository pipeline. Only pipeline handoffs mark inventory delivered.
Formal, synthesis, and physical results remain separate from this baseline
functional status; their absence never becomes a claimed pass.

Use a SQLite index under `spec_catalog_service/.state` by default, with
package/evidence files as durable truth. Keep state outside the published tree.
Support CLI `spec2gds-catalog index --catalog-root PATH --state-dir PATH` to rebuild
the entire index. Discover only canonical category/ID/version `.spec` paths;
ignore `TEMP_*`, `.state`, plans, and unknown layouts. Report malformed durable
files and never silently delete them. Current startup fails readiness if index
reconciliation reports errors. The Phase 4 degraded/read-only recovery scenarios
remain delivery obligations; do not assume they already pass. A rebuild must
recover after an interrupted index update. Reconcile durable files at startup.
Store uploaded evidence as `evidence/<evidence_sha256_hex>.json` beside its package.
The pipeline `evidence.json` is also indexed; duplicates coalesce by digest.

Enforce upload bounds while streaming, before normal package loading: 8 MiB
compressed, 64 MiB total uncompressed, 4 MiB per member, 1,024 members, maximum
ratio 100:1 per non-empty member. Reject encrypted entries, symlinks, duplicate
names, absolute/traversal/backslash paths, malformed ZIP, and unsupported source
profiles. Keep the source's tighter section limits. Reject a package with missing
dependencies, metadata, or an ambiguous/invalid root. A valid package may have
no implementation or no functional evidence: expose these as separate states;
only library delivery requires a functional implementation.

No archive extraction or user filename becomes a storage path. Compute paths
from validated identity fields; reject symlinked storage ancestors and writes
outside the configured root. Stage under `temp/TEMP_uploads`, fsync and
atomically publish with same-filesystem no-clobber semantics. Serialize the same
VLNV across workers with a filesystem lock plus a SQLite uniqueness constraint.
After a crash, disk truth wins. Do not overwrite on retry. The service never runs
uploaded RTL, Python, shell, Activity, or tests. Evidence JSON limit is 1 MiB;
read only expected evidence paths and do not follow symlinks.

API errors are `{error:{code,message,details}}`. Use 400 malformed request/package,
404 unknown identity/version, 409 immutable conflict, 413 limit exceeded,
422 schema/profile/semantic validation failure, 503 unavailable storage. Details
may include safe member paths and diagnostics, never arbitrary file contents or
host paths. Escape all catalogue text; uploaded SV/HTML is never executable UI.

The UI must upload one file, browse/search/filter, open details and versions,
download exact files, and show validation separately from supplied functional
evidence. Empty, loading, invalid upload, conflict, disconnected service, keyboard
navigation, and narrow-window states are required. Preserve Spec Editor's existing
catalog browse/import dialog and its Spec-service proxy. The proxy provides
`GET /catalog/components`, Component/version details, `POST /catalog/imports/preview`,
and `POST /catalog/imports`, relative to the Spec service API base. Imported
published evidence is an origin record, separate from current-Spec verification.
Planned inventory entries remain unavailable for import until published.

## 8. Integration checks, defects, and phase handoff

Register new maintained suites in `scripts/test_profiles.py` and capability
evidence in `scripts/test_capabilities.py`. Use existing scopes: `spec` for source
and hosting, `activities` for RTL execution, plus the affected application scope.
Do not add a new scope merely for this library. Keep fast checks short; select
complete hardware matrices in integration/regression and run them explicitly.

After code changes run `scripts/test-all.sh fast` and phase-specific integration.
Run regression for cross-application contracts, persistence, shared runtime, or
release preparation. Each phase file states its minimum scope. Fast includes
exactly three live model checks. Missing credentials/tools makes a profile
incomplete. Continue independent checks and report the limits. A dry-run is suite
selection evidence only, not executed tests. Put all outputs, including child
temporary files, in ignored repository `temp/TEMP_*` directories; configure child
`TMPDIR` as needed. Never use system `/tmp` for this work.

For every confirmed defect: retain the reproducer and source revision; add the
lowest effective regression check; fix the cause; repeat the failing path; and
run affected profiles. Add browser protection for browser defects. Never repair
an archive behind the APIs, suppress a failure, or relabel API mutations as UI
actions. A missing product feature is not automatically a defect to implement.
Record unrelated feature requests separately. Do not claim a stress check passed
when its actual user path was unavailable. Functional library failures block
delivery; an unavailable secondary path is recorded as an explicit incomplete
stress result and must not expand this library into an application redesign.

At each phase end create `spec_catalog_service/catalog/handoffs/phase-N.md` with:
commit/revision; commands and
exit codes; tool versions; delivered IDs and digests; preset results; reproducible
evidence directory; service API examples; confirmed defects and regression tests;
secondary stress results; prerequisites and limits; and exact next-phase inputs.
Use `complete`, `incomplete`, or `blocked` for the phase result. `complete` requires
all planned Components for that phase, passing mandatory functional checks,
working service obligations, and required software profiles. Secondary stress
can be explicitly incomplete without falsely marking it passed. Do not close a
phase with missing required hardware checks or credentials for required profiles.

Planning sources: `RTL Building Block Library Taxonomy.md` (breadth, categories,
parameters, and risk distinctions) and `deep-research-report.md` (reusable Specs,
implementation/evidence profiles, composition, and staged delivery). This guide
is self-contained; implementation does not require the reports or embedded images.
Preserve the deferred families as backlog, not delivered entries.

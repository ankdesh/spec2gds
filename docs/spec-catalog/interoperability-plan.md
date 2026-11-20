# Spec Catalog interoperability and phase unification plan

Reviewed on 5 November 2026. This is a proposal, not a delivery record. Check the current implementation and inventory before using it.

This plan reviews [the recommendations](interoperability-recommendations.md)
against the catalog at commit `0585633`. The recommendations are input to this
review, not instructions to apply every proposed change. The objective is reliable
composition across phases while preserving published interfaces, reproducible
RTL, and editable, self-contained Spec files.

## 1. Baseline and review evidence

Review source: `/home/ankdesh/explore/spec2gds`. Check the current commit and
inventory again before implementation. Do not infer delivery from a phase title.

| Phase | Delivered IDs | Planned IDs | Published implementation |
| --- | ---: | ---: | --- |
| 1: logic and state | 32 | 0 | 32 `body_sv` roots |
| 2: storage, streams, CDC/reset | 32 | 0 | 32 `body_sv` roots |
| 3: arithmetic/DSP/integrity | 12 | 20 | 12 `composite` roots |
| 4: protocols and IP starters | 0 | 24 | None |
| Total | 76 | 44 | 76 published packages |

The review loaded all 76 delivered packages, read their ports, parameters,
metadata and reachable Component definitions, and compared package hashes with
the runtime inventory. All 76 package hashes matched. This is source inspection
and integrity evidence; it is not a new lint, simulation, CDC, or regression pass.
The audit is retained at `temp/TEMP_phase_unification_review/catalog-audit.json`.
No hardware checks or live model evaluations were run for this planning work.

Main code references:

| Area | Current source |
| --- | --- |
| Delivery records | `spec_catalog_service/catalog/inventory.json` |
| Saved metadata schema | `spec_catalog_service/src/spec_catalog_service/catalog/schemas.py` |
| Maintained Component descriptions | `spec_catalog_service/src/spec_catalog_service/catalog/components/` |
| Candidate authoring | `spec_catalog_service/src/spec_catalog_service/catalog/authoring.py` |
| Phase 3 hierarchy construction | `spec_catalog_service/src/spec_catalog_service/catalog/phase3_hierarchy.py` |
| Hardware checks | `spec_catalog_service/src/spec_catalog_service/catalog/verification.py` |
| Source types and transactions | `spec2gds/spec/spec_format/{models,ir,transactions}.py` |
| Package import and origins | `spec2gds/spec/spec_format/catalog_import.py` |
| RTL analysis and rendering | `spec2gds/spec/activities/rtl/codegen.py` |
| Existing domain/timing annotations | `spec2gds/spec/spec_format/circuit_timings.py` |
| Spec Editor | `circuit-designer/apps/editor/` and `packages/document-*` |
| Circuit Designer | `circuit-designer/packages/{core,service,client-http}/` and its applications |

## 2. Review of the six recommendations

| Recommendation | Assessment | Recommended action |
| --- | --- | --- |
| Channel roles and consistent names | Semantic channel descriptions are useful. Different physical port names are not, by themselves, a protocol incompatibility. | Keep existing names. Add typed channel-to-port maps and reviewed connection previews. New wrappers may use a consistent naming profile. |
| Stream splitter/joiner | Packed operands need a format definition. The catalog already has `stream_join`, `stream_fork`, mux and demux Components with their own transfer rules. | Add arithmetic pack/unpack adapters with distinct IDs and exact atomic-transfer rules. Reuse existing primitives where their contract fits. |
| `USER_W` everywhere | Sideband preservation is important. Conditional port omission is not an established capability of the fixed saved-port model. One universal width-conversion rule would be unsafe. | Start with explicitly packed transaction records through existing queues. Consider separate sideband-aware versions only after transport rules and zero-width behavior are specified. |
| Skid buffer egress | Breaking long combinational dependencies is useful. “Zero throughput loss” is too broad for the current buffer. | Reuse existing buffers as explicit wrappers. Record latency, capacity, paths and recovery bubbles. Do not insert a buffer or change a preset silently. |
| External catalog VLNV resolution during generation | This conflicts with offline packages and immutable Activity snapshots. VLNV without a digest is also insufficient for source pinning. | Resolve and vendor dependencies during explicit authoring/import. Keep RTL generation and verification free of catalog access. |
| Three-level structural consistency | Useful decomposition can improve inspection. A fixed number of levels does not prove reuse or good architecture. | Select `body_sv` or composite structure by behavior and reuse. Add selected structural templates; retain existing leaves. |
| All parameters become `int unsigned` | Appropriate for bounded dimensions and some mode flags; unsafe for wide bit patterns and signed coefficients. | Use a type policy with bounded integers, logical modes, packed values and signed values. Validate before casting. |

### 2.1 Corrections to the technical assumptions

1. `divider_pipeline` uses `dividend_i` and `divisor_i`, not generic `a_i` and
   `b_i`. Its result is quotient, remainder and two flags. `add_sub` publishes
   `carry_o`, whose subtraction meaning is **no borrow**; it has no `borrow_o`
   port. Preserve these semantic differences in the channel maps.
2. `stream_register` has a downstream-ready to upstream-ready combinational
   path. The current `stream_skid_buffer` uses registered occupancy and stored
   output data. It can sustain one transfer per cycle under steady conditions,
   but its contract explicitly includes an input bubble when a full buffer
   starts draining. Neither its name nor a one-cycle latency establishes a
   physical timing-closure result.
3. Each published Phase 3 package has four Component definitions, of which three
   are reachable from the selected root. The hierarchy is top → subsystem →
   behavioral core, with pass-through wiring. An extra mux definition is
   unreachable. The current builder does not construct the described separate
   calculation and flag stages. It declares several unused references, while
   `authoring.py` selects hierarchy through `comp_def.phase == 3`.
4. The generated mux has narrative text claiming Phase 1 provenance, but the
   packages' catalog dependency lists are empty. Treat narrative provenance as
   unverified until an exact source digest and a reproducible transform exist.
5. At published roots, 118 parameter declarations are `int unsigned` and one is
   ROM's packed `bit [(W*DEPTH)-1:0]` value. No scalar `bit` mode flag was found
   at those roots. The proposed scalar-flag cleanup is therefore an audit item,
   not a confirmed current cross-phase defect.
6. `register_async_reset` and `register_sync_reset` allow W up to 256 while
   `RESET_VALUE` is `int unsigned`. Existing presets do not prove that a nonzero
   bit above bit 31 survives. Add a focused reproducer before selecting a fix.
7. `InstanceIR` currently has a name and Component VLNV, without a general
   per-instance parameter map. RTL code nevertheless forwards parameters when
   parent and child names match. This implicit behavior needs explicit tests and
   a documented binding policy; it must not be mistaken for a general binding API.
8. RTL validation currently rejects bus-interface Components. Adding native
   bus interfaces to releases would affect code generation, source validation,
   import, projection and editing. It is a larger change than adding metadata.
9. Current package import accepts a fixed set of annotation namespaces. A new
   channel annotation must gain validation and structured import transforms
   before any published package contains it.
10. The checker and verifier skip missing files whose inventory status is
    `planned`. A passing Phase 3 command can therefore cover the delivered subset
    without proving that all 32 Phase 3 entries exist. Selection and completion
    reporting need explicit covered, missing and planned counts.
11. The checker requires exactly one Component in packages from phases below 3.
    This phase-dependent rule would reject otherwise valid Phase 1/2 structural
    variants. Refactor it with the authoring dispatch; validate the declared
    implementation and closure rather than rollout phase.
12. Verification selects a maintained definition by ID and includes a fallback
    to the first Component when the expected versioned root is absent. Audit
    replacement-version behavior before extending publication: root selection,
    contract version and evidence paths must follow the selected release exactly.

## 3. Decisions and compatibility rules

Use these defaults for implementation. Record any approved change to them before
changing source contracts.

- Preserve every published `.spec`, VLNV, digest, historical evidence file and
  historical handoff. Publish corrections as new releases. Do not rebuild an old
  accepted version from a changed Python definition and overwrite its bytes.
- Keep all dependencies needed by a release inside its package. Source validation,
  Activity discovery, RTL generation and simulation must not download dependencies.
- Keep current flat wire ports and physical names for existing releases. Channel
  metadata describes those ports; it does not replace their source definitions.
- Preserve the Spec/Circuit boundary. The Spec holds interfaces, logic and
  committed topology. Circuit layout remains presentation data.
- Do not require every Component to use a handshake or hierarchy. Combinational,
  pulse, credit, request/response, elastic-stream and CDC contracts remain distinct.
- Do not add upstream auto-update or hidden buffer insertion. Every import,
  dependency update and connection change has a preview, revision guard, atomic
  commit, journal record and explicit designer action.
- Keep `spec_catalog_service/` as the catalog package. The Spec service accesses
  it through HTTP. Do not create a reverse Python dependency from the Spec service.
- Keep `library_catalogue_v1` and its strict version-1 schema unchanged in old
  releases. Add optional, separately versioned annotations for new semantics.
- Use the existing local-work identity rules for editable copies. Record catalog
  identity, version, package digest, transform parameters and fingerprints as origins.
- Keep the original 120 planned Component IDs as a separate delivery count.
  Adapters and structural templates must not silently replace or inflate that count.

Suggested release policy:

| Change | Release treatment |
| --- | --- |
| Fix with the same public ports, legal parameter values and transfer behavior | New patch release, subject to regression evidence |
| Add a compatible optional capability with identical default behavior and fixed ports | New minor release after compatibility review |
| Rename/remove ports, alter mandatory parameters, packing, reset, latency or acceptance behavior incompatibly | New major version or a distinct adapter/template ID |
| New adapter or structural template | New identity with its own contract and evidence |
| Add annotations to an existing immutable package | Publish a new release; never edit old bytes |

## 4. Common channel and transaction contract

### 4.1 Typed source annotation

Propose optional namespace `spec2gds.channels`, version 1. Use the existing
annotation registration mechanism and files under `annotations/channels/`.
Freeze the exact schema in work package U1 before publishing annotated releases.

Each channel definition must identify:

- The containing Component and a stable channel ID.
- A protocol profile and version: initially single-clock ready/valid and a
  request/response grouping. Combinational and pulse ports are described without
  assigning them ready/valid behavior.
- Directional roles and explicit references to valid, ready and payload ports.
- Logical fields mapped to physical ports, including operands, results, controls,
  exception flags, tags and any packet markers.
- Packing order, field signedness and units. Derive widths from canonical port
  declarations and parameter values instead of storing another editable width.
- Clock/reset association, reset polarity, assertion/deassertion assumptions and
  reset flush behavior. Reuse existing timing-domain references where applicable;
  otherwise use explicit clock/reset port references. Do not create a second
  conflicting clock-domain authority.
- Transfer rule, stall stability, ordering, permitted outstanding requests and
  reset cancellation behavior.
- Minimum no-stall latency, acceptance interval, capacity, variable-latency bounds
  and fairness assumptions. Keep these quantities separate.
- Declared combinational input/output dependencies, with source or structural
  evidence. Mark unverified declarations as such.

Validate roles, directions, references, evaluated widths, duplicate field coverage
and incompatible domain assignments in Python. No JavaScript expression execution
or protocol inference from port prefixes or narrative is permitted.

Register structured transforms for copy, rename, delete, import and reopen.
Unknown required annotation versions must fail with diagnostics. Old packages
without annotations must remain loadable and manually connectable. Optional
annotations must not be discarded silently by authoring or format round-trips.

The catalog may return a derived channel summary through HTTP. The canonical
annotation remains inside the `.spec` file. Old releases can have external audit
summaries, but those are suggestions for review and not executable source truth.

### 4.2 Stable payload format

Use named, versioned format descriptions with least-significant field first.
Format equality requires matching field meaning, widths, order and signedness;
equal total width alone is insufficient. Include `sub_i`, `clear_i`, and all
result flags where required by the selected Component.

Example divider transport:

| Record | Low to high bits | Total width |
| --- | --- | --- |
| Request | `dividend[W-1:0]`, `divisor[W-1:0]` | `2*W` |
| Response | `quotient[W-1:0]`, `remainder[W-1:0]`, `div_zero`, `overflow` | `2*W+2` |

In this example, `quotient` occupies bits `W-1:0`, `remainder` occupies
`2*W-1:W`, `div_zero` is bit `2*W`, and `overflow` is bit `2*W+1`.
Choose a format ID scoped to the divider contract and version. Do not relabel
an adder carry/no-borrow flag as a divider overflow flag.

All record fields transfer atomically on the same valid/ready event. While
valid is high and ready is low, the complete record stays stable. A format adapter
must never accept one operand or deliver one result flag independently.

## 5. Transport, adapters and sideband policy

### 5.1 First delivery: packed records and existing storage

Create reviewed adapters for at least multiplier request/response and divider
request/response. Extend the pattern to MAC control and results after the first
compositions pass. Keep the arithmetic release's existing physical ports.

An unpacker from one packed input channel to an existing arithmetic request may
be a combinational field map with the same valid/ready event. A response packer
must bundle every result and status field. The contract states any buffering;
a pack/unpack label alone does not authorize adding a cycle.

Do not use this adapter to invent a handshake for a combinational Component.
Wrapping a combinational adder requires a separate elastic-register contract.
Joining two independent operand streams requires state and a defined pairing
rule, such as FIFO order with one slot per operand. It is a separate capability.
Existing `stream_join` must be checked for exact suitability before reuse.

Feed the entire packed record through `fifo_sync`, `stream_register`,
`stream_skid_buffer`, or a supported CDC transport by setting the payload width
to the record width. Check each Component's legal width range before authoring.
Reject an oversized record rather than truncating it or increasing limits silently.
For an asynchronous queue or handshake, cross the whole record using its existing
CDC protocol; do not synchronize result bits and flags separately.

### 5.2 Later delivery: explicit sideband interfaces

Do not retrofit `USER_W` into all 76 releases. First demonstrate a use case that
cannot be represented safely by the packed-record approach. Then publish selected
sideband-aware wrappers or new versions with a complete transfer contract.

- `USER_W=0` must not produce `[-1:0]`, a zero-width packed slice, or a dynamic
  omission of saved ports. If one fixed-port design supports zero, reserve a
  physical width of `max(1, USER_W)`, tie the disabled output to zero, and document
  the reserved input behavior. Otherwise publish distinct plain and sideband variants.
- A native conditional-port feature would require a separate source-format and
  editor design. It is not a prerequisite for this plan.
- Width converters need an explicit metadata policy. For per-input-beat metadata,
  upsizing may preserve an ordered vector of metadata entries; downsizing may
  select the corresponding entry. For packet metadata, stability and boundary
  rules differ. Reject unsupported profiles rather than taking an OR, replicating
  fields, or dropping bits by default.
- Define `last`, byte-valid masks, empty/partial words and packet-boundary behavior
  before claiming packet-aware conversion. Keep opaque record transport separate
  from converters that interpret record fields.
- Test fork completion, join pairing, arbitration selection and packet rollback
  with metadata. A generic sideband label does not establish any of these rules.

Arm's AXI-Stream specification treats transfer data and associated information
as a protocol contract, including packing and width-conversion rules. Use it as
a design reference where relevant; this project's custom channels are not thereby
AXI-Stream compliant. See [Arm IHI 0051B, sections 2.2–2.9](https://documentation-service.arm.com/static/64819f1516f0f201aa6b963c).

## 6. Timing, buffering and domain checks

Keep current unbuffered arithmetic behavior unchanged. Offer an explicit wrapper
that composes a chosen arithmetic release with a chosen existing buffer.
Its metadata names both releases and records the added capacity and latency.
Parameter presets alone cannot select a different topology unless that selection
is an actual declared and validated source capability.

For each wrapper, test continuous flow, abrupt stall, occupancy transitions,
simultaneous push/pop, draining from full, reset while occupied and recovery.
Measure acceptance interval and first-result latency separately. Preserve the
current skid buffer's full-drain bubble unless a separately versioned design
has been proved to change that behavior.

Use an elaborated RTL dependency check, where supported, to confirm a declared
ready-path break. A source string search is not sufficient evidence. At the
connection layer, detect cycles in declared combinational dependencies and warn
about long paths. Logical depth is not an Fmax estimate. Physical timing claims
require separate synthesis, constraints and implementation evidence.

AMD's register-slice documentation distinguishes latency from back-to-back delay
and states assumptions about downstream readiness. Apply that distinction to our
own measured contracts; do not transfer AMD IP performance claims to catalog RTL.
See [PG085, Latency](https://docs.amd.com/r/1.1-English/pg085-axi4stream-infrastructure/Latency).

Require explicit domain agreement before connecting channels. Different clocks,
different reset release policies, or unknown domain mappings require a reviewed
CDC adapter or an explicit diagnostic. Do not auto-connect two channels across
clock domains because their fields match. Digital tests and structural checks do
not establish metastability MTBF or a physical CDC signoff.

## 7. Dependency reuse and meaningful hierarchy

### 7.1 Resolve at authoring time

Reuse the catalog client's exact-version download and digest validation, bounded
archive checks, dependency closure, structured remapping and atomic transaction
path. Extend shared Spec-domain functions where necessary, not the HTTP handler
or catalog service through a new direct import dependency.

Pin each vendored source to identity, version and digest. Record parameter
specialization, transform version, local definition mapping and content fingerprint.
Use one identical local definition for identical pinned content and specialization.
Different versions, edited copies or specializations must coexist with explicit
local identities; never deduplicate by display name or VLNV alone when content differs.

The published package, downloaded release and Activity snapshot must each contain
the complete implementation closure. Disable the catalog after import and repeat
strict validation, save/reopen, RTL and simulation. A lock/origin record supports
reproducibility; it does not authorize network resolution during an Activity.

An upstream fix creates an update candidate. A developer or designer reviews its
diff and dependency impact, publishes or saves a new version, and obtains new
evidence. Imported local edits are preserved. Automatic update remains deferred.

### 7.2 Remove phase-based structural policy

Replace `comp_def.phase == 3` dispatch with explicit implementation selection
and a named topology builder. Keep phase as rollout metadata. Do not change a
published file when making this authoring refactor.

For new Phase 3 versions, remove unreachable source definitions and correct
unverified provenance. Keep a simple arithmetic leaf when it has no useful
internal partition. Use hierarchy when it exposes meaningful reusable behavior,
such as arithmetic plus an independently specified elastic result buffer.

Select a small structural-template set after adapters pass. `fifo_sync` and
`cdc_bus_handshake` are possible cases; `fifo_async` is later and higher risk.
Do not assume that RAM + counters + comparator reproduces the existing FIFO's
read latency, full-cycle acceptance, reset, occupancy and collision rules.
Likewise, a control synchronizer plus register is not by itself a complete
multi-bit handshake. Each template needs an explicit topology and independent
contract-equivalence checks, including non-power-of-two depths and reset in flight.

Retain the optimized leaves as separate releases. Templates need their own IDs,
parameter rules, provenance and verification evidence. Group alternate forms in
catalog presentation instead of inventing extra layers to make drill-down uniform.

## 8. Parameter and numeric policy

| Parameter kind | Recommended representation | Required checks |
| --- | --- | --- |
| Dimensions, depths, iteration counts | Bounded `int unsigned`, or a documented wider type when required | Legal range, arithmetic overflow, cross-parameter relations |
| Logical mode flags | Consistent 0/1 integer mode for new catalog contracts; compare with zero explicitly | Reject values outside the mode set; typed specialization |
| Wide reset values, ROM images, masks and polynomials | Sized packed unsigned values tied to the declared data width | Highest legal bit, no truncation through 32-bit integers |
| Signed coefficients and gains | Explicit signed packed values or a justified signed integer type | Negative limits, sign extension, rounding, saturation |
| Preset values in JSON and HTTP | Canonical decimal strings | Exact values above `2**53`; no JavaScript-number round-trip |

Normalize mode tests such as `SIGNED != 0` in new code. Do not change data types
or reset patterns merely to remove a lint warning. Prove the legal value range
before any cast; a cast must not hide an out-of-range caller value.

Audit the wide reset-value issue first with W=64 and W=256, a nonzero top bit,
reset assertion and deassertion, save/reopen and generated RTL. Verify ROM images
and signed/128-bit arithmetic values through the same source-to-UI-to-RTL path.

Audit same-name parameter forwarding in `codegen.py`. At minimum, distinguish
intentional inherited parameters from fixed specialized children; test a parent
and unrelated child that happen to use `W` or `SIGNED`. Specify typed explicit
bindings before extending general per-instance parameter support. Existing
implicit forwarding cannot be removed without a compatibility plan. Track this
as a separate source contract change if the focused checks prove a defect.

## 9. Implementation work packages

The order below replaces the recommendation document's simple priority list.
Contract and compatibility work precede broad interface changes.

| Work package | Dependencies | Scope and deliverables | Completion gate |
| --- | --- | --- | --- |
| U0: baseline and compatibility audit | None | Snapshot current inventory, source/evidence hashes, channel shapes, parameter types, hierarchy and dependency closure. Reconcile README/phase status with the 76-release inventory. Audit partial-phase reporting and versioned root selection. Record available tools. | Repeatable audit, no altered releases; focused issues separated from assumptions. |
| U1: channel and format contract | U0 | Typed version-1 annotation/schema, transfer and domain rules, two concrete format examples, release compatibility policy and reference-remapping design. | Agreed schema fixtures; no inferred semantics, zero-width ports or duplicate width authority. |
| U2: persistence and transport support | U1 | Spec validation and transactions, rename/import transforms, archive round-trip, optional-source handling, typed API/client data, derived catalog summaries. | Old releases load unchanged; new annotations survive import/edit/reopen and reject stale or invalid changes atomically. |
| U3: arithmetic adapters and compositions | U1, U2 | Multiplier and divider adapters, control/flag preservation, reuse of existing queues and buffer wrappers, exact packing examples and independent scoreboards. | Mixed Phase 2/3 pipelines pass under stalls, reset and exceptional arithmetic results; offline generation works. |
| U4: timing and domain validation | U2, U3 | Buffer characterization, combinational-dependency checks, domain mismatch diagnostics and explicit CDC composition. | No implicit retiming or CDC; measured latency/acceptance/recovery behavior matches the wrapper contract. |
| U5: hierarchy, provenance and numeric fixes | U0; U2 for annotations | Remove phase-driven authoring/checker policy; publish justified new versions/templates; correct provenance; fix confirmed wide-constant/binding defects. | Reachable closure, meaningful topology, exact origin records and contract-equivalence evidence; old versions unchanged. |
| U6: reviewed connection assistance | U2–U4 | Spec Editor channel details; Circuit Designer matching, mapping/adapter preview, revision-safe apply and rejection diagnostics. | Real-browser acceptance; no edits from port-name heuristics or a stale preview. |
| U7: release and handoff | U3–U6 | Extension-release policy, exact candidate publication, immutable download/reindex checks, compatibility report, usage examples and remaining-phase updates. | Required selected profiles and hardware matrices pass, or the release remains explicitly incomplete. |

U5's narrow numeric reproducers may run during U0. A confirmed correctness fix
need not wait for UI work, but still requires versioned release handling.
General per-instance bindings, native bus-interface RTL, automatic dependency
updates and conditional saved-port support are separate follow-up designs.

### 9.1 Expected code and document changes

The following were proposed at review time. Check the current code before implementation; some files now exist:

- `spec2gds/spec/spec_format/channels.py`: typed annotation access, validation and
  reference transforms, with a schema under the established annotation mechanism.
- `spec_catalog_service/src/spec_catalog_service/catalog/channel_profiles.py`:
  reviewed mappings for specific Component versions and format definitions.
- `spec_catalog_service/src/spec_catalog_service/catalog/components/adapters.py`:
  independently specified adapter contracts and reference models.
- Maintained catalog tests for adapter contracts, hierarchy reachability,
  provenance, parameter bounds and exact payload-format round-trips.
- Spec-format tests for optional annotations, structured rename/import, atomic
  failures, origin fingerprints and complete closure.
- Circuit core/service/client changes only after U6 needs are specified. Shared
  types belong in the existing typed packages; presentation code does not infer RTL.
- Existing archive, transactions, import, RTL and verification files listed in
  section 1, with consumers selected through `scripts/test_profiles.py`.
- `docs/spec-catalog/`: Component contracts and links to this proposal. Use the
  runtime inventory for delivery status. Preserve contract anchors and historical
  handoffs.
- `spec_catalog_service/README.md`, `docs/spec-editor.md`, `docs/rtl-generation.md`
  and format documentation: new schema versions, reviewed controls and examples
  only when those capabilities exist.

### 9.2 Catalog extension and publication policy

Before releasing extra adapter/template IDs, extend maintained verification and
publication selection to support an explicitly listed extension set. The catalog
can already discover releases outside the original inventory, but that does not
establish phase CLI verification or delivery accounting for them.

Select the verification contract by the exact release version and explicit root.
Reject a missing root instead of falling back to the first Component. Evidence
paths must use that same selected version. Separate “all selected published
releases passed” from “the full phase is complete,” and report skipped/planned
IDs explicitly. A partial matrix must never produce a full-phase acceptance claim.

Prefer a separate versioned extension manifest with contracts, selected versions,
dependencies and evidence references. Keep the original phase inventory and its
120-ID acceptance gates unchanged. Existing category constraints still apply.
Index and download the selected extension releases only through the established
immutable storage path. Test discovery, filtering, status, upload, rebuild and
download for both the original inventory and extensions.

Do not add a new phase number or synthetic delivered entries solely to make the
current CLI accept a new adapter. Local prototype Specs stay under `temp/TEMP_*`
until this release path and its evidence requirements are implemented.

## 10. Reviewed connection assistance

Keep catalog browsing/import in Spec Editor. Start channel assistance with a
read-only explanation of fields, protocol, clock/reset and versioned format.

Circuit Designer may then offer compatible channel candidates. Its preview must
show every physical mapping, payload order, inserted adapter, added latency,
clock/reset association and fields that would otherwise be lost. Prefer an exact
direct map when all semantics agree. Require an adapter when they do not.

Reject ambiguous multiple matches, unsupported width conversions, sign changes,
domain mismatch, double drivers, unbound flags and unproven combinational cycles.
Do not truncate or tie off status automatically. The designer can inspect a
diagnostic or select a separately reviewed adapter.

Apply through the existing private draft and Save to Spec path. Capture the
source revision with the preview and revalidate it on commit. Cancel keeps the
loaded Spec unchanged. Preserve existing Options menus, focus behavior, themes
and draft coordination. The saved Spec must remain valid if layout data is removed.

## 11. Verification matrix

| Area | Required evidence |
| --- | --- |
| Compatibility | All 76 old package digests unchanged; old CLI/API consumers and unannotated Specs still work; major changes use new identities/versions. |
| Source schema | Strict parse, unsupported versions, invalid refs/roles/directions, duplicate fields, illegal widths, schema registration and optional-field round-trip. |
| Payload adapters | Pack/unpack inverse, asymmetric operand values, signed values, every flag combination, sub/clear control, W=1 where legal and widest supported records. |
| Handshake | Pre-edge transfer sampling, complete payload stable during stall, continuous traffic, randomized bursts, full/empty edges, no drop/duplicate/reorder, explicit outstanding limits. |
| Arithmetic | Independent expected values, divide by zero, signed min/-1, carry/no-borrow distinction, overflow, reset in flight and flags aligned to the accepted result. |
| Width conversion | Each supported metadata policy, partial/last/keep rules where implemented, unsupported profiles rejected; no inferred reduction policy. |
| Buffers and timing | Empty latency, steady throughput, full-drain recovery, declared forward/reverse dependencies, composed backpressure, reset occupancy. |
| CDC | Multiple unrelated clock ratios and phase offsets, source/destination reset assumptions, no independently crossed flags, stable bundled data and accepted/delivered counts. |
| Hierarchy | Leaf/composite contract equivalence, all required definitions reachable, no fabricated provenance, no duplicate module collisions, parent/child parameter independence. |
| Wide values | Nonzero bits above 31 and 53, W=256 reset patterns, ROM images, signed coefficients, decimal-string preservation and lint without hidden truncation. |
| Import and origins | Exact release/digest/root, shared-leaf reuse, edited local content, renamed copies, conflicting versions, unsupported annotations, stale revisions and no partial save. |
| Offline/determinism | Catalog unavailable after import; repeat RTL from the same immutable snapshot; compare outputs; validate complete source closure. |
| Browser | Browse/import/channel details; preview/apply/cancel; stale concurrent edit; correct diagnostics; menu keyboard/focus behavior and both themes. |
| Catalog durability | First-start discovery, submitted and canonical evidence retention, rebuild/restart, byte-identical downloads and safe corrupt-file handling. |

Use generated RTL, not only Python descriptions, for end-to-end behavior. Keep
independent models separate from implementation translation. Lint the selected
root explicitly and bind evidence to the complete reachable source and presets.
Review warning suppression in simulation harnesses so it cannot hide DUT width
defects that a separate strict lint check did not cover. Testbench-only waivers
must be narrow, visible and justified.

Use one event convention: sample transfer from valid and ready immediately before
the active edge, then update the reference state. Compare result validity/data
at the contract's specified observation point. Reset and simultaneous operations
must have defined priority. Do not compare a post-edge ready signal to decide
whether a pre-edge transaction was accepted.

## 12. Commands and execution evidence

This section specifies later implementation checks. It does not report that they
have run. Use a fresh ignored directory under repository `temp/TEMP_*` for each
run, and configure child temporary output there. Never use `/tmp` for this work.

Start by inspecting selection:

```bash
scripts/test-all.sh fast --dry-run
scripts/test-all.sh integration --scope spec,circuit,assistant,verification,activities,shared --dry-run
scripts/test-all.sh regression --dry-run
```

Run the maintained catalog and Spec-domain tests after their relevant work packages:

```bash
uv run --package spec-catalog-service python -m pytest spec_catalog_service/tests -m 'not extensive' --basetemp temp/TEMP_unify_catalog_pytest
uv run --no-sync python -m pytest tests/spec/spec_format -m 'not extensive' --basetemp temp/TEMP_unify_spec_pytest
```

Validate the fully delivered predecessor phases with the current CLI:

```bash
uv run --package spec-catalog-service spec2gds-catalog check --phase 1 --output temp/TEMP_unify_check_p1
uv run --package spec-catalog-service spec2gds-catalog check --phase 2 --output temp/TEMP_unify_check_p2
```

Phase 3 is partially delivered. Current check/verify code skips absent planned
files, so `--phase 3` can pass without completing all 32 entries. Treat its result
as a partial-delivery check, not a full-phase completion gate. U0 must record which
12 IDs and presets actually ran and which 20 remain planned. Before new subset or
extension publication, add explicit selection and coverage reporting to existing
tooling, with tests and documented commands. Do not invent a `--components` flag
or relabel planned records as delivered.

For source/format/runtime changes, run:

```bash
scripts/test-all.sh fast
scripts/test-all.sh integration --scope spec,circuit,assistant,verification,activities,shared
scripts/test-all.sh regression
```

Use configured credentials for the three live smoke checks in Full regression. Missing tools
or credentials make the affected profile incomplete. Record optional synthesis,
formal and physical checks separately. Run new adapter/composition hardware
matrices explicitly through the maintained verifier after selection support exists.
Release preparation also includes predecessor hardware matrices and a hash sweep.

Long-running tests remain deferred under the designer's current instruction.
Do not resume them while authoring this plan. At implementation handoff, list
exact commands, outcomes, corrected reruns, incomplete coverage and evidence
directories. Preserve original failures; a later focused pass is additional
evidence rather than a reason to overwrite a profile result.

## 13. Delivery sequence and acceptance

Use separate reviewable changes:

1. Baseline audit and current status corrections; numeric reproducer results.
2. Channel/format specification, schemas, and migration fixtures.
3. Persistence, import and typed API/client support.
4. Two arithmetic adapter families and FIFO/buffer compositions.
5. Timing/domain checks, CDC composition and provenance/authoring corrections.
6. Reviewed connection assistance and browser regression protection.
7. Versioned extension releases, selected structural templates and final handoff.

Each change records its dependencies and can be reviewed before the next one
changes shared behavior. Do not regenerate every catalog package as an early step.

Initial interoperability acceptance requires:

- A saved pipeline that imports Phase 2 storage and Phase 3 arithmetic by exact
  release, carries a complete result record, and generates RTL offline.
- Divider flags and results remain associated under stalls, divide-by-zero,
  signed overflow and reset. No field is dropped or reinterpreted.
- A selected buffer wrapper has measured timing and capacity behavior matching
  its declared contract; old arithmetic latency remains available unchanged.
- Clock/reset mismatch is diagnosed; an explicitly selected CDC composition is
  independently checked before any cross-domain success is claimed.
- Channel annotations and origins survive rename, import, edit, save/reopen and
  Circuit Designer draft/commit, with atomic stale-revision rejection.
- New versions/templates have meaningful reachable structure and exact provenance.
  Old releases, identities, evidence and manual editing paths remain intact.
- Documentation reports 76 delivered and 44 planned at this baseline, then follows
  the runtime inventory as subsequent work is accepted. Completing interoperability
  does not mark the remaining Phase 3/4 hardware as delivered.
- Required software and hardware checks have recorded outcomes. Deferred checks
  remain explicit; acceptance must not imply a full regression or physical signoff.

After acceptance, consider explicit instance-parameter bindings, selected native
bus-interface RTL support, more sideband-aware variants and dependency-update
assistance as separately scoped work. They are not prerequisites for the first
safe mixed-phase pipeline.

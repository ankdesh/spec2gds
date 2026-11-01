# Component library: implementation guide

Status: plan only. No library implementation is complete.
Prepared and revised: 31 October 2026.

## 1. Purpose and execution order

Build a reusable hardware Component library for Spec Editor and Circuit Designer.
Combine precise Specs, executable behaviour, reusable verification assets, and
controlled technology bindings. Make the library useful before expanding its
catalogue.

Give the coding agent this file and **one** phase file. Implement the phases in
order. Each phase contains ordered work packages, acceptance checks, and a
handoff record. Finish a work package before starting the next. Do not start a
later phase to avoid an incomplete gate in the current phase.

| Order | Required authoring method | Phase file | Required result |
| --- | --- | --- | --- |
| 1 | HTTP Spec API against a real service | [API foundation](phase-1-foundation.md) | Shared library contracts, six seed Components, exact release/import APIs, and service defect checks |
| 2 | Spec Editor UI | [Leaf Components and Spec Editor](phase-2-core-and-editors.md) | Core leaf catalogue, structured CSR Activity, library publication/import controls, and UI defect checks |
| 3 | Circuit Designer UI | [Composite Components and Circuit Designer](phase-3-control-and-composition.md) | Three reusable composite Components, nested topology, private-draft library placement, and save-back defect checks |
| 4 | AI Assistant through published flows | [Highest-level assembly and release](phase-4-releases-and-evolution.md) | One new leaf, a two-lane subsystem, Assistant library support, controlled updates, and release/storage checks |

These are dependency gates, not calendar estimates. The research reports do
not establish the effort needed in this repository. Record actual effort and
remaining work at each handoff.

## 2. Decisions and working defaults

| Topic | Decision | Basis |
| --- | --- | --- |
| Use in a Spec | Import an exact release into the destination `.spec` file. Local edits create a recorded fork. | Confirmed by the designer |
| First proving example | A control and streaming subsystem with registers, FIFO storage, and arbitration | Confirmed by the designer |
| Authoring methods | API → Spec Editor UI → Circuit Designer UI → AI Assistant | Confirmed by the designer |
| Defects | Reproduce, fix, and protect defects found while using each method | Confirmed by the designer |
| Deliverables | Complete Spec, executable SystemVerilog, and scoped verification evidence | Planning default selected to close the earlier open choice |
| Targets | Portable digital behaviour usable by ASIC and FPGA flows; generic qualification first; physical bindings qualified separately | Planning default |
| Existing RTL | Original implementations for the mandatory catalogue; third-party adaptations are later opt-in additions | Planning default; removes a licence/tool choice from mandatory work |
| Initial storage | Small unpacked authoring packages in Git; local provider in the Spec service process | Fixed starting design |
| Hosted catalogue | Provider contract and failure tests only; no production service in these phases | Fixed scope |
| CSR source | Typed JSON v1 under `annotations/library/csr/`; deterministic `csr.build` Activity | Fixed design; no SystemRDL/HJSON tool selection during implementation |
| First bus profiles | Flat-wire APB4 and AXI4-Lite targets, 32-bit little-endian data | Fixed initial scope |
| Reset | Rising-edge logic; `rst_ni` asynchronously asserts and synchronously releases at the environment boundary; internal controls use asynchronous active-low reset | Fixed default; synchronizer contracts remain explicit |
| Parameters | `DATA_WIDTH=32`, `DEPTH=4`, and `COUNT_WIDTH=32` where applicable; exact phase tables override these defaults | Fixed initial presets |
| Technology and advanced IP | Generic digital implementations only; vendor mappings, async FIFO, full AXI, FPU, crypto, and other retained candidates are outside mandatory delivery | Fixed scope with a retained backlog |

Planning defaults are decisions in this plan, not claims that the designer
explicitly selected them. Use them without reopening the choices during
implementation. Change them only for an explicit new instruction or a proved
technical incompatibility. Record the incompatibility and choose the smallest
compatible correction.

### Required method and permitted supporting work

The method in each phase controls how its mandatory hardware source is authored
and saved. Implementation code, unit fixtures, build scripts, and read-only
inspection can use normal developer tools in every phase.

| Method | Required evidence | Prohibited substitute for acceptance |
| --- | --- | --- |
| Spec API | Recorded HTTP requests, service responses, bound document identity, revision changes, and reopened `.spec` source | Directly writing XML/ZIP/IR and then opening it in the service |
| Spec Editor UI | Actual create/edit/import/publish controls, browser interaction trace, and reopened durable source | Calling mutations from a shell, test request client, or browser evaluation while calling the result UI-authored |
| Circuit Designer UI | Placement, connections, hierarchy, save/cancel, and publication through the source-bound UI | Seeding the expected final graph through a lower-level API |
| AI Assistant | Explicit designer request, published flow execution, required product decisions, exact applied receipts, and reopened source | Scripted model output or direct API authoring presented as live Assistant success |

Read-only API calls and archive inspection are encouraged to verify UI and
Assistant results. Internal service calls made by genuine controls and flows
are the expected implementation. A missing control or flow capability is work
to implement and test, not permission to bypass the selected method.

SpecIR remains a derived immutable read model. Typed operations can use its
value types internally. Do not create a separate handwritten IR file or use IR
mutation as a persistence path. All methods share the same domain validators,
revision rules, source format, and library resolver.

Later phases reuse released earlier Components. They add new mandatory content
through their assigned method. Repeat a small shared reference case in each
method to expose differences. Compare normalized interface, behaviour, and
topology plus identity mappings; independent authoring can allocate different
opaque IDs, so raw archive equality is not the cross-method equivalence test.
Equal-input rebuilds of one saved source must still produce equal bytes.

### Shared reference Design for all four methods

Use a non-published acceptance Design named `register_reference`. It has exactly
three instances of the released Phase 1 register: `u_reg8a` and `u_reg8b` share
the width-8/reset-zero realization; `u_reg32` uses width 32/reset zero.

| Boundary ports | Direction | Width |
| --- | --- | --- |
| clk_i, rst_ni, en_i | in | 1 each |
| d8_i, d32_i | in | 8 and 32 |
| q8_o, q32_o | out | 8 and 32 |

Make eight nets: clock/reset/enable each fan to all three instances; d8_i feeds
u_reg8a.d_i; u_reg8a.q_o feeds u_reg8b.d_i; u_reg8b.q_o feeds q8_o; d32_i feeds
u_reg32.d_i; u_reg32.q_o feeds q32_o. Check two enabled-edge latency on q8_o,
one enabled-edge latency on q32_o, hold when disabled, and reset to zero.
The local-fork check changes the shared width-8 reset value to 165 and shows
both affected instances. The width-32 instance and published baseline stay
unchanged. Do not add this acceptance Design as another catalogue release.

### Common defect-handling instructions

For every confirmed defect found within these phase flows:

1. Save the failing input, interaction, source revision, expected result,
   observed result, and diagnostic output under `TEMP_library_<run>/issues/`.
2. Add a maintained failing check at the lowest effective layer. Add a browser
   scenario when rendering, focus, gestures, drafts, or browser behaviour matters.
3. Fix the shared cause. Do not patch a generated archive, suppress a diagnostic,
   add an unconditional retry, or weaken the expected result.
4. Re-run the reproducer, affected checks, and required profiles. Repeat the
   original operation through the phase's assigned method.
5. Record the cause, code change, regression check, and before/after evidence in
   the phase handoff. Recheck other method paths that share the changed code.

Fix defects that affect these library flows, data integrity, or required checks.
Record unrelated findings in the handoff with a reproducible case; do not turn
these phases into a repository-wide cleanup. Missing mandatory features remain
incomplete gates. A normal editable incomplete draft is not itself a defect:
the existing UI can preserve invalid SV text and report failed lint. Such a
draft cannot be published as an executable qualified Component.

### Known gaps and unattended decisions

These are code-inspection findings, not claims of completed runtime fixes.
Confirm behaviour during the assigned phase and add regression protection.

| ID | Evidence or prior ambiguity | Required resolution |
| --- | --- | --- |
| L01 | `circuit_adapter.py` emits empty parameter definitions/values and does not fully resolve symbolic terminal widths | Phase 1 implements realization rules; Phase 3 projects numeric terminals from the shared resolver and tests save/reload |
| L02 | Circuit catalog lists definitions from the active Spec | Phase 1 adds library service contracts; Phase 2 adds Spec Editor controls; Phase 3 adds provisional library placement |
| L03 | `verify_target` reports functional simulation as unverified | Keep lint meaning unchanged; Phase 1 adds separate simulation, synthesis, assertion, and formal evidence |
| L04 | Existing `rtl.generate` rejects bus interfaces; Circuit can omit bus-mapped pins | Flat wire protocol profiles in Phase 2; Phase 3 checks every connected pin; full bus lowering stays deferred |
| L05 | The old plan left reset, CSR source, source reuse, and tools to choose later | Defaults here and the exact phase contracts close those choices |
| L06 | No typed library/CSR authoring, publication, or import commands exist yet | Add versioned commands in Phase 1, UI controls in Phase 2, and Assistant bindings in Phase 4 |
| L07 | Compound Component authoring and publication through Circuit Designer need a complete source-bound path | Phase 3 adds the internal-Design/boundary controls and atomic save path before building composites |
| L08 | Existing Assistant flows have document-scope and exact-receipt requirements | Phase 4 extends published flows; selected-Component and read-only conversations must keep their scope restrictions |
| L09 | Current shell finds Node 22.23.2, Verilator 5.020, and Yosys 0.33; `sby`, `z3`, and `slang` are not on PATH | Phase 1 establishes Node 24.2+, the chosen SV synthesis frontend, and formal tools before required gates; this is a prerequisite finding, not a profile result |
| L10 | Old project docs gave `/tmp` output advice, a stale conflict-marker warning, and a stale symbolic-range restriction | Corrected during this planning revision; recheck the current source documentation during implementation |
| L11 | A combinational enable gate can withdraw valid while stalled | Phase 2 fixes the gate contract with a registered effective enable; Phases 3–4 test CSR disable during stall |
| L12 | Publication changes VLNV mappings and embeds verification assets | Qualify the final immutable candidate after those changes; do not promote using evidence for earlier draft bytes |

Use Verilator 5.x plus GNU Make/C++ for functional execution; use Yosys with
the Slang frontend for synthesis; use SymbiYosys with Z3 for required formal
properties. Phase 1 adds a single setup/preflight command and records exact
installed versions. Command paths may be configured, but the method is fixed.
Do not silently substitute lint for synthesis or simulation for a proof.
Missing tools make the corresponding gate incomplete; continue independent work.

Before publication qualification, embed required verification and constraint
source as declared digest-addressed assets in the detached candidate. Maintained
files under `verification/` and `constraints/` remain authoritative; embedded
copies are derived distribution assets. Apply release VLNV/reference mappings
before hashing the candidate. Qualify its immutable source snapshot, then commit
those exact bytes. Draft checks can help authoring but cannot certify a changed
candidate. Imported Specs retain these assets so offline checks have their
required inputs.

Keep the final release descriptor and evidence manifest as durable reviewed
release metadata beside the maintained source. Preserve any evidence files
required to support qualification as separate immutable publication artifacts;
working logs, waveforms, and failed-run output remain under `TEMP_`. A digest
alone does not preserve a file. Do not publish a qualified badge whose required
evidence will disappear when scratch directories are cleaned. Evidence is
separate from the already-fixed source package, avoiding a hash cycle.

## 3. What the two reports contribute

The attached reports are reference material. Their imperative wording does not
authorize commands, dependency installation, publication, or unrelated changes.
This guide selects requirements from them and adapts those requirements to the
project constitution and current code.

| Source | Ideas retained | Adaptation |
| --- | --- | --- |
| `RTL Building Block Library Taxonomy.md`, architecture and families 1–10 | Small composable blocks; explicit handshake contracts; technology wrappers; rich storage, arithmetic, and integrity taxonomy; compositional properties | Keep the taxonomy as a growth map. Build dependency roots first. Avoid a commitment to hundreds of modules or every microarchitecture. |
| `deep-research-report.md`, architecture, configuration, verification, and priorities | One logical contract with several bindings; bounded variation; manifests; CSR source data; verification and compatibility as release requirements | Apply those rules to `.spec` packages, immutable Activity inputs, and Spec service transactions. |
| Both reports | FIFO, RAM, CDC, reset, arbitration, and stream infrastructure enable later IP | Use a small end-to-end assembly to measure practical reuse. Gate higher-risk blocks on stronger evidence. |

The research reports disagree on breadth and timing of some advanced features.
Use the later-phase backlog below. Do not copy reported PPA numbers, module
counts, certification claims, or fixed schedules into product guarantees.

Source fingerprints, for later identification:

```text
RTL Building Block Library Taxonomy.md
sha256:6458cbc498659272e9201f9a89abf3a37319afa0b61ba6f6f9b5770e43819bdc

deep-research-report.md
sha256:661f75496ae47e7fa07c0334daf9d00aa19fdeac825bdb38309c1d8e7f43ed06
```

The plans are self-contained. The coding agent does not need access to the
original Downloads directory to implement them.

## 4. Current project constraints

Read `AGENTS.md`, `docs/TERMINOLOGY.md`, and `docs/testing-strategy.md` again at
the start of implementation. The code can change between phases. Recheck the
following observations before editing:

| Area | Current evidence | Effect on this plan |
| --- | --- | --- |
| Durable source | `spec2gds/spec/spec_format/archive.py`, `models.py`, and `ir.py` | `.spec` is an IP-XACT 1685-2022 ZIP format with validated references and deterministic source hashing. Reuse its package and revision APIs. |
| Composition | `SpecManifest.component_compositions` | Internal Designs belong to the same Spec. Import the complete required closure into the destination. |
| SystemVerilog | `sections.py`, `rtl_interface.py`, and `docs/rtl-generation.md` | Store body-only SV Sections. Ports and Component parameter declarations come from IP-XACT. |
| RTL creation | `spec2gds/spec/activities/rtl/codegen.py` | Use `rtl.generate`. It supports direct wire topology and declared parameters. It rejects bus interfaces and unsupported connections. |
| Circuit projection | `spec2gds/spec/spec_format/circuit_adapter.py` | The catalogue is local to a Spec. Parameter definitions and instance values are not yet carried through this adapter. Bus-mapped pins can be omitted. |
| Verification | `component_verification.py` | The current result explicitly reports functional simulation as unverified. Lint success is insufficient for library qualification. |
| Saves | `transactions.py`, `v1_api.py`, and `docs/spec-circuit-integration-architecture.md` | The Spec service validates and commits. Circuit service state is a projection. Preserve revision conflicts, leases, approval policy, and Save to Spec behaviour. |
| Activity inputs | `docs/activity-sdk.md` | Jobs use immutable snapshots. Import required source before snapshot creation. A running job must not resolve a changing library. |

Extend existing boundaries. Do not add library persistence to Circuit core or
make one browser call the other browser. Keep library search and package
resolution deterministic and usable without the AI Assistant.

## 5. Storage design that can change later

Keep four concepts separate:

1. **Authoring source:** reviewed files used to create a Component release.
2. **Release artifact:** immutable package bytes and their verified digest.
3. **Catalogue:** searchable metadata that points to exact releases.
4. **Imported copy:** source stored in a design's `.spec` file, with provenance.

The catalogue location is not part of Component identity. A moved folder or new
server must not change a library ID, VLNV, release digest, or imported source.

### Initial organization

Use a top-level `library/` directory, separate from the software npm packages.
Start with one authoring package per independently versioned Component release.
A package can include an internal Design. Reusable dependencies remain explicit.
Collections select releases; they do not contain another editable copy of RTL.

```text
library/
  schemas/                    # Library metadata schemas
  components/
    <family>/<component-id>/<version>/
      library.json            # Library-only metadata and dependency pins
      source/                 # Canonical unpacked V1 .spec source
        mimetype
        manifest.json
        ipxact/...
        document/document.json
        annotations/entity-sections/...
        annotations/library/...
      verification/           # Maintained tests and property source
      constraints/            # Maintained constraint source, if applicable
      LICENSES/               # Required licence and notice text
  collections/                # Named lists of exact releases and presets
  examples/                   # Maintained assembly source and checks
TEMP_library_<run>/           # Ignored packages, indexes, builds, logs, evidence
```

All paths above are proposed paths. They are not existing features. Use the
current pack/unpack APIs rather than a second ZIP implementation. Keep normal
code in an appropriate Python module, proposed as
`spec2gds/spec/component_library/`. Keep it independent of HTTP and UI code.

For handwritten Components, the unpacked Spec is the only editable hardware
source. Author it through the phase's required method; the publication service
exports validated source for Git review. Build full SV modules through
`rtl.generate`; do not maintain a second handwritten full module. For a
structured CSR Activity, the CSR description is the editable source. Record its
digest and Activity version in the derived SV Section and reject stale output.
Third-party source adaptation is outside mandatory delivery. A later adaptation
must preserve upstream source, licence, and an explicit implementation profile.

### Storage options

| Option | Useful when | Main cost | Plan |
| --- | --- | --- | --- |
| One library `.spec` file | Small exchange bundle or offline demonstration | Coarse review and release boundaries; larger reads; unrelated Components change together | Support as a distribution view in Phase 4 |
| Several packages with an index | Independent review, release, and test selection | Dependency resolution and closure import | Start here |
| Hosted catalogue with immutable packages | Several installations need one release source or access rules | Service operations, authentication, availability, and cache management | Reuse the provider contract; implement only for an identified deployment |

Do not choose a database, registry product, object store, or new service
framework in Phase 1. A local catalogue is enough to prove the contract.

### Minimal provider contract

Define typed operations with no filesystem paths in public identity:

- `search(query, filters, cursor)`: return summaries and a catalogue revision.
- `describe(release_ref)`: return contract, limits, presets, and evidence summary.
- `resolve(release_ref, target, parameters)`: return an exact dependency graph,
  selected bindings, digests, and import capability diagnostics.
- `fetch(artifact_ref)`: return bytes that must match the requested digest.

Search can show the newest release. Resolution and import require exact
versions and digests. A catalogue response is data, not executable build code.
The provider does not write a destination Spec. The Spec service performs
preview, approval where configured, and atomic import.

## 6. Identity, parameters, import, and local forks

Keep these values distinct:

| Value | Meaning |
| --- | --- |
| Stable library ID | Logical family identity, independent of directory and provider |
| Exact VLNV | Hardware contract identity for one version |
| Release digest | Immutable content identity for one published package |
| Local `EntityRef` | Identity after import into a destination Spec |
| Realization key | Digest of exact release, normalized parameter values, selected binding, and adaptation version |
| Fork provenance | Original release, imported baseline digest, and the locally changed source |

Use semantic versions for contracts. A reset, latency, collision, handshake, or
parameter compatibility break needs a major version even if the ports match.
Reject different bytes for the same published release identity. A new source
revision needs a new release. Store tested parameter combinations explicitly.

For the first integration, use deterministic **specialized definitions** for
concrete parameter sets. The current instance model has no complete override
path. A specialization gets its own legal local hardware ID and VLNV mapping.
Retain the original parameter declarations and selected values in provenance;
present numeric terminals to Circuit Designer. Do not rewrite identifiers or
SV text with ad-hoc string substitution. Phase 1 defines realization and import;
Phase 3 completes numeric Circuit projection and round-trip checks.

The import sequence is:

1. Resolve an exact release and dependency closure. Check digests, supported
   parameters, target bindings, licences, and application capabilities.
2. Build a detached candidate. Map source IDs to destination IDs. Include
   Components, internal Designs, Sections, necessary assets, contracts,
   constraints, dependency pins, and all applicable source references.
3. Preview added, reused, specialized, and conflicting definitions. No source
   changes occur while browsing or cancelling the preview.
4. Commit with the destination document binding and base source revision. Use
   the existing approval policy. Write source and provenance in one transaction.
5. Re-project Circuit state from the accepted Spec revision. A downloaded or
   offline Spec must remain usable without the provider.

Reuse only an unchanged imported realization with matching provenance and
content. Equal display names or ports do not prove equality. Reject unresolved
ID/VLNV conflicts or produce a reviewed deterministic mapping. Never overwrite
a local definition or silently retarget existing instances.

An edit to imported source creates a local fork and removes the qualified
release badge from that realization. Preserve its origin and baseline. A fork
of a shared local definition affects all its local instances; show those
instances before committing. Offer an explicit clone when the designer wants
only one instance to change. Do not modify the upstream library.

Give the fork a local identity that cannot be mistaken for an unchanged
published release. A changed dependency also invalidates the dependent
realization's inherited qualification. Recheck the reverse dependency closure;
do not update only the directly edited Component's badge.

Keep a typed import record under a registered `annotations/library/` namespace.
Do not add arbitrary keys to strict existing manifests. Source-affecting pins,
contracts, and binding choices must affect source identity. Logs, timestamps,
and job history must not. Keep qualification evidence tied to the exact source,
configuration, tool versions, and binding that it tested.

## 7. Component construction contract

For every released Component, require the following information. Reuse existing
IP-XACT fields for ports, parameters, and logical interfaces. Library annotations
add semantics and evidence pointers; they must not become a second port schema.

| Area | Required content |
| --- | --- |
| Identity | Stable ID, exact VLNV, display name, summary, family, version, dependency pins |
| Behaviour | Reset values and priority; operations; legal and illegal inputs; side effects; unknown or unspecified results |
| Interface | Port roles; clock/reset domain associations; signedness where supported; handshake and stability rules |
| Timing | Transfer event; minimum/maximum latency; initiation interval; stalls; combinational path classification |
| Parameters | Types, defaults, legal combinations, tested combinations, derived values, and preset names |
| Implementation | Portable synthesizable body, composite Design, explicit abstract model, or external binding requirement |
| Memory | Port topology, read latency, collision policy, masks, initialization, and invalid-address response |
| Provenance | Original or adapted source; upstream revision if used; file digests; licence and notices; adaptation tool version |
| Verification | Requirement-to-check mapping, simulation, assertions, synthesis result, and formal/CDC evidence where applicable |
| Capability | Spec import, Circuit placement, RTL creation, simulation, synthesis, and target qualification reported separately |
| Limitations | Unsupported combinations and targets; required external tools; model-only or incomplete capabilities |

Use lower snake case for new hardware IDs, `_i` and `_o` for new ports,
`clk_i`, and `rst_ni` for asynchronous active-low reset variants. Use uppercase
parameter IDs such as `DATA_WIDTH` and `DEPTH`. Preserve upstream names behind
an adapter when necessary. Separate reset styles and materially different
behaviours into named variants. Do not silently rename existing project data.

Use valid/ready for the initial stream family. A transfer occurs on the active
clock edge with both signals asserted. The source must hold valid and payload
stable while stalled. The source must be able to assert valid without waiting
for ready. Specify combinational paths per block; do not declare every internal
stream adapter equivalent to an AXI interface. Detect loops across assemblies.
Adapters for credit and consume-acknowledgement interfaces need explicit contracts.

Do not require a separate Component for each Boolean operator. Add a wrapper
when it carries reusable structure, timing, target, or verification meaning.
Use operators for basic arithmetic until measured target evidence justifies a
special architecture. Keep physical clock, SRAM, pad, power, and entropy
implementation behind explicit bindings. A behavioural model is not evidence
of a physical implementation.

## 8. Taxonomy and scope boundaries

Use families for search, not for identity or hard-coded import logic. A
Component can have several tags. Hierarchy depth is derived from dependencies.
Do not encode hierarchy level in stable IDs or require one fixed directory tree.

| Family | Required initial delivery | Later candidates retained from the reports |
| --- | --- | --- |
| State, clock, reset, and technology wrappers | Registers and reset synchronizer in Phase 1; generic binding metadata | Scan-aware variants, clock mux/divider, retention/isolation control, physical bindings |
| CDC | Single-bit level crossing and reset-release contract in Phase 1 | Handshake/event crossings, async FIFO, clearable crossings, reset controllers, credit links |
| Stream buffers and routing | Register slice, skid buffer, FIFO, arbiter, and controlled gate in Phase 2 | Fork/join, packet routing, throttling, credit adapters |
| Width and format adapters | Integer width ratios and explicit byte ordering in Phase 2 | Arbitrary M:N gearboxes and line framing |
| Queues and data structures | Sync FIFO in Phase 2 | Async FIFO, reorder queues, shared linked queues, stacks, rings, PLRU, Bloom filters |
| Memories | Portable 1RW and 1R1W in Phase 2 | 2RW, replicated multi-read, banking, LVT/XOR, multi-pumping, CAM/TCAM |
| Arbitration and fabrics | Round-robin arbiter in Phase 1; stream arbitration/APB demux in Phase 2; composed control fabric in Phases 3–4 | Fixed/weighted/deficit arbitration, allocators, AXI fabrics, NoC |
| Bit operations and counters | Mux/counter in Phase 1; accepted-transfer counter in Phase 2 | Encoders, comparison, population count, masks, scans, permutations |
| Integer, fixed-point, and DSP | Add/subtract, bounded multiply, and round/saturate helpers in Phase 2 | MAC, divider, prefix arithmetic, CORDIC, FPU/HardFloat, microscaling, posit/quire |
| Integrity, safety, and security | Parity, CRC, SECDED in Phase 2; stall watchdog in Phase 4 | Protected FSM/counter, alert channels, scrambling, crypto, secure-boot assembly |
| CSR and bus infrastructure | JSON CSR source, APB4 and AXI4-Lite endpoint profiles in Phase 2; assemblies in Phases 3–4 | Full AXI, TileLink, Wishbone, AHB, legacy bridges |
| External interfaces | Preserve controller/PHY separation in all metadata | UART/SPI/I²C, Ethernet, DDR/USB/PCIe/MIPI controller integration |

Later candidates are a retained backlog, not Phase 4 completion requirements.
Select them using a concrete design need, dependency readiness, implementation
effort, and available verification. Do not implement analogue PLL, SERDES, POR,
or entropy sources as generic synthesizable RTL.

## 9. Verification and release rules

Software profile evidence and hardware qualification evidence are separate.
Verification Planner can supply a hardware Test Plan. A Test Plan describes
checks; it does not prove that those checks ran.

Use a small lifecycle: `draft`, `candidate`, `qualified`, `deprecated`, and
`withdrawn`. Qualification is scoped to a parameter/binding matrix. An unknown
tool result is not a pass. Draft and model-only entries can be searchable when
clearly labelled; normal placement defaults to supported qualified releases.

Every portable executable release needs package/schema checks, resolved
interfaces, lint, functional simulation, applicable assertions, a requirement
coverage record, and a synthesis smoke check. Add formal proof for FIFO
ordering, round-robin progress under stated assumptions, and CDC control
properties. Add structural CDC/RDC review and constraints for crossings. Digital
simulation and formal proof do not establish analogue metastability performance.
Target-specific qualification needs that target's tools and constraints.

Use boundary and risk-based parameter selection. Include width/depth one where
legal, non-power-of-two cases where supported, simultaneous events, reset during
traffic, and invalid settings. Do not claim all parameter combinations from a
few samples. Record proof assumptions and avoid circular assume/guarantee claims.

After implementation, run the required profiles with evidence inside an ignored
repository `TEMP_` directory. Use a new run path each time:

```bash
LIBRARY_RUN_DIR="$(mktemp -d "$PWD/TEMP_library_XXXXXX")"
scripts/test-all.sh fast --dry-run
scripts/test-all.sh integration --scope spec,circuit,activities --dry-run
scripts/test-all.sh fast --output "$LIBRARY_RUN_DIR/fast"
scripts/test-all.sh integration --scope spec,circuit,activities --output "$LIBRARY_RUN_DIR/integration"
scripts/test-all.sh regression --output "$LIBRARY_RUN_DIR/regression"
```

Use the actual scopes from the phase and changed consumers. Shared changes
include all consumers. Run regression for broad contract, persistence, shared
runtime, Activity SDK, model/prompt, and release changes. Fast includes exactly
three live model checks. Use configured credentials. If tools or credentials
are missing, continue independent checks and report the profile as incomplete.
Register new maintained checks in `scripts/test_profiles.py` and the capability
mapping where needed. Do not create a duplicate regression collection.

Use `TEMP_*` for every scratch Spec, compiler output, screenshot, log, cache,
and progress file. Set child-process temporary directories accordingly. Never
use `/tmp`. Existing `.gitignore` rules already cover `TEMP_*` and `**/TEMP_*`;
verify that they still apply. Keep maintained test sources in tracked folders.

At each handoff, report changes, executed commands, outcomes, evidence paths,
untested combinations, and unresolved limitations. Do not mark a phase complete
with missing required evidence.

## 10. Primary references and interpretation

The following references confirm selected patterns. They do not mandate a tool
dependency for spec2gds. Checked on 31 October 2026.

- [OpenTitan hardware primitives](https://opentitan.org/book/hw/ip/prim/index.html)
  describe technology libraries, generic models, and virtual implementation
  selection. This plan adopts the separation and requires deterministic binding
  selection.
- [FuseSoC core files](https://fusesoc.readthedocs.io/en/stable/user/build_system/core_files.html)
  describe ordered file sets, dependencies, parameters, and build targets. This
  plan uses those concepts for release metadata without requiring FuseSoC.
- [OpenTitan register tooling](https://opentitan.org/book/util/reggen/index.html)
  describes structured register input and software/hardware access semantics.
  This plan fixes a small internal JSON source and a deterministic adapter in
  Phase 2; it does not require OpenTitan tooling.
- [PULP common cells](https://github.com/pulp-platform/common_cells) provide a
  catalogue of reusable clock/reset, CDC, storage, and stream blocks. Treat it
  as a source candidate for later work; the mandatory initial RTL is original.
- [sv-elab](https://github.com/povik/sv-elab) documents the Slang-based
  SystemVerilog frontend and its Yosys integration. The installed Yosys 0.33 is
  not a sufficient frontend preflight. Check actual `read_slang` availability
  and pin a compatible tool bundle in Phase 1.
- [SymbiYosys formal constructs](https://yosyshq.readthedocs.io/projects/sby/en/latest/verilog.html)
  and [proof modes](https://yosyshq.readthedocs.io/projects/sby/en/latest/reference.html)
  distinguish assumptions, assertions, cover checks, and bounded/unbounded
  checking. Use portable immediate property harnesses; no proprietary SVA
  frontend is required by this plan. Report proof mode and assumptions.

## 11. Coding-agent handoff instructions

At the start of each phase:

1. Read this guide and the selected phase. Check the previous phase handoff.
2. Inspect the working tree and preserve unrelated changes. Recheck current
   APIs, source contracts, and required test selection.
3. State the first work package. Resolve routine details within the decisions
   above. Ask a focused question only when a missing decision changes behaviour
   or prevents required verification.
4. Implement and verify the work packages in order. Keep an incomplete work
   package explicit if a required external prerequisite is unavailable.
5. Complete the phase handoff record. Stop at that phase boundary.

Use the actual phase filename from the execution table in the request. For
example, the first implementation request is:

> Implement `docs/component-library/phase-1-foundation.md`. Follow
> `docs/component-library/README.md` and the project rules. Build the mandatory
> Components through the real HTTP Spec API. Fix in-scope confirmed defects,
> add regression protection, and record the required evidence. Complete Phase 1
> only and stop at its exit gate.

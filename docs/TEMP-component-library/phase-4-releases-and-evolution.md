# Phase 4: build the highest level through AI Assistant and qualify release

Status: not started. Required authoring method: live AI Assistant through
published flows, with requests entered in the Assistant UI.
Prerequisite: [Phase 3](phase-3-control-and-composition.md) complete and
[implementation guide](README.md).

## 1. Fixed result and scope

Use AI Assistant to author one new leaf, `stall_watchdog`, and one highest-level
composite, `dual_stream_subsystem`, from exact existing library releases. Complete
the required product approvals and verify exact applied receipts. Fix defects
in context, discovery, scope, authoring, approvals, persistence, and recovery.
Then qualify the initial library release, controlled updates, and both storage
layouts.

Highest-level authoring must use a live configured model and the real Spec
service. Scripted model fixtures are valuable regression checks, but they do
not satisfy the live acceptance case. Direct API edits cannot repair a failed
Assistant acceptance run invisibly. Fix the cause and repeat through the flow.

## 2. Complete Assistant library support

Read `docs/ai-assistant-flows.md`, the current Spec operation contracts,
`ai-assistant/src/spec-flows.ts`, `service-clients.ts`, and the published flow
catalogue before editing. Preserve unrelated working-tree changes.

Use a **document-bound Focused Spec conversation**. It can create a leaf and a
Design. Selected-Component scope cannot create another top-level Component.
Orchestrated Spec conversations are read-only. Circuit conversations do not
inherit Spec-authoring tools. Enforce those boundaries in tools and services.

Add deterministic read tools `library_search`, `library_describe`, and
`library_resolve` to the appropriate profile. The tools return exact references,
contracts, capabilities, limits, and scoped evidence. The model may suggest a
release, but the host validates identity, supported configuration, and digest.
No model-supplied filesystem path or arbitrary downloaded archive is a source
reference.

Extend published `flow_edit_spec` with a deterministic library-import preparation
stage. It resolves exact dependencies and merges the resulting typed import
operations with the approved Component/Design/topology batch. Preparation does
not save. Structural review covers the **exact combined batch**, including
source/dependency digests. Commit imports, provenance, instances, connections,
and composition links atomically. Keep scope and base-revision checks.

Continue using `flow_add_component` for new leaf authoring. Add published
`flow_publish_library_component` for detached local publication preview,
qualification of the exact final candidate, required review, exact local publication, and receipt
reconciliation. Both use shared library domain commands, not manual transaction
routes called outside approval. Extend operation/client schemas and integration
metadata in the same change. Do not invent a separate Assistant library store.

A flow is complete only with the authoritative exact applied receipt. A model
message, accepted tool call, empty created Spec, architecture approval, pending
proposal, or displayed preview is not saved-content evidence. Preserve content
and structural decisions, request IDs, artifact digests, trace state, and
restart/reconciliation rules from the current flow implementation.

The Assistant may author SV from an explicit designer request. `rtl.generate`
and other deterministic Activities still emit only stored explicit source;
they must not infer missing logic from narrative.

## 3. Assistant reference case

Enter a request through the Assistant UI to import `register_en_arst_n` at width
8 twice and width 32 once, using exact Phase 1 references. Ask for a Design with
repeated width-8 instances and the same direct reference connection used in
Phase 3. Include the guide's exact register_reference boundary and eight nets.
Complete product reviews and inspect exact saved receipts.

Compare normalized ports, parameters, behaviour, realization reuse, instances,
and reference mapping with the other methods. Opaque IDs and layout can differ.
No new definition is allowed solely because the model omitted an existing exact
library match. Explicitly test a requested local fork and show its affected
instances. Existing published source remains unchanged.

## 4. Author stall_watchdog through AI Assistant

Enter this complete request in the same document-bound conversation. Replace
only the destination path and exact library release references with those from
the handoff; the behaviour is fixed:

> Create a complete reusable leaf Component with ID stall_watchdog and name
> Stall watchdog. Use clk_i and asynchronous active-low rst_ni. Inputs valid_i
> and ready_i are scalar. Output timeout_o is scalar. Parameter LIMIT is int
> unsigned, default 16, and must be at least 1. At each rising edge, count
> consecutive cycles where valid_i is 1 and ready_i is 0. Saturate at LIMIT.
> Reset the count to zero when that condition is false. timeout_o is high
> exactly when the stored count equals LIMIT. Asynchronous reset clears the
> count and timeout. The first stalled edge increments from zero to one; the
> LIMITth consecutive stalled edge asserts timeout. A non-stalled edge clears
> it. It is a monitor and must not drive ready or modify stream data. Include
> complete ports, parameters, description, body-only SystemVerilog, library
> contract, and tests for LIMIT 1, 2, and 16. Do not save a placeholder or
> instantiate another missing block. Use flow_add_component and report the
> exact applied content receipt.

The host validates parameter legality, port shape, scope, operation schema,
complete SV content, and approved interface before submission. Qualification
uses an independent reference counter and directed reset/threshold cases;
formal checks prove saturation and timeout equivalence under the stated reset
model. Publish version 1.0.0 through the new publication flow.

The source is original. No security or safety certification is claimed. An
active stall that clears ready on the next edge must clear timeout on that edge,
not leave it sticky.

## 5. Author dual_stream_subsystem through AI Assistant

Use exact 1.0.0 releases for `apb_stream_subsystem`, `apb_demux2`, and
`stall_watchdog`. Enter a request containing all of the following contract and
connection requirements. Store the request and exact resolved release/digest
list in the acceptance evidence. Do not ask the model to invent an architecture.

### Exact structure

Create a composite Component and its internal Design with hardware ID
`dual_stream_subsystem`, display name Dual stream subsystem, and no configurable
public parameters. Place exactly five direct instances:

| Instance | Released Component | Selected configuration |
| --- | --- | --- |
| `u_bus` | apb_demux2 | Fixed 16-bit input/12-bit output address profile |
| `u_lane0`, `u_lane1` | apb_stream_subsystem | Fixed Phase 3 32-bit stream/depth-4 configuration |
| `u_watch0`, `u_watch1` | stall_watchdog | LIMIT=16 |

Reuse one unchanged definition for both lanes and one for both watchdogs.
Import each shared dependency realization once, retaining nested internal
Designs. No full RTL rewrite, flattened hierarchy, or top-level behavioural
SV body is needed.

### Exact boundary

- Common scalar `clk_i` and `rst_ni`.
- One complete APB4 boundary with the Phase 3 signal IDs, except
  `paddr_i[15:0]` is 16 bits. Data/strobes/protection retain widths 32/4/3.
- For j in {0,1} and k in {0,1}: inputs `lane{j}_s{k}_valid_i`,
  `lane{j}_s{k}_data_i[31:0]`, and output `lane{j}_s{k}_ready_o`.
- For each j: outputs `lane{j}_m_valid_o`, `lane{j}_m_data_o[31:0]`,
  `lane{j}_irq_o`, `lane{j}_stall_o`, and input `lane{j}_m_ready_i`.

The indexed names above expand to concrete ports during authoring. They are
not array ports or symbolic Circuit slices.

### Exact connections

1. Fan common clock/reset to all five direct instances.
2. Map each APB boundary request signal to the corresponding u_bus `s_` input.
   Map u_bus `s_` read-data/ready/error outputs to boundary responses.
3. For j in {0,1}, connect u_bus `m{j}_` address/select/enable/write/data/strobe/
   protection outputs to the same APB inputs of u_lane{j}. Connect that lane's
   APB read-data/ready/error outputs to u_bus `m{j}_` response inputs.
4. Map every lane boundary source stream to the corresponding u_lane{j}
   source stream, with data/valid forward and ready backward.
5. Map u_lane{j}'s output stream to lane{j}_m_* with reverse ready. Also connect
   the same output valid and external ready to u_watch{j}.valid_i/ready_i.
6. Connect each lane IRQ to lane{j}_irq_o and watchdog timeout to
   lane{j}_stall_o. A watchdog observes traffic and does not affect it.

Address map: lane 0 is 0x0000..0x0fff, lane 1 is 0x1000..0x1fff; local register
offsets are the Phase 2 map. Other addresses return the demux error response.
Reset and runtime stream-enable semantics are inherited unchanged from Phase 3.
There are four stream sources and two independent outputs.

Use the extended `flow_edit_spec` to prepare imports, review the exact proposed
structure, and commit it. Content plus structure must be complete before a
success message. Publish the composite only after saved-source qualification.

### Required highest-level checks

Through bus transactions, enable both lanes, set different thresholds, and
exercise both input pairs with independent randomized output stalls. Check
correct lane address decoding, no cross-lane data/status leakage, round-robin
service, ingress counts, accepted-egress CRC, and IRQ clear/set semantics.
Hold one output stalled for 15 cycles: no timeout. On the 16th stalled edge,
timeout asserts. Continue stalling: it stays asserted. Accept or remove valid
according to the stream contract: the next non-stalled edge clears it. Keep the
other lane transferring to prove isolation.

Close and reopen in both applications without editing. Inspect all five direct
instances, both nested lane hierarchies, dependency deduplication, and source
contracts. Create RTL from the saved snapshot, then simulate and synthesize
that actual output. The request text is a requirement input, not proof of result.

## 6. Assistant defect campaign and recovery

Add maintained deterministic regressions and actual live acceptance evidence
for the paths below. Record failed runs; do not present only a successful retry.

| Case | Required result |
| --- | --- |
| Exact qualified match exists | Reuse the pinned library definition and selected realization |
| Unknown/unqualified release or illegal parameter | Specific diagnostic; no invented replacement or implicit parameter change |
| Selected-Component or read-only conversation | Scope restriction remains enforced; no top-level source write |
| Incomplete/invalid authored leaf | No placeholder success; failed validation identifies missing source; correction uses a new guarded proposal |
| Model changes approved structure | Reject mismatched operation/artifact digest |
| Rejected architecture/content/publication | No dependent writes; preserve already confirmed writes accurately |
| Spec switches in another browser | The conversation remains bound to its original destination |
| Concurrent source edit | Stale proposal fails safely; reread and obtain review for changed operations |
| Lost response after save | Reconcile exact receipt; no duplicate imports/instances and no unnecessary new model phase |
| Restart while waiting or submitting | Resume only through existing explicit controls; retain request/artifact identity and spending records |
| Activity/tool failure or missing credentials | Visible incomplete/failed state; no false saved/qualified result |
| Cancellation | Stop future actions; report any already committed source honestly |

Fix the shared cause, add regression protection, rerun the original UI request
or resume path, and verify durable source. Use the current configured model;
do not select a new model or hide overruns by changing its test allowances.

## 7. Release, update, and storage checks

### Immutable initial release

Run release validation over the exact six Phase 1 seeds, nineteen Phase 2
leaves/profiles, three Phase 3 composites, and two Phase 4 Components: thirty
logical releases before any defect-fix replacement versions. Verify requirements,
source/provenance, tested presets, generic target limits, dependency digests,
licence, stale derived content, and evidence consistency.

A required unavailable check blocks that release's qualification. Draft/model
entries may remain labelled candidates but cannot count toward the required
thirty. New implementation bytes require a new version. Interface, reset,
latency, memory collision, access-policy, or legal-parameter breaks require a
behavioural compatibility review and major version where correct use can break.
Do not infer compatibility from equal port lists.

### Controlled upgrades and restore

Expose explicit update preparation through the Assistant's guarded edit flow
and the shared service command. Show exact old/new pins, parameter and contract
differences, affected instances, and local-fork conflicts. No background updates.
Accept the exact preview with the existing approval/revision policy. Revalidate
connections, nested topology, CSR derivation, and evidence before saving.

Keep an immutable pre-upgrade source revision or validated backup. Restore its
complete source, dependency pins, and provenance through the same guarded
flow. Do not describe an in-memory Circuit undo stack as durable recovery.
Test cancelled/stale upgrades, a fork conflict, one compatible upgrade, one
incompatible interface rejected before save, and successful full restore.
Create a defect-fix test release through its original authoring method; do not
rewrite an immutable release to make this case work.

### Directory and single-file storage conformance

Keep the directory provider as authoring source. Add a single-file `.spec`
distribution provider that stores exact release payloads as declared assets and
a registered catalogue annotation. Preserve original release bytes/digests;
the outer bundle has its own digest. Do not add unsupported ZIP top-level paths
or arbitrary keys to the strict manifest.

The same conformance suite must verify equal search meaning, normalized
contracts, exact release references, dependency graphs, and import results
through both providers. Test overlapping dependency closures, name collisions,
corrupt/truncated fetches, unsupported schemas, and missing payloads.

Move the directory tree, rebuild its index, export/import the bundle, and reopen
previously imported Specs with providers unavailable. Existing Specs and
Activity snapshots must work offline. Storage movement cannot require hardware
source edits. Keep source mappings, constraints, licence assets, structured
CSR source, and all implementation inputs in the imported closure.

### Hosted and target-specific follow-on boundary

Document the provider transport mapping and use a local test double for timeout,
integrity, stale-catalogue, and offline-cache cases. Do not deploy a production
service. Authentication, access rules, storage product, and hosting selection
need a concrete later deployment request.

The required release is qualified only for generic digital behaviour. Preserve
the binding contract and deterministic-selection checks. Actual FPGA/ASIC cell
mapping, third-party RTL adaptation, async FIFO, full AXI, advanced arithmetic,
crypto, and other retained families need separately scoped follow-on plans and
the corresponding tools/evidence. They are not hidden incomplete requirements
of these four phases.

## 8. Exit gate and handoff

Both new Components are authored through live Assistant flows with exact applied
receipts, qualified, and published. The thirty-release initial catalogue passes
its declared matrix. Directory/bundle storage, explicit updates, restore, and
offline use preserve source authority. Every method has real acceptance evidence
and in-scope confirmed defects have fixes plus regression protection.

Run `fast`, `integration --scope spec,circuit,assistant,verification,activities`,
and `regression`. Add `shared` for shared changes and all consumers. Missing
required live-model credentials or toolchains make the relevant gate incomplete.
All scratch source, traces, output, and logs stay in new `TEMP_library_<run>/`
paths. Never expose secrets in flow evidence.

Record:

- Implementation and flow/schema versions; configured model identity.
- Exact user requests, reviews, flow executions, applied receipts, and traces.
- Two new release references/digests and the final thirty-release catalogue.
- Live and deterministic case outcomes, including failed attempts and recovery.
- Highest-level RTL/functional/synthesis evidence and limitations.
- Defect register: cause, fix, regression checks, and original-path rerun.
- Upgrade/restore, provider migration, and offline evidence.
- Executed software profiles, outcomes, and evidence directory.
- Deferred follow-on list with a concrete consuming Design and required evidence.
- Exit gate: not evaluated.

# Verification Planner remaining requirements

These are unimplemented or partially implemented design requirements, not
current service guarantees. [Architecture](verification-planner-architecture.md)
and the three layer references describe the delivered foundation. Keep only
remaining work here; move proven behavior to those references when implemented.

## Shared service and browser hardening

- Complete strict request validation, unknown-field/version rejection, payload
  and archive limits at actual admission boundaries, If-Match/body agreement,
  consistent diagnostic actions and deployment-derived actor identity.
- Preserve rejected/stale drafts, compare saved and proposed fields, preview
  fresh rebases, and add an explicit upstream-checkpoint update wizard.
  Rebase changes must remain drafts until reviewed; historical checkpoints and
  evidence stay immutable. Do not reuse evidence across changed definitions
  implicitly.
- Add bounded SSE retention/replay and `resync_required`, hidden-tab-aware
  fallback polling, query pagination and filtered included/excluded counts.
  Measure the proposed million-observation and large-plan targets before
  advertising them.
- Verify standalone browser authoring across all layers, keyboard navigation,
  focus trapping, empty/error states, artifact inspection and persistent drafts.
  Existing API acceptance tests do not prove these browser behaviors.
- Implement consistent database/blob backup and restore verification. Define
  import integrity checks and failure atomicity for archives and artifact jobs.
- Register optional service discovery/combined launch and an Assistant owner
  adapter only after its operation schema, context, revision, preview/commit and
  approval contracts exist. The current Assistant supports Spec/Circuit only.

## Layer 1 and reusable design checklists

Validate scope/occurrence restrictions and all archive/reuse/rebind edge cases
against imported source. Preserve verbatim citations/digests and explicit source
ambiguity issues. Extend fixtures beyond synchronous FIFO and composed two-FIFO
examples where needed.

Useful domain checklist topics from the original prototype are port boundaries,
reset behavior, functional modes, protocol compliance, error injection,
timing/sequencing, cross-port interactions, structural connectivity and special
bit patterns. These are authoring topics, not enforced canonical coverage
families or a claim that ALU/UART/CDC/crossbar plans are currently bundled.

## Coverage and evidence

Finish family-specific acceptance and producer/result compatibility checks,
stable definition hashes, evidence profile/baseline isolation and denominator
rules. A coverage hit without evaluated checking evidence must not close an
intent. Preserve unresolved failures across retries; require reviewed invalid-run
or superseded-after-fix dispositions. Waivers require rationale, owner,
checkpoint/profile scope and expiry and cannot suppress known failures.

Property evidence must expose proof bound, assumptions, vacuity and reachability;
bounded proof must not claim unbounded correctness. Structural and mutation
coverage need compatible native adapters, eligible denominators and explicit
unsupported states. Missing collectors are not zero-percent measurements.
Selected crosses must have explicit tuple/exclusion previews and enforced bin
limits; pairwise generation needs a specified algorithm before adoption.

Complete stable gap/action mappings, cross-profile aggregation, eligible-run
merging, stale/unbound/weak evidence reporting and full external producer
registration. Snapshot, intent, objective, implementation and DUT/tool changes
must create new provenance rather than rewriting historical closure.

## Complete portable Test IR validation and semantics

- Replace open dictionaries with versioned typed expression/step unions and
  recursive validation. Reject unknown/no-op constructs before plugin lowering.
- Check bool/uint/sint/integer/enum/vector widths and ranges (vectors 1–4096),
  explicit casts, signedness, checked versus wrapping arithmetic, slices and
  concatenation. Previous samples need defined initialization.
- Define finite typed value streams with exhaustion errors. Random stimulus is
  a later extension requiring algorithm/version, seed and portability rules.
- Preserve named drive/sample/edge/settle phases, clocks in femtoseconds and
  explicit reset domains. Validate bounded wait timeouts, repeat counts,
  conditional branches and declared extension effects recursively.
- Validate sample initialization, check reachability/evaluation counts, parallel
  disjoint signal/model/local-state ownership, reference-model queue bounds and
  oracle provenance. Reject identical expected/actual checks but retain human
  oracle review; syntax alone cannot prove meaningful correctness.
- Implement invariant, fixed-delay implication, bounded response, stability and
  reachability property capability checks. Unsupported multiclock/four-state
  behavior must be rejected by executable backends.
- Preserve failure-and-continue versus explicit abort semantics, best-effort
  teardown, unexecuted-check `not_evaluated` and non-successful timeout outcomes.
  Enforce edge/step/runtime limits in whichever external runtime executes IR.

## Generation and external backends

Add durable queued/running/terminal generation with actual cooperative
cancellation, timeout and restart reconciliation. Define transactional artifact
publication so partially persisted outputs cannot be mistaken for success.
Trusted plugin execution requires explicit isolation and configuration/version
policy; an in-memory output writer is insufficient process isolation.

Later backends may target cocotb, UVM or formal tools. Each must preserve timing,
types, oracles, observation IDs and producer/result mappings or reject an
unsupported capability. Test backend substitution without changing intent or
coverage meaning. Existing external testbenches need reviewed artifact/repository
revision and observation maps before their results count. Automated simulator
execution and autonomous gap closure remain separate, later work.

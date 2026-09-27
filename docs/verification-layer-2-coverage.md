# Layer 2 — Coverage & Evidence

Status: implementation plan. Shared UX/API rules are in [the overall contract](verification-service-overall.md).
Consumes [Layer 1](verification-layer-1-test-plan.md) intent; supplies objectives to [Layer 3](verification-layer-3-implementation.md).

## 1. Purpose and ownership

Layer 2 answers two different questions:

1. **Planning coverage:** Does every required behavior have a sufficient, explicit plan for evidence?
2. **Achieved evidence:** Has compatible, valid evidence met that plan?

An objective defines what evidence is needed, without committing to a simulator or coding language. A result records what an external verification activity observed. A link between them must be explicit and versioned. An objective being mapped, a test being generated, and a test passing are three separate facts.

This layer owns objectives, selected scenario dimensions/bins, intent-to-objective policies, normalized result import, compatibility, gap classification, exceptions and reports. It never generates HDL/Python, chooses RTL signal paths, or changes Layer 1 expected behavior.

The service can find missing declared mappings, missing declared bins, stale references and absent evidence. It cannot prove that humans captured every implicit requirement or meaningful scenario in prose. Every “no gaps” message must state its reviewed scope and declared model.

## 2. Two dimensions of coverage

### 2.1 Scope dimension

Use Layer 1 occurrence scopes: component, interface, subsystem/design. An objective has one owning scope plus optional participant scopes. An intent-objective edge is valid only when the objective's declared scope/participants cover the intent's occurrence. A shared component definition does not grant evidence to every instance.

### 2.2 Evidence dimension

| Family | Question | Representation |
| --- | --- | --- |
| Requirement mapping | Were reviewed requirements assigned intents? | Derived Layer 1 relationship metric |
| Intent mapping | Does each intent have a reviewed evidence policy? | Explicit policy/edge validity |
| Scenario | Were selected preconditions/events exercised? | Enumerated bins and hit counts |
| Functional | Were meaningful observed values/transitions/crosses reached? | Enumerated bins and hit counts |
| Correctness | Did the expected behavior hold when checked? | Check evaluations and pass/fail outcomes |
| Property | Was the declared property established under the recorded assumptions? | Proof/bounded-check/reachability/vacuity metadata |
| Structural | Which implementation elements were exercised? | Separate line/branch/toggle/FSM/expression metrics |
| Mutation | Did checkers detect the selected defects? | Mutant classifications and detection counts |

Integration is a scope/participant characteristic, not a competing evidence family. A design integration intent can need scenario, functional and correctness evidence simultaneously.

Initial foundation implements scenario, functional, correctness, property and structural normalized contracts. Mutation records/denominators are specified for extension compatibility, but mutation generation and native tool adapters are deferred. Unsupported family collectors appear as **No compatible collector configured**, never as zero coverage.

Do not average functional hits, proof outcomes and line coverage into a single percentage. Structural coverage does not satisfy a behavioral intent unless it accompanies a separately sufficient correctness/scenario policy; it is otherwise a supplemental diagnostic.

## 3. Data model

### 3.1 Coverage objective

| Field | Rule |
| --- | --- |
| `id`, `key`, common metadata | Shared immutable identity rules; display key `OBJ-n` |
| `title`, `description` | Human-readable evidence goal, independent of test code |
| `scope_id`, `participant_scope_ids` | Valid Layer 1 occurrence references |
| `family` | `scenario`, `functional`, `correctness`, `property`, `structural`, `mutation` |
| `semantic_definition` | Plain-language meaning of measurement/check and relevant timing |
| `dimension_ids` | Explicit selected dimensions; empty for non-bin objectives |
| `bins` | Ordered `CoverageBin` records for scenario/functional objectives |
| `acceptance` | Typed family-specific criterion below |
| `rationale` | Why these measurements address the intended behavior |
| `authoring_state` | `draft` or `ready`; readiness requires complete definition |
| `supplemental` | False by default; true means informative and cannot independently close intent |

An objective may support several intents. An intent may need several objectives. Deleting or changing an objective never silently edits the linked intent's policy.

### 3.2 Dimensions, bins and exclusions

`CoverageDimension`: ID, title, semantic description, scope, type (`enum`, `integer_range`, `boolean`), unit where applicable, and explicit value classes. Integer classes use inclusive bounds; symbolic bounds such as DEPTH must resolve against the pinned scope parameters before review. Overlapping classes require explicit `allow_overlap=true` and a rationale; otherwise validation fails.

`CoverageBin`: stable ID within objective, title, dimension-class assignments, optional transition description, `required_hits` positive integer default 1, status (`required`, `excluded`), and exclusion ID if excluded. Membership predicates are semantic classifications in Layer 2; executable expressions/bindings live in Layer 3.

Users select **Add bin** or **Add selected cross**. Cross preview shows dimensions, product size, included tuples, and exclusions. No automatic full Cartesian product in the normal workflow. Explicit crosses can generate up to 1,000 bins in one action and 100,000 per plan; above that require narrowing the selection, not an invisible truncated cross. Pairwise generation is deferred rather than leaving its algorithm undefined.

`Exclusion`: record ID, exact objective/bin IDs, reason kind (`not_applicable`, `unreachable`, `out_of_scope`), rationale, optional supporting evidence IDs, reviewer/time, and pinned coverage checkpoint. Exclusions first exist as draft proposals; become effective only in a reviewed Coverage checkpoint. Claimed unreachability needs supporting proof or a documented engineering justification; absence of hits is not a justification. Reports retain excluded count and reason alongside raw and effective denominators.

### 3.3 Acceptance criteria by family

| Family | Required acceptance fields | Satisfied only when |
| --- | --- | --- |
| Scenario / functional | Per-bin required hits | Every required bin reaches threshold with eligible observations |
| Correctness | `minimum_evaluations` ≥1; semantic check description | At least that many evaluations; every required eligible attempt passes; no unresolved fail/error/unknown |
| Property | `claim=unbounded` or `bounded`, bound for bounded, assumption-set identifier, reachability obligations, vacuity requirement | Matching claim established with valid assumptions and all required quality evidence |
| Structural | Metric kind, explicit target elements, threshold in basis points 0–10000, optional exclusions | Compatible hit element set meets threshold; no aggregate mixing with other metric kinds |
| Mutation | Versioned mutant set, minimum detection ratio, exclusions | Declared relevant mutants classified and kill target met; unknown/timeouts do not count killed |

Zero nonexcluded bins/elements/mutants produces **N/A** and a review blocker for an objective used in a required policy. It must not count as satisfied by an empty “all” operation. Scenario/functional coverage shows integer numerator/denominator; correctness shows evaluated/passed/failed counts; property shows claim/result and bound rather than a fake percentage.

### 3.4 Intent evidence policy and mapping edges

Each active intent has exactly one `IntentEvidencePolicy` per Coverage checkpoint. Fields: intent ID, pinned intent semantic hash, `branches[]`, and rationale. A branch has ID, title, and nonempty ordered objective IDs. All objectives in one branch must be satisfied; any branch can provide a successful evidence path. This represents explicit alternatives such as “simulation with checking and scenario hits” or “formal proof with reachability.” Nested arbitrary Boolean expressions are not supported initially.

Every intent/objective edge records `justification`: what part of the intent that objective demonstrates. The same objective cannot appear twice in one branch. Every branch must include either a correctness objective or a property objective sufficient for the intent; scenario, functional, structural and mutation objectives alone cannot close it. Supplemental objectives appear separately outside closure branches.

Default policy builder starts with **All required objectives** containing placeholders **Behavior checked** and **Relevant scenario exercised**. These are UI prompts, not saved fake objectives. Users can define a property branch instead. The editor must explain AND/OR in natural language: **All of these**, **Or this alternative**.

An explicit failed correctness/property observation on any linked required or alternative branch prevents overall satisfaction until resolved, even if another branch passes. A contradiction is evidence to investigate; the user cannot hide it simply by selecting the passing method. Supplemental coverage misses do not block closure; a supplemental correctness failure still raises an unresolved-failure blocker.

### 3.5 Reviewed Coverage checkpoint

`CoverageCheckpoint` contains complete objectives/dimensions/bins, policies and mapping edges, approved exclusions, exact Plan checkpoint ID/hash, source snapshot, review metadata, and content hash. It contains no imported results. Review checks mappings/definitions, not achievement.

Layer 2 working drafts may reference a working intent revision while authoring. **Review coverage** must select an existing Plan checkpoint, reconcile every reference to that immutable baseline, and include exactly its active intents. Draft links to newer working intents appear separately as **Outside selected baseline** and cannot leak into the checkpoint.

### 3.6 Evaluation profile and campaign

Evidence never means “all historical runs.” An explicit campaign defines the population used for current status.

`EvaluationProfile`: immutable ID/digest, display name, Coverage checkpoint ID, source snapshot/hash, DUT source digest, root occurrence, resolved parameters, clock/reset configuration, and an explicit set of allowed realization descriptors. Each descriptor pins a producer manifest, tool identity/version, build artifact/options digest, and assumption-set digest where applicable. Simulation seed belongs to an attempt, not profile identity. Plugin generation version and recipe identity are recorded on each evidence producer.

A profile represents one DUT/parameter configuration and can contain both a simulation and a formal realization, permitting the policy's alternative methods to be evaluated for the same configuration. Tool-specific compiled artifact digests live in those realization descriptors; they need not equal each other, but must resolve to the same declared DUT source/configuration. An incoming run must match one complete descriptor. Adding or changing a producer/tool/assumption descriptor creates a new profile and requires an explicit new campaign; no mutable allowed-tool wildcard.

`EvidenceCampaign`: ID, title, selected Coverage checkpoint, required profile IDs, included run IDs, immutable purpose (`verification` by default, or `fixture`), state (`open`, `frozen`), and baseline membership sequence. A campaign must list profiles explicitly, even if only one. It is empty initially and never appears satisfied. Changing profile configuration creates a new profile. Changing the reviewed coverage baseline creates a new campaign; no silent evidence carryover. Fixture campaigns permit explicitly synthetic evidence and display **Synthetic fixture — not verification evidence** in every view/export. Synthetic results are rejected for verification campaign membership. Frozen campaigns reject membership/disposition/waiver changes; create a new campaign to continue.

Profiles represent configurations the user needs verified. Default each intent applies to every campaign profile in which its scope exists. An explicit profile applicability exclusion requires a reviewed rationale; it remains visible. A profile where scope resolution fails is an error, not auto-excluded.

Campaign membership changes and run dispositions use their own `campaign_revision` with If-Match, avoiding conflicts with authoring revisions. Importing a run does not auto-enroll it in an unrelated campaign. Import UI defaults to the selected matching open campaign and displays that choice.

### 3.7 Evidence and results

`EvidenceRun` fields:

- ID; external producer run ID and attempt ID; import ID/time; start/end timestamps; producer kind (`generated`, `external`); required `synthetic` boolean; profile ID; coverage checkpoint ID.
- Immutable producer manifest digest (Layer 3), recipe/implementation checkpoint when generated; DUT/source/configuration hashes; tool/version; seed if used.
- Run status `completed`, `failed`, `error`, `cancelled`, `incomplete`; raw artifact digests; parser adapter ID/version; validation diagnostics.
- Trust label `imported_local` or `registered_pipeline`; labels describe origin, not independent verification of tool truth.

`Observation` fields: run ID, producer-local observation ID, objective ID/definition hash, scope ID, optional bin ID, family, outcome, evaluation count/hit count or structural element set, sampling/checkpoint interval if relevant, correctness association ID for scenario evidence, property claim/bound/assumptions/reachability/vacuity fields as relevant, artifact anchors, diagnostic message.

Counts must be nonnegative integers; IDs resolve exactly. Outcome enum is family-specific: check `pass/fail/not_evaluated/error`; property `proven/bounded_pass/counterexample/unknown/timeout/error`; reachability `reached/unreachable/unknown`; mutation `killed/survived/equivalent/invalid/unknown`. Unknown fields/results never default to pass.

An external tool run without an approved producer-to-objective manifest is retained as **Unbound results** and cannot close anything. Users bind external observation keys in Layer 3 through the external-implementation mapping UI, then reprocess the saved report. JUnit-style test success alone provides test-level status, not functional bins or per-intent check evaluations.

## 4. Status computation and denominators

### 4.1 Separate status dimensions

| Dimension | Values | Meaning |
| --- | --- | --- |
| Authoring | Draft / Ready / Changed since review | Objective/policy definitions |
| Mapping | No policy / Incomplete / Mapped / Invalid | Traceability of intent to evidence plan |
| Implementation | Unbound / Partial / Bound / Unsupported | Layer 3 ability to produce declared observations |
| Achievement | Not evaluated / Open / Satisfied / Failed / Blocked / Waived | Evidence against selected campaign/profile |
| Freshness | Current / Stale / Incompatible | Provenance against selected baseline |

Do not compress these into one mutable status field. Derived views return reason codes and references so UI and API callers receive identical explanations.

### 4.2 Deterministic evaluation order

For each intent in the selected Plan/Coverage checkpoint and each required applicable profile:

1. Validate policy, mappings and manifest/objective compatibility. Missing definitions/bindings yield branch-specific blockers; they cannot be made satisfied by evidence with guessed IDs. An unavailable alternative does not block a different complete branch; unresolved behavioral failures still override all branches.
2. Select campaign runs explicitly included for that profile. Disposition rules below determine eligible attempts.
3. Validate observation provenance against exact objective, source, DUT, config and producer identities. Exclude incompatible observations from achievement; list them separately.
4. If an unresolved current failure/counterexample exists for a linked behavioral check, status is **Failed**. This takes precedence over a waiver or passing alternative.
5. If required tool outcomes are error/unknown/timeout/incomplete and no sufficient eligible evidence path exists, status is **Blocked** with reason. A missing run is **Not evaluated**, not a tool error.
6. Evaluate each objective and branch. At least one complete branch with no failure blocker yields **Satisfied**.
7. If no branch is satisfied and a valid intent waiver applies, show **Waived**, with remaining gaps preserved.
8. Otherwise show **Open** if there is partial evidence, or **Not evaluated** if none. A compatible historic result outside the current campaign remains history and does not affect current status.

Across required profiles an intent is Satisfied only if every applicable profile is satisfied. Otherwise propagate Failed, then Blocked, then Open/Not evaluated. Mixed satisfied+waived profiles display **Waived in part** and never count as fully satisfied. Report profile detail on click.

Mapping completeness is independent: all required intents have valid policies and no missing referenced objectives. Implementation holes do not reduce mapping percentage; they have their own count. A reviewed Coverage checkpoint can legitimately have zero implementations and zero evidence.

### 4.3 Aggregation rules

Let `R` be verifiable requirements in the Plan checkpoint, `I` active intents, `M` intents with valid policies, `S` fully satisfied intents, `W` fully/partly waived intents, and `B` required bins in a selected objective.

- Requirement mapping = requirements in R with ≥1 valid active intent / |R|. Requirement satisfaction requires all its linked intents to be satisfied; any waived one is separately reported.
- Intent mapping = |M| / |I|; intent satisfaction = |S| / |I|. Waivers stay in the denominator and are displayed as their own count. Never claim `(S+W)/I` is “verified.”
- Objective bins = required bins reaching their own hit threshold / |B|. Show excluded bins separately and raw total. Do not sum hit counts from duplicated reports.
- Scope rollups union intent IDs, objective IDs and bin IDs by identity. Do not average child percentages or double-count objectives linked to several intents.
- A definition-level view may group occurrences but shows occurrence counts; one passing ingress result cannot count for egress.
- Filters affect visible rows and an explicitly labeled **Filtered view** summary. A persistent **Whole baseline** summary remains available; hiding failed rows never changes baseline closure.
- No denominator → **N/A (no applicable items)**. A plan with zero intents cannot pass plan or coverage review.

### 4.4 Runs, retries and merging

- Import idempotency key is `(producer_id, external_run_id, attempt_id)` plus canonical content digest. Exact duplicate returns original import; conflicting content with same key fails 409.
- Different attempts are distinct. A passing retry does not erase an earlier failure in the same campaign. **Resolve run** requires a disposition `invalid_tool_run` or `superseded_after_fix`, reason, reviewer label and replacement run reference when applicable. Preserve failures in history. `superseded_after_fix` with a changed DUT/profile belongs in a new campaign, not a current-profile retry.
- Campaign inclusion/exclusion is audited and report-visible. Excluding a failed run requires the same explicit disposition; simple unchecked membership cannot hide it.
- Scenario/functional hits can merge across eligible completed runs with the same profile and objective definition. Failed/incomplete-run hits remain diagnostic only. A bin hit used for behavioral closure must be associated with passing check evidence for that observation interval; stimulus occurrence alone can populate exploratory charts but cannot satisfy the default checked-scenario branch.
- Structural merge is set union of stable instrumented element IDs for the same DUT/tool/instrumentation schema, never addition/average of percentages. If only aggregate percentages are imported, show per-run measurements and **Cannot merge without element identities**.
- Counts from different parameter configurations never merge; evaluate each required profile separately. Property evidence from different assumption sets never combines into one claim, including within a profile that permits several realization descriptors.
- Property results do not merge by summing bounds. Bounded pass at 20 and 30 cycles is not a 50-cycle proof and never an unbounded proof.

### 4.5 Formal quality semantics

For an unbounded property objective, require a proof outcome explicitly labeled unbounded, exact recorded assumption set, required reachability results, and required vacuity analysis result `checked_nonvacuous`. A reported antecedent cover hit is useful evidence but is not by itself a universal non-vacuity certificate. A collector incapable of the declared quality check reports unknown/unsupported, leaving the objective blocked. Do not downgrade the policy automatically.

For a bounded objective, display the bound and time unit prominently; threshold is the declared minimum bound. A proof under stronger/different assumptions is incompatible unless a new reviewed definition/profile explicitly permits them. Counterexamples open failures linked to the property and source intent.

## 5. Gap analysis and exceptions

Gap analysis is deterministic over the selected model. Each gap has stable identity derived from baseline, record, gap kind and profile; severity, title, explanation, affected IDs, and one primary navigation action.

| Gap code | Condition | Primary action |
| --- | --- | --- |
| `source_unreviewed` | Source audit incomplete | Review source in Test Plan |
| `requirement_unmapped` | Verifiable requirement lacks intent | Add/link intent |
| `intent_policy_missing` | No policy for intent | Define evidence policy |
| `objective_incomplete` | Missing definition/bins/criterion | Edit objective |
| `checking_missing` | Branch contains coverage only | Add correctness/property objective |
| `dangling_mapping` | Referenced record absent/archived/outside baseline | Repair mapping |
| `bin_unplanned` | Required dimension tuple selected but no bin/collector | Complete objective/binding |
| `implementation_missing` | No bound producer for objective | Open Implementation |
| `backend_unsupported` | Configured backend cannot realize required feature | Select/add compatible plugin |
| `evidence_missing` | No eligible observation | Inspect expected result/import path |
| `bin_unhit` | Required hit target not met | View bin and producer |
| `check_failed` | Unresolved behavioral failure | Open failure trace |
| `proof_inconclusive` | Bound/assumptions/vacuity/reachability insufficient | Inspect property evidence |
| `stale_evidence` | Current selection differs from evidence provenance | Compare baselines |
| `unbound_result` | Tool result key lacks approved mapping | Bind external result |
| `weak_check_evidence` | Bin exists without evaluations of its behavior | Inspect checking relationship |

Users may add a human explanation/classification to a gap, but cannot mark a computed gap “resolved” manually. It disappears only when the model/evidence condition changes or becomes explicitly waived/excluded. Notes persist in history.

An `IntentWaiver` specifies intent ID, profile IDs, Coverage checkpoint, reason, owner/reviewer, required UTC expiration timestamp, optional milestone display label, and optional supporting evidence. It is an explicit acceptance of incomplete verification, not passing evidence. Initial local review can be performed by the author. Expired waivers become open gaps automatically at evaluation time. A waiver cannot suppress an unresolved known behavioral failure; resolving that failure requires the run disposition/change process.

## 6. UI specification

### 6.1 Coverage matrix

Default workspace is **Matrix**. Secondary views: **Gaps**, **Results**, **Trace**. Retain the common left hierarchy and right details panel.

```text
Coverage & Evidence    Baseline C1 ▾   Campaign FIFO smoke ▾
12/12 intents mapped    8/12 satisfied    1 failed    0 waived

Intent                    Scenario  Functional  Checking  Property  State
Full write: occupancy     1/1       1/1         Failed    —         Failed
Full write: data intact    0/1       —           Missing   —         Open
Read while empty          1/1       —           Passed    —         Satisfied
Ordering across wrap      1/1       1/1         Passed    Unknown   Blocked

[Add objective] [Map selected intents] [Review coverage] [Import results]
```

This wireframe illustrates labels, not a golden numeric fixture; a property marked Unknown blocks only if the selected policy requires it and no sufficient alternative exists.

Rows are intents grouped by scope/section. Family columns default to scenario, functional, checking, property; structural/mutation are opt-in supplemental columns. Cells show counts/state and open the exact objective list. Many objectives in one cell appear as a compact count; clicking exposes names before details. Empty cell text is **None planned**, not a dash implying N/A. Explicit nonapplicability is **Not required** with policy rationale.

Two summary strips remain distinct: **Plan coverage** (source/requirement/intent mapping) and **Evidence** (satisfied/failed/open/blocked/waived). Do not combine them into a progress ring. The selected baseline and campaign are always visible. Without a campaign, evidence says **No campaign selected**.

### 6.2 Objective builder and mapping workflow

**Add objective** flow: choose human evidence family → title/meaning → select scope/intents → define bins or criterion → describe why it addresses each intent → save draft/ready. Defaults come from selected intent context, not source interpretation.

Bin editor is a table with name, dimension values, target hits and applicability. Cross dialog previews exact tuples. Exclusions have a reason column and review state. Large lists are paged; search can find an unhit bin by name/dimensions.

**Map selected intents** opens a two-column picker: intent list and existing objectives. Display objective semantics before linking; a checkbox cannot count as sufficient until the policy has checking/property support. Multi-intent mapping requires a separate justification per edge or explicit identical text applied to all with preview.

Right inspector for an intent contains **Evidence policy**, **Objectives**, **Results**, **Gaps**, and **Source**. Policy UI renders AND/OR branches with text, not programming syntax. **Show why this is open** produces an ordered explanation linking every missing predicate.

### 6.3 Gaps view

Default sort: unresolved failures, invalid model/binding, blocking proof/tool issues, missing coverage/evidence, advisory notes. Within each priority use intent priority then display key. Filters include scope, family, reason, profile and responsible owner label. Show whole-baseline totals when filtering.

Each row has gap title, intent path, cause, and a direct action such as **Add checking objective** or **Inspect failed check**. The action navigates with context but does not automatically generate tests or modify intent.

### 6.4 Result import and inspection

**Import results** opens a file/API instruction dialog. File flow:

1. Select registered adapter or normalized JSON; show supported file/schema versions.
2. Upload and validate. Preview run count, known/unbound observations, baseline/profile compatibility, failures, duplicates, and raw report links.
3. Choose matching open campaign and confirm **Import N runs**. Incompatible records may be archived as historical/unbound evidence only with an explicit separate choice; they never silently count.
4. Return to import report with links to changed objectives and remaining unbound items.

Malformed counts/digests/schema reject the entire import transaction. A well-formed file with unknown external observation keys can be stored as unbound raw results; none of those unknown observations become accepted evidence. Reprocessing uses the raw digest and a new adapter/mapping revision, retaining prior normalization history and preventing duplicate eligible observations.

Results view shows run/profile/tool/status, source/DUT digest summaries, producer/adapter identity and import time. Details show raw artifact, observation table, trace to source and compatibility reasons. No report HTML executes in the application origin; download or render sanitized plain content.

### 6.5 Coverage review and evidence reports

**Review coverage** checks every intent policy against selected P1, objective completeness, valid scope edges, required checking, nonempty denominators, and acknowledged exclusions. Missing implementations/results are listed informationally and do not block the coverage-model review.

**Create evidence report** freezes a read-only report at `C1 + campaign_revision + evidence_sequence`, recording all run inclusion/disposition decisions and evaluation algorithm version. Report states: **Complete evidence**, **Incomplete evidence**, or **Complete with waivers**; unresolved failures always produce Incomplete. Complete with waivers requires all other intents satisfied and no blocking failure. These reports are engineering records, not regulatory certificates.

Reports include source/plan/coverage identities, per-scope counts, profile list, objective details, exclusions/waivers, unresolved gaps, tool outcomes, raw artifact links and reverse traces. Printed/exported reports retain the same denominators as UI/API.

## 7. API contract

Authoring operations use common revision-checked command batches:

| Operation family | Required behavior |
| --- | --- |
| `dimension.create/update/archive` | Validate scope, value classes, dependent bins |
| `objective.create/update/archive` | Typed family/acceptance payload; semantic edits reset readiness |
| `bin.add/update/remove` | Stable IDs; reject removal from reviewed historical definitions; working change requires new checkpoint |
| `policy.set` | Replace one intent's complete branch/edge structure atomically |
| `exclusion.propose/update` | Explicit targets/reason; review activates it in checkpoint |
| `coverage.rebase` | Plan checkpoint ID, preview digest, resolved relation map |

Evidence/campaign endpoints use separate revisions and do not mutate authoring content:

| Method/path under plan | Purpose |
| --- | --- |
| `GET /coverage/matrix?checkpoint=...&campaign=...` | Paged rows and separate whole/filtered summaries |
| `GET /coverage/gaps?...` | Typed deterministic gap records |
| `GET /coverage/trace?record_id=...` | Relationship list/graph, bounded depth max 3 |
| `POST /profiles` | Register immutable validated evaluation profile |
| `POST /campaigns` | Select checkpoint/profiles; starts empty |
| `POST /campaigns/:id/commands` | Revision-checked inclusion/disposition/waiver/freeze operations |
| `POST /result-imports` | Stage normalized JSON or adapter file; returns preview ID/digest |
| `POST /result-imports/:id/commit` | Idempotent import, exact preview digest, optional campaign and campaign revision |
| `POST /result-imports/:id/reprocess` | New registered adapter/mapping revision; preview, then commit |
| `GET /runs` and `/runs/:id/observations` | Paged immutable evidence |
| `POST /evidence-reports` | Freeze computed report with exact selected campaign/evidence revision |

Campaign command types: `run.include`, `run.resolve`, `run.exclude`, `waiver.create`, `waiver.revoke`, `campaign.freeze`. Payload includes base campaign revision and request ID; same retry/conflict semantics as authoring. New result import plus campaign enrollment is atomic; stale campaign precondition rejects the commit without partial membership.

Normalized result schema `verification.results.v1` contains `producer`, `run`, `profile_id`, `producer_manifest_digest`, `observations[]`, and `artifacts[]`. JSON schema must be published so test scripts can construct fixtures without importing internal service modules. All objective and bin IDs come from the producer manifest; the adapter cannot invent new objectives while importing.

## 8. Worked FIFO coverage slice

Use the precise FIFO semantics from Layer 1. For intent **Full write preserves occupancy**:

| Record | Definition |
| --- | --- |
| Scenario objective S | Observe pre-edge full, reset inactive, wr_en=1, rd_en=0; required bin `full_write_no_read`, target 1 |
| Correctness objective K | In that event, post-edge count remains DEPTH and full stays asserted; minimum evaluations 1 |
| Default policy | All of S and K |
| Optional later property P | Under reviewed reset/clock assumptions, that event always preserves count/full; unbounded, with reachability/vacuity requirements |
| Alternative policy after review | (S AND K) OR P |

Correctness of queued data belongs to a separate intent/objective, requiring subsequent reads against the accepted-word sequence. A count/full check does not satisfy it. Structural line coverage of the write branch cannot substitute for either.

Golden evidence progression for the one-intent slice:

| Imported state | Mapped | Scenario | Correctness | Intent |
| --- | --- | --- | --- | --- |
| No results | 1/1 | 0/1 | Not evaluated | Not evaluated |
| Hit with no associated behavioral evaluation | 1/1 | Exploratory hit only | Not evaluated | Open |
| Completed run, hit and evaluated check pass | 1/1 | 1/1 eligible | Pass, 1 evaluation | Satisfied |
| Additional included run with failed check | 1/1 | Prior hit retained | Unresolved fail | Failed |
| Repeat identical failed import | 1/1 | Unchanged | Unchanged, no double count | Failed |
| Results from changed DUT digest | 1/1 | No change to current campaign | Incompatible/history | Prior current state preserved |

Full fixture: every one of the 12 intents receives at least one scenario+correctness branch (two objectives per intent, 24 total). Use one required bin per scenario objective for the baseline fixture; more detailed boundary dimensions are additional explicit tests. API fixture stages create 8 satisfied, 1 failed, 2 not evaluated and 1 blocked intents, with zero waivers: total 12. Use a campaign with `purpose=fixture` and explicitly synthetic reports; freeze that exact golden population and assert summary counts. Two-FIFO fixture duplicates occurrence-specific objectives for 24 local intents and adds 8 objectives for 4 integration intents, giving 56 objectives for 28 intents; component results alone leave all four integration intents not evaluated.

Create intents in the following order for deterministic fixture keys. Import a separate run for each row with evidence so that a failed run cannot invalidate unrelated passing rows through the failed-run eligibility rule.

| Fixture key | Intent | Golden evidence state |
| --- | --- | --- |
| INT-1 | Reset clears queue | Completed, scenario hit and check pass |
| INT-2 | Reset overrides simultaneous requests | Completed, scenario hit and check pass |
| INT-3 | Write appends one word | Completed, scenario hit and check pass |
| INT-4 | Read returns oldest word | Completed, scenario hit and check pass |
| INT-5 | Full write preserves occupancy | Failed, explicit behavioral mismatch |
| INT-6 | Full write preserves queued data | Completed, scenario hit and check pass |
| INT-7 | Empty read preserves queue/output | Completed, scenario hit and check pass |
| INT-8 | Mid-occupancy accepts both requests | Completed, scenario hit and check pass |
| INT-9 | Full accepts read only | No run |
| INT-10 | Empty accepts write only | Completed, scenario hit and check pass |
| INT-11 | Ordering survives wrap-around | No run |
| INT-12 | Full/empty agree with occupancy | Tool error; no valid check evaluation |

Keys are allocated by the normal API; the script asserts them only within a freshly created plan. It uses returned immutable IDs for every relationship.

## 9. Acceptance requirements

| ID | Scenario | Required result |
| --- | --- | --- |
| L2-01 | 12 intents, 11 policies | Mapping 11/12; missing-policy gap links to exact intent |
| L2-02 | Every intent mapped to scenario-only objectives | Review blocked by checking_missing for each; hits cannot close intent |
| L2-03 | One objective linked to two intents | Objective rollup counted once; each policy evaluated separately |
| L2-04 | Full FIFO golden campaign | 8 satisfied, 1 failed, 2 not evaluated, 1 blocked; 12 total regardless of filters |
| L2-05 | Bin hit with zero check evaluations | Exploratory reachability shown; no default branch closure |
| L2-06 | Completed pass then failing retry | Intent Failed; no latest-pass/any-pass shortcut |
| L2-07 | Duplicate import / conflicting same external run identity | Replay original / reject 409; no double counting |
| L2-08 | Result has wrong DUT/config/source/objective hash | Explicit incompatibility; current counts unchanged |
| L2-09 | Full exclusion or no denominator | N/A, visible exclusions; required objective review blocked |
| L2-10 | Unbounded objective receives bounded pass or unknown vacuity | Blocked/inconclusive, never Proven |
| L2-11 | OR policy has passing simulation and formal counterexample | Failed until counterexample disposition is reviewed |
| L2-12 | Structural reports have differing denominators or no element IDs | No merge; per-run display with explanation |
| L2-13 | One profile passes, another required profile absent | Intent not fully satisfied; profiles remain separate |
| L2-14 | Waiver expires or current failure arrives | Recompute open/failed; never silently retain closure |
| L2-15 | User filters out failed rows | Filtered count changes; whole-baseline failure and report unchanged |
| L2-16 | Imported test-level pass has no objective manifest | Unbound results; no intent achievement |
| L2-17 | Two-FIFO component evidence only | Integration gaps remain; ingress evidence not reused for egress |
| L2-18 | Upstream source/intent policy changes | Old C1 report reproducible; new baseline/campaign starts without automatic reuse |
| L2-19 | Malformed count/unknown outcome mid-import | Whole accepted-evidence transaction rejected; staged raw file may remain diagnostic |
| L2-20 | Script constructs all objectives/imports through public API | UI matrix/gaps/reports equal API projections after restart |

Implement the evaluation engine as deterministic domain logic with table-driven cases for every status precedence, denominator, retry and compatibility rule. Browser tests must cover mapping, import preview, click-to-gap navigation, and readable explanations, not only colored badges.

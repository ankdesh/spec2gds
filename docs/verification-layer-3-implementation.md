# Layer 3 — Implementation, test IR and backend plugins

Status: implementation plan. Read [the overall service contract](verification-service-overall.md), [Test Plan](verification-layer-1-test-plan.md), and [Coverage & Evidence](verification-layer-2-coverage.md) first.

## 1. Purpose and scope

Layer 3 answers **How will we produce the evidence specified in Layer 2?** It is the only layer that contains test steps, signal bindings, reference models, executable property expressions, backend settings, generated files and external-result mappings.

Initial delivery must implement the recipe editor, typed test intermediate representation (IR), validation, plugin registry/contract, deterministic reference plugin, generated-bundle review, and normalized external-result mapping. Production Cocotb, UVM and formal backends are later plugins using that contract. Do not present a stub or emitted TODO as a working verification backend.

No model is required to interpret a prose intent. The user explicitly constructs stimulus, observations, checks and properties. A future assistant may construct the same records through the API, subject to the same validation/review boundary.

Test recipes may reference several intents/objectives. Several recipes may jointly produce evidence for one objective. Changing backend must preserve intent and coverage IDs; it must never rewrite upstream behavior to fit a tool's limitations.

## 2. User-facing model and workflow

### 2.1 Default workspace

```text
Implementation         Coverage baseline C1 ▾
Bindings: 10/10 ready   Recipes: 3 ready / 1 draft   Backends: 1 enabled

Recipe                    Intents         Backend       Readiness
Full-write boundary       INT-5, INT-6     Reference     Ready
Queue wrap-around         INT-11          Unselected    Needs backend
FIFO safety properties    INT-5, INT-12    Formal        Not installed

[New recipe] [Target bindings] [Backends] [Review implementation]

Selected recipe: Full-write boundary
  Purpose → Setup → Steps / Properties → Checks → Coverage → Preview
```

The left hierarchy remains Layer 1 hierarchy. Selecting an intent filters recipes, objectives and missing bindings. A recipe list is central, not a replacement hierarchy of UVM classes. The right inspector shows purpose, source links, objective links, validation and artifact history.

### 2.2 Recipe authoring flow

1. **New recipe**: choose one or more related objectives from the selected Coverage checkpoint. Show their exact intent descriptions and acceptance conditions.
2. Name the recipe; choose target occurrence(s) and simulation/property recipe kind. Choose backend now or later; authoring is permitted without installed backends.
3. **Target bindings**: map semantic ports/observations to target interfaces, define clock/reset behavior, resolve parameters and data types.
4. **Setup**: explicit input initialization, model state and reset sequence. No implicit reset assumptions.
5. **Steps** for scenario recipes, or **Properties** for formal-capable recipes. Use labeled forms and readable preview sentences.
6. **Checks**: define an oracle independent of the DUT outcome, including evaluation timing; link each check to correctness/property objectives.
7. **Coverage**: map semantic events to stable scenario/functional bin IDs; confirm association to the check evaluation that validates the behavior.
8. **Validate**: shared IR/type validation and selected-plugin capability validation. Show all blockers with links to exact controls.
9. **Review implementation** creates an immutable checkpoint for the selected set; **Generate** consumes that checkpoint and produces a new bundle for review/download.

There is no one-click “generate tests from prose.” A readable recipe can still be Draft, Unsupported, or Blocked. The application must make the missing work visible.

### 2.3 Editor presentation

Default to an ordered step list with line numbers, verbs and descriptions. Example: “Drive write request and data 0x2A before the next rising edge,” “Sample count after settling,” “Check count equals 4.” Selecting a row opens its form in the right panel. Insert, duplicate, move, disable and remove have visible buttons/menu actions. Disabling a required check creates a validation blocker; it is not a bypass.

Condition, loop and parallel blocks are visually indented. Explain timeout and completion behavior in the block heading. A **Structured IR** tab is available for advanced inspection/import/export but is not needed to build any reference recipe. Editing raw IR uses the same draft/preview/save validation as forms and cannot create hidden fields the UI cannot display.

Use a timing strip for drive/edge/sample phases with textual labels, not a waveform editor. Backend-specific settings appear under **Backend configuration**, separated from behavioral recipe content. Technical class/module names are secondary details.

## 3. Canonical records

### 3.1 Target profile and observation bindings

`TargetBindingSet` fields: ID/revision, source snapshot/root scope, DUT language/top module, immutable DUT artifact manifest/digest, resolved parameter values, clock declarations, reset declarations, named binding records, and authoring state.

Each binding: ID, semantic observation/port name, source reference where available, target kind (`input`, `output`, `internal`, `transaction`, `model_value`), target locator, type/width/signedness, clock domain, sampling phase and permissions (`drive`, `sample`). Initial core supports scalar and packed bit-vector ports; aggregate/transaction interfaces are supported through capability-declared extensions, not flattened silently.

Logical observation `queue occupancy` may bind to public `count`. If it has no direct signal, a user may map it to an explicitly authored model/derived expression with stated limitations. If the required behavior cannot be observed, report `missing_observation`; do not replace the objective with an easier one.

Bindings are typed user declarations, checked against source/RTL metadata when available. Parsing RTL declarations is an optional adapter; it cannot infer expected behavior. Missing RTL is permitted during draft authoring but blocks a runnable backend generation that requires it. The reference plugin can emit an IR-only bundle and must label that distinction.

### 3.2 Recipe

| Field | Contract |
| --- | --- |
| `id`, `key`, title/description | Shared identity rules, `RCP-n` |
| `kind` | `scenario`, `property`, `external` |
| `coverage_checkpoint_id` | Exact immutable upstream baseline |
| `intent_ids`, `objective_ids` | Nonempty explicit relationship sets |
| `target_binding_set_id` | Pinned revision before review/generation |
| `test_ir` | Structured `verification.test-ir.v1` for scenario/property; absent for external |
| `backend_configuration_id` | Optional while draft; required for generated realization |
| `evidence_bindings` | Producer observation keys → objective/bin IDs and definition hashes |
| `oracle_provenance` | Source locators, independently authored model/check description, reviewed assumptions |
| `authoring_state` | `draft`, `ready`, `unsupported`, `blocked` |

`ready` indicates the recipe is semantically complete for its selected realization. It does not mean generated, compiled, run or passed. Unsupported is a capability finding, not an invitation to drop behavior.

### 3.3 Backend configuration

Fields: ID, backend plugin ID/version/package digest, target toolchain identifier and explicit version constraints, typed configuration JSON, capability snapshot, configuration digest. No plaintext secrets in exports; reference named host credentials where required by future extensions. Profiles and generated manifests pin the resolved toolchain/configuration, not a mutable “latest” backend.

### 3.4 Implementation checkpoint and producer manifest

`ImplementationCheckpoint` freezes a selected nonempty recipe set, target bindings, backend configurations, evidence bindings, and Coverage checkpoint ID. Partial implementation coverage is allowed, with explicit counts of unimplemented objectives. An incomplete recipe cannot be included; other ready recipes can be reviewed and generated while remaining objectives are still unimplemented.

Each generated or externally registered realization has a `ProducerManifest` with schema `verification.producer.v1`, immutable identity/digest, checkpoint/recipe IDs where applicable, source/coverage/target hashes, backend and tool configuration, and an `observations` map. Each entry includes external observation key, objective definition hash, optional bin IDs, scope, family, check identity/association, and intended output field shape. This is the sole mapping authority for results; test names alone are not enough.

An external recipe records an artifact/repository revision, tool/configuration, named tests/checks and manually reviewed observation mappings. It can be reviewed/registered without generating code. This lets existing testbenches and foundation result-fixture scripts participate. External mapping cannot claim that a test-level pass measured unspecified functional bins or properties.

## 4. Test IR v1

### 4.1 Envelope and design rules

Test IR is a typed, serializable tree with stable IDs on steps/checks/properties/coverage events. It is a language-neutral representation, not arbitrary Python/SystemVerilog strings. It contains no shell commands or executable template fragments.

Top-level fields:

| Field | Content |
| --- | --- |
| `schema_version` | `verification.test-ir.v1` |
| `recipe_kind` | Scenario or property |
| `parameters` | Typed resolved values and source provenance |
| `ports` | Semantic binding references and access directions |
| `clocks`, `resets` | Explicit domain relationships and reset behavior |
| `variables` | Typed local state with defined initial values |
| `models` | Explicit portable reference-state definitions |
| `setup`, `body`, `teardown` | Structured steps for scenario recipes |
| `properties` | Structured temporal claims/assumptions for property recipes |
| `checks` | Typed expressions and objective links |
| `coverage_events` | Sampling predicates and stable objective/bin links |
| `limits` | Maximum cycles/steps, random draws and wall-time request |
| `required_capabilities` | Canonical feature set computed from content |
| `extensions` | Namespaced, schema-versioned optional data |

Every supported field has a form and readable summary. Every executable construct has specified timing, types and failure behavior. Unknown constructs or major versions fail preflight. Do not allow plugins to interpret an unknown field as an empty/no-op behavior.

### 4.2 Type system and expressions

Core scalar types: `bool`, `uint(width)`, `sint(width)`, bounded `integer(min,max)`, and declared enums. Packed vectors must have width 1–4096; values outside their declared range are errors. Four-state values are an explicit `logic_vector(width)` capability extension; the core reference contract uses two-state vectors and must reject unknown/Z inputs where they would affect checks.

Expression nodes: literal, variable reference, sampled observation reference, parameter reference, explicit cast, unary NOT/bitwise NOT/negate, arithmetic add/subtract/multiply, bitwise operations, comparisons, boolean AND/OR, conditional select, fixed-width slice/concat, and previous sampled value. No arbitrary function calls or string evaluation. Division/modulus, variable shifts and complex math are deferred extensions with declared semantics.

Operands require compatible types; no implicit signed/unsigned conversion. Arithmetic results use an explicitly declared result type; overflow requires an explicit `wrap` or `checked` arithmetic mode. Default is checked with overflow diagnostic. Slice bounds are resolved integers; concat width is the sum of inputs. Comparisons return bool; time comparisons require the same unit/domain. Previous value before first sample is invalid unless an initial value is declared.

Portable v1 stimulus uses explicit literal values or finite typed value streams supplied in the reviewed request. A stream has stable ID, element type, ordered values and cursor; requesting beyond its end is an error. This gives identical vectors across backends without choosing a hidden random algorithm. A future randomization extension must declare algorithm/version, initialization, seed and stream/distribution semantics; backend-local constrained randomization must be labeled nonportable. Random generation is not a foundation capability, and a seed metadata field alone does not imply supported random execution.

### 4.3 Timing and step semantics

Each clock has a stable ID, edge, period in integer femtoseconds, phase offset and optional source-clock binding. Each reset states active polarity, synchronous/asynchronous nature, and associated domains. First release reference fixtures are single-clock; multi-clock remains representable but executable support depends on explicit capabilities.

Scenario scheduling has named phases: **drive before edge**, **sample before edge**, **active edge**, **sample after settle**. Every check/cover references a named sampled value. A backend must preserve these phases or reject the recipe. It cannot substitute scheduling based on its language's default race behavior.

| Step | Required fields and behavior |
| --- | --- |
| `drive` | Binding→expression assignments, domain, phase; direction/type validated; assignments applied together |
| `wait_edges` | Domain/edge and positive count; advances deterministic simulation steps |
| `wait_until` | Boolean sampled condition, domain/phase, positive max edges; timeout yields error and no fabricated pass |
| `sample` | Binding/derived-expression list to named typed sample slots, domain and phase |
| `assign` | Local variable value from typed expression; no DUT write |
| `model_update` | Declared reference-model action using precomputed input values |
| `check` | Check ID and boolean expression; increments evaluations; false records failure with values and source links |
| `cover` | Objective/bin ID, predicate, and check-association reference; increments only when predicate true |
| `if` | Boolean expression, then/else step arrays; explicit branch |
| `repeat` | Resolved count 0–10000 and body; zero allowed but readiness detects required checks never evaluated |
| `parallel` | Bounded branches, `join=all`, exclusive drive ownership; no nondeterministic shared local/model writes |
| `call_extension` | Registered namespaced operation, schema version, typed arguments and declared side effects |

Global limits are mandatory even for bounded constructs: default 100,000 simulated edges, 1,000,000 evaluated steps and requested external runtime timeout 60 seconds. These are requested run-bundle constraints, not service-executed simulator jobs. Long intentional tests can use explicit higher values in reviewed recipes. Timeout cannot be treated as ordinary successful completion.

`check` defaults to record failure and continue so subsequent observations remain diagnostic; `abort_on_failure=true` terminates the test as failed. An aborted/failed run never contributes successful scenario closure evidence. Unexecuted checks remain `not_evaluated`, not passed by default. Teardown runs best effort and cannot change the primary outcome.

Parallel branches share clocks but must have disjoint driven bindings and disjoint mutable state; conflicts fail validation. Branch completion waits for all, subject to limits. There is no dynamic thread spawning, event-race winner or shared-queue concurrency in v1.

### 4.4 Reference model and oracle design

Core reference models support typed records, finite-state machines and bounded queues with explicit transitions. Queue operations are initialize, append, peek, pop, clear and length; capacity and element type are declared. Illegal operation on a full/empty model raises a recipe error unless explicitly guarded. A model is user-authored expected behavior from source, not cloned DUT code.

Each model/check stores `oracle_provenance`: source requirement locators, human explanation, and whether it is independently authored or externally supplied. Backend plugins may translate its operations; they cannot replace it with “expected = actual.” A check whose expected expression is syntactically identical to its actual observation is rejected as tautological. This guard is limited; review must still assess oracle meaning.

Custom models are versioned extensions with deterministic API and typed input/output. Arbitrary imported Python/SystemVerilog belongs to a backend-specific extension artifact with its digest and review label, not a hidden escape hatch in the portable IR. A recipe using such an extension declares reduced portability.

### 4.5 Property representation

Property recipes contain typed, clocked expressions and explicit assumption references. Initial portable templates:

- **Invariant**: at every sampled edge after declared reset release, predicate holds.
- **Implication at fixed delay**: when antecedent holds at sample n, consequent holds at n+k, k ≥ 0; reset disable/abort behavior explicit.
- **Bounded response**: antecedent implies at least one consequent at samples n+a through n+b, inclusive, 0 ≤ a ≤ b; no hidden fairness assumption.
- **Stability window**: when guard holds, selected sampled value remains equal to the entry value for an explicit number of edges.
- **Reachability cover**: named antecedent/state predicate must be reachable under the same assumptions.

An unbounded proof claim refers to establishing a property for all relevant traces; it is distinct from the property's bounded-response interval. A bounded checker reports the explored proof horizon separately. Every property has a correctness/property objective ID, exact assumption-set digest, reset semantics, observation bindings, and required reachability/vacuity checks.

No full SVA grammar in core. A formal backend declares exactly which templates, operators, clocks and reset semantics it can realize, and how it reports proof quality. It must reject unsupported temporal operators. SVA simulation assertions are an output possibility, not synonymous with formal proof.

### 4.6 Coverage event semantics

Coverage events refer to Layer 2 objective/bin IDs and definitions. Each event declares its predicate, sampling phase, semantic measurement values and optional check association. Scenario evidence intended for closure must identify the corresponding check evaluation window. A later read-drain checker may validate a scenario after its occurrence; the result writer must defer accepted association until the whole check window completes successfully.

Sample/cover/check identifiers appear in generated files and manifests. A backend can rename generated symbols but must return the stable mapping. Native coverage databases that cannot retain these IDs need an explicit sidecar map, reviewed and pinned with the generation bundle.

## 5. Plugin architecture

### 5.1 Plugin types and manifests

Use two independent extension types: **BackendPlugin** produces artifacts from IR; **ResultAdapterPlugin** parses external reports into normalized candidate observations. A package may register both, but neither requires the other. Execution runners are reserved as a future separate capability; do not embed arbitrary simulator command execution in the generator interface.

Manifest fields:

| Field | Requirement |
| --- | --- |
| `plugin_id`, `version`, `package_digest` | Stable reverse-domain ID, semantic version, installed-content digest |
| `kind` | backend or result_adapter |
| `title`, `description` | Human-readable labels |
| `contract_versions` | Supported host plugin contract major versions |
| `input_schema_versions` | Explicit test IR or result format versions |
| `capabilities` | Typed supported features, constraints and diagnostics |
| `configuration_schema` | JSON Schema with defaults, enums, labels/help, secret-reference fields |
| `artifact_roles` | Allowed output types: IR, source, manifest, report, runner instructions, etc. |
| `tool_requirements` | Declared tool/language versions for eventual execution or parsing |
| `portability` | portable / backend_specific, with extension IDs |

Capabilities enumerate recipe kinds, expression operators, types/max widths, clocks/resets, step kinds, reference models, property templates, evidence families, report formats, and whether output is executable or explanatory only. Wildcard “supports everything” is not valid. The UI renders a **Supported / Unsupported / Needs configuration** table per recipe.

Host discovers plugins from an explicit configured registration list (`module:callable`), following the Activity SDK's registry pattern. Registration validates manifests/schema versions and is atomic per plugin. Duplicate IDs/versions or import failure disable that plugin and show a diagnostic; valid plugins and plan authoring remain available. Browser/API users cannot upload and activate executable plugins.

### 5.2 Backend contract

Logical methods, specified independently of their eventual Python class syntax:

| Method | Input | Output / rule |
| --- | --- | --- |
| `describe` | No live document | Validated immutable plugin manifest |
| `validate` | Immutable GenerationRequest | Capability/configuration diagnostics; no artifacts or mutation |
| `lower` | Same request | Backend intermediate plan plus trace map and diagnostics; must preserve all requested semantics |
| `generate` | Validated lowered plan plus host output writer | Staged artifacts and GenerationResult manifest |

`GenerationRequest` schema `verification.generation-request.v1`: implementation checkpoint, recipe IR, coverage objective definitions/policies required by recipes, source/target binding projection, resolved configurations, plugin identity/digest, seed/vector data if applicable, and input digest. No mutable database handles, live editor references, model credentials, unrestricted filesystem output directory, or neighboring-service clients.

`GenerationResult`: input/plugin digests, artifact descriptors `{relative_path, role, media_type, sha256}`, stable producer manifest, source-map entries, recipe realization states (`generated`, `unsupported`, `blocked`), and diagnostics. Output source maps resolve each generated check/event to recipe step/check ID and objective/intent IDs. Batch success requires all selected recipes generated; users must explicitly select a smaller supported subset rather than receiving a partly missing suite labeled successful.

The output writer accepts relative validated paths and bytes/streams. Reject `..`, absolute paths, symlinks and conflicting output paths. Deterministic input must produce identical artifact bytes/paths/digests. Job timestamps, run IDs and host paths belong in the job record, not deterministic artifact contents.

### 5.3 Result adapter contract

`inspect(raw_artifact_manifest)` identifies supported schema/version without shell execution. `normalize(raw_artifacts, producer_manifest, profile)` returns candidate `verification.results.v1`, raw-to-normalized anchors, parser diagnostics and unknown keys. It must preserve failures/unknowns and cannot change objective definitions, policy, profile or manifest mappings. Host validates every normalized record before it becomes evidence.

Multiple adapters may inspect a file; if more than one supports it the user chooses. No unreviewed heuristic mapping of a test name to an intent title. Adapter version and package digest are saved with each normalization. An adapter failure cannot crash plan authoring or erase raw reports.

### 5.4 Plugin host, jobs and failure isolation

Run configured plugin calls in a separate supervised worker process with read-only request data, a staged output capability, 60-second default generation timeout, and a 512 MiB output cap. Hosts may configure higher explicit limits. Process separation provides crash/resource isolation; it is not a claim that untrusted Python is a secure sandbox. Treat installed plugins as trusted deployment code. Foundation plugin calls need no network or simulator processes.

Generation job lifecycle: `queued → running → succeeded | failed | cancelled | interrupted`. Cancellation closes output writer and terminates worker; staged outputs never become a successful manifest. On host restart, queued jobs resume; running jobs become interrupted. **Retry** creates a new attempt using exactly the saved immutable request. No auto-retry of an interrupted third-party plugin without declared deterministic/retry-safe capability.

Publish artifacts only after validating all hashes, paths, declared roles and trace maps. The same request may reuse an existing successful content-addressed output. Idempotency request replay returns the same job, not a second worker invocation.

A missing plugin after upgrade leaves historical artifacts/manifests readable. New generation is blocked with **Required plugin version unavailable**. Do not silently use another version. A plugin update requires a new configuration/checkpoint and preview of changed capability/outputs.

## 6. Reference plugin and later backend requirements

### 6.1 Required foundation plugin

Implement `spec2gds.reference.bundle` as a deterministic artifact-only backend. It outputs:

- Canonical `test-ir.json` and target/objective binding manifests.
- Human-readable `recipe.md` with source/intent/objective links, phase descriptions and checks.
- `producer-manifest.json` plus a normalized **example result schema/template**, explicitly labeled synthetic and not importable as actual evidence without a fixture-only flag in the test environment.
- Validation report including unsupported executable constructs, if any.

It emits no HDL/Python testbench and claims no compile/run capability. UI backend title is **Reference bundle — no executable tests**. Generation success means **Bundle generated**, never **Tests passed**. A separate fixture result producer used in automated tests creates normalized reports with `synthetic=true`; production UI labels synthetic evidence and excludes it from real campaign closure. Test campaigns explicitly created with `purpose=fixture` may evaluate those reports for acceptance; real campaigns cannot change purpose after creation.

The backend contract harness also uses intentionally incompatible and failing fixture plugins to test version mismatch, unsupported operators, malformed output, timeout, exception, cancellation, duplicate registration and artifact-path rejection. Do not create fake production Cocotb/UVM/formal plugins merely to populate the selector.

### 6.2 Cocotb backend, later

Expected artifacts: Python tests, runner/build configuration, reference-model runtime if required, DUT bindings, producer manifest, usage README, and normalized-result writer. Preserve explicit edge/sampling phases, typed comparisons and seeds. Python environments use `uv` and a pinned dependency lock/environment definition.

Per-intent checking and semantic bins must be emitted explicitly by the generated observer or a report sidecar. A simulator's code coverage and Cocotb test-result XML are not interchangeable with semantic objective evidence. See the official [Cocotb runner documentation](https://docs.cocotb.org/en/stable/runner.html): runner APIs are documented as experimental, so the plugin must pin/test the supported API version rather than expose it as the service's permanent public contract.

### 6.3 UVM backend, later

Expected artifacts: test/sequence classes, environment/agent integration or declared external VIP dependencies, scoreboard/checker/coverage implementation, file list, simulator configuration, producer manifest, README and result-adapter instructions. Backend configuration explicitly distinguishes **Generate a standalone environment** from **Integrate with an existing environment**. The latter requires user-supplied typed handles/interface adapters and their versioned artifacts.

No global service assumption that one intent maps to one UVM test or that a covergroup proves correctness. A single test can emit observations for multiple objectives. Unavailable VIP or unsupported simulator syntax appears in preflight. Production acceptance must compile and run against the explicitly supported simulator versions; emitting text alone is insufficient.

### 6.4 Formal backend, later

Expected artifacts: property/checker modules, explicit assumptions, bind/wrapper files, tool task configuration, reachability tasks, proof-quality reporting and manifest. Separate bounded checks, unbounded proof, covers and vacuity outcomes in normalized results. Tool-specific frontends need declared supported syntax/operators; “SVA” is not a blanket portability guarantee.

For a SymbiYosys realization, mode and bound must map explicitly: its [documented task modes](https://symbiyosys.readthedocs.io/en/latest/reference.html) distinguish bounded checks, unbounded safety proofs, liveness and cover tasks. The plugin must not report a bounded pass as proof of an unbounded objective. Other formal tools can implement the same normalized contract.

### 6.5 Structural/mutation and future extensions

Structural report adapters declare supported metric kind, element-ID schema and exact build/instrumentation identity. Mutation adapters declare mutant-set identity and classification mapping. Neither can adjust the reviewed denominator silently. Protocol-specific drivers, external reference models, multi-clock scheduling, analog/mixed-signal tests and execution runners require explicit capability/contract extensions; they are not implied by the initial IR.

## 7. Generation, editing and external execution

### 7.1 Generation preview

**Generate** first shows the selected I checkpoint, recipes/objectives, plugin/version, target profile, unsupported features and output destination. If not executable, display that prominently. Block only selected unsupported recipes; let the user change the selection explicitly. Generation does not change upstream checkpoints.

On success, **Artifacts** view has file tree, readable preview, manifest/provenance panel and download. Initial delivery produces a downloadable bundle, not arbitrary server-path overwrites. **Regenerate** creates a new immutable artifact set and a diff from the previous one. No editing generated files in place inside canonical service storage.

If users maintain generated code externally, use extension directories or a separately versioned external implementation. A later import records their changed artifact digest and reviewed mappings. They cannot reuse the old producer manifest while claiming modified code is byte-identical.

### 7.2 External run boundary

Run instructions and portable manifests accompany generated output. External tools/CI run the tests and submit results through Layer 2 import. Initial UI includes **Download bundle**, **Copy run instructions**, **Import results**, and **Register external implementation**. No misleading **Run** button with unimplemented scheduling.

The generated result writer records actual tool version, DUT/build/configuration digests, producer manifest digest, run/attempt identity, seeds, per-check evaluations/outcomes and per-bin hits. If actual environment differs from the manifest's allowed envelope, it marks incompatibility; Layer 2 verifies it before counting evidence. Neither producer nor adapter can assert global intent status.

### 7.3 External implementation mapping

UI flow: name implementation → select source/coverage baseline and DUT/configuration → attach immutable external artifact manifest → choose observed test/check keys from a report or enter them → map each to objective/bin IDs → preview semantic coverage and unresolved mappings → review/register.

Mapping a test key to a correctness objective requires a declared check identity and semantic assertion matching that objective, plus actual evaluation evidence from the report. Test-level JUnit pass may remain an execution-only record when this information is missing. Imported structural metrics remain supplemental unless the policy explicitly includes them in addition to behavioral evidence.

## 8. API contract

Use common revision-checked authoring batches for `binding_set.create/update/archive`, `recipe.create/update/archive`, `recipe.set_state`, `backend_configuration.create`, `recipe.bind_evidence`, `implementation.rebase`, and `external_implementation.register`. Backend configurations and reviewed manifests are immutable; editing creates a new revision/record and updates draft references through an explicit command.

| Method/path | Purpose |
| --- | --- |
| `GET /plugins` | Installed manifests, versions, capabilities, disabled diagnostics |
| `GET /plugins/:id/configuration-schema` | Exact form/API schema and schema digest |
| `GET /schemas/verification.test-ir.v1` | Public machine-readable IR schema |
| `POST /plans/:id/recipes/:recipeId/validate` | Core plus optional backend validation; no mutation |
| `POST /plans/:id/generations/preview` | Selected immutable checkpoint/recipes/configuration; readiness/output overview |
| `POST /plans/:id/generations` | Idempotent asynchronous generation from immutable request |
| `GET /plans/:id/generations/:jobId` | Job state, saved inputs, diagnostics, artifact handles |
| `POST /plans/:id/generations/:jobId/cancel` | Cancel queued/running generation only |
| `POST /plans/:id/generations/:jobId/retry` | New attempt of identical saved request |
| `GET /plans/:id/artifacts/:artifactId` | Authenticated/read-authorized streamed artifact |
| `GET /plans/:id/producer-manifests/:digest` | Immutable evidence mapping and provenance |

Checkpoint creation uses the shared `/checkpoints` route with `layer=implementation` and selected recipe IDs. Generation POST names the immutable checkpoint and exact plugin/config digests, so an unrelated later text edit cannot change its input. If draft inputs differ from that checkpoint, UI says **Generating reviewed I1; working draft has changes**. HTTP 202 means queued; only a terminal success with validated artifacts means generated.

Registration of external implementation is an authoring command followed by implementation review; the service then publishes its producer manifest without generator invocation. This endpoint is part of the evidence foundation so API result fixtures can establish valid mappings before real backends exist.

## 9. Worked FIFO recipe

Use the Layer 1 fixture exactly. Target the two intents **Full write preserves occupancy** and **Full write preserves queued data**, with distinct checking objectives.

The readable recipe must state:

1. Initialize inputs to inactive; apply reset for two rising edges; sample after settle; explicitly check the reset state using its own check if mapped, otherwise setup validation only.
2. Deassert reset before the next edge. Write literal values `[0x11, 0x22, 0x33, 0x44]`, one accepted write per rising edge. Maintain the reference queue only on declared pre-edge acceptance.
3. Before the next edge, sample count/full. Require count=4/full=1 as a setup condition; if not reached, report setup error, not a successful full-boundary check.
4. Drive `wr_en=1`, `rd_en=0`, `din=0xEE`; advance one rising edge and sample count/full after settling.
5. Check count remains 4/full remains 1; emit its evaluation. Record the full-write scenario occurrence with this check association.
6. Deassert write; drain exactly four accepted reads. Sample `dout` after each edge and compare with successive reference values. This is the data-preservation oracle; observing count alone is insufficient.
7. Mark the data-preservation scenario eligible only if all four comparisons complete and pass; verify queue empty at the end. A fifth unexpected accepted value or any mismatch fails its check.

The IR model updates use pre-edge count, the explicit acceptance rules, and a reference queue authored from the source requirement. Never enqueue 0xEE because the attempt was rejected. Generated formal alternatives must express their assumptions and reachability separately; translating this finite scenario is not an unbounded proof.

For two-FIFO design, reference recipes must bind ingress and egress independently. A design-level sequence feeds a known accepted-word stream, stalls the external consumer long enough to fill egress/bridge, resumes, and compares the complete consumed stream. Its model includes the explicitly specified one-entry bridge and transfer bubble; it may not assume a combinational FIFO output. This realization maps to composition objectives; local FIFO recipes alone do not cover it.

## 10. Validation and acceptance requirements

### Core validation order

1. Schema/version/limits and reference integrity.
2. Scope/upstream hashes and evidence-binding compatibility.
3. Types, directions, clock/reset declarations, initial values and finite limits.
4. Control/data flow: sample-before-use, single-writer parallel blocks, reachable required checks and bins.
5. Oracle provenance, tautology guards and trace map completeness.
6. Backend capability/configuration validation.
7. Output manifest, path/hash/role checks before publication.

Return every independently discoverable diagnostic, in stable path order; avoid cascading noise after an invalid parent type. Every error includes a recipe record ID, IR path and primary UI action.

| ID | Scenario | Required result |
| --- | --- | --- |
| L3-01 | Build FIFO recipe entirely with forms | Readable sequence and canonical IR agree; JSON editing not required |
| L3-02 | Script builds identical recipe via public API | Same normalized IR/relationships as UI after removing generated metadata |
| L3-03 | No backend installed | Planning/editing works; generation explains missing backend |
| L3-04 | Reference backend selected | Artifact-only status visible; deterministic bundle, no runnable-test/pass claim |
| L3-05 | Generate same immutable inputs twice | Identical artifact bytes/digests; distinct host job metadata permitted |
| L3-06 | Unsupported step/operator/model/property | Preflight links exact node; nothing silently dropped |
| L3-07 | Output binding driven, width mismatch, uninitialized sample | Core validation rejects before plugin call |
| L3-08 | Parallel branches drive same input or mutate same model | Validation rejects conflicting branches |
| L3-09 | Check never evaluates, compares value to itself, or lacks source rationale | Readiness blocked; no generated “passing” placeholder |
| L3-10 | Plugin exception/timeout/cancel/path traversal/malformed map | Job fails/cancels; no published partial artifact; plan stays usable |
| L3-11 | Source/coverage changes during generation | Job uses saved checkpoint; output visibly tied to old baseline |
| L3-12 | Generated output renamed symbols | Stable trace still resolves every check/bin to objective and source intent |
| L3-13 | External test passes without semantic mappings | Unbound/execution-only record; no invented bin hits |
| L3-14 | Adapter reports unknown property status | Unknown retained; never success default |
| L3-15 | Plugin upgrade/removal | Old bundles readable; new generation requires exact version or new reviewed config |
| L3-16 | Synthetic fixture result sent to real campaign | Rejected for closure; fixture campaign explicitly labeled synthetic |
| L3-17 | User switches backend | Intent/objective identities and semantics unchanged; unsupported capabilities surfaced |
| L3-18 | Later Cocotb/UVM/formal backend release | Contract suite plus real compile/run/proof fixtures, including intentional DUT defect detection |

Foundation completion requires no production backend. It does require a working public abstraction, useful manual UI, end-to-end stable traceability, deterministic reference generation and API-driven tests. Later backend work must add implementations behind these boundaries rather than move implementation details into Test Plan or Coverage.

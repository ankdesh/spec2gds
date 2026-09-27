# Verification Planner (`testplan-service`)

A standalone, deterministic test planning and verification service for hardware systems, implementing **Layer 1 (Test Plan)**, **Layer 2 (Coverage & Evidence Mapping)**, and **Layer 3 (Implementation, Test IR & Backend Plugins)** of the specification-first verification architecture.

## Overview

`testplan-service` is an independent service with zero runtime dependencies on Spec Editor, Circuit Designer, or AI Assistant. It operates on immutable, content-addressed Activity Snapshots (`spec2gds Activity Snapshot v1`) and provides authoring of auditable requirements, atomic behavioral intents, multi-family coverage objectives, intent evidence policies, campaigns, frozen evidence reports, language-neutral Test IR ASTs, target bindings, and deterministic backend generation.

### Core Architecture & Guiding Principles

1. **Full Three-Layer Decoupled Verification Model**:
   - **Layer 1 (Test Plan)**: Audited requirements, sections, atomic verification intents, and review checkpoint P1.
   - **Layer 2 (Coverage & Evidence)**: Coverage dimensions, bins, exclusions, objectives across all 6 families (Scenario, Functional, Correctness, Property, Structural, Mutation), IntentEvidencePolicy mapping, evaluation profiles, campaigns (`verification`/`fixture`), result imports (`verification.results.v1`), deterministic status evaluation order, 16 typed gap kinds, and frozen evidence reports.
   - **Layer 3 (Implementation & Generation)**: Target binding sets (port mapping, clocks, resets, permissions), backend configurations, neutral Test IR v1 AST, preflight validation engine, review checkpoint I1, pluggable backend generators (`spec2gds.reference.bundle`), and generation runner publishing producer manifests.
2. **Deterministic & Content-Addressed Persistence**: Built upon SQLite in WAL mode with content-addressed SHA-256 blob storage and explicit transaction boundaries. Every snapshot, checkpoint, profile, run, recipe, and generated artifact has cryptographically verifiable integrity.
3. **Deterministic Evaluation Order**: Precedence strictly follows:
   $$\text{Fail} > \text{Blocked} > \text{Satisfied} > \text{Waived} > \text{Open} > \text{Not evaluated}$$
   Passing retries never erase earlier failures without formal review dispositions (`invalid_tool_run` or `superseded_after_fix`). Unresolved failures override waivers.
4. **Three-Panel Blueprint Slate UI**: Professional, high-density interface with:
   - **Layer Switcher**: Seamless switching between **1 · Test Plan**, **2 · Coverage & Evidence**, and **3 · Implementation**.
   - **Left Panel**: Occurrence scope hierarchy tree with descendant counts and occurrence filtering.
   - **Center Panel**:
     - *Layer 1*: Test Plan outline, Source & Requirements review matrix, and P1 Checkpoint management.
     - *Layer 2*: Coverage Matrix with family summary cells, Gap analysis with direct actions, Evidence Runs table, and Trace explorer.
     - *Layer 3*: Verification Recipes table, Target Bindings editor, Backend Plugins catalog, and Generation Jobs / Artifact downloads.
   - **Right Panel**: Contextual inspector with Details, verbatim Source citations, Policy rules, and History trace.
5. **Review Checkpoint Immutability**:
   - **Checkpoint P1**: Read-only, immutable baseline of audited requirements and ready intents.
   - **Checkpoint C1**: Read-only, immutable baseline of coverage objectives and evidence policies referencing upstream P1.
   - **Checkpoint I1**: Read-only, immutable baseline of recipes, target bindings, and backend configurations referencing upstream C1. Subsequent draft edits never mutate frozen checkpoints or historical reports.

---

## Directory Structure

```
testplan-service/
├── pyproject.toml
├── README.md
├── scripts/
│   └── build_fixtures.py           # Ordered API fixture builder (Steps 1–10)
├── src/
│   └── testplan_service/
│       ├── constants.py            # Hoisted constants, ports, schemas, Blueprint Slate tokens
│       ├── exceptions.py           # Structured domain exception hierarchy (Layers 1, 2, 3)
│       ├── logging.py              # Structured logging
│       ├── domain/
│       │   ├── enums.py            # Priority, AuthoringState, Dispositions, IssueSeverity
│       │   ├── hash.py             # Canonical key-sorted JSON hashing (sha256_digest)
│       │   ├── models.py           # Layer 1 Pydantic models (PlanHeader, Requirement, Section, Intent, Issue)
│       │   ├── objectives.py       # Layer 2 models (CoverageObjective, Dimension, Bin, Exclusion)
│       │   ├── policies.py         # Layer 2 models (IntentEvidencePolicy, PolicyBranch)
│       │   ├── evidence.py         # Layer 2 models (Profile, Campaign, Run, Observation, Report)
│       │   ├── coverage_evaluator.py# Deterministic status evaluator, matrix rollup, gap engine
│       │   ├── test_ir.py          # Layer 3 neutral Test IR v1 AST (expressions, steps, models)
│       │   ├── recipes.py          # Layer 3 models (TargetBindingSet, Recipe, BackendConfiguration)
│       │   ├── recipe_validation.py# Preflight validation engine (Core Validation Order & Reachability)
│       │   ├── plugins/            # Layer 3 Backend Plugin framework
│       │   │   ├── base.py         # BackendPlugin, ResultAdapterPlugin, OutputWriter sandbox
│       │   │   ├── models.py       # PluginManifest, GenerationRequest, GenerationResult
│       │   │   ├── reference_bundle.py# spec2gds.reference.bundle foundation plugin
│       │   │   └── registry.py     # Default plugin registry
│       │   ├── operations.py       # Typed batch command operation models
│       │   ├── validation.py       # Invariant validation, cycle detection, intent readiness
│       │   └── hierarchy.py        # Scope tree projection and descendant count aggregation
│       ├── integrations/
│       │   ├── models.py           # SourceSnapshotView, EntitySummary, OccurrenceSummary
│       │   └── snapshot_decoder.py # Activity Snapshot v1 decoder & IP-XACT occurrence projector
│       ├── fixtures/
│       │   ├── fifo_snapshot.py    # Synthetic Synchronous FIFO snapshot generator
│       │   └── two_fifo_snapshot.py# Synthetic Two-FIFO design snapshot generator
│       ├── storage/
│       │   ├── blob_store.py       # Content-addressed SHA-256 blob storage (blobs/ and staging/)
│       │   └── sqlite_repo.py      # SQLite repository (WAL mode, generation_jobs, artifacts, producer manifests)
│       ├── application/
│       │   ├── command_handler.py  # Atomic command batch handler with revision preconditions
│       │   ├── coverage_service.py # Layer 2 service (profiles, campaigns, imports, matrix, gaps)
│       │   ├── review_engine.py    # Checklist evaluation and immutable P1 / C1 / I1 checkpoint creation
│       │   ├── generation_runner.py# Layer 3 generation orchestrator and artifact publisher
│       │   ├── export_service.py   # .vplan ZIP bundles, Markdown, and CSV export/import
│       │   └── service.py          # Unified TestPlanService coordinator
│       ├── api/
│       │   ├── app.py              # FastAPI app factory, CORS, exception handlers
│       │   ├── routes_meta.py      # /capabilities, /operation-catalog, /health
│       │   ├── routes_plans.py     # Plan lifecycle, records, source sections, requirements, hierarchy
│       │   ├── routes_commands.py  # Atomic batch /commands and /commands/preview
│       │   ├── routes_checkpoints.py# Checkpoint evaluation, preview, creation, inspection (P1, C1, I1)
│       │   ├── routes_coverage.py  # Layer 2 coverage matrix, gaps, profiles, campaigns, imports, reports
│       │   ├── routes_recipes.py   # Layer 3 recipes and preflight validation (/recipes, /validate)
│       │   ├── routes_plugins.py   # Layer 3 plugin discovery (/plugins)
│       │   ├── routes_generations.py# Layer 3 code generation and artifact streaming (/generations, /artifacts)
│       │   ├── routes_imports.py   # Snapshot uploads (/source-imports) and bundle imports (/bundle-imports)
│       │   ├── routes_exports.py   # Markdown, CSV, and .vplan bundle exports
│       │   └── routes_events.py    # SSE plan change event stream (/events)
│       ├── ui/static/
│       │   ├── index.html          # Blueprint Slate single-page application (Layers 1, 2, 3)
│       │   ├── styles.css          # Slate tokens, badges, matrix styling, dialogs
│       │   └── app.js              # State store, layer switching, subnavs, matrix, recipes & generators
│       └── cli.py                  # CLI entrypoint
└── tests/
    ├── conftest.py                 # Clean test fixtures
    ├── test_layer1_acceptance.py   # Comprehensive Layer 1 acceptance suite (L1-01 through L1-15)
    ├── test_layer2_acceptance.py   # Comprehensive Layer 2 acceptance suite (L2-01 through L2-20)
    └── test_layer3_acceptance.py   # Comprehensive Layer 3 acceptance suite (L3-01 through L3-17)
```

---

## API Summary (`/api/verification/v1`)

### Layer 1: Core Test Plan Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/capabilities` | `GET` | Discovery endpoint reporting service version, schemas, active layers, and limits |
| `/operation-catalog` | `GET` | Catalog of all typed batch operations |
| `/source-imports` | `POST` | Upload and decode an Activity Snapshot v1 container |
| `/bundle-imports` | `POST` | Upload and stage a `.vplan` bundle archive |
| `/bundle-imports/{staging_id}/commit` | `POST` | Commit staged bundle (`create` or `import_as_copy`) |
| `/plans` | `POST`, `GET` | Create a new plan bound to a snapshot root; list all plans |
| `/plans/{id}` | `GET` | Read plan header, active snapshot view, and checkpoint list |
| `/plans/{id}/hierarchy` | `GET` | Scope tree projection with descendant counts |
| `/plans/{id}/records` | `GET`, `POST` | Query records (filtered by type, scope, archived) |
| `/plans/{id}/commands` | `POST` | Transactional command batch with revision precondition (`base_edit_revision`) |
| `/plans/{id}/commands?preview=true` | `POST` | Dry-run preview returning diffs and diagnostics without committing |
| `/plans/{id}/checkpoints/preview` | `POST` | Evaluate readiness checklist, blockers, and candidate digest for P1 or C1 |
| `/plans/{id}/checkpoints` | `POST`, `GET` | Create immutable checkpoint (P1 or C1); list checkpoints |
| `/plans/{id}/exports` | `POST` | Export plan as Markdown, spreadsheet-safe CSV, or `.vplan` bundle |
| `/plans/{id}/events` | `GET` | Server-Sent Events stream for concurrent update notifications |

### Layer 2: Coverage & Evidence Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/plans/{id}/coverage/matrix` | `GET` | Coverage matrix with baseline and filtered summaries, profile statuses, and family cells |
| `/plans/{id}/coverage/gaps` | `GET` | Deterministic gap analysis records with stable IDs, severity, and primary actions |
| `/plans/{id}/coverage/trace` | `GET` | Upstream/downstream lineage trace linking requirements, intents, objectives, and runs |
| `/plans/{id}/profiles` | `POST`, `GET` | Create an evaluation profile (DUT hash, parameters, descriptors); list profiles |
| `/plans/{id}/profiles/{prof_id}` | `GET` | Retrieve a single evaluation profile |
| `/plans/{id}/campaigns` | `POST`, `GET` | Create an evidence campaign bound to a coverage checkpoint; list campaigns |
| `/plans/{id}/campaigns/{camp_id}` | `GET` | Retrieve campaign state, included runs, dispositions, and active waivers |
| `/plans/{id}/campaigns/{camp_id}/commands` | `POST` | Revision-checked campaign batch (`run.include`, `run.exclude`, `run.resolve`, `waiver.create`, `waiver.revoke`, `campaign.freeze`) |
| `/plans/{id}/result-imports` | `POST` | Stage a `verification.results.v1` result import payload; returns preview digest |
| `/plans/{id}/result-imports/{staging_id}/commit` | `POST` | Idempotent commit of staged run and observations, with optional campaign enrollment |
| `/plans/{id}/runs` | `GET` | List imported immutable evidence runs |
| `/plans/{id}/runs/{run_id}` | `GET` | Retrieve run header, producer info, execution metadata, and tool provenance |
| `/plans/{id}/runs/{run_id}/observations` | `GET` | Retrieve atomic observations captured during the run |
| `/plans/{id}/evidence-reports` | `POST`, `GET` | Freeze an immutable evidence report over a campaign; list reports |
| `/plans/{id}/evidence-reports/{report_id}` | `GET` | Retrieve a frozen evidence report |

### Layer 3: Implementation & Generation Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/plugins` | `GET` | Catalog of registered backend generator and result adapter plugins |
| `/plans/{id}/recipes/{recipe_id}/validate` | `POST` | Preflight validate recipe against target binding and Core Validation Order |
| `/plans/{id}/generations/preview` | `POST` | Preview lowered generation inputs and preflight diagnostics |
| `/plans/{id}/generations` | `POST`, `GET` | Submit generation job against Checkpoint I1; list generation jobs |
| `/plans/{id}/generations/{job_id}` | `GET` | Retrieve status, diagnostics, and output artifact descriptors |
| `/plans/{id}/generations/{job_id}/cancel` | `POST` | Cancel queued or running generation job |
| `/plans/{id}/artifacts/{artifact_id}` | `GET` | Stream raw generated artifact content |
| `/plans/{id}/producer-manifests/{digest}` | `GET` | Retrieve published producer manifest |

---

## Running the Service

```bash
# Start the Verification Planner service on port 6016
uv run python -m testplan_service.cli --host 127.0.0.1 --port 6016 --storage-dir verification-data/
```

Access the Blueprint Slate UI by navigating to:
```
http://127.0.0.1:6016/
```

---

## Running Tests & Fixtures

### Full Acceptance Test Suite (Layers 1, 2, and 3)

```bash
# Run all 47 acceptance tests (14 Layer 1 + 20 Layer 2 + 13 Layer 3)
uv run pytest -v tests/
```

### API Fixture-Building Sequence

To run the complete 10-step API fixture building sequence:

```bash
# Target running service (or falls back to in-process client if service is offline)
uv run python scripts/build_fixtures.py --base-url http://127.0.0.1:6016
```


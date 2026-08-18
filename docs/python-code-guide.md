# Python code-reading guide

This guide gives a new contributor a safe reading order for the Python side of
spec2gds. Module docstrings explain each file's local responsibility; this page
connects those modules into the main runtime and data flows.

## Start with the ownership boundaries

There are three Python distributions:

1. The root `spec2gds` project owns `.spec` packages, immutable semantic reads,
   validated edits, imports, Activities, the Spec API, and the Log Viewer.
2. `runtime/` is the deliberately small shared package for service-independent
   logging configuration and structured events.
3. `ai-assistant/` is an optional, separately installed service. It owns chats
   and review records, but it never owns specification or circuit source.

The Circuit Designer service and browser applications are TypeScript. Python
integrates with them only through their versioned HTTP and JSON contracts.

## Follow a specification request

Read these modules in order:

1. `spec2gds/agent_spec/api/__main__.py` parses bind settings and starts the
   server.
2. `spec2gds/agent_spec/spec_format/v1_api.py` is the HTTP composition root. It
   converts request models into reads or transactions and publishes browser
   events.
3. `spec2gds/agent_spec/spec_format/ir.py` builds the immutable semantic view
   used after a package is loaded.
4. `spec2gds/agent_spec/spec_format/transactions.py` is the revision-guarded
   mutation boundary.
5. `spec2gds/agent_spec/spec_format/archive.py` validates and atomically writes
   the deterministic `.spec` ZIP.
6. `spec2gds/agent_spec/spec_format/document.py` derives the renderer-neutral
   document projection consumed by the browser editor.

The important invariant is that HTTP handlers and renderers do not mutate XML
or package objects directly. A save constructs a candidate revision, validates
it, checks the expected source hash, and only then replaces the package.

## Follow an Activity

The Activity path separates portable plugin contracts from any future queue or
worker host:

1. `activities/snapshot.py` captures one deterministic, source-only revision.
2. `activities/view.py` exposes stable high-level queries and detailed typed
   low-level reads without mutation methods.
3. `activities/contracts.py` defines plugin metadata, contexts, results,
   artifacts, cancellation, and the constrained workspace capability.
4. `activities/registry.py` validates extensions and performs direct
   invocation.
5. `activities/workspace.py` atomically publishes only generator-owned relative
   directories.

The RTL and SystemC generators deliberately use two phases. Analysis traverses
and validates the complete reachable source graph before output begins;
normalization then converts accepted IR into simple template values. Jinja
templates format text but make no topology or naming decisions.

## Follow an Assistant proposal

The optional Assistant uses a review boundary rather than a source-write
shortcut:

1. `ai-assistant/src/spec2gds_assistant/app.py` wires FastAPI, A2A execution,
   agents, clients, and local storage.
2. `api.py` owns conversation/binding/review HTTP routes.
3. `database.py` persists only Assistant-owned threads, messages, and review
   records in SQLite.
4. `circuit_client.py` and `spec_client.py` validate allowlisted owner URLs and
   call their public APIs.
5. `agents/context.py` renders immutable semantic snapshots into deterministic
   prompt context with exact IDs and writable boundaries.
6. `agents/circuit_editor.py` and `agents/spec_editor.py` request typed model
   output; `models.py` rejects extra fields and invalid operation shapes.
7. `a2a_agent.py` converts domain results into A2A task updates and artifacts.

Discussion and model output never mutate source. Preview and apply cross back
into the owning Spec or Circuit API, which rechecks the source revision and all
domain invariants. The Assistant database is not a second source of truth.

## How to read the models

Data-only Pydantic classes mirror JSON wire contracts. Read their discriminated
`type` or `kind` field first, then their required payload fields. Validators
explain cross-field rules that are not visible from types alone. In
`ai-assistant/models.py`, Circuit values and operations precede their proposal
envelope; Spec values and operations follow in the same order.

Private helpers beginning with `_` are implementation details. Their names and
nearby comments explain local mechanics; non-obvious security, ownership,
determinism, and collision behavior is documented at the decision point.

## Verify a Python change

From the repository root:

```bash
uv run python -m pytest -q
uv run ruff check spec2gds runtime/src
uv run vulture spec2gds runtime/src --min-confidence 90
```

From `ai-assistant/`:

```bash
uv run python -m pytest -q
uv run python -m ruff check src
uv run python -m vulture src --min-confidence 90
```

The root suite requires GNU Make and Verilator 5.x because generated RTL is
linted as part of the Activity tests. See the development guide for frontend
and focused test commands.

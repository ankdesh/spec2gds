# Python code-reading guide

This guide gives a new contributor a safe reading order for the Python side of
spec2gds. Module docstrings explain each file's local responsibility; this page
connects those modules into the main runtime and data flows.

## Start with the ownership boundaries

There are two Python distributions:

1. The root `spec2gds` project owns `.spec` packages, immutable semantic reads,
   validated edits, imports, Activities, the Spec API, and the Log Viewer.
2. `runtime/` is the deliberately small shared package for service-independent
   logging configuration and structured events.

The optional `ai-assistant/` is a TypeScript/Node DeepSeek Harness product, not
a Python distribution. It owns chats and review records but never owns
specification or circuit source.

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

Assistant proposal execution is documented in [AI Assistant](ai-assistant.md).
Its TypeScript source lives under `ai-assistant/src`; no Assistant Python,
FastAPI, Pydantic, or A2A package remains.

## Verify a Python change

From the repository root:

```bash
uv run python -m pytest -q
uv run ruff check spec2gds runtime/src
uv run vulture spec2gds runtime/src --min-confidence 90
```

The root suite requires GNU Make and Verilator 5.x because generated RTL is
linted as part of the Activity tests. See the development guide for frontend
and focused test commands.

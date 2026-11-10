# Python Code Architecture and Standards

This document specifies the structure, reading order, and engineering standards for Python code in spec2hw.

## 1. Codebase Boundaries

The Python codebase contains three main packages:

1. **`spec2gds`**: The core package. Manages `.spec` containers, IP-XACT semantic models, transactional mutations, document importers, Activities, the Spec API, and the Log Viewer.
2. **`runtime`**: A shared utility library for structured logging and event definitions.
3. **`testplan-service`**: Verification Planner. Manages verification plans, review checkpoints, evidence evaluation, and reference generation.

The AI Assistant (`ai-assistant/`) and Circuit Designer (`circuit-designer/`) use TypeScript.
Python modules communicate with them only through versioned HTTP and JSON interfaces.

---

## 2. Recommended Reading Order

### Specification Service and Transactions
To understand specification handling, read modules in this order:

1. `spec2gds/spec/api/__main__.py`: CLI entrypoint and server binding.
2. `spec2gds/spec/spec_format/v1_api.py`: FastAPI routes, transaction dispatch, and event publishing.
3. `spec2gds/spec/spec_format/ir.py`: Immutable semantic representation of hardware specs (`SpecRevision`).
4. `spec2gds/spec/spec_format/transactions.py`: Revision-guarded transaction processor.
5. `spec2gds/spec/spec_format/archive.py`: Deterministic `.spec` ZIP packaging and validation.
6. `spec2gds/spec/spec_format/document.py`: Projection logic converting IP-XACT models into UI view models.

HTTP route handlers never mutate XML directly.
Edits construct a candidate `SpecRevision`, validate hardware consistency, verify the base revision hash, and commit atomically to the ZIP archive.

### Activity Pipeline
To understand Activities and code generators, read modules in this order:

1. `spec2gds/spec/activities/snapshot.py`: Captures immutable, source-only `.spec` revisions.
2. `spec2gds/spec/activities/view.py`: Provides `context.spec.high` and `context.spec.low` read APIs.
3. `spec2gds/spec/activities/contracts.py`: Defines Activity metadata, parameters, results, and artifacts.
4. `spec2gds/spec/activities/registry.py`: Activity discovery, registration, and invocation.
5. `spec2gds/spec/activities/scratch_directory.py`: Manages isolated temporary build directories.

---

## 3. Engineering and Code-Quality Standards

### Architecture Rules
- **One Primary Class Per File**: Keep modules lightweight, focused, and readable.
- **Fail Explicitly and Early**: Validate inputs at service boundaries. Raise precise exceptions instead of returning generic fallbacks.
- **No Stale Overwrites**: Enforce revision hash validation on every state mutation.
- **Static Typing**: Annotate all functions and classes with complete type hints. Verify types with `mypy`.

### Documentation and Comments
- **Module Docstrings**: Every production module must begin with a docstring describing its boundary and authority.
- **Intent over Syntax**: Inline comments must explain *why* non-obvious algorithms and constraints exist.
- **Do Not Comment Boilerplate**: Avoid manual comments on generated code, schemas, or routine test setups.

---

## 4. Lint and Static Analysis Checks

Run formatting, linting, and dead-code analysis from the repository root:

```bash
# Check code style and imports
uv run ruff check spec2gds runtime/src

# Scan for dead code with high confidence threshold
uv run vulture spec2gds runtime/src --min-confidence 90

# Run all unit and integration tests
uv run python -m pytest tests testplan-service/tests -q
```

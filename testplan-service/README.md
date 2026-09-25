# Testplan Service

A self-contained hierarchical testplan management service and interactive web editor for hardware verification.

## Architecture

`testplan-service` is an independent, modular service designed on similar lines as `spec-editor` and `circuit-designer`. It has zero hard runtime dependencies on either service or `ai-assistant`, while exposing full contract compatibility with the AI Assistant for verification proposal generation and review.

```
testplan-service/
├── pyproject.toml
├── README.md
├── src/
│   └── testplan_service/
│       ├── constants.py       # Hoisted network, limits, and action constants
│       ├── exceptions.py      # Precise domain exception hierarchy
│       ├── logging.py         # Structured JSON logging
│       ├── models/            # Pydantic v2 domain models (one primary class per file)
│       │   ├── enums.py       # NodeKind, CoverageCategory, NodeStatus, etc.
│       │   ├── node.py        # TestPlanNode (hierarchical tree node)
│       │   ├── testplan.py    # TestPlanDocument (authoritative plan document)
│       │   ├── operations.py  # PlanOperation, ProposalArtifact
│       │   └── summary.py     # TestPlanSummary (metrics & progress aggregation)
│       ├── storage/           # Interface-driven persistence
│       │   ├── interface.py   # TestPlanRepository protocol
│       │   ├── memory_repository.py
│       │   └── file_repository.py
│       ├── service/           # Core domain logic
│       │   ├── manager.py     # TestPlanManager (CRUD, tree operations, cycle detection)
│       │   ├── proposal_handler.py # AI Assistant proposal preview & apply
│       │   └── export_service.py   # Markdown & JSON serialization
│       ├── api/               # FastAPI REST endpoints
│       │   ├── app.py         # App factory with middleware & error handlers
│       │   ├── routes_testplans.py # Document CRUD
│       │   ├── routes_nodes.py     # Hierarchical node CRUD & move
│       │   ├── routes_assistant.py # AI Assistant contract endpoints
│       │   └── routes_export.py    # Markdown/JSON export and import
│       ├── ui/static/         # Interactive Web Application
│       │   ├── index.html     # Single-page interface
│       │   ├── styles.css     # Blueprint Slate responsive design
│       │   └── app.js         # Interactive tree, inspector, and proposal reviewer
│       └── cli.py             # CLI runner entrypoint
└── tests/                     # Direct test suite (models, manager, API, storage)
```

## Features

- **Hierarchical Tree Structure**: Group -> Feature -> Testpoint -> TestCase -> Covergroup -> Assertion.
- **Coverage Taxonomy**: 9 domain categories (Port Boundary, Reset, Functional Mode, Protocol, Error Injection, Timing, Cross-Port, Structural Connectivity, Special Patterns).
- **Cycle-Safe Tree Manipulation**: Subtree moving with strict cycle detection and maximum depth limits.
- **AI Assistant Contract Compatibility**:
  - `GET /health` & `GET /capabilities`: Service identification and capabilities.
  - `GET /documents`: Target discovery.
  - `GET /assistant/context`: Structured context and Markdown summary for LLM prompt injection.
  - `POST /assistant/proposals/preview`: Color-coded diff preview without mutating document state.
  - `POST /assistant/proposals/apply`: Atomic commit of proposed operations with revision bump.
- **Interactive Web Editor**: Responsive web UI served at `/` and `/ui` featuring live tree manipulation, node inspector, filter/search, Markdown/JSON export, and AI proposal reviewer.

## Running the Service

```bash
# Run standalone using default port 6016
uv run python -m testplan_service.cli --host 0.0.0.0 --port 6016 --storage-dir .testplans

# Or using the console script
uv run testplan-service --port 6016
```

Open `http://127.0.0.1:6016` in your browser.

## Running Tests

```bash
uv run python -m pytest testplan-service/tests -v
```

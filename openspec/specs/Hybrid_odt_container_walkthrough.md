# Walkthrough: Hybrid ODT Container and Multi-Modal Specifications

This document provides a comprehensive summary of the architecture, implementations, test results, and validation reports for the entire ODT hybrid spec framework. This includes both the baseline container engine and the new `IPXACTPlugin` multi-modal specification extension.

---

## Accomplishments

We have built a headless Python API and CLI tool to package, validate, and query multi-modal hardware data directly inside standard ODT documents (preserving data integrity across LibreOffice editing cycles). 

Every component strictly adheres to the **Mojo-Readiness guidelines**:
- **Strict Type Annotations**: Fully typed signatures and variables.
- **Value Semantics**: Explicit `copy.deepcopy()` cloning on all boundary traversals to enforce state isolation.
- **Protocol-Driven Extensibility**: Modular plugin architecture using `typing.Protocol` interfaces.
- **Namespace-Only Imports**: Direct namespace loading only (e.g., `import copy`, `import lxml.etree`).
- **Sequential Error Flows**: Specific sequential try-except clauses avoiding multi-exception catch-alls.
- **Independent Test Suites**: Zero-argument standalone test functions returning `None` and asserting via Python `assert` statements.

---

## Core Implementations

### 1. Hybrid ODT Container (`spec/odt_container/container.py`)
- Interfaces `odfdo.Document` and low-level `zipfile` packaging.
- Isolates all custom hardware spec payloads within the namespaced `spec_data/` directory inside ODT.
- Synchronously updates `META-INF/manifest.xml` to associate custom media-types (e.g., `application/xml+ipxact`, `application/x-spec-json`), preventing office suites from stripping embedded files.
- **Mimetype Alignment**: Uses a custom ZIP layout post-processor to ensure `mimetype` is stored uncompressed and placed as the absolute first entry, keeping documents perfectly compliant with ISO/IEC 26300 standards.

### 2. Extensible Plugin Registry (`spec/odt_container/plugin.py`, `manager.py`)
- Defines `ModalityPlugin` protocol to enable third-party schema formats.
- Implements `PluginManager` to bootstrap modality handlers, delegate payloads, and parse custom links.
- Resolves URIs conforming to `spec://<modality_id>/<file_path>/<node_path>`.

### 3. Simple JSON Modality (`spec/odt_container/json_plugin.py`)
- Implements `ModalityPlugin` for `simple-json` payloads.
- Validates data against strict templates using Pydantic (`SimpleJSONSpecSchema`).
- Resolves JSON pointer query paths (e.g. `/metadata/1/value`).

### 4. IP-XACT Modality (`spec/odt_container/ipxact_plugin.py`)
- Implements `ModalityPlugin` for `ipxact` payloads.
- **Namespace Dispatching**: Supports transparent validation of both IEEE 1685-2009 and 2014 documents by dynamically selecting the schema based on XML namespace attributes.
- **Custom Deepcopy Subclass**: Extends the third-party `pyEDAA.IPXACT.Component.Component` class into a custom `HybridIPXACTComponent` subclass to support Python `copy.deepcopy()` operations by serializing state to XML via `lxml` and re-parsing. This completely bypasses pickling bugs present in the underlying third-party package.
- **Hybrid Path Resolution**: Resolves queries by searching logical attributes (case-insensitively) first, falling back to standard `lxml` XPath queries (e.g., `//ipxact:description`) on mismatch.

### 5. Semantic Link Verification Engine (`spec/odt_container/verifier.py`)
- Scans `content.xml` via `lxml` to find all hyperlinks containing the `spec://` protocol.
- Executes referential integrity validations to confirm that all targets resolve to actual values.
- Compiles a complete `ContainerVerificationReport` returned as structured JSON.

### 6. Command-Line Interface (`spec/odt_container/cli.py`)
- Provides a clean CLI with subcommands: `list-plugins`, `inject`, `extract`, and `validate`.
- Enhanced `inject` and `extract` commands to dynamically dispatch between JSON and raw XML payloads based on modality type.

---

## Test Engineering & Verification

We established a comprehensive suite of **13 standalone unit/integration tests** covering container integrity, Pydantic validations, path traversals, link validations, IP-XACT version dispatching, hybrid XPath resolutions, and CLI subcommands.

### Test Results
Executing `PYTHONPATH=. .venv/bin/pytest tests/spec/odt_container/` succeeds flawlessly with all 13 tests passing:

```bash
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/ankdesh/explore/spec2gds
configfile: pyproject.toml
collecting ...
collected 13 items

tests/spec/odt_container/test_cli.py ..                                  [ 15%]
tests/spec/odt_container/test_container.py ....                          [ 46%]
tests/spec/odt_container/test_ipxact.py ...                              [ 69%]
tests/spec/odt_container/test_plugins.py ....                            [100%]

============================== 13 passed in 0.32s ==============================
```

### Verification Scenarios Covered
1. **Container Integrity & MIME Magic**: Verifies `mimetype` byte alignments.
2. **File Injection & Deletion Cascades**: Confirms proper sync of `META-INF/manifest.xml`.
3. **Pydantic Schema Validation**: Assures JSON spec validation rejects incorrect profiles.
4. **Dynamic IP-XACT Validation**: Verifies that both 1685-2009 and 2014 documents are parsed and validated against their appropriate XSDs without manual intervention.
5. **Hybrid Path Traversals**: Verifies logical queries (e.g., `VLNV/Name`) and XPath queries (e.g. `//ipxact:description`) against the IP-XACT database.
6. **Custom Deepcopy Copy Semantics**: Confirms the `deepcopy` workaround isolates the object model from side-effect mutations.
7. **Referential Integrity Audits**: Verifies the link resolver flags dangling spec references inside the ODT document narrative.
8. **CLI subcommand routing**: Validates the end-to-end user pipeline.

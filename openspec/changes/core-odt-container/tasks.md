## 1. Setup and Environment

- [x] 1.1 Create the directory structure `spec2gds/spec/odt_container/` and ensure mirror `tests/spec/odt_container/` exists
- [x] 1.2 Configure `pyproject.toml` dependencies ensuring `odfdo`, `lxml`, and `pydantic` are declared and managed strictly via uv
- [x] 1.3 Implement `spec2gds/spec/odt_container/__init__.py` using entire namespace imports only, exposing the public interface

## 2. Core Container Development (HybridODTContainer)

- [x] 2.1 Pre-declare all instance attributes and type annotations directly in the `HybridODTContainer` class body in `spec2gds/spec/odt_container/container.py`
- [x] 2.2 Implement robust constructor and ODT ZIP loader utilizing `odfdo.Document`, strictly annotating all parameters and return values
- [x] 2.3 Implement standard-compliant ODT ZIP writer/saver forcing the uncompressed `mimetype` file at byte offset 30 as the first entry
- [x] 2.4 Build sequential `try-except` blocks for all low-level ZIP manipulation to strictly isolate exception flows
- [x] 2.5 Implement `lxml`-based manifest processor to search, parse, and surgically update `META-INF/manifest.xml` namespaces without corruption
- [x] 2.6 Integrate synchronous registration logic so that saving/injecting files under `spec_data/` triggers manifest node insertion with custom MIME types

## 3. Plugin Architecture and Registry (PluginManager)

- [x] 3.1 Define the abstract `ModalityPlugin` protocol using `typing.Protocol` or `abc.ABC` in `spec2gds/spec/odt_container/plugin.py` to enforce composition
- [x] 3.2 Pre-declare static configuration structures using Pydantic models for plugin and modality attributes
- [x] 3.3 Implement `PluginManager` in `spec2gds/spec/odt_container/manager.py` with strict type-locking and optional parameter annotations
- [x] 3.4 Ensure the payload extraction functions on `PluginManager` perform explicit value deep-copying before returning objects to the caller

## 4. Simple JSON Modality (SimpleJSONPlugin)

- [x] 4.1 Implement the concrete `SimpleJSONPlugin` in `spec2gds/spec/odt_container/json_plugin.py` conforming to the `ModalityPlugin` interface
- [x] 4.2 Define strict Pydantic schemas for verifying JSON structures before injection
- [x] 4.3 Implement raw JSON validation, injection to `spec_data/simple-json/`, and extraction with value copy semantics
- [x] 4.4 Build the JSON pointer node resolution function to query nested keys and values using `node_path` selectors

## 5. URI Resolution and Link Verification Engine

- [x] 5.1 Implement the parser to extract standard ODT `<text:a>` elements from `content.xml` using `lxml` XPath search
- [x] 5.2 Build the URI parser for routing `spec://<modality_id>/<file_path>/<node_path>` syntax
- [x] 5.3 Implement the full referential integrity validator returning a Pydantic-based `ContainerVerificationReport` representing link and file consistencies

## 6. Headless Command-Line Interface (CLI)

- [x] 6.1 Implement `spec2gds/spec/odt_container/cli.py` using whole module imports only (`import argparse`)
- [x] 6.2 Define and configure subcommands: `inject`, `extract`, `validate`, and `list-plugins` with clean parameter parsing
- [x] 6.3 Standardize exception handling and print output for command executions

## 7. Test Engineering (Mojo-Compliant Verification)

- [x] 7.1 Create module-scoped, standalone test functions prefixed with `test_` in `tests/spec/odt_container/test_container.py`
- [x] 7.2 Implement standalone test functions for plugins in `tests/spec/odt_container/test_plugins.py` asserting via simple exception raising
- [x] 7.3 Implement standalone CLI integration tests in `tests/spec/odt_container/test_cli.py` validating command outputs

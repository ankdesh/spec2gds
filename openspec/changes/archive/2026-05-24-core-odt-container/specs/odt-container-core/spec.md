## ADDED Requirements

### Requirement: Container Initialization and Mimetype Integrity
The `HybridODTContainer` SHALL be initialized from a local ODT file or a stream, and MUST enforce that the `mimetype` file is the first entry in the ZIP archive, stored uncompressed, with byte-level alignment compliant with the ODF ISO/IEC 26300 standard.

#### Scenario: Verify uncompressed mimetype placement
- **WHEN** the container is saved to a file or stream
- **THEN** the mimetype file is placed at the absolute beginning of the archive, stored with zero compression, and functions as the ODF magic number

---

### Requirement: Manifest Synchronization
The `HybridODTContainer` SHALL synchronize any embedded file modifications with `META-INF/manifest.xml`. When a file is injected under `spec_data/`, a corresponding `<manifest:file-entry>` with the correct path and custom media-type MUST be added. When a file is removed, its entry MUST be deleted.

#### Scenario: Register custom modality file in manifest
- **WHEN** a custom payload is injected into `spec_data/simple-json/registers.json` with media-type `application/x-spec-json`
- **THEN** the `META-INF/manifest.xml` is modified to include a `<manifest:file-entry manifest:full-path="spec_data/simple-json/registers.json" manifest:media-type="application/x-spec-json"/>` node

---

### Requirement: Modality Plugin Registry
The `PluginManager` SHALL allow loose coupling of plugins by registering concrete implementations of the `ModalityPlugin` protocol and routing custom URIs based on the unique `modality_id`.

#### Scenario: Retrieve registered plugin for modality routing
- **WHEN** the `PluginManager` receives a request for modality `simple-json`
- **THEN** it resolves and delegates the operation to the registered `SimpleJSONPlugin` instance

---

### Requirement: Custom URI Semantic Resolution
The system SHALL parse and resolve custom semantic URIs using the `spec://<modality_id>/<file_path>/<node_path>` protocol found within standard ODT `<text:a>` hyperlinks in `content.xml`.

#### Scenario: Resolve register path from ODT link
- **WHEN** a URI `spec://simple-json/regs.json/registers/0/name` is resolved
- **THEN** the system extracts the file path `regs.json`, routes to the `simple-json` plugin, parses the file, and retrieves the value of the node at `/registers/0/name`

---

### Requirement: Referential Integrity and Link Verification
The container SHALL verify the referential consistency of all custom URIs inside the ODT file by checking that each referenced file exists within the container and the target node resolves successfully.

#### Scenario: Run consistency check on container links
- **WHEN** the CLI or verification engine parses a container featuring two valid links and one dangling link
- **THEN** it returns a report detailing the valid links and highlighting the dangling link with a resolution error

---

### Requirement: Mojo-Compliant Test Architecture
The test suite for this capability SHALL conform to Mojo-readiness testing standards: defined as standalone functions at module scope, prefixed with `test_`, taking zero arguments, and asserting by raising standard Python exceptions.

#### Scenario: Run unit tests under Mojo-readiness rules
- **WHEN** tests are executed using pytest
- **THEN** all tests run successfully as standalone functions and raise explicit exceptions rather than using class-based TestCase abstractions

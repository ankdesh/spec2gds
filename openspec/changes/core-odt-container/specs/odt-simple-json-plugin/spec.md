## ADDED Requirements

### Requirement: JSON Modality Payload Injection
The `SimpleJSONPlugin` SHALL inject JSON payloads into the ODT ZIP archive under `spec_data/simple-json/<file_path>`, ensuring they are correctly registered with a custom MIME type `application/x-spec-json` in the manifest.

#### Scenario: Inject a raw JSON file
- **WHEN** a JSON dictionary is injected with file path `test.json`
- **THEN** it is saved inside the container ZIP under `spec_data/simple-json/test.json` and registered with the specified media-type

---

### Requirement: Strict Pydantic Validation
The `SimpleJSONPlugin` SHALL validate JSON payloads against a strict Pydantic model before injection, ensuring type integrity and rejecting malformed inputs.

#### Scenario: Reject non-conforming JSON structure
- **WHEN** an invalid JSON dictionary is injected
- **THEN** the validation fails, a Pydantic validation error is raised, and the injection is aborted to prevent container corruption

---

### Requirement: Value Copy Semantics Extraction
The `SimpleJSONPlugin` SHALL extract JSON payloads and return a decoupled copy of the parsed data to conform to Mojo-readiness value semantics, preventing unexpected cross-scope mutations.

#### Scenario: Extract JSON data as cloned copy
- **WHEN** a payload is extracted from the container
- **THEN** the plugin returns a deep-copied dictionary or Pydantic instance, isolating the state from subsequent container modifications

---

### Requirement: Path Pointer Node Resolution
The `SimpleJSONPlugin` SHALL resolve query paths (node paths) within the JSON data hierarchy using standard key/index lookups or JSON pointers.

#### Scenario: Resolve nested JSON value
- **WHEN** a query path `/registers/0/name` is resolved against a JSON structure
- **THEN** the plugin parses the JSON, traverses the nested structure, and returns the string value of the name field

---

### Requirement: Mojo-Compliant Test Implementation
All unit tests for the `SimpleJSONPlugin` SHALL be defined as standalone module-scope functions, prefixed with `test_`, taking zero arguments, and asserting by raising standard exceptions.

#### Scenario: Run simple json plugin tests
- **WHEN** the test suite is run with pytest
- **THEN** all tests succeed as decoupled module-level functions raising AssertionError or standard exceptions on failures

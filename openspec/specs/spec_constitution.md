# Submodule Specification: spec

The `spec` submodule is the entry point of the `spec2gds` flow. It operates as a **Multi-format Compiler**, translating human/machine-readable specifications into both standard internal models and skeleton assets for downstream stages (RTL, simulation, etc.).

---

## 1. Submodule Role & Boundaries

The `spec` submodule is responsible for:
1. **Parsing**: Consuming and validating high-level specs in various formats.
2. **Intermediate Representation (IR)**: Representing parsed structures in memory using strictly-typed Python classes.
3. **Generation**: Emitting basic skeletons/wrappers for RTL, testbenches, and register files.

It does **not** perform physical synthesis, simulation execution, or GDS layout creation.

---

## 2. Supported Formats

### Inputs
The parser must support the following formats:
* **YAML/JSON**: Structured configuration and register maps.
* **SystemRDL**: The standard register description language.
* **CSV**: Tabular register and memory definitions.

### Outputs
The compiler generates:
* **Skeleton RTL**: Verilog/SystemVerilog headers, port lists, and basic register slices.
* **Simulation Environments**: Base testbenches, UVM register models (if applicable), or python-based test configurations.
* **Register Maps**: Documentation (Markdown/HTML) or memory map files.

---

## 3. Technical Requirements & Design Patterns

* **Parser Architecture**:
  * Implement format-specific parser classes (e.g., `YamlParser`, `RdlParser`, `CsvParser`).
  * All parsers must return a unified **Abstract Syntax Tree (AST)** represented by strictly-typed Pydantic models.
* **AST / Intermediate Representation (IR)**:
  * Defined under `spec2gds/spec/models.py`.
  * Must be serializable and self-validating.
* **Code Generator Architecture**:
  * Employs generator classes (e.g., `RtlGenerator`, `SimGenerator`) that consume the unified Pydantic AST and output target files.
  * Use Jinja2 templates where appropriate to maintain separation between generation logic and target formats.

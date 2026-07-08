# Project Constitution: spec2gds

This document defines the core principles, coding standards, and architectural guidelines for `spec2gds`. All AI assistants and developers must adhere to these rules in every interaction. Keep this file minimal, high-impact, and action-oriented.

---

## 1. Core Architecture Principles

* **Loose Coupling of Flow Stages**: The overall flow (`Spec ↔ Simulation ↔ RTL Code ↔ ... ↔ GDS`) must be loosely coupled. Individual submodules and stages should be pluggable and evolve independently without hard dependencies on specific downstream tools.
* **Pragmatic Back-Documentation**: Manual optimizations or changes to RTL, simulation environments, or GDS layouts are fully permitted. However, any manual downstream modifications **must be back-documented in the spec** to maintain the spec as the ultimate source of truth.
* **Flexible, Project-Specific Tool Wrappers**: Tool wrapper interfaces can vary per project. Wrapper structures must support both open-source and proprietary toolchains seamlessly.
* **Standards Integrity**: Do not redefine external standards for convenience. IP-XACT payloads must preserve IEEE 1685 semantics: physical ports belong under `model/ports`, bus interfaces belong under `busInterfaces/busInterface`, and tools must not present physical ports as bus interfaces unless the XML contains a formal bus interface.

---

## 2. Coding & Testing Standards

* **Language**: Strictly typed Modern Python (Python >= 3.12).
* **Data Schemas**: Use strictly typed schemas utilizing **Pydantic** or **Python dataclasses** for all internal representations, parser ASTs, and configuration schemas.
* **Testing Framework**: Use `pytest` for all unit and integration testing.
* **Directory Layout**: Maintain a mirroring structure between source and tests. For example:
  * Source: `spec2gds/spec/parser.py`
  * Tests: `tests/spec/test_parser.py`
* **Explanatory Commenting**: All modules, classes, functions, and non-obvious logic steps must feature clear, descriptive docstrings and inline comments explaining the purpose, design, and "why" behind the code to ensure high readability and ease of understanding.
* **Protocol Fidelity**: Tests and benchmarks that exercise external protocols must validate protocol-correct data instead of relying on project-specific fallback interpretations.

---

## 3. Mojo-Readiness Guidelines (Future Migration)

To ensure smooth future migration to Mojo, all new Python code must adhere to these readiness principles:
* **Strict Type-Locking**: Always assign explicit type annotations upon first assignment (e.g., `value: int = 1`). Never reassign variables to a different type. Use `Optional[T]` from `typing` for nullability.
* **Value Semantics**: Use `copy.copy()` or `copy.deepcopy()` explicitly when sharing object state (lists, dicts, custom objects) to mirror Mojo's default value copy behavior.
* **Function & Class Signature Rules**:
  * Declare functions with `def` only. Complete all parameter and return annotations.
  * Treat incoming parameters as immutable; make local mutable copies immediately if mutation is required.
  * Pre-declare all instance attributes directly inside the class body with type annotations. Fully initialize them in `__init__`. Avoid dynamic runtime properties.
  * Design for composition. Do not use concrete class inheritance. Define abstract traits/interfaces via `typing.Protocol` or `abc.ABC`.
  * Avoid recursive data structures (e.g., direct self-nesting). Use index maps or flat collections instead.
* **Exception Flow**: Do not catch multiple exception types in a single `try` block. Use sequential `try-except` blocks for different failure points.
* **Imports**: Import only entire module namespaces (e.g. `import os`), never individual members (`from os import path` is prohibited).
* **Test Architecture**: Define tests at the module scope as zero-argument standalone functions prefixed with `test_` returning `None`. Assert by raising standard exceptions instead of relying on complex runner classes/assert APIs.

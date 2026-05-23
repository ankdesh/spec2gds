# Project Constitution: spec2gds

This document defines the core principles, coding standards, and architectural guidelines for `spec2gds`. All AI assistants and developers must adhere to these rules in every interaction. Keep this file minimal, high-impact, and action-oriented.

---

## 1. Core Architecture Principles

* **Loose Coupling of Flow Stages**: The overall flow (`Spec ↔ Simulation ↔ RTL Code ↔ ... ↔ GDS`) must be loosely coupled. Individual submodules and stages should be pluggable and evolve independently without hard dependencies on specific downstream tools.
* **Pragmatic Back-Documentation**: Manual optimizations or changes to RTL, simulation environments, or GDS layouts are fully permitted. However, any manual downstream modifications **must be back-documented in the spec** to maintain the spec as the ultimate source of truth.
* **Flexible, Project-Specific Tool Wrappers**: Tool wrapper interfaces can vary per project. Wrapper structures must support both open-source and proprietary toolchains seamlessly.

---

## 2. Coding & Testing Standards

* **Language**: Strictly typed Modern Python (Python >= 3.12).
* **Data Schemas**: Use strictly typed schemas utilizing **Pydantic** or **Python dataclasses** for all internal representations, parser ASTs, and configuration schemas.
* **Testing Framework**: Use `pytest` for all unit and integration testing.
* **Directory Layout**: Maintain a mirroring structure between source and tests. For example:
  * Source: `spec2gds/spec/parser.py`
  * Tests: `tests/spec/test_parser.py`

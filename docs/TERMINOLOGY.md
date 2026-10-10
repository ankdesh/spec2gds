# Spec2GDS Canonical Terminology

This document defines the canonical terminology that must be used consistently across the spec2gds codebase, documentation, UI, and AI Assistant interactions.

## 1. The AI Component
- **AI Assistant**: Formal name for the AI system (used in titles, UI buttons, first mentions).
- **Assistant**: Short form for prose references.
- **DeepSeek Harness** (first mention) / **Harness**: The underlying framework.
- **model**: The runtime execution unit (avoid "LLM", "agent", or "copilot" when referring to the text generator).

## 2. The Human User
- **designer**: The end-user persona operating Circuit Designer or Spec Editor.
- **developer**: Codebase contributors working on the spec2gds repository.
- *(Do NOT use "owner" to refer to a human user).*

## 3. Specification Artifacts
- **`.spec` file**: The physical ZIP bundle/archive stored on disk.
- **Spec**: The logical document unit presented in the UI (short form, capitalized).

## 4. Disambiguating "Owner"
- **Spec service** / **Circuit service**: Use for the backend authority.
- **Parent entity**: Use for the AST hierarchy relationship (e.g., a Design containing an Instance).
- *(Never use "owner" for human users).*

## 5. Disambiguating "Workspace"
- **environment**: The entire spec2gds system/platform.
- **workspace**: The bound design data / logical design source.
- **npm package** (or equivalent): Code repository components in the monorepo.
- **scratch directory**: Temporary build/generation directories.

## 6. Hardware Structure vs. Content
- **Component** / **Design**: Top-level hardware concepts (do not use the generic term "Entity").
- **Section**: The inner tabs/fields of a Component or Design (e.g., Narrative, Ports).

## 7. Processes and Generation Tools
- **Activity**: The registered SDK tool/plugin (e.g., `rtl.generate`).
- **job**: An instance of an Activity's execution.
- **flow**: A declared sequence of operations, conditions and approval waits, shown to the designer as progress.
- **flow definition**: A reusable versioned definition.
- **flow execution**: One run with concrete inputs and recorded progress.
- *(Avoid "generator", "task", or "workflow").*

## 8. Embedded RTL
- **SystemVerilog section** (or **SV section**): The embedded SystemVerilog code block within a Component.

## 9. UI Applications
- **Spec Editor**: The specification authoring frontend (always capitalized, never "Specification Editor").
- **Circuit Designer**: The schematic/circuit authoring frontend (always capitalized).

## 10. Core Actions
- **Save to Spec**: The action to commit a private draft back to the Spec.

## 11. Identifiers vs. Display Strings
- **ID**: The strict hardware identifier (e.g., `alu_top`, code-legal, no spaces).
- **name**: The human-readable UI display string (e.g., "Main ALU").

## 12. Verification Layer
- **Verification Planner**: The application/service name (even if the codebase is `testplan-service`).
- **Test Plan**: The resulting verification artifact (two words, capitalized).

## 13. AI Interaction
- **conversation**: The overall multi-agent thread.
- **turn**: A single back-and-forth exchange within the conversation.
- *(Avoid "chat", "session", "round", or "step").*

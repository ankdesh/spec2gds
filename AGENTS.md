# spec2gds Project Constitution

This file defines the overarching rules, architecture, and terminology for the spec2gds project. All AI agents (Antigravity, Codex, OpenCode, etc.) must adhere to these guidelines.

## 1. Canonical Terminology
We have strict terminology rules to disambiguate overloaded terms (e.g., never use "owner" for a human, the UI apps are "Spec Editor" and "Circuit Designer"). 
**Agents MUST strictly adhere to the rules defined in `docs/TERMINOLOGY.md` before generating text, documentation, or code.**

## 2. Architecture Guidelines
- Follow the established component boundaries.
- Adhere to the deterministic generation principles for Activities (no inferring behavior from narrative).
- Ensure strict separation between Spec (logical/IP-XACT) and Circuit (visual/topology) domains.

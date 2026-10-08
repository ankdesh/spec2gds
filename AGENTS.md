# spec2gds Project Constitution

This file defines the overarching rules, architecture, and terminology for the spec2gds project. All AI agents (Antigravity, Codex, OpenCode, etc.) must adhere to these guidelines.

## 1. Canonical Terminology
We have strict terminology rules to disambiguate overloaded terms (e.g., never use "owner" for a human, the UI apps are "Spec Editor" and "Circuit Designer"). 
**Agents MUST strictly adhere to the rules defined in `docs/TERMINOLOGY.md` before generating text, documentation, or code.**

## 2. Architecture Guidelines
- Follow the established component boundaries.
- Adhere to the deterministic generation principles for Activities (no inferring behavior from narrative).
- Ensure strict separation between Spec (logical/IP-XACT) and Circuit (visual/topology) domains.

## 3. Local Test and Regression Rules

- Follow `docs/testing-strategy.md` for suite selection and evidence rules.
- After implementation, run `scripts/test-all.sh fast` and
  `scripts/test-all.sh integration --scope <affected-scopes>`.
- Scopes are `spec`, `circuit`, `assistant`, `verification`, `activities`, and
  `shared`. Combine scopes with commas. Shared changes include all consumers.
- Run `scripts/test-all.sh regression` for broad or high-risk changes to
  cross-application contracts, persistence, shared runtime, the Activity SDK,
  model/prompt releases, and release preparation.
- Use `--dry-run` to inspect selection and prerequisites. Profiles run locally.
- Fast includes exactly three short live model checks. Use configured
  credentials. Do not replace live checks with fixtures or silently omit them.
- Missing required credentials or tools makes a profile incomplete. Continue
  independent checks, report the missing prerequisites, and do not claim a pass.
- Report executed commands, outcomes, coverage limits, and the evidence directory.
- Add regression protection for confirmed defects at the lowest effective layer.
  Add browser protection when the defect depends on browser behaviour.

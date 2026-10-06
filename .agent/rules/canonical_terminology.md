---
name: Use Canonical Terminology
description: Enforces the use of standard spec2gds terminology across all agent communications, code modifications, and documentation.
---
# Canonical Terminology Enforcement

When discussing, editing, or creating documentation, UI text, or code for the spec2gds project, you MUST strictly adhere to the project's canonical terminology. 

The canonical terminology map is located at `/home/ankdesh/explore/spec2gds/docs/TERMINOLOGY.md`.

## Key Enforcement Rules:
- Never use the term "owner" when referring to a human. Use "designer" or "developer".
- Call the UI applications exactly "Spec Editor" and "Circuit Designer".
- Call the AI system the "AI Assistant" (or "Assistant").
- Refer to the logical design document as the "Spec" and the physical archive as the "`.spec` file".
- Differentiate strict hardware identifiers ("ID") from UI display text ("name").
- Use "conversation" and "turn" for AI interactions.
- Use "Component" and "Design" for hardware, and "Section" for their tabs/fields.
- When committing changes, the action is "Save to Spec".
- Use "Activity" (for tools), "job" (for execution), and "flow" (for UI sequence).
- For verification, use "Verification Planner" (the service) and "Test Plan" (the artifact).

Review the `/home/ankdesh/explore/spec2gds/TERMINOLOGY.md` file if you are unsure of any term.

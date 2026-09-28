# Plan: DSH Agentic Systems Architecture Report

Date: 2026-09-28. Status: report delivered; runtime implementation is proposed.

This is the requested report-production plan. Its deliverable is the
[architecture report](agentic-systems-architecture-report.md). It does not
authorize or describe completed runtime changes.

## Objective and deliverables

Assess whether the current DSH-based assistant supports:

1. A fixed workflow of tool calls and LLM stages, each with its own prompt,
   context schema, output contract, and skills.
2. Independent agents that receive work, generate work for peers, complete
   tasks, and wait for subsequent events.

Compare extending existing workflows, adding an independent team preset, and
sharing orchestration foundations with fixed workflows as one execution mode.
Deliver one recommendation, evidence, gaps, illustrative interfaces, examples,
and a phased adoption roadmap.

Save this plan and the report under `docs/`. Link the report from the
documentation index and root and assistant READMEs. Preserve unrelated edits.

## 1. Establish current capabilities

- Inspect product profiles, preset compositions, prompt and workflow catalogs,
  lifecycle hooks, domain tool registration, and persistence.
- Verify the sibling DSH checkout against `ai-assistant/harness.lock.json`.
- Inspect DSH workflow, subagent, Agent Teams, prompt, and skill capabilities
  together with relevant tests.
- Classify requirements as enabled, available but not integrated, partially
  supported, or requiring development. Cite implementation sources and separate
  product behavior from underlying DSH capabilities.

## 2. Define the execution models

- Describe reusable agent definitions: prompts, model settings, context and
  output contracts, tools, skills, and resource policy.
- For fixed workflows, cover host-enforced ordering, direct tool stages,
  independent LLM stages, validated data mappings, retries, review, and recovery.
- For event-driven agents, cover stable identities, peer routing, typed work and
  results, durable queues, wake-up, waiting, failure, and restart recovery.
- Distinguish message acceptance from task completion and external side effects.
- Provide one worked example and sequence diagram for each model.

## 3. Compare and recommend

Compare implementation effort, reuse, deterministic control, durability,
configuration complexity, compatibility, and maintenance across the options.
Evaluate shared execution foundations with separate fixed-workflow and team
policies, keeping presets as capability compositions. Assess reuse and hardening
of DSH Agent Teams and retain the existing product review boundary.

State proposed public interface responsibilities, integration ownership,
compatibility implications, and delivery phases. Label example configuration
and future interfaces as unimplemented.

## 4. Validate

Trace conclusions to source and test evidence. Document acceptance scenarios
for stage order, schema rejection, context isolation, peer work/results,
restart recovery, duplicate delivery, interrupted processing, idle agents,
budgets, cancellation, and compatibility with current presets and review.

Inspect existing tests; run runtime tests only if needed to resolve a behavioral
uncertainty. Do not represent inspected tests as passing executions. Validate
Markdown links, source references, illustrative configuration syntax, and the
documentation diff. Do not introduce runtime tests for this documentation-only
task.

## Confirmed assumptions

- The audience is engineers building reusable DSH capabilities; spec2gds is the
  first integration.
- Agent state and queued work must survive server restarts.
- Initial deployment is a single server; distributed coordination is deferred.
- Experimental Agent Teams may be reused with explicit validation and hardening.
- Creating work for existing agents does not imply authority to spawn new ones.
- Existing owner bindings and human review boundaries remain in force.
- Any Python verification uses the repository's `uv`-managed `.venv`.

The report records additional recommended defaults separately from these
user-confirmed requirements. Runtime implementation remains a subsequent task.

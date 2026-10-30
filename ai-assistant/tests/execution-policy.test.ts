import assert from "node:assert/strict";
import test from "node:test";
import { executionLimits, proposalExecutionDenial } from "../src/execution-policy.js";
import type { EventSystemSnapshot } from "@ankdesh/dsh-event-system";
const configured = { maxRounds: 8, maxRequests: 48, maxTokens: 500000, maxActiveMillis: 2700000, maxMembers: 3, maxConcurrency: 2, maxPending: 100, maxEvents: 100, maxPayloadBytes: 8192, maxDepth: 8 };
const state = (mode = "orchestrated", events: unknown[] = []): EventSystemSnapshot => ({ mode, status: "active", definition: { primary: "primary" }, events }) as EventSystemSnapshot;
const event = (id: string, type: string, causation: string | null = null) => ({ id, type, causation });
test("execution bounds require explicit known values and enforce product ceilings", () => {
  assert.equal(executionLimits("orchestrated", configured, 1200).maxOutputTokens, 1200);
  assert.throws(() => executionLimits("goal", configured, 1200), /ceiling/);
  assert.throws(() => executionLimits("orchestrated", { ...configured, maxRounds: 25 }, 1200), /ceiling/);
  assert.throws(() => executionLimits("orchestrated", { ...configured, maxPending: undefined }, 1200), /positive safe integer/);
  assert.throws(() => executionLimits("orchestrated", { ...configured, maxRequests: 1.5 }, 1200), /positive safe integer/);
  assert.throws(() => executionLimits("orchestrated", { ...configured, maxConcurrency: 4 }, 1200), /capacity/);
  assert.throws(() => executionLimits("orchestrated", { ...configured, unknown: 1 }, 1200), /Unknown/);
});
test("only an active primary can prepare owner proposals", () => {
  assert.equal(proposalExecutionDenial(state("goal"), "primary"), undefined);
  assert.match(proposalExecutionDenial(state("goal"), "analyst")!, /primary/);
  for (const status of ["paused", "stopped", "needs-resume", "exhausted"] as const) assert.match(proposalExecutionDenial({ ...state("goal"), status }, "primary")!, /resume/);
});
test("orchestration requires a causal reviewer result for the latest human request", () => {
  const first = [event("request-1", "user.requested"), event("analysis-1", "analysis.ready", "request-1"), event("review-1", "review.ready", "analysis-1")];
  assert.equal(proposalExecutionDenial(state("orchestrated", first), "primary"), undefined);
  assert.match(proposalExecutionDenial(state("orchestrated", [...first, event("request-2", "user.requested")]), "primary")!, /Wait/);
  assert.match(proposalExecutionDenial(state(), "primary")!, /recorded user request/);
  assert.match(proposalExecutionDenial(state("orchestrated", [first[0], event("unrelated", "review.ready")]), "primary")!, /Wait/);
});

test("a new source observation requires its own causal reviewer result", () => {
  const events = [event("human", "user.requested"), event("old-review", "review.ready", "human"), event("source", "source.changed")];
  assert.match(proposalExecutionDenial(state("orchestrated", events), "primary")!, /Wait/);
  events.push(event("source-analysis", "analysis.ready", "source"), event("source-review", "review.ready", "source-analysis"));
  assert.equal(proposalExecutionDenial(state("orchestrated", events), "primary"), undefined);
});

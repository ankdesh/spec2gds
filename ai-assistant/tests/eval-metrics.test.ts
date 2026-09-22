import assert from "node:assert/strict";
import test from "node:test";
import { calculateMetrics, parseJsonLines } from "../src/eval-metrics.js";

test("evaluation metrics derive raw counts from durable DSH events", () => {
  const payload = JSON.stringify({ success: true, review: { state: "ready", artifact: { operations: [{ type: "create_entity" }, { type: "create_entity" }] } } });
  const events = parseJsonLines([
    JSON.stringify({ type: "turn/start", time: 10, data: { turn: 1 } }),
    JSON.stringify({ type: "tool/call", data: { turn: 1, name: "prepare_spec_proposal" } }),
    JSON.stringify({ type: "tool/result", data: { turn: 1, message: { content: [{ type: "tool-result", content: [{ type: "text", text: payload }] }] } } }),
    JSON.stringify({ type: "assistant/message", data: { turn: 1, message: { content: [{ type: "text", text: "Ready for review." }] }, usage: { inputTokens: 20, cacheReadTokens: 4, outputTokens: 5, reasoningTokens: 2 } } }),
    JSON.stringify({ type: "turn/end", time: 35, data: { turn: 1 } }),
    JSON.stringify({ type: "spec2gds/evaluation", data: { assertion: "false_completion", passed: false } }),
  ].join("\n"));
  assert.deepEqual(calculateMetrics(events, 13), {
    cases: 13, proposalCalls: 1, schemaValidProposalCalls: 1, firstPreviewReadyCases: 1,
    proposedOperations: 2, appliedOrSentOperations: 0, clarificationTurns: 0, retries: 0,
    latencyMs: { count: 1, total: 25 }, tokens: { input: 20, cacheRead: 4, output: 5, reasoning: 2 },
    falseCompletionViolations: 1,
  });
});

test("metrics count proposal retries and non-proposal clarification turns", () => {
  const metrics = calculateMetrics([
    { type: "tool/call", data: { turn: 1, name: "prepare_circuit_proposal" } },
    { type: "tool/call", data: { turn: 1, name: "prepare_circuit_proposal" } },
    { type: "assistant/message", data: { turn: 2, message: { content: [{ type: "text", text: "Which endpoint should be used?" }] } } },
  ], 1);
  assert.equal(metrics.retries, 1);
  assert.equal(metrics.clarificationTurns, 1);
});
